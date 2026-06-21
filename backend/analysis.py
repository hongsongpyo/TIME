# =========================================================
# TIME - backend/analysis.py
# ---------------------------------------------------------
# 역할
# 1. 다변량 시계열 이상탐지 분석 실행
# 2. preprocessing.py의 다변량 전처리 결과와 anomaly.py의 탐지 결과 연결
# 3. result.html / result.js / anomaly-chart.js에서 사용할 payload 생성
# 4. 기존 main.py 호환을 위해 run_time_series_analysis 함수명 유지
# =========================================================

from typing import Any, Dict, List, Optional

import pandas as pd

from preprocessing import (
    preprocess_multivariate_time_series,
    serialize_values,
)

from anomaly import run_anomaly_detection


# =========================================================
# 1. 옵션 정규화
# =========================================================

def normalize_analysis_mode(mode: Optional[str]) -> str:
    mode_text = str(mode or "anomaly").strip().lower()

    if mode_text in ["anomaly", "anomaly_detection", "detect", "이상탐지"]:
        return "anomaly"

    # 예측 기능은 사용하지 않으므로 다른 값이 들어와도 anomaly로 처리
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


def get_sensitivity_label(sensitivity: Optional[str]) -> str:
    sensitivity = normalize_sensitivity(sensitivity)

    if sensitivity == "high":
        return "높음"

    if sensitivity == "low":
        return "낮음"

    return "보통"


def normalize_anomaly_options(
    anomaly_options: Optional[Dict[str, Any]] = None,
    method: Optional[str] = None,
    sensitivity: Optional[str] = None,
) -> Dict[str, str]:
    if anomaly_options is None:
        anomaly_options = {}

    resolved_method = method
    resolved_sensitivity = sensitivity

    if resolved_method is None:
        resolved_method = anomaly_options.get("method", "auto")

    if resolved_sensitivity is None:
        resolved_sensitivity = anomaly_options.get("sensitivity", "medium")

    normalized_method = normalize_anomaly_method(resolved_method)
    normalized_sensitivity = normalize_sensitivity(resolved_sensitivity)

    return {
        "method": normalized_method,
        "sensitivity": normalized_sensitivity,
        "sensitivity_label": get_sensitivity_label(normalized_sensitivity),
    }


# =========================================================
# 2. 날짜 / 값 직렬화
# =========================================================

def normalize_date_string(value: Any) -> Optional[str]:
    try:
        timestamp = pd.Timestamp(value)

        if pd.isna(timestamp):
            return None

        if (
            timestamp.hour == 0
            and timestamp.minute == 0
            and timestamp.second == 0
            and timestamp.microsecond == 0
        ):
            return timestamp.strftime("%Y-%m-%d")

        return timestamp.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def serialize_point_list(
    points: Optional[List[Dict[str, Any]]],
) -> Dict[str, List[Any]]:
    if not points:
        return {
            "date": [],
            "column": [],
            "value": [],
        }

    return {
        "date": [point.get("date") for point in points],
        "column": [point.get("column") for point in points],
        "value": [point.get("value") for point in points],
    }


def serialize_primary_points(
    points: Optional[List[Dict[str, Any]]],
    primary_column: Optional[str],
) -> Dict[str, List[Any]]:
    if not points or not primary_column:
        return {
            "date": [],
            "value": [],
        }

    filtered_points = [
        point
        for point in points
        if str(point.get("column")) == str(primary_column)
    ]

    return {
        "date": [point.get("date") for point in filtered_points],
        "value": [point.get("value") for point in filtered_points],
    }


def get_primary_column(
    preprocess_summary: Dict[str, Any],
    value_columns: List[str],
) -> Optional[str]:
    value_column = preprocess_summary.get("value_column")

    if value_column and value_column in value_columns:
        return value_column

    if value_columns:
        return value_columns[0]

    return None


# =========================================================
# 3. Summary payload 생성
# =========================================================

