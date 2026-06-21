# =========================================================
# TIME - backend/anomaly_metrics.py
# ---------------------------------------------------------
# 역할
# 1. anomaly.py에서 생성된 이상탐지 결과를 대시보드 형태로 정리
# 2. Result 페이지 요약 카드에 필요한 summary 생성
# 3. 이상 점수 시계열, threshold, 이상 여부 데이터 생성
# 4. 변수별 이상 기여도 대시보드 생성
# 5. 이상 시점 테이블 생성
# 6. anomaly score 분포 데이터 생성
# =========================================================

from typing import Any, Dict, List, Optional

import numpy as np


# =========================================================
# 1. 기본 유틸
# =========================================================

def safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None

        value = float(value)

        if np.isnan(value) or np.isinf(value):
            return None

        return round(value, 4)
    except Exception:
        return None


def safe_int(value: Any) -> int:
    try:
        if value is None:
            return 0

        value = int(value)

        return value
    except Exception:
        return 0


def safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value

    return []


def get_score_array(anomaly_result: Dict[str, Any]) -> np.ndarray:
    score = anomaly_result.get("score", [])

    if not isinstance(score, list):
        return np.array([], dtype=float)

    numeric_score = []

    for value in score:
        try:
            if value is None:
                numeric_score.append(np.nan)
            else:
                numeric_score.append(float(value))
        except Exception:
            numeric_score.append(np.nan)

    return np.array(numeric_score, dtype=float)


def get_anomaly_bool_array(anomaly_result: Dict[str, Any]) -> np.ndarray:
    is_anomaly = anomaly_result.get("is_anomaly", [])

    if not isinstance(is_anomaly, list):
        return np.array([], dtype=bool)

    return np.array([bool(value) for value in is_anomaly], dtype=bool)


# =========================================================
# 2. 이상 점수 통계 계산
# =========================================================

def calculate_score_statistics(
    anomaly_result: Dict[str, Any],
) -> Dict[str, Optional[float]]:
    score_array = get_score_array(anomaly_result)

    if len(score_array) == 0:
        return {
            "score_mean": None,
            "score_std": None,
            "score_min": None,
            "score_q1": None,
            "score_median": None,
            "score_q3": None,
            "score_max": None,
        }

    valid_score = score_array[np.isfinite(score_array)]

    if len(valid_score) == 0:
        return {
            "score_mean": None,
            "score_std": None,
            "score_min": None,
            "score_q1": None,
            "score_median": None,
            "score_q3": None,
            "score_max": None,
        }

    return {
        "score_mean": safe_float(np.mean(valid_score)),
        "score_std": safe_float(np.std(valid_score)),
        "score_min": safe_float(np.min(valid_score)),
        "score_q1": safe_float(np.percentile(valid_score, 25)),
        "score_median": safe_float(np.percentile(valid_score, 50)),
        "score_q3": safe_float(np.percentile(valid_score, 75)),
        "score_max": safe_float(np.max(valid_score)),
    }


# =========================================================
# 3. 이상탐지 요약 생성
# ---------------------------------------------------------
# Result 페이지의 상단 summary card에 사용
# =========================================================

