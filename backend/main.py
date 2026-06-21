# =========================================================
# TIME - backend/main.py
# ---------------------------------------------------------
# 역할
# 1. FastAPI 서버 실행
# 2. 프론트엔드와 통신할 API 제공
# 3. CSV 업로드 확인
# 4. 편집된 표 데이터를 받아 자동 시계열 분석 실행
# 5. mode 값에 따라 예측 분석 / 이상탐지 분석 분기
# =========================================================

from typing import Any, Dict, List, Optional

import io

import pandas as pd

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from analysis import run_analysis


# =========================================================
# 1. FastAPI 앱 생성
# =========================================================

app = FastAPI(
    title="TIME API",
    description="CSV 기반 시계열 자동 분석, 예측 및 이상탐지 API",
    version="2.0.0",
)


# =========================================================
# 2. CORS 설정
# ---------------------------------------------------------
# GitHub Pages 프론트엔드에서 Render 백엔드 요청 허용
# 로컬 개발 환경도 함께 허용
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://hongsongpyo.github.io",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# 3. 요청 데이터 모델
# =========================================================

class AnomalyOptions(BaseModel):
    method: str = "auto"
    sensitivity: str = "medium"


class AnalysisRequest(BaseModel):
    data: List[Dict[str, Any]]

    # forecast: 기존 예측 분석
    # anomaly : 신규 이상탐지 분석
    mode: str = "forecast"

    # forecast 모드에서 사용
    # anomaly 모드에서는 사용하지 않지만 기존 프론트와 호환을 위해 유지
    horizon: Optional[Any] = 12

    # editor.html에서 사용자가 특이치로 지정한 셀
    protected_cells: Optional[List[Dict[str, Any]]] = None

    # anomaly 모드에서 사용
    anomaly_options: Optional[AnomalyOptions] = None


# =========================================================
# 4. 기본 상태 확인 API
# =========================================================

@app.get("/")
def read_root() -> Dict[str, str]:
    return {
        "message": "TIME FastAPI server is running.",
        "status": "ok",
        "version": "2.0.0",
    }


@app.get("/health")
def health_check() -> Dict[str, str]:
    return {
        "status": "ok",
    }


# =========================================================
# 5. CSV 디코딩 유틸
# ---------------------------------------------------------
# utf-8-sig 우선 사용
# 실패 시 cp949, euc-kr 순서로 재시도
# =========================================================

def decode_csv_contents(contents: bytes) -> str:
    encodings = [
        "utf-8-sig",
        "utf-8",
        "cp949",
        "euc-kr",
    ]

    last_error = None

    for encoding in encodings:
        try:
            return contents.decode(encoding)
        except Exception as error:
            last_error = error

    raise ValueError(f"CSV 파일 인코딩을 해석할 수 없습니다: {str(last_error)}")


# =========================================================
# 6. CSV 업로드 API
# ---------------------------------------------------------
# upload.html에서 CSV 파일을 업로드하면
# 컬럼명과 전체 행 데이터를 반환
# 실제 분석은 editor.html에서 수정된 데이터를 기준으로 실행
# =========================================================

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="파일명이 올바르지 않습니다.",
        )

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="CSV 파일만 업로드할 수 있습니다.",
        )

    try:
        contents = await file.read()
        decoded = decode_csv_contents(contents)
        df = pd.read_csv(io.StringIO(decoded))
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"CSV 파일을 읽는 중 오류가 발생했습니다: {str(error)}",
        )

    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="CSV 파일에 데이터가 없습니다.",
        )

    return {
        "filename": file.filename,
        "columns": df.columns.tolist(),
        "rows": df.fillna("").to_dict(orient="records"),
        "row_count": len(df),
        "column_count": len(df.columns),
    }


# =========================================================
# 7. 분석 모드 검증
# =========================================================

def validate_analysis_mode(mode: str) -> str:
    mode = str(mode or "forecast").lower().strip()

    if mode in ["forecast", "prediction", "predict"]:
        return "forecast"

    if mode in ["anomaly", "anomaly_detection", "detect", "outlier"]:
        return "anomaly"

    raise ValueError("분석 모드는 forecast 또는 anomaly여야 합니다.")


def normalize_anomaly_options(
    anomaly_options: Optional[AnomalyOptions],
) -> Dict[str, str]:
    if anomaly_options is None:
        return {
            "method": "auto",
            "sensitivity": "medium",
        }

    try:
        if hasattr(anomaly_options, "model_dump"):
            return anomaly_options.model_dump()

        return anomaly_options.dict()
    except Exception:
        return {
            "method": "auto",
            "sensitivity": "medium",
        }


# =========================================================
# 8. 자동 분석 API
# ---------------------------------------------------------
# editor.html에서 수정된 표 데이터와 분석 옵션을 받아
# Python 기반 자동 분석을 실행
#
# mode="forecast":
#   기존 예측 분석 실행
#
# mode="anomaly":
#   신규 다변량 이상탐지 분석 실행
# =========================================================

@app.post("/analyze")
def analyze(request: AnalysisRequest) -> Dict[str, Any]:
    if not request.data:
        raise HTTPException(
            status_code=400,
            detail="분석할 데이터가 없습니다.",
        )

    try:
        mode = validate_analysis_mode(request.mode)

        anomaly_options = normalize_anomaly_options(
            request.anomaly_options,
        )

        result = run_analysis(
            data=request.data,
            mode=mode,
            horizon=request.horizon,
            protected_cells=request.protected_cells or [],
            anomaly_options=anomaly_options,
        )

        return result

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"자동 분석 중 오류가 발생했습니다: {str(error)}",
        )


# =========================================================
# 9. 로컬 실행용
# ---------------------------------------------------------
# 실행 명령:
# uvicorn main:app --reload
# =========================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )