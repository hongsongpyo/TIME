# =========================================================
# TIME - backend/analysis.py
# =========================================================

from typing import Any, Dict, List, Optional

import pandas as pd

from preprocessing import preprocess_time_series, serialize_values
from decomposition import decompose_time_series
from forecasting import run_all_forecasts
from metrics import build_metrics_dashboard, get_best_model


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


def build_validation_series(
    forecast_result: Dict[str, Any],
) -> Dict[str, Any]:
    validation_dates = forecast_result.get("validation_dates", [])
    model_results = forecast_result.get("model_results", {})

    series = {}

    for model_name, result in model_results.items():
        validation_pred = result.get("validation_pred", [])

        series[model_name] = {
            "date": validation_dates[:len(validation_pred)],
            "value": validation_pred,
            "success": result.get("success", False),
            "message": result.get("message", ""),
        }

    return series


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
        "validation_length": forecast_result.get("validation_length"),
    }


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

    # STL / decomposition 단계에서 추정된 주기
    seasonal_period = decomposition_result.get("period")
    print("STL seasonal_period =", seasonal_period)
    forecast_result = run_all_forecasts(
        df=processed_df,
        horizon=horizon,
        frequency=preprocess_summary.get("frequency"),
        value_column="value_preprocessed",
        seasonal_period=seasonal_period,
    )

    model_results = forecast_result["model_results"]

    validation_length = forecast_result.get(
        "validation_length",
        len(forecast_result["test_values"]),
    )

    y_test_for_metrics = forecast_result["test_values"][:validation_length]

    metrics_dashboard = build_metrics_dashboard(
        model_results=model_results,
        y_train=forecast_result["train_values"],
        y_test=y_test_for_metrics,
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
            "train_dates": forecast_result["train_dates"],
            "train_values": forecast_result["train_values"],

            # y_test는 전체 test 데이터 그대로 표시
            "validation_dates": forecast_result["test_dates"],
            "validation_actual": forecast_result["test_values"],

            # 모델별 validation 예측만 표시
            "validation": build_validation_series(forecast_result),

            "horizon": forecast_result["horizon"],
            "validation_length": validation_length,
            "seasonal_period": forecast_result.get("seasonal_period"),
        },

        "metrics_dashboard": metrics_dashboard,
    }