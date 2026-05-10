# =========================================================
# TIME - backend/main.py
# ---------------------------------------------------------
# 역할
# 1. FastAPI 서버 실행
# 2. 프론트엔드와 통신할 API 제공
# 3. CSV 업로드 확인
# 4. 편집된 표 데이터를 받아 자동 시계열 분석 실행
# =========================================================

from typing import Any, Dict, List, Optional

import io
import pandas as pd

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from analysis import run_time_series_analysis


# =========================================================
# 1. FastAPI 앱 생성
# =========================================================

app = FastAPI(
    title="TIME API",
    description="CSV 기반 시계열 자동 분석 및 예측 API",
    version="1.0.0",
)


# =========================================================
# 2. CORS 설정
# ---------------------------------------------------------
# GitHub Pages 프론트엔드에서 Render 백엔드 요청 허용
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://hongsongpyo.github.io",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# 3. 요청 데이터 모델
# =========================================================

class AnalysisRequest(BaseModel):
    data: List[Dict[str, Any]]
    horizon: int = 12
    protected_cells: Optional[List[Dict[str, Any]]] = None


# =========================================================
# 4. 기본 상태 확인 API
# =========================================================

@app.get("/")
def read_root() -> Dict[str, str]:
    return {
        "message": "TIME FastAPI server is running.",
        "status": "ok",
    }


@app.get("/health")
def health_check() -> Dict[str, str]:
    return {
        "status": "ok",
    }


# =========================================================
# 5. CSV 업로드 API
# ---------------------------------------------------------
# upload.html에서 CSV 파일을 업로드하면
# 컬럼명과 데이터 미리보기 정보를 반환
# 실제 분석은 editor.html에서 수정된 데이터를 기준으로 실행
# =========================================================

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="CSV 파일만 업로드할 수 있습니다.",
        )

    try:
        contents = await file.read()
        decoded = contents.decode("utf-8-sig")
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
# 6. 자동 시계열 분석 API
# ---------------------------------------------------------
# editor.html에서 수정된 표 데이터와 horizon을 받아
# Python 기반 자동 분석을 실행
# =========================================================

@app.post("/analyze")
def analyze(request: AnalysisRequest) -> Dict[str, Any]:
    if not request.data:
        raise HTTPException(
            status_code=400,
            detail="분석할 데이터가 없습니다.",
        )

    if request.horizon <= 0:
        raise HTTPException(
            status_code=400,
            detail="시평 horizon은 1 이상이어야 합니다.",
        )

    try:
        result = run_time_series_analysis(
            data=request.data,
            horizon=request.horizon,
            protected_cells=request.protected_cells or [],
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"자동 분석 중 오류가 발생했습니다: {str(error)}",
        )

    return result


# =========================================================
# 7. 로컬 실행용
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