def build_anomaly_summary(
    anomaly_result: Dict[str, Any],
    preprocess_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if preprocess_summary is None:
        preprocess_summary = {}

    dates = safe_list(anomaly_result.get("date"))
    value_columns = safe_list(anomaly_result.get("value_columns"))

    data_count = len(dates)
    variable_count = len(value_columns)

    anomaly_count = safe_int(anomaly_result.get("anomaly_count"))

    if data_count > 0:
        anomaly_ratio = (anomaly_count / data_count) * 100
    else:
        anomaly_ratio = 0

    score_statistics = calculate_score_statistics(anomaly_result)

    return {
        "mode": "anomaly",

        "data_count": data_count,
        "variable_count": variable_count,
        "value_columns": value_columns,

        "date_column": preprocess_summary.get("date_column", "date"),
        "frequency": preprocess_summary.get("frequency"),

        "method": anomaly_result.get("method", "-"),
        "resolved_method": anomaly_result.get("resolved_method", "-"),
        "sensitivity": anomaly_result.get("sensitivity", "medium"),
        "threshold": safe_float(anomaly_result.get("threshold")),

        "anomaly_count": anomaly_count,
        "anomaly_ratio": safe_float(anomaly_ratio),

        "top_anomaly_date": anomaly_result.get("top_anomaly_date"),
        "top_anomaly_score": safe_float(anomaly_result.get("top_anomaly_score")),

        "missing_count": safe_int(preprocess_summary.get("missing_count")),
        "protected_count": safe_int(preprocess_summary.get("protected_count")),

        "message": anomaly_result.get("message", ""),

        **score_statistics,
    }


# =========================================================
# 4. 이상 점수 시계열 생성
# ---------------------------------------------------------
# anomaly score line chart에 사용
# =========================================================

def build_anomaly_series(
    anomaly_result: Dict[str, Any],
) -> Dict[str, Any]:
    dates = safe_list(anomaly_result.get("date"))
    score = safe_list(anomaly_result.get("score"))
    is_anomaly = safe_list(anomaly_result.get("is_anomaly"))

    min_length = min(len(dates), len(score), len(is_anomaly))

    dates = dates[:min_length]
    score = score[:min_length]
    is_anomaly = is_anomaly[:min_length]

    threshold = safe_float(anomaly_result.get("threshold"))

    threshold_values = []

    for _ in range(min_length):
        threshold_values.append(threshold)

    return {
        "date": dates,
        "score": score,
        "is_anomaly": [bool(value) for value in is_anomaly],
        "threshold": threshold,
        "threshold_values": threshold_values,
    }


# =========================================================
# 5. 다변량 시계열 데이터 생성
# ---------------------------------------------------------
# 변수별 line chart와 이상 시점 marker에 사용
# =========================================================

def build_multivariate_series(
    anomaly_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "date": safe_list(anomaly_result.get("date")),
        "value_columns": safe_list(anomaly_result.get("value_columns")),
        "series": anomaly_result.get("series", {}),
        "anomaly_points": anomaly_result.get(
            "anomaly_points",
            {
                "date": [],
                "score": [],
                "features": {},
            },
        ),
    }


# =========================================================
# 6. 변수별 기여도 대시보드 생성
# ---------------------------------------------------------
# anomaly.py의 feature_contribution을 받아 rank와 비율을 추가
# =========================================================

def build_feature_contribution_dashboard(
    anomaly_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    raw_rows = anomaly_result.get("feature_contribution", [])

    if not isinstance(raw_rows, list) or len(raw_rows) == 0:
        return []

    valid_scores = []

    for row in raw_rows:
        mean_score = row.get("mean_score")

        if mean_score is None:
            valid_scores.append(0.0)
        else:
            try:
                valid_scores.append(float(mean_score))
            except Exception:
                valid_scores.append(0.0)

    total_score = sum(valid_scores)

    dashboard_rows = []

    for index, row in enumerate(raw_rows):
        mean_score = safe_float(row.get("mean_score"))
        max_score = safe_float(row.get("max_score"))
        anomaly_count = safe_int(row.get("anomaly_count"))

        if total_score > 0 and mean_score is not None:
            contribution_ratio = (float(mean_score) / total_score) * 100
        else:
            contribution_ratio = 0

        dashboard_rows.append(
            {
                "feature": str(row.get("feature", "-")),
                "mean_score": mean_score,
                "max_score": max_score,
                "anomaly_count": anomaly_count,
                "contribution_ratio": safe_float(contribution_ratio),
                "rank": index + 1,
            }
        )

    dashboard_rows = sorted(
        dashboard_rows,
        key=lambda row: (
            row["mean_score"] if row["mean_score"] is not None else -1
        ),
        reverse=True,
    )

    for index, row in enumerate(dashboard_rows):
        row["rank"] = index + 1

    return dashboard_rows


# =========================================================
# 7. 이상 시점 테이블 생성
# ---------------------------------------------------------
# Result 페이지의 anomaly table에 사용
# =========================================================

def build_anomaly_table(
    anomaly_result: Dict[str, Any],
    max_rows: int = 100,
) -> List[Dict[str, Any]]:
    raw_table = anomaly_result.get("anomaly_table", [])

    if not isinstance(raw_table, list):
        return []

    table_rows = []

    for row in raw_table:
        table_rows.append(
            {
                "date": row.get("date", "-"),
                "score": safe_float(row.get("score")),
                "status": row.get("status", "anomaly"),
                "main_feature": row.get("main_feature", "-"),
                "feature_values": row.get("feature_values", {}),
            }
        )

    table_rows = sorted(
        table_rows,
        key=lambda row: row["score"] if row["score"] is not None else -1,
        reverse=True,
    )

    return table_rows[:max_rows]


# =========================================================
# 8. 이상 점수 분포 생성
# ---------------------------------------------------------
# 히스토그램/분포 대시보드에 사용
# =========================================================

def build_score_distribution(
    anomaly_result: Dict[str, Any],
    bins: int = 10,
) -> Dict[str, Any]:
    score_array = get_score_array(anomaly_result)

    if len(score_array) == 0:
        return {
            "bin_start": [],
            "bin_end": [],
            "count": [],
        }

    valid_score = score_array[np.isfinite(score_array)]

    if len(valid_score) == 0:
        return {
            "bin_start": [],
            "bin_end": [],
            "count": [],
        }

    if np.min(valid_score) == np.max(valid_score):
        return {
            "bin_start": [safe_float(np.min(valid_score))],
            "bin_end": [safe_float(np.max(valid_score))],
            "count": [int(len(valid_score))],
        }

    counts, edges = np.histogram(valid_score, bins=bins)

    return {
        "bin_start": [safe_float(value) for value in edges[:-1]],
        "bin_end": [safe_float(value) for value in edges[1:]],
        "count": [int(value) for value in counts],
    }


# =========================================================
# 9. 이상 여부별 카운트 생성
# ---------------------------------------------------------
# 정상/이상 비율 시각화에 사용
# =========================================================

def build_status_counts(
    anomaly_result: Dict[str, Any],
) -> Dict[str, int]:
    is_anomaly = get_anomaly_bool_array(anomaly_result)

    anomaly_count = int(np.sum(is_anomaly))
    normal_count = int(len(is_anomaly) - anomaly_count)

    return {
        "normal": normal_count,
        "anomaly": anomaly_count,
        "total": int(len(is_anomaly)),
    }


# =========================================================
# 10. 변수별 이상 대표값 생성
# ---------------------------------------------------------
# 이상 시점에서 변수별 평균값/최대값을 대시보드에 표시할 때 사용
# =========================================================

def build_feature_value_summary(
    anomaly_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    anomaly_points = anomaly_result.get("anomaly_points", {})
    features = anomaly_points.get("features", {})

    if not isinstance(features, dict):
        return []

    rows = []

    for feature_name, values in features.items():
        if not isinstance(values, list) or len(values) == 0:
            rows.append(
                {
                    "feature": str(feature_name),
                    "anomaly_mean_value": None,
                    "anomaly_min_value": None,
                    "anomaly_max_value": None,
                }
            )
            continue

        numeric_values = []

        for value in values:
            try:
                if value is not None:
                    numeric_values.append(float(value))
            except Exception:
                continue

        if len(numeric_values) == 0:
            rows.append(
                {
                    "feature": str(feature_name),
                    "anomaly_mean_value": None,
                    "anomaly_min_value": None,
                    "anomaly_max_value": None,
                }
            )
            continue

        rows.append(
            {
                "feature": str(feature_name),
                "anomaly_mean_value": safe_float(np.mean(numeric_values)),
                "anomaly_min_value": safe_float(np.min(numeric_values)),
                "anomaly_max_value": safe_float(np.max(numeric_values)),
            }
        )

    return rows


# =========================================================
# 11. Result 페이지용 전체 payload 생성
# ---------------------------------------------------------
# analysis.py에서 anomaly_result를 받은 뒤 이 함수를 호출하면 됨
# =========================================================

def build_anomaly_metrics_payload(
    anomaly_result: Dict[str, Any],
    preprocess_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    summary = build_anomaly_summary(
        anomaly_result=anomaly_result,
        preprocess_summary=preprocess_summary,
    )

    anomaly_series = build_anomaly_series(
        anomaly_result=anomaly_result,
    )

    multivariate_series = build_multivariate_series(
        anomaly_result=anomaly_result,
    )

    feature_contribution = build_feature_contribution_dashboard(
        anomaly_result=anomaly_result,
    )

    anomaly_table = build_anomaly_table(
        anomaly_result=anomaly_result,
    )

    score_distribution = build_score_distribution(
        anomaly_result=anomaly_result,
    )

    status_counts = build_status_counts(
        anomaly_result=anomaly_result,
    )

    feature_value_summary = build_feature_value_summary(
        anomaly_result=anomaly_result,
    )

    return {
        "summary": summary,

        "anomaly_series": anomaly_series,
        "multivariate_series": multivariate_series,

        "anomaly_points": anomaly_result.get(
            "anomaly_points",
            {
                "date": [],
                "score": [],
                "features": {},
            },
        ),

        "feature_contribution": feature_contribution,
        "feature_value_summary": feature_value_summary,

        "anomaly_table": anomaly_table,

        "score_distribution": score_distribution,
        "status_counts": status_counts,

        "raw_anomaly_result": {
            "method": anomaly_result.get("method"),
            "resolved_method": anomaly_result.get("resolved_method"),
            "sensitivity": anomaly_result.get("sensitivity"),
            "threshold": safe_float(anomaly_result.get("threshold")),
            "message": anomaly_result.get("message", ""),
            "extra": anomaly_result.get("extra", {}),
        },
    }


# =========================================================
# 12. 간단한 이상탐지 품질 해석 문구 생성
# ---------------------------------------------------------
# 라벨이 없는 이상탐지 과제이므로 Precision/Recall 대신
# 탐지 비율과 score 분포를 기준으로 해석 문구 제공
# =========================================================

def build_anomaly_interpretation(
    anomaly_payload: Dict[str, Any],
) -> List[str]:
    summary = anomaly_payload.get("summary", {})

    anomaly_ratio = summary.get("anomaly_ratio")
    method = summary.get("method", "-")
    threshold = summary.get("threshold")
    top_anomaly_date = summary.get("top_anomaly_date")

    messages = []

    messages.append(
        f"{method} 기반으로 시계열 이상탐지를 수행했습니다."
    )

    if anomaly_ratio is not None:
        if anomaly_ratio == 0:
            messages.append(
                "현재 설정에서는 이상 시점이 탐지되지 않았습니다. 더 민감한 탐지를 원하면 민감도를 높일 수 있습니다."
            )
        elif anomaly_ratio <= 5:
            messages.append(
                f"전체 데이터 중 약 {anomaly_ratio}%가 이상 시점으로 탐지되어 비교적 보수적인 탐지 결과입니다."
            )
        elif anomaly_ratio <= 15:
            messages.append(
                f"전체 데이터 중 약 {anomaly_ratio}%가 이상 시점으로 탐지되어 일반적인 수준의 탐지 결과입니다."
            )
        else:
            messages.append(
                f"전체 데이터 중 약 {anomaly_ratio}%가 이상 시점으로 탐지되었습니다. 이상 비율이 높으므로 threshold 또는 민감도 조정이 필요할 수 있습니다."
            )

    if threshold is not None:
        messages.append(
            f"이상 판정 기준 threshold는 {threshold}입니다."
        )

    if top_anomaly_date:
        messages.append(
            f"가장 높은 이상 점수를 보인 시점은 {top_anomaly_date}입니다."
        )

    return messages


def attach_anomaly_interpretation(
    anomaly_payload: Dict[str, Any],
) -> Dict[str, Any]:
    payload = dict(anomaly_payload)

    payload["interpretation"] = build_anomaly_interpretation(
        anomaly_payload=payload,
    )

    return payload