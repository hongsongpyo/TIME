# =========================================================
# TIME - backend/analysis.py
# ---------------------------------------------------------
# 역할
# 1. 예측 분석과 이상탐지 분석의 공통 진입점 제공
# 2. mode="forecast"일 때 기존 시계열 예측 분석 실행
# 3. mode="anomaly"일 때 다변량 시계열 이상탐지 실행
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
# 1. 공통 유틸
# =========================================================

def normalize_analysis_mode(mode: Optional[str]) -> str:
    mode = str(mode or "forecast").lower().strip()

    if mode in ["forecast", "prediction", "predict"]:
        return "forecast"

    if mode in ["anomaly", "anomaly_detection", "detect", "outlier"]:
        return "anomaly"

    return "forecast"


def normalize_forecast_horizon(horizon: Union[int, str, None]) -> Union[int, str]:
    if horizon is None:
        return 12

    if isinstance(horizon, str):
        horizon_text = horizon.strip().lower()

        if horizon_text == "auto":
            return "auto"

        try:
            horizon_value = int(horizon_text)
        except Exception:
            raise ValueError("시평 horizon은 1 이상의 숫자이거나 auto여야 합니다.")
    else:
        try:
            horizon_value = int(horizon)
        except Exception:
            raise ValueError("시평 horizon은 1 이상의 숫자이거나 auto여야 합니다.")

    if horizon_value <= 0:
        raise ValueError("시평 horizon은 1 이상이어야 합니다.")

    return horizon_value


def normalize_anomaly_options(
    anomaly_options: Optional[Any] = None,
) -> Dict[str, str]:
    if anomaly_options is None:
        return {
            "method": "auto",
            "sensitivity": "medium",
        }

    if isinstance(anomaly_options, dict):
        options = anomaly_options
    elif hasattr(anomaly_options, "model_dump"):
        options = anomaly_options.model_dump()
    elif hasattr(anomaly_options, "dict"):
        options = anomaly_options.dict()
    else:
        options = {}

    method = str(options.get("method", "auto") or "auto").lower().strip()
    sensitivity = str(
        options.get("sensitivity", "medium") or "medium"
    ).lower().strip()

    allowed_methods = {
        "auto",
        "zscore",
        "z_score",
        "z-score",
        "iqr",
        "stl",
        "stl_residual",
        "isolation",
        "isolationforest",
        "isolation_forest",
    }

    allowed_sensitivities = {
        "low",
        "medium",
        "high",
    }

    if method not in allowed_methods:
        method = "auto"

    if sensitivity not in allowed_sensitivities:
        sensitivity = "medium"

    return {
        "method": method,
        "sensitivity": sensitivity,
    }


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
# 2. 예측 결과 payload 생성
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
        "horizon": forecast_result.get("horizon", horizon),

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


# 기존 이름과 호환되도록 남겨둠
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
# 3. 예측 분석 실행
# ---------------------------------------------------------
# 기존 result.html / chart.js / metrics.py 구조와 호환
# =========================================================

def run_time_series_forecast_analysis(
    data: List[Dict[str, Any]],
    horizon: Union[int, str] = 12,
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


# 기존 main.py가 이 함수를 호출하던 구조와 호환되도록 유지
def run_time_series_analysis(
    data: List[Dict[str, Any]],
    horizon: Union[int, str] = 12,
    protected_cells: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return run_time_series_forecast_analysis(
        data=data,
        horizon=horizon,
        protected_cells=protected_cells,
    )


# =========================================================
# 4. 이상탐지용 전처리 payload 생성
# ---------------------------------------------------------
# 프론트에서 원본/보간값 확인이 필요할 때 사용할 수 있음
# =========================================================

def build_multivariate_preprocess_payload(
    preprocess_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "date": preprocess_result.get("date", []),
        "value_columns": preprocess_result.get("value_columns", []),
        "original_values": preprocess_result.get("original_values", {}),
        "filled_values": preprocess_result.get("filled_values", {}),
        "missing_count": preprocess_result.get("missing_count", 0),
        "protected_dates": preprocess_result.get("protected_dates", []),
        "protected_date_map": preprocess_result.get("protected_date_map", {}),
    }


# =========================================================
# 5. 이상탐지 분석 실행
# ---------------------------------------------------------
# 신규 anomaly.py / anomaly_metrics.py와 연결
# =========================================================

def run_time_series_anomaly_analysis(
    data: List[Dict[str, Any]],
    protected_cells: Optional[List[Dict[str, Any]]] = None,
    anomaly_options: Optional[Any] = None,
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

    value_columns = preprocess_summary.get("value_columns", [])

    if not value_columns:
        raise ValueError("이상탐지에 사용할 숫자형 컬럼이 없습니다.")

    anomaly_result = run_anomaly_detection(
        df=processed_df,
        date_column="date",
        value_columns=value_columns,
        method=options.get("method", "auto"),
        sensitivity=options.get("sensitivity", "medium"),
        frequency=preprocess_summary.get("frequency"),
        protected_dates=preprocess_summary.get("protected_dates", []),
    )

    anomaly_payload = build_anomaly_metrics_payload(
        anomaly_result=anomaly_result,
        preprocess_summary=preprocess_summary,
    )

    anomaly_payload = attach_anomaly_interpretation(anomaly_payload)

    # result.js에서 forecast/anomaly 분기를 쉽게 하기 위해 summary.mode 보장
    anomaly_payload["summary"]["mode"] = "anomaly"

    return {
        **anomaly_payload,

        "preprocessing": build_multivariate_preprocess_payload(
            preprocess_result=preprocess_result,
        ),

        "anomaly_options": options,
    }


# =========================================================
# 6. 전체 분석 진입점
# ---------------------------------------------------------
# main.py의 /analyze API에서 이 함수만 호출하면 됨
# =========================================================

def run_analysis(
    data: List[Dict[str, Any]],
    mode: str = "forecast",
    horizon: Union[int, str, None] = 12,
    protected_cells: Optional[List[Dict[str, Any]]] = None,
    anomaly_options: Optional[Any] = None,
) -> Dict[str, Any]:
    if protected_cells is None:
        protected_cells = []

    analysis_mode = normalize_analysis_mode(mode)

    if analysis_mode == "anomaly":
        return run_time_series_anomaly_analysis(
            data=data,
            protected_cells=protected_cells,
            anomaly_options=anomaly_options,
        )

    return run_time_series_forecast_analysis(
        data=data,
        horizon=normalize_forecast_horizon(horizon),
        protected_cells=protected_cells,
    )