def build_anomaly_summary(
    preprocess_summary: Dict[str, Any],
    anomaly_result: Dict[str, Any],
    value_columns: List[str],
    options: Dict[str, str],
) -> Dict[str, Any]:
    anomaly_summary = anomaly_result.get("summary", {})

    data_count = preprocess_summary.get("final_count")
    anomaly_count = anomaly_result.get("anomaly_count", 0)

    if data_count:
        anomaly_ratio = anomaly_count / data_count * 100
    else:
        anomaly_ratio = anomaly_result.get("anomaly_ratio")

    return {
        "mode": "anomaly",

        "method": anomaly_result.get("method"),
        "resolved_method": anomaly_result.get("resolved_method"),
        "sensitivity": options.get("sensitivity"),
        "sensitivity_label": options.get("sensitivity_label"),
        "threshold": anomaly_result.get("threshold"),

        "date_column": preprocess_summary.get("date_column"),
        "value_column": preprocess_summary.get("value_column"),
        "value_columns": value_columns,
        "numeric_columns": value_columns,
        "frequency": preprocess_summary.get("frequency"),

        "original_count": preprocess_summary.get("original_count"),
        "valid_count": preprocess_summary.get("valid_count"),
        "final_count": preprocess_summary.get("final_count"),
        "data_count": data_count,
        "variable_count": len(value_columns),

        "missing_count": preprocess_summary.get("missing_count", 0),
        "protected_count": preprocess_summary.get("protected_count", 0),

        "anomaly_count": anomaly_count,
        "anomaly_ratio": anomaly_result.get("anomaly_ratio", anomaly_ratio),
        "outlier_count": anomaly_count,

        "top_variable": anomaly_result.get(
            "top_variable",
            anomaly_summary.get("top_variable"),
        ),
        "top_anomaly_date": anomaly_result.get(
            "top_anomaly_date",
            anomaly_summary.get("top_anomaly_date"),
        ),
        "top_anomaly_score": anomaly_result.get(
            "top_anomaly_score",
            anomaly_summary.get("top_anomaly_score"),
        ),

        "message": anomaly_result.get("message", ""),
    }


# =========================================================
# 4. Time series payload 생성
# ---------------------------------------------------------
# result.js / anomaly-chart.js에서 공통으로 사용할 데이터
# =========================================================

def build_time_series_payload(
    preprocess_result: Dict[str, Any],
    anomaly_result: Dict[str, Any],
    primary_column: Optional[str],
) -> Dict[str, Any]:
    date_values = preprocess_result.get("date", [])
    original_values = preprocess_result.get("original_values", {})
    filled_values = preprocess_result.get("filled_values", {})
    preprocessed_values = preprocess_result.get("preprocessed_values", filled_values)

    primary_original = []
    primary_filled = []
    primary_preprocessed = []

    if primary_column:
        primary_original = original_values.get(primary_column, [])
        primary_filled = filled_values.get(primary_column, [])
        primary_preprocessed = preprocessed_values.get(primary_column, primary_filled)

    missing_points_long = preprocess_result.get("missing_points_long", [])
    protected_points_long = preprocess_result.get("protected_points_long", [])

    return {
        "date": date_values,

        # 다변량 전체 값
        "value_columns": preprocess_result.get("value_columns", []),
        "original_values": original_values,
        "filled_values": filled_values,
        "preprocessed_values": preprocessed_values,

        # anomaly.py 결과
        "series": anomaly_result.get("series", {}),
        "anomaly_score": anomaly_result.get("score", []),
        "score": anomaly_result.get("score", []),
        "raw_score": anomaly_result.get("raw_score", []),
        "is_anomaly": anomaly_result.get("is_anomaly", []),

        "feature_scores": anomaly_result.get("feature_scores", {}),
        "raw_feature_scores": anomaly_result.get("raw_feature_scores", {}),
        "feature_anomaly_matrix": anomaly_result.get("feature_anomaly_matrix", {}),
        "protected_mask": anomaly_result.get("protected_mask", {}),

        "anomaly_points": anomaly_result.get("anomaly_points", {}),
        "protected_points_by_feature": anomaly_result.get("protected_points", {}),

        # 데이터 품질 포인트
        "missing_points_long": missing_points_long,
        "protected_points_long": protected_points_long,

        # 기존 chart.js와의 호환 필드
        "primary_column": primary_column,
        "original": primary_original,
        "filled": primary_filled,
        "preprocessed": primary_preprocessed,
        "missing_points": serialize_primary_points(
            missing_points_long,
            primary_column,
        ),
        "protected_points": serialize_primary_points(
            protected_points_long,
            primary_column,
        ),
        "outlier_points": {
            "date": anomaly_result.get("anomaly_points", {}).get("date", []),
            "value": anomaly_result.get("anomaly_points", {}).get("value", []),
        },
    }


