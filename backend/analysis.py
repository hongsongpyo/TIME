# =========================================================
# TIME - backend/analysis.py
# ---------------------------------------------------------
# 역할
# 1. 예측 모드와 이상탐지 모드 분기
# 2. 단변량 시계열 예측 분석 실행
# 3. 다변량 시계열 이상탐지 분석 실행
# 4. 프론트엔드 result.html에서 사용할 payload 생성
# =========================================================

from typing import Any, Dict, List, Optional, Union

import pandas as pd

from preprocessing import (
    preprocess_time_series,
    preprocess_multivariate_time_series,
    serialize_values,
)

from decomposition import decompose_time_series
from forecasting import run_all_forecasts
from metrics import build_metrics_dashboard, get_best_model

from anomaly import run_anomaly_detection
from anomaly_metrics import (
    build_anomaly_metrics_payload,
    attach_anomaly_interpretation,
)


# =========================================================
# 1. 공통 정규화
# =========================================================

def normalize_analysis_mode(mode: Optional[str]) -> str:
    mode_text = str(mode or "forecast").strip().lower()

    if mode_text == "anomaly":
        return "anomaly"

    return "forecast"


def normalize_forecast_horizon(horizon: Any) -> Union[int, str]:
    if horizon == "auto":
        return "auto"

    try:
        horizon_value = int(horizon)

        if horizon_value <= 0:
            raise ValueError

        return horizon_value

    except Exception:
        return 12


