# =========================================================
# TIME - backend/main.py
# ---------------------------------------------------------
# 역할
# 1. FastAPI 서버 실행
# 2. 프론트엔드와 통신할 API 제공
# 3. CSV 업로드 확인
# 4. 편집된 표 데이터를 받아 다변량 시계열 이상탐지 실행
# 5. 민감도 / 탐지 방법 옵션을 받아 anomaly.py로 전달
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
    description="CSV 기반 다변량 시계열 이상탐지 API",
    version="3.0.0",
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
    # auto, isolation_forest, zscore, iqr, stl_residual
    method: str = "auto"

    # low, medium, high
    sensitivity: str = "medium"


class AnalysisRequest(BaseModel):
    # editor.html에서 전달하는 표 데이터
    data: List[Dict[str, Any]]

    # 기존 forecast 구조와 호환하기 위해 유지
    # 현재 서버는 어떤 mode가 들어와도 anomaly 분석으로 처리함
    mode: Optional[str] = "anomaly"

    # 기존 예측 기능 호환 필드
    # 이상탐지에서는 사용하지 않음
    horizon: Optional[Any] = 12

    # editor.html에서 사용자가 특이치로 지정한 셀
    protected_cells: Optional[List[Dict[str, Any]]] = None

    # 이상탐지 옵션
    anomaly_options: Optional[AnomalyOptions] = None

    # 프론트에서 anomaly_options 없이 직접 보낼 경우를 대비한 호환 필드
    method: Optional[str] = None
    sensitivity: Optional[str] = None


# =========================================================
# 4. 기본 상태 확인 API
# =========================================================

@app.get("/")
def read_root() -> Dict[str, str]:
    return {
        "message": "TIME FastAPI server is running.",
        "status": "ok",
        "version": "3.0.0",
        "mode": "anomaly",
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
# 실패 시 utf-8, cp949, euc-kr 순서로 재시도
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

    raise ValueError(
        f"CSV 파일 인코딩을 해석할 수 없습니다: {str(last_error)}"
    )


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
# 7. 분석 모드 정규화
# ---------------------------------------------------------
# 현재 프로젝트는 이상탐지 전용으로 변경
# 기존 프론트가 forecast를 보내도 anomaly로 처리
# =========================================================

def normalize_analysis_mode(mode: Optional[str]) -> str:
    mode_text = str(mode or "anomaly").lower().strip()

    if mode_text in [
        "anomaly",
        "anomaly_detection",
        "detect",
        "outlier",
        "이상탐지",
    ]:
        return "anomaly"

    # forecast, prediction 등이 들어와도 현재는 anomaly로 처리
    return "anomaly"


def normalize_anomaly_method(method: Optional[str]) -> str:
    method_text = str(method or "auto").strip().lower()

    method_alias = {
        "자동": "auto",
        "오토": "auto",
        "isolationforest": "isolation_forest",
        "isolation forest": "isolation_forest",
        "격리숲": "isolation_forest",
        "z-score": "zscore",
        "z score": "zscore",
        "z스코어": "zscore",
        "stl": "stl_residual",
        "stl residual": "stl_residual",
        "잔차": "stl_residual",
    }

    method_text = method_alias.get(method_text, method_text)

    allowed_methods = [
        "auto",
        "isolation_forest",
        "zscore",
        "iqr",
        "stl_residual",
    ]

    if method_text not in allowed_methods:
        return "auto"

    return method_text


def normalize_sensitivity(sensitivity: Optional[str]) -> str:
    sensitivity_text = str(sensitivity or "medium").strip().lower()

    high_values = ["high", "높음", "민감", "높은"]
    medium_values = ["medium", "normal", "보통", "중간", "기본"]
    low_values = ["low", "낮음", "낮은"]

    if sensitivity_text in high_values:
        return "high"

    if sensitivity_text in low_values:
        return "low"

    if sensitivity_text in medium_values:
        return "medium"

    return "medium"


def model_to_dict(model: Any) -> Dict[str, Any]:
    if model is None:
        return {}

    try:
        if hasattr(model, "model_dump"):
            return model.model_dump()

        if hasattr(model, "dict"):
            return model.dict()
    except Exception:
        return {}

    if isinstance(model, dict):
        return model

    return {}


def normalize_anomaly_options_from_request(
    request: AnalysisRequest,
) -> Dict[str, str]:
    option_dict = model_to_dict(request.anomaly_options)

    method = request.method

    if method is None:
        method = option_dict.get("method", "auto")

    sensitivity = request.sensitivity

    if sensitivity is None:
        sensitivity = option_dict.get("sensitivity", "medium")

    return {
        "method": normalize_anomaly_method(method),
        "sensitivity": normalize_sensitivity(sensitivity),
    }


# =========================================================
# 8. 자동 이상탐지 API
# ---------------------------------------------------------
# editor.html에서 수정된 표 데이터와 분석 옵션을 받아
# Python 기반 다변량 이상탐지를 실행
# =========================================================

@app.post("/analyze")
def analyze(request: AnalysisRequest) -> Dict[str, Any]:
    if not request.data:
        raise HTTPException(
            status_code=400,
            detail="분석할 데이터가 없습니다.",
        )

    try:
        mode = normalize_analysis_mode(request.mode)

        anomaly_options = normalize_anomaly_options_from_request(request)

        result = run_analysis(
            data=request.data,
            mode=mode,
            horizon=request.horizon,
            protected_cells=request.protected_cells or [],
            anomaly_options=anomaly_options,
            method=anomaly_options.get("method"),
            sensitivity=anomaly_options.get("sensitivity"),
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
            detail=f"자동 이상탐지 중 오류가 발생했습니다: {str(error)}",
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