# =========================================================
# 5. 데이터 품질 payload 생성
# =========================================================

def build_data_quality_payload(
    preprocess_result: Dict[str, Any],
) -> Dict[str, Any]:
    summary = preprocess_result.get("summary", {})

    missing_points_long = preprocess_result.get("missing_points_long", [])
    protected_points_long = preprocess_result.get("protected_points_long", [])

    return {
        "date_column": summary.get("date_column"),
        "value_column": summary.get("value_column"),
        "value_columns": preprocess_result.get("value_columns", []),
        "numeric_columns": preprocess_result.get("numeric_columns", []),

        "frequency": summary.get("frequency"),

        "original_count": summary.get("original_count"),
        "valid_count": summary.get("valid_count"),
        "final_count": summary.get("final_count"),

        "missing_count": summary.get("missing_count", 0),
        "missing_by_column": summary.get("missing_by_column", {}),

        "protected_count": summary.get("protected_count", 0),
        "protected_dates": summary.get("protected_dates", []),
        "protected_date_map": summary.get("protected_date_map", {}),

        "missing_points": serialize_point_list(missing_points_long),
        "protected_points": serialize_point_list(protected_points_long),

        "missing_points_long": missing_points_long,
        "protected_points_long": protected_points_long,
    }


# =========================================================
# 6. 이상탐지 대시보드 payload 생성
# =========================================================

def build_anomaly_dashboard_payload(
    anomaly_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "score_timeline": anomaly_result.get("score_timeline", {}),
        "heatmap": anomaly_result.get("heatmap", {}),

        "feature_contribution": anomaly_result.get("feature_contribution", []),
        "variable_summary": anomaly_result.get(
            "variable_summary",
            anomaly_result.get("feature_contribution", []),
        ),

        "top_anomaly_contribution": anomaly_result.get(
            "top_anomaly_contribution",
            {
                "date": None,
                "items": [],
            },
        ),

        "anomaly_table": anomaly_result.get("anomaly_table", []),
        "top_anomaly_table": anomaly_result.get(
            "top_anomaly_table",
            anomaly_result.get("anomaly_table", [])[:20],
        ),

        "anomaly_type_summary": anomaly_result.get("anomaly_type_summary", []),

        "download_rows": anomaly_result.get("download_rows", []),
    }


# =========================================================
# 7. 다변량 이상탐지 분석 실행
# =========================================================