def normalize_anomaly_options(
    anomaly_options: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    if anomaly_options is None:
        anomaly_options = {}

    method = str(anomaly_options.get("method", "auto")).strip().lower()
    sensitivity = str(anomaly_options.get("sensitivity", "medium")).strip().lower()

    allowed_methods = [
        "auto",
        "isolation_forest",
        "zscore",
        "iqr",
        "stl_residual",
    ]

    allowed_sensitivities = [
        "low",
        "medium",
        "high",
    ]

    if method not in allowed_methods:
        method = "auto"

    if sensitivity not in allowed_sensitivities:
        sensitivity = "medium"

    return {
        "method": method,
        "sensitivity": sensitivity,
    }


# =========================================================
# 2. Point 직렬화
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
# 3. Forecast - 검증 예측 시계열 생성
# =========================================================

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


def build_future_series(
    forecast_result: Dict[str, Any],
) -> Dict[str, Any]:
    model_results = forecast_result.get("model_results", {})

    series = {}

    for model_name, result in model_results.items():
        future_pred = result.get("future_pred", [])
        future_dates = result.get("future_dates", [])

        if not future_pred and not future_dates:
            continue

        series[model_name] = {
            "date": future_dates,
            "value": future_pred,
            "success": result.get("success", False),
            "message": result.get("message", ""),
        }

    return series


# =========================================================
# 4. Forecast - 시계열 payload
# =========================================================

def build_time_series_payload(
    preprocess_result: Dict[str, Any],
) -> Dict[str, Any]:
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
# 5. Forecast - 요약 payload
# =========================================================

def build_forecast_analysis_summary(
    preprocess_summary: Dict[str, Any],
    decomposition_result: Dict[str, Any],
    forecast_result: Dict[str, Any],
    metrics_dashboard: List[Dict[str, Any]],
    horizon: Union[int, str],
) -> Dict[str, Any]:
    best_model = get_best_model(metrics_dashboard)

    return {
        "mode": "forecast",
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


# 기존 코드 호환용 alias
def build_analysis_summary(
    preprocess_summary: Dict[str, Any],
    decomposition_result: Dict[str, Any],
    forecast_result: Dict[str, Any],
    metrics_dashboard: List[Dict[str, Any]],
    horizon: Union[int, str],
) -> Dict[str, Any]:
    return build_forecast_analysis_summary(
        preprocess_summary=preprocess_summary,
        decomposition_result=decomposition_result,
        forecast_result=forecast_result,
        metrics_dashboard=metrics_dashboard,
        horizon=horizon,
    )


# =========================================================
# 6. Forecast 분석 실행
# =========================================================

def run_time_series_forecast_analysis(
    data: List[Dict[str, Any]],
    horizon: Any = 12,
    protected_cells: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if protected_cells is None:
        protected_cells = []

    horizon = normalize_forecast_horizon(horizon)

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

    seasonal_period = decomposition_result.get("period")

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
        len(forecast_result.get("test_values", [])),
    )

    y_test_for_metrics = forecast_result.get("test_values", [])[:validation_length]

    metrics_dashboard = build_metrics_dashboard(
        model_results=model_results,
        y_train=forecast_result.get("train_values", []),
        y_test=y_test_for_metrics,
    )

    summary = build_forecast_analysis_summary(
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
            "trend": decomposition_result.get("trend", []),
            "seasonal": decomposition_result.get("seasonal", []),
            "residual": decomposition_result.get("residual", []),
            "method": decomposition_result.get("method"),
            "period": decomposition_result.get("period"),
        },

        "forecast": {
            "train_dates": forecast_result.get("train_dates", []),
            "train_values": forecast_result.get("train_values", []),
            "validation_dates": forecast_result.get("validation_dates", []),
            "validation_actual": forecast_result.get("test_values", [])[:validation_length],
            "validation": build_validation_series(forecast_result),
            "future": build_future_series(forecast_result),
            "horizon": forecast_result.get("horizon", horizon),
            "validation_length": validation_length,
            "seasonal_period": forecast_result.get("seasonal_period"),
        },

        "metrics_dashboard": metrics_dashboard,

        "model_results": model_results,
    }


# 기존 main.py 호환용 함수명
def run_time_series_analysis(
    data: List[Dict[str, Any]],
    horizon: Any = 12,
    protected_cells: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return run_time_series_forecast_analysis(
        data=data,
        horizon=horizon,
        protected_cells=protected_cells,
    )


# =========================================================
# 7. Anomaly - 전처리 payload
# =========================================================

def build_multivariate_preprocess_payload(
    preprocess_result: Dict[str, Any],
) -> Dict[str, Any]:
    summary = preprocess_result.get("summary", {})

    return {
        "date": preprocess_result.get("date", []),
        "value_columns": preprocess_result.get("value_columns", []),
        "original_values": preprocess_result.get("original_values", {}),
        "filled_values": preprocess_result.get("filled_values", {}),
        "missing_count": preprocess_result.get("missing_count"),
        "protected_dates": summary.get("protected_dates", []),
        "protected_date_map": summary.get("protected_date_map", {}),
        "summary": summary,
    }


# =========================================================
# 8. Anomaly 분석 실행
# =========================================================

def run_time_series_anomaly_analysis(
    data: List[Dict[str, Any]],
    protected_cells: Optional[List[Dict[str, Any]]] = None,
    anomaly_options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if protected_cells is None:
        protected_cells = []

    options = normalize_anomaly_options(anomaly_options)

    preprocess_result = preprocess_multivariate_time_series(
        data=data,
        protected_cells=protected_cells,
    )

    processed_df = preprocess_result["df"]
    preprocess_summary = preprocess_result["summary"]

    value_columns = preprocess_result.get(
        "value_columns",
        preprocess_summary.get("value_columns", []),
    )

    protected_dates = preprocess_summary.get("protected_dates", [])
    protected_date_map = preprocess_summary.get("protected_date_map", {})

    anomaly_result = run_anomaly_detection(
        df=processed_df,
        date_column="date",
        value_columns=value_columns,
        method=options.get("method", "auto"),
        sensitivity=options.get("sensitivity", "medium"),
        frequency=preprocess_summary.get("frequency"),
        protected_dates=protected_dates,
        protected_date_map=protected_date_map,
    )

    anomaly_payload = build_anomaly_metrics_payload(
        anomaly_result=anomaly_result,
        preprocess_summary=preprocess_summary,
    )

    anomaly_payload = attach_anomaly_interpretation(anomaly_payload)

    # ---------------------------------------------------------
    # anomaly_metrics.py가 모든 신규 필드를 그대로 올려주지 않을 수 있으므로
    # result.js / anomaly-chart.js에서 바로 접근할 수 있게 top-level에 보강
    # ---------------------------------------------------------

    anomaly_payload["summary"]["mode"] = "anomaly"
    anomaly_payload["summary"]["method"] = anomaly_result.get("method")
    anomaly_payload["summary"]["resolved_method"] = anomaly_result.get("resolved_method")
    anomaly_payload["summary"]["sensitivity"] = anomaly_result.get("sensitivity")
    anomaly_payload["summary"]["threshold"] = anomaly_result.get("threshold")
    anomaly_payload["summary"]["anomaly_count"] = anomaly_result.get("anomaly_count")
    anomaly_payload["summary"]["anomaly_ratio"] = anomaly_result.get("anomaly_ratio")
    anomaly_payload["summary"]["top_anomaly_date"] = anomaly_result.get("top_anomaly_date")
    anomaly_payload["summary"]["top_anomaly_score"] = anomaly_result.get("top_anomaly_score")
    anomaly_payload["summary"]["data_count"] = preprocess_summary.get("final_count")
    anomaly_payload["summary"]["variable_count"] = len(value_columns)
    anomaly_payload["summary"]["missing_count"] = preprocess_summary.get("missing_count")
    anomaly_payload["summary"]["protected_count"] = preprocess_summary.get("protected_count")
    anomaly_payload["summary"]["date_column"] = preprocess_summary.get("date_column")
    anomaly_payload["summary"]["value_columns"] = value_columns
    anomaly_payload["summary"]["frequency"] = preprocess_summary.get("frequency")

    anomaly_payload["date"] = anomaly_result.get("date", [])
    anomaly_payload["value_columns"] = anomaly_result.get("value_columns", [])
    anomaly_payload["series"] = anomaly_result.get("series", {})

    anomaly_payload["score"] = anomaly_result.get("score", [])
    anomaly_payload["is_anomaly"] = anomaly_result.get("is_anomaly", [])

    anomaly_payload["feature_scores"] = anomaly_result.get("feature_scores", {})
    anomaly_payload["feature_anomaly_matrix"] = anomaly_result.get(
        "feature_anomaly_matrix",
        {},
    )
    anomaly_payload["protected_mask"] = anomaly_result.get("protected_mask", {})

    anomaly_payload["anomaly_points"] = anomaly_result.get("anomaly_points", {})
    anomaly_payload["protected_points"] = anomaly_result.get("protected_points", {})

    anomaly_payload["feature_contribution"] = anomaly_result.get(
        "feature_contribution",
        [],
    )
    anomaly_payload["anomaly_table"] = anomaly_result.get("anomaly_table", [])

    anomaly_payload["protected_dates"] = anomaly_result.get("protected_dates", [])
    anomaly_payload["protected_date_map"] = anomaly_result.get(
        "protected_date_map",
        {},
    )

    anomaly_payload["preprocessing"] = build_multivariate_preprocess_payload(
        preprocess_result,
    )

    anomaly_payload["anomaly_options"] = options
    anomaly_payload["raw_anomaly_result"] = anomaly_result

    return anomaly_payload


# =========================================================
# 9. 통합 분석 실행
# =========================================================

def run_analysis(
    data: List[Dict[str, Any]],
    mode: str = "forecast",
    horizon: Any = 12,
    protected_cells: Optional[List[Dict[str, Any]]] = None,
    anomaly_options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if protected_cells is None:
        protected_cells = []

    normalized_mode = normalize_analysis_mode(mode)

    if normalized_mode == "anomaly":
        return run_time_series_anomaly_analysis(
            data=data,
            protected_cells=protected_cells,
            anomaly_options=anomaly_options,
        )

    return run_time_series_forecast_analysis(
        data=data,
        horizon=horizon,
        protected_cells=protected_cells,
    )