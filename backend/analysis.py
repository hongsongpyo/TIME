# =========================================================
# TIME - backend/analysis.py
# ---------------------------------------------------------
# 역할
# 1. 전체 자동 시계열 분석 흐름 실행
# 2. 전처리 → 분해 → 예측 → 평가지표 계산
# 3. 프론트엔드 result.html에서 사용할 JSON 구조 생성
# =========================================================

from typing import Any, Dict, List, Optional

import pandas as pd

from preprocessing import preprocess_time_series, serialize_values
from decomposition import decompose_time_series
from forecasting import run_all_forecasts
from metrics import build_metrics_dashboard, get_best_model


# =========================================================
# 1. DataFrame 포인트 직렬화
# =========================================================

def serialize_points(
    points_df: pd.DataFrame,
    value_column: str = "value_filled",
) -> Dict[str, List[Any]]:
    if points_df is None or points_df.empty:
        return {
            "date": [],
            "value": [],
        }

    return {
        "date": [
            pd.Timestamp(date).strftime("%Y-%m-%d")
            for date in points_df["date"]
        ],
        "value": serialize_values(points_df[value_column]),
    }


# =========================================================
# 2. 모델별 미래 예측값 정리
# =========================================================

def build_forecast_series(
    forecast_result: Dict[str, Any],
) -> Dict[str, Any]:
    future_dates = forecast_result.get("future_dates", [])
    model_results = forecast_result.get("model_results", {})

    series = {}

    for model_name, result in model_results.items():
        series[model_name] = {
            "date": future_dates,
            "value": result.get("future_pred", []),
            "success": result.get("success", False),
            "message": result.get("message", ""),
        }

    return series


# =========================================================
# 3. 모델별 검증 예측값 정리
# =========================================================

def build_validation_series(
    forecast_result: Dict[str, Any],
) -> Dict[str, Any]:
    test_dates = forecast_result.get("test_dates", [])
    model_results = forecast_result.get("model_results", {})

    series = {}

    for model_name, result in model_results.items():
        series[model_name] = {
            "date": test_dates,
            "value": result.get("validation_pred", []),
            "success": result.get("success", False),
            "message": result.get("message", ""),
        }

    return series


# =========================================================
# 4. 원본/전처리 시계열 정리
# =========================================================

def build_time_series_payload(preprocess_result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "date": preprocess_result["date"],
        "original": preprocess_result["original_value"],
        "filled": preprocess_result["filled_value"],
        "preprocessed": preprocess_result["preprocessed_value"],
        "missing_points": serialize_points(
            preprocess_result["missing_points"],
            value_column="value_filled",
        ),
        "outlier_points": serialize_points(
            preprocess_result["outlier_points"],
            value_column="value_filled",
        ),
        "protected_points": serialize_points(
            preprocess_result["protected_points"],
            value_column="value_filled",
        ),
    }


# =========================================================
# 5. 분석 요약 생성
# =========================================================

def build_analysis_summary(
    preprocess_summary: Dict[str, Any],
    decomposition_result: Dict[str, Any],
    forecast_result: Dict[str, Any],
    metrics_dashboard: List[Dict[str, Any]],
    horizon: int,
) -> Dict[str, Any]:
    best_model = get_best_model(metrics_dashboard)

    return {
        "best_model": best_model,
        "horizon": horizon,
        "date_column": preprocess_summary.get("date_column"),
        "value_column": preprocess_summary.get("value_column"),
        "frequency": preprocess_summary.get("frequency"),
        "data_count": preprocess_summary.get("final_count"),
        "missing_count": preprocess_summary.get("missing_count"),
        "outlier_count": preprocess_summary.get("outlier_count"),
        "protected_count": preprocess_summary.get("protected_count"),
        "decomposition_method": decomposition_result.get("method"),
        "seasonal_period": forecast_result.get("seasonal_period"),
    }


# =========================================================
# 6. 전체 자동 분석 실행
# =========================================================

def run_time_series_analysis(
    data: List[Dict[str, Any]],
    horizon: int = 12,
    protected_cells: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if protected_cells is None:
        protected_cells = []

    horizon = int(horizon)

    if horizon <= 0:
        raise ValueError("시평 horizon은 1 이상이어야 합니다.")

    preprocess_result = preprocess_time_series(
        data=data,
        protected_cells=protected_cells,
    )

    processed_df = preprocess_result["df"]
    preprocess_summary = preprocess_result["summary"]

    decomposition_result = decompose_time_series(
        df=processed_df,
        frequency=preprocess_summary.get("frequency"),
        value_column="value_preprocessed",
    )

    forecast_result = run_all_forecasts(
        df=processed_df,
        horizon=horizon,
        frequency=preprocess_summary.get("frequency"),
        value_column="value_preprocessed",
    )

    model_results = forecast_result["model_results"]

    metrics_dashboard = build_metrics_dashboard(
        model_results=model_results,
        y_train=forecast_result["train_values"],
        y_test=forecast_result["test_values"],
    )

    summary = build_analysis_summary(
        preprocess_summary=preprocess_summary,
        decomposition_result=decomposition_result,
        forecast_result=forecast_result,
        metrics_dashboard=metrics_dashboard,
        horizon=horizon,
    )

    return {
        "summary": summary,
        "time_series": build_time_series_payload(preprocess_result),
        "decomposition": {
            "date": preprocess_result["date"],
            "trend": decomposition_result["trend"],
            "seasonal": decomposition_result["seasonal"],
            "residual": decomposition_result["residual"],
            "period": decomposition_result["period"],
            "method": decomposition_result["method"],
        },
        "forecast": {
            "future_dates": forecast_result["future_dates"],
            "validation_dates": forecast_result["test_dates"],
            "validation_actual": forecast_result["test_values"],
            "future": build_forecast_series(forecast_result),
            "validation": build_validation_series(forecast_result),
        },
        "metrics_dashboard": metrics_dashboard,
    }