def run_time_series_anomaly_analysis(
    data: List[Dict[str, Any]],
    protected_cells: Optional[List[Dict[str, Any]]] = None,
    anomaly_options: Optional[Dict[str, Any]] = None,
    method: Optional[str] = None,
    sensitivity: Optional[str] = None,
) -> Dict[str, Any]:
    if protected_cells is None:
        protected_cells = []

    options = normalize_anomaly_options(
        anomaly_options=anomaly_options,
        method=method,
        sensitivity=sensitivity,
    )

    preprocess_result = preprocess_multivariate_time_series(
        data=data,
        protected_cells=protected_cells,
    )

    processed_df = preprocess_result["df"]
    preprocess_summary = preprocess_result.get("summary", {})

    value_columns = preprocess_result.get(
        "value_columns",
        preprocess_summary.get("value_columns", []),
    )

    if not value_columns:
        raise ValueError("이상탐지에 사용할 숫자형 컬럼이 없습니다.")

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

    primary_column = get_primary_column(
        preprocess_summary=preprocess_summary,
        value_columns=value_columns,
    )

    summary = build_anomaly_summary(
        preprocess_summary=preprocess_summary,
        anomaly_result=anomaly_result,
        value_columns=value_columns,
        options=options,
    )

    time_series = build_time_series_payload(
        preprocess_result=preprocess_result,
        anomaly_result=anomaly_result,
        primary_column=primary_column,
    )

    data_quality = build_data_quality_payload(
        preprocess_result=preprocess_result,
    )

    dashboard = build_anomaly_dashboard_payload(
        anomaly_result=anomaly_result,
    )

    # -----------------------------------------------------
    # 프론트엔드에서 접근하기 쉽게 top-level에도 주요 필드 배치
    # -----------------------------------------------------
    result = {
        "summary": summary,

        "time_series": time_series,
        "data_quality": data_quality,

        "anomaly": {
            "method": anomaly_result.get("method"),
            "resolved_method": anomaly_result.get("resolved_method"),
            "sensitivity": anomaly_result.get("sensitivity"),
            "sensitivity_label": anomaly_result.get("sensitivity_label"),
            "threshold": anomaly_result.get("threshold"),
            "message": anomaly_result.get("message", ""),

            **dashboard,
        },

        # 메뉴형 그래프에서 바로 접근할 수 있도록 top-level 제공
        "score_timeline": dashboard["score_timeline"],
        "heatmap": dashboard["heatmap"],
        "feature_contribution": dashboard["feature_contribution"],
        "variable_summary": dashboard["variable_summary"],
        "top_anomaly_contribution": dashboard["top_anomaly_contribution"],
        "anomaly_table": dashboard["anomaly_table"],
        "top_anomaly_table": dashboard["top_anomaly_table"],
        "anomaly_type_summary": dashboard["anomaly_type_summary"],
        "download_rows": dashboard["download_rows"],

        # 기존 result.js 호환용
        "metrics_dashboard": [],
        "model_results": {},

        # 상세 원본 결과
        "anomaly_result": anomaly_result,
        "preprocessing": {
            "date": preprocess_result.get("date", []),
            "value_columns": value_columns,
            "original_values": preprocess_result.get("original_values", {}),
            "filled_values": preprocess_result.get("filled_values", {}),
            "preprocessed_values": preprocess_result.get("preprocessed_values", {}),
            "summary": preprocess_summary,
        },
        "anomaly_options": options,
    }

    return result


# =========================================================
# 8. 통합 분석 실행
# ---------------------------------------------------------
# 예측 기능은 제외하고 모든 요청을 anomaly 분석으로 처리
# =========================================================

def run_analysis(
    data: List[Dict[str, Any]],
    mode: str = "anomaly",
    horizon: Any = 12,
    protected_cells: Optional[List[Dict[str, Any]]] = None,
    anomaly_options: Optional[Dict[str, Any]] = None,
    method: Optional[str] = None,
    sensitivity: Optional[str] = None,
) -> Dict[str, Any]:
    if protected_cells is None:
        protected_cells = []

    _ = normalize_analysis_mode(mode)

    return run_time_series_anomaly_analysis(
        data=data,
        protected_cells=protected_cells,
        anomaly_options=anomaly_options,
        method=method,
        sensitivity=sensitivity,
    )


# =========================================================
# 9. 기존 main.py 호환용 함수명
# ---------------------------------------------------------
# 기존 main.py가 run_time_series_analysis를 import하고 있어도
# 오류 없이 이상탐지 분석이 실행되도록 유지
# =========================================================

def run_time_series_analysis(
    data: List[Dict[str, Any]],
    horizon: Any = 12,
    protected_cells: Optional[List[Dict[str, Any]]] = None,
    mode: str = "anomaly",
    anomaly_options: Optional[Dict[str, Any]] = None,
    method: Optional[str] = None,
    sensitivity: Optional[str] = None,
) -> Dict[str, Any]:
    return run_analysis(
        data=data,
        mode=mode,
        horizon=horizon,
        protected_cells=protected_cells,
        anomaly_options=anomaly_options,
        method=method,
        sensitivity=sensitivity,
    )