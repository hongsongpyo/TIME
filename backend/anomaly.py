# =========================================================
# TIME - backend/anomaly.py
# ---------------------------------------------------------
# 역할
# 1. 다변량 시계열 이상탐지 수행
# 2. Z-score / IQR / STL residual / Isolation Forest 지원
# 3. row-level anomaly와 feature-level anomaly를 함께 계산
# 4. 사용자가 지정한 특이치 셀은 protected point로 분리
# 5. 이상 점수, threshold, 변수별 기여도, heatmap, Top N table payload 생성
# 6. 메뉴형 이상탐지 대시보드에서 사용할 응답 구조 생성
# =========================================================

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
except Exception:
    IsolationForest = None
    StandardScaler = None

try:
    from statsmodels.tsa.seasonal import STL
except Exception:
    STL = None


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

        return round(value, 6)
    except Exception:
        return None


def safe_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None

        return int(value)
    except Exception:
        return None


def format_date(value: Any) -> str:
    timestamp = pd.to_datetime(value, errors="coerce")

    if pd.isna(timestamp):
        return str(value)

    timestamp = pd.Timestamp(timestamp)

    if (
        timestamp.hour == 0
        and timestamp.minute == 0
        and timestamp.second == 0
        and timestamp.microsecond == 0
    ):
        return timestamp.strftime("%Y-%m-%d")

    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def normalize_date_key(value: Any) -> str:
    return format_date(value)


def serialize_values(values: Any) -> List[Optional[float]]:
    result = []

    for value in list(values):
        result.append(safe_float(value))

    return result


def serialize_bool_values(values: Any) -> List[bool]:
    return [bool(value) for value in list(values)]


def safe_array(values: Any) -> np.ndarray:
    array = np.asarray(values, dtype=float)

    if array.ndim == 1:
        array = array.reshape(-1, 1)

    array = np.where(np.isfinite(array), array, np.nan)

    return array


def normalize_score(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)

    if len(values) == 0:
        return values

    finite_mask = np.isfinite(values)

    if not np.any(finite_mask):
        return np.zeros_like(values, dtype=float)

    finite_values = values[finite_mask]
    min_value = np.min(finite_values)
    max_value = np.max(finite_values)

    if max_value - min_value == 0:
        result = np.zeros_like(values, dtype=float)
        result[finite_mask] = 0.0
        return result

    result = np.zeros_like(values, dtype=float)
    result[finite_mask] = (
        (finite_values - min_value) / (max_value - min_value) * 100.0
    )

    return result


def normalize_sensitivity(sensitivity: str) -> str:
    sensitivity = str(sensitivity or "medium").strip().lower()

    high_values = ["high", "높음", "민감", "높은"]
    low_values = ["low", "낮음", "낮은"]
    medium_values = ["medium", "normal", "보통", "중간", "기본"]

    if sensitivity in high_values:
        return "high"

    if sensitivity in low_values:
        return "low"

    if sensitivity in medium_values:
        return "medium"

    return "medium"


def get_sensitivity_label(sensitivity: str) -> str:
    sensitivity = normalize_sensitivity(sensitivity)

    if sensitivity == "high":
        return "높음"

    if sensitivity == "low":
        return "낮음"

    return "보통"


def normalize_method(method: str) -> str:
    method = str(method or "auto").strip().lower()

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

    return method_alias.get(method, method)


# =========================================================
# 2. 민감도별 threshold 설정
# ---------------------------------------------------------
# 민감도 높음: threshold 낮음 → 더 많이 탐지
# 민감도 낮음: threshold 높음 → 확실한 이상만 탐지
# =========================================================

def get_z_threshold(sensitivity: str) -> float:
    sensitivity = normalize_sensitivity(sensitivity)

    if sensitivity == "high":
        return 2.5

    if sensitivity == "low":
        return 3.5

    return 3.0


def get_iqr_multiplier(sensitivity: str) -> float:
    sensitivity = normalize_sensitivity(sensitivity)

    if sensitivity == "high":
        return 1.2

    if sensitivity == "low":
        return 2.0

    return 1.5


def get_contamination(sensitivity: str, data_length: int) -> float:
    sensitivity = normalize_sensitivity(sensitivity)

    if sensitivity == "high":
        base = 0.12
    elif sensitivity == "low":
        base = 0.04
    else:
        base = 0.07

    if data_length < 30:
        base = min(base, 0.08)

    return float(max(0.01, min(base, 0.2)))


# =========================================================
# 3. 데이터 준비
# =========================================================

def prepare_anomaly_dataframe(
    df: pd.DataFrame,
    date_column: str = "date",
    value_columns: Optional[List[str]] = None,
) -> Tuple[pd.DataFrame, List[str]]:
    if df is None or df.empty:
        raise ValueError("이상탐지를 수행할 데이터가 없습니다.")

    if date_column not in df.columns:
        raise ValueError(f"{date_column} 컬럼을 찾을 수 없습니다.")

    prepared_df = df.copy()
    prepared_df[date_column] = pd.to_datetime(
        prepared_df[date_column],
        errors="coerce",
    )

    prepared_df = prepared_df.dropna(subset=[date_column])
    prepared_df = prepared_df.sort_values(date_column)
    prepared_df = prepared_df.drop_duplicates(subset=[date_column], keep="last")
    prepared_df = prepared_df.reset_index(drop=True)

    if prepared_df.empty:
        raise ValueError("유효한 날짜 데이터가 없습니다.")

    if value_columns is None:
        value_columns = []

        for column in prepared_df.columns:
            if column == date_column:
                continue

            numeric = pd.to_numeric(prepared_df[column], errors="coerce")

            if numeric.notna().sum() > 0:
                value_columns.append(str(column))

    value_columns = [
        str(column)
        for column in value_columns
        if str(column) in prepared_df.columns and str(column) != date_column
    ]

    if not value_columns:
        raise ValueError("이상탐지를 수행할 숫자형 컬럼을 찾을 수 없습니다.")

    for column in value_columns:
        prepared_df[column] = pd.to_numeric(prepared_df[column], errors="coerce")

    prepared_df[value_columns] = (
        prepared_df[value_columns]
        .interpolate(method="linear", limit_direction="both")
        .ffill()
        .bfill()
    )

    prepared_df = prepared_df.dropna(subset=value_columns, how="all")
    prepared_df[value_columns] = prepared_df[value_columns].fillna(0)

    if prepared_df.empty:
        raise ValueError("숫자형 데이터가 모두 비어 있습니다.")

    return prepared_df, value_columns


# =========================================================
# 4. Robust Z-score 계산
# =========================================================

def calculate_robust_z_matrix(values: np.ndarray) -> np.ndarray:
    values = safe_array(values)

    median = np.nanmedian(values, axis=0)
    mad = np.nanmedian(np.abs(values - median), axis=0)

    std = np.nanstd(values, axis=0)
    scale = 1.4826 * mad

    scale = np.where(scale == 0, std, scale)
    scale = np.where(scale == 0, 1.0, scale)

    z_matrix = np.abs((values - median) / scale)
    z_matrix = np.where(np.isfinite(z_matrix), z_matrix, 0.0)

    return z_matrix


# =========================================================
# 5. Z-score 이상탐지
# =========================================================

def detect_by_zscore(
    values: np.ndarray,
    sensitivity: str,
) -> Dict[str, Any]:
    threshold = get_z_threshold(sensitivity)
    feature_scores = calculate_robust_z_matrix(values)
    feature_anomaly_matrix = feature_scores >= threshold
    row_score = np.nanmax(feature_scores, axis=1)
    is_anomaly = np.any(feature_anomaly_matrix, axis=1)

    return {
        "method": "Z-score",
        "resolved_method": "zscore",
        "threshold": threshold,
        "score": row_score,
        "is_anomaly": is_anomaly,
        "feature_scores": feature_scores,
        "feature_anomaly_matrix": feature_anomaly_matrix,
        "message": "Robust Z-score 기반 이상탐지를 수행했습니다.",
        "extra": {},
    }


# =========================================================
# 6. IQR 이상탐지
# =========================================================

def detect_by_iqr(
    values: np.ndarray,
    sensitivity: str,
) -> Dict[str, Any]:
    values = safe_array(values)

    multiplier = get_iqr_multiplier(sensitivity)

    q1 = np.nanpercentile(values, 25, axis=0)
    q3 = np.nanpercentile(values, 75, axis=0)
    iqr = q3 - q1

    std = np.nanstd(values, axis=0)

    iqr = np.where(iqr == 0, std, iqr)
    iqr = np.where(iqr == 0, 1.0, iqr)

    lower_bound = q1 - multiplier * iqr
    upper_bound = q3 + multiplier * iqr

    lower_excess = np.maximum(lower_bound - values, 0)
    upper_excess = np.maximum(values - upper_bound, 0)

    feature_scores = np.maximum(lower_excess, upper_excess) / iqr
    feature_scores = np.where(np.isfinite(feature_scores), feature_scores, 0.0)

    feature_anomaly_matrix = (values < lower_bound) | (values > upper_bound)

    row_score = np.nanmax(feature_scores, axis=1)
    is_anomaly = np.any(feature_anomaly_matrix, axis=1)

    return {
        "method": "IQR",
        "resolved_method": "iqr",
        "threshold": 1.0,
        "score": row_score,
        "is_anomaly": is_anomaly,
        "feature_scores": feature_scores,
        "feature_anomaly_matrix": feature_anomaly_matrix,
        "message": "IQR 기반 이상탐지를 수행했습니다.",
        "extra": {
            "multiplier": multiplier,
            "lower_bound": serialize_values(lower_bound),
            "upper_bound": serialize_values(upper_bound),
        },
    }


# =========================================================
# 7. STL Residual 이상탐지
# =========================================================

def infer_stl_period(
    frequency: Optional[str],
    data_length: int,
) -> int:
    if data_length < 4:
        return 2

    if not frequency:
        return min(7, max(2, data_length // 3))

    freq = str(frequency).upper()

    if freq.startswith("D"):
        period = 7
    elif freq.startswith("W"):
        period = 52
    elif freq.startswith("M"):
        period = 12
    elif freq.startswith("Q"):
        period = 4
    elif freq.startswith("H"):
        period = 24
    elif freq.startswith("T") or freq.startswith("MIN"):
        period = 60
    else:
        period = min(7, max(2, data_length // 3))

    if data_length < period * 2:
        period = max(2, data_length // 2)

    return max(2, int(period))


def calculate_stl_residuals(
    values: np.ndarray,
    period: int,
) -> np.ndarray:
    values = safe_array(values)

    residual_matrix = np.zeros_like(values, dtype=float)

    for column_index in range(values.shape[1]):
        series = pd.Series(values[:, column_index])
        series = series.interpolate(method="linear").ffill().bfill()

        try:
            if STL is None:
                raise ValueError("STL을 사용할 수 없습니다.")

            stl = STL(
                series,
                period=period,
                robust=True,
            )

            result = stl.fit()
            residual = np.asarray(result.resid, dtype=float)

        except Exception:
            trend = series.rolling(
                window=period,
                min_periods=1,
                center=True,
            ).mean()

            residual = np.asarray(series - trend, dtype=float)

        residual_matrix[:, column_index] = residual

    return residual_matrix


def detect_by_stl_residual(
    values: np.ndarray,
    sensitivity: str,
    frequency: Optional[str],
) -> Dict[str, Any]:
    values = safe_array(values)

    if len(values) < 8:
        fallback = detect_by_zscore(values, sensitivity)
        fallback["method"] = "STL Residual fallback Z-score"
        fallback["resolved_method"] = "zscore"
        fallback["message"] = "데이터가 짧아 STL 대신 Z-score 기반 이상탐지를 수행했습니다."
        return fallback

    period = infer_stl_period(frequency, len(values))
    residual_matrix = calculate_stl_residuals(values, period)
    threshold = get_z_threshold(sensitivity)

    feature_scores = calculate_robust_z_matrix(residual_matrix)
    feature_anomaly_matrix = feature_scores >= threshold

    row_score = np.nanmax(feature_scores, axis=1)
    is_anomaly = np.any(feature_anomaly_matrix, axis=1)

    return {
        "method": "STL Residual",
        "resolved_method": "stl_residual",
        "threshold": threshold,
        "score": row_score,
        "is_anomaly": is_anomaly,
        "feature_scores": feature_scores,
        "feature_anomaly_matrix": feature_anomaly_matrix,
        "message": "STL residual 기반 이상탐지를 수행했습니다.",
        "extra": {
            "period": period,
        },
    }


# =========================================================
# 8. Isolation Forest 이상탐지
# ---------------------------------------------------------
# Isolation Forest는 row-level 탐지기이므로
# feature-level marker는 robust z-score 기반 기여도를 함께 사용함
# =========================================================

def detect_by_isolation_forest(
    values: np.ndarray,
    sensitivity: str,
) -> Dict[str, Any]:
    values = safe_array(values)
    data_length = values.shape[0]

    if IsolationForest is None or StandardScaler is None or data_length < 8:
        fallback = detect_by_zscore(values, sensitivity)
        fallback["method"] = "Isolation Forest fallback Z-score"
        fallback["resolved_method"] = "zscore"
        fallback["message"] = "Isolation Forest를 사용할 수 없어 Z-score 기반 이상탐지를 수행했습니다."
        return fallback

    contamination = get_contamination(sensitivity, data_length)

    try:
        scaler = StandardScaler()
        scaled_values = scaler.fit_transform(values)

        model = IsolationForest(
            n_estimators=100,
            contamination=contamination,
            random_state=42,
        )

        model.fit(scaled_values)

        prediction = model.predict(scaled_values)
        raw_score = -model.decision_function(scaled_values)

        row_if_anomaly = prediction == -1
        normalized_row_score = normalize_score(raw_score)

        feature_scores = calculate_robust_z_matrix(values)
        z_threshold = get_z_threshold(sensitivity)

        feature_anomaly_matrix = feature_scores >= z_threshold

        for row_index, is_row_anomaly in enumerate(row_if_anomaly):
            if not is_row_anomaly:
                feature_anomaly_matrix[row_index, :] = False
                continue

            if not np.any(feature_anomaly_matrix[row_index, :]):
                top_feature_index = int(np.nanargmax(feature_scores[row_index, :]))
                feature_anomaly_matrix[row_index, top_feature_index] = True

        row_score = np.nanmax(feature_scores, axis=1)
        is_anomaly = np.any(feature_anomaly_matrix, axis=1)

        return {
            "method": "Isolation Forest",
            "resolved_method": "isolation_forest",
            "threshold": z_threshold,
            "score": row_score,
            "is_anomaly": is_anomaly,
            "feature_scores": feature_scores,
            "feature_anomaly_matrix": feature_anomaly_matrix,
            "message": "Isolation Forest 기반 이상탐지를 수행했습니다.",
            "extra": {
                "contamination": contamination,
                "isolation_forest_score": serialize_values(normalized_row_score),
                "score_note": "Isolation Forest는 행 단위 탐지이고, 변수별 기여도는 robust z-score 기준입니다.",
            },
        }

    except Exception as error:
        fallback = detect_by_zscore(values, sensitivity)
        fallback["method"] = "Isolation Forest fallback Z-score"
        fallback["resolved_method"] = "zscore"
        fallback["message"] = f"Isolation Forest 실행 실패로 Z-score를 사용했습니다: {str(error)}"
        return fallback


# =========================================================
# 9. 탐지 방식 선택
# =========================================================

def resolve_method(
    method: str,
    values: np.ndarray,
) -> str:
    method = normalize_method(method)

    allowed_methods = [
        "auto",
        "isolation_forest",
        "zscore",
        "iqr",
        "stl_residual",
    ]

    if method not in allowed_methods:
        method = "auto"

    if method != "auto":
        return method

    data_length = values.shape[0]
    feature_count = values.shape[1]

    if data_length >= 20 and feature_count >= 2 and IsolationForest is not None:
        return "isolation_forest"

    if data_length >= 14:
        return "stl_residual"

    return "zscore"


def run_detector(
    values: np.ndarray,
    method: str,
    sensitivity: str,
    frequency: Optional[str],
) -> Dict[str, Any]:
    resolved_method = resolve_method(method, values)

    if resolved_method == "isolation_forest":
        return detect_by_isolation_forest(values, sensitivity)

    if resolved_method == "iqr":
        return detect_by_iqr(values, sensitivity)

    if resolved_method == "stl_residual":
        return detect_by_stl_residual(values, sensitivity, frequency)

    return detect_by_zscore(values, sensitivity)


# =========================================================
# 10. 보호점 처리
# =========================================================

def normalize_protected_dates(
    protected_dates: Optional[List[Any]],
) -> List[str]:
    if not protected_dates:
        return []

    result = []

    for value in protected_dates:
        result.append(normalize_date_key(value))

    return sorted(list(set(result)))


def normalize_protected_date_map(
    protected_date_map: Optional[Dict[str, List[Any]]],
) -> Dict[str, List[str]]:
    if not protected_date_map:
        return {}

    result = {}

    for column_name, date_list in protected_date_map.items():
        if not isinstance(date_list, list):
            continue

        normalized_dates = normalize_protected_dates(date_list)

        if normalized_dates:
            result[str(column_name)] = normalized_dates

    return result


def build_protected_mask(
    date_keys: List[str],
    value_columns: List[str],
    protected_dates: Optional[List[Any]] = None,
    protected_date_map: Optional[Dict[str, List[Any]]] = None,
) -> np.ndarray:
    protected_mask = np.zeros(
        (len(date_keys), len(value_columns)),
        dtype=bool,
    )

    normalized_map = normalize_protected_date_map(protected_date_map)

    # 신규 방식: 컬럼별 보호 날짜
    # energy 셀만 특이치로 지정한 경우 energy만 보호
    if normalized_map:
        for column_index, column_name in enumerate(value_columns):
            protected_set = set(normalized_map.get(str(column_name), []))

            if not protected_set:
                continue

            for row_index, date_key in enumerate(date_keys):
                if date_key in protected_set:
                    protected_mask[row_index, column_index] = True

        return protected_mask

    # 구버전 호환: 날짜만 있으면 해당 날짜의 모든 feature를 보호
    normalized_dates = set(normalize_protected_dates(protected_dates))

    if normalized_dates:
        for row_index, date_key in enumerate(date_keys):
            if date_key in normalized_dates:
                protected_mask[row_index, :] = True

    return protected_mask


def apply_protected_mask(
    feature_scores: np.ndarray,
    feature_anomaly_matrix: np.ndarray,
    protected_mask: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    feature_scores = np.asarray(feature_scores, dtype=float)
    feature_anomaly_matrix = np.asarray(feature_anomaly_matrix, dtype=bool)
    protected_mask = np.asarray(protected_mask, dtype=bool)

    if protected_mask.shape != feature_anomaly_matrix.shape:
        protected_mask = np.zeros_like(feature_anomaly_matrix, dtype=bool)

    masked_feature_scores = feature_scores.copy()
    masked_feature_anomaly_matrix = feature_anomaly_matrix.copy()

    masked_feature_scores[protected_mask] = 0.0
    masked_feature_anomaly_matrix[protected_mask] = False

    if masked_feature_scores.size == 0:
        row_score = np.array([])
    else:
        row_score = np.nanmax(masked_feature_scores, axis=1)

    is_anomaly = np.any(masked_feature_anomaly_matrix, axis=1)

    return (
        masked_feature_scores,
        masked_feature_anomaly_matrix,
        row_score,
        is_anomaly,
    )


# =========================================================
# 11. 기본 payload 생성 함수
# =========================================================

def build_series_payload(
    df: pd.DataFrame,
    value_columns: List[str],
) -> Dict[str, List[Optional[float]]]:
    series = {}

    for column in value_columns:
        series[column] = serialize_values(df[column])

    return series


def build_feature_scores_payload(
    feature_scores: np.ndarray,
    value_columns: List[str],
) -> Dict[str, List[Optional[float]]]:
    result = {}

    for column_index, column in enumerate(value_columns):
        result[column] = serialize_values(feature_scores[:, column_index])

    return result


def build_feature_anomaly_payload(
    feature_anomaly_matrix: np.ndarray,
    value_columns: List[str],
) -> Dict[str, List[bool]]:
    result = {}

    for column_index, column in enumerate(value_columns):
        result[column] = serialize_bool_values(
            feature_anomaly_matrix[:, column_index]
        )

    return result


def build_feature_point_payload(
    df: pd.DataFrame,
    date_keys: List[str],
    value_columns: List[str],
    feature_scores: np.ndarray,
    point_mask: np.ndarray,
) -> Dict[str, Any]:
    features = {}

    all_dates = []
    all_features = []
    all_values = []
    all_scores = []

    for column_index, column in enumerate(value_columns):
        column_dates = []
        column_values = []
        column_scores = []

        for row_index, is_point in enumerate(point_mask[:, column_index]):
            if not bool(is_point):
                continue

            date = date_keys[row_index]
            value = safe_float(df.iloc[row_index][column])
            score = safe_float(feature_scores[row_index, column_index])

            column_dates.append(date)
            column_values.append(value)
            column_scores.append(score)

            all_dates.append(date)
            all_features.append(column)
            all_values.append(value)
            all_scores.append(score)

        features[column] = {
            "date": column_dates,
            "value": column_values,
            "score": column_scores,
        }

    return {
        "date": all_dates,
        "feature": all_features,
        "value": all_values,
        "score": all_scores,
        "features": features,
    }


# =========================================================
# 12. 메뉴형 대시보드 payload 생성
# =========================================================

def build_score_timeline_payload(
    dates: List[str],
    row_score: np.ndarray,
    is_anomaly: np.ndarray,
    threshold: float,
) -> Dict[str, Any]:
    return {
        "date": dates,
        "score": serialize_values(row_score),
        "threshold": [
            safe_float(threshold)
            for _ in dates
        ],
        "is_anomaly": serialize_bool_values(is_anomaly),
    }


def build_heatmap_payload(
    dates: List[str],
    value_columns: List[str],
    feature_scores: np.ndarray,
) -> Dict[str, Any]:
    z_values = []

    for column_index, _ in enumerate(value_columns):
        z_values.append(
            serialize_values(feature_scores[:, column_index])
        )

    return {
        "date": dates,
        "variables": value_columns,
        "z": z_values,
    }


def build_feature_contribution(
    feature_scores: np.ndarray,
    feature_anomaly_matrix: np.ndarray,
    value_columns: List[str],
) -> List[Dict[str, Any]]:
    rows = []

    total_score = 0.0

    for column_index, column in enumerate(value_columns):
        mask = feature_anomaly_matrix[:, column_index]
        scores = feature_scores[:, column_index]

        column_score_sum = float(np.nansum(scores[mask])) if np.any(mask) else 0.0
        total_score += column_score_sum

    for column_index, column in enumerate(value_columns):
        mask = feature_anomaly_matrix[:, column_index]
        scores = feature_scores[:, column_index]

        anomaly_count = int(np.sum(mask))

        if anomaly_count > 0:
            mean_score = float(np.nanmean(scores[mask]))
            max_score = float(np.nanmax(scores[mask]))
            score_sum = float(np.nansum(scores[mask]))
        else:
            mean_score = 0.0
            max_score = 0.0
            score_sum = 0.0

        contribution_ratio = (
            score_sum / total_score * 100.0
            if total_score > 0
            else 0.0
        )

        rows.append(
            {
                "feature": column,
                "variable": column,
                "mean_score": safe_float(mean_score),
                "max_score": safe_float(max_score),
                "score_sum": safe_float(score_sum),
                "contribution_ratio": safe_float(contribution_ratio),
                "main_count": anomaly_count,
                "anomaly_count": anomaly_count,
            }
        )

    rows = sorted(
        rows,
        key=lambda item: (
            item.get("main_count") or 0,
            item.get("mean_score") or 0,
            item.get("max_score") or 0,
        ),
        reverse=True,
    )

    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank

    return rows


def build_row_contribution_payload(
    row_index: int,
    df: pd.DataFrame,
    date_keys: List[str],
    value_columns: List[str],
    feature_scores: np.ndarray,
    feature_anomaly_matrix: np.ndarray,
    protected_mask: np.ndarray,
) -> Dict[str, Any]:
    if row_index is None or row_index < 0 or row_index >= len(df):
        return {
            "date": None,
            "items": [],
        }

    score_sum = float(np.nansum(feature_scores[row_index, :]))

    items = []

    for column_index, column in enumerate(value_columns):
        score = float(feature_scores[row_index, column_index])

        if protected_mask[row_index, column_index]:
            status = "protected"
        elif feature_anomaly_matrix[row_index, column_index]:
            status = "anomaly"
        else:
            status = "normal"

        contribution_ratio = (
            score / score_sum * 100.0
            if score_sum > 0
            else 0.0
        )

        items.append(
            {
                "feature": column,
                "variable": column,
                "value": safe_float(df.iloc[row_index][column]),
                "score": safe_float(score),
                "contribution_ratio": safe_float(contribution_ratio),
                "status": status,
            }
        )

    items = sorted(
        items,
        key=lambda item: item.get("score") or 0,
        reverse=True,
    )

    for rank, item in enumerate(items, start=1):
        item["rank"] = rank

    return {
        "date": date_keys[row_index],
        "items": items,
    }


# =========================================================
# 13. 이상 유형 및 테이블 생성
# =========================================================

def get_main_feature_for_row(
    row_index: int,
    value_columns: List[str],
    feature_scores: np.ndarray,
    feature_anomaly_matrix: np.ndarray,
) -> str:
    anomaly_feature_indices = np.where(feature_anomaly_matrix[row_index, :])[0]

    if len(anomaly_feature_indices) > 0:
        best_index = anomaly_feature_indices[
            int(np.nanargmax(feature_scores[row_index, anomaly_feature_indices]))
        ]

        return value_columns[int(best_index)]

    best_index = int(np.nanargmax(feature_scores[row_index, :]))

    return value_columns[best_index]


def count_consecutive_anomaly_length(
    row_index: int,
    is_anomaly: np.ndarray,
) -> int:
    if row_index < 0 or row_index >= len(is_anomaly):
        return 0

    if not bool(is_anomaly[row_index]):
        return 0

    left = row_index
    right = row_index

    while left - 1 >= 0 and bool(is_anomaly[left - 1]):
        left -= 1

    while right + 1 < len(is_anomaly) and bool(is_anomaly[right + 1]):
        right += 1

    return right - left + 1


def classify_anomaly_type(
    row_index: int,
    row_score: np.ndarray,
    is_anomaly: np.ndarray,
    feature_anomaly_matrix: np.ndarray,
    threshold: float,
) -> str:
    feature_count = int(np.sum(feature_anomaly_matrix[row_index, :]))
    run_length = count_consecutive_anomaly_length(row_index, is_anomaly)
    score = float(row_score[row_index]) if len(row_score) > row_index else 0.0

    if run_length >= 3:
        return "패턴 이상"

    if feature_count >= 2:
        return "다변량 동시 이상"

    if threshold > 0 and score >= threshold * 1.5:
        return "전역 이상"

    return "맥락 이상"


def build_anomaly_description(
    anomaly_type: str,
    main_feature: str,
    score: Optional[float],
    threshold: Optional[float],
) -> str:
    score_text = "-" if score is None else str(score)
    threshold_text = "-" if threshold is None else str(threshold)

    if anomaly_type == "패턴 이상":
        return (
            f"연속된 시점에서 이상 점수가 높게 나타났으며, "
            f"주요 변수는 {main_feature}입니다. "
            f"score={score_text}, threshold={threshold_text}"
        )

    if anomaly_type == "다변량 동시 이상":
        return (
            f"여러 변수가 동시에 정상 범위에서 벗어났으며, "
            f"가장 큰 기여 변수는 {main_feature}입니다. "
            f"score={score_text}, threshold={threshold_text}"
        )

    if anomaly_type == "전역 이상":
        return (
            f"{main_feature} 값이 전체 분포 기준 크게 벗어났습니다. "
            f"score={score_text}, threshold={threshold_text}"
        )

    return (
        f"{main_feature} 값이 주변 패턴 또는 일반적인 변동 범위에서 벗어났습니다. "
        f"score={score_text}, threshold={threshold_text}"
    )


def build_anomaly_table(
    df: pd.DataFrame,
    date_keys: List[str],
    value_columns: List[str],
    row_score: np.ndarray,
    is_anomaly: np.ndarray,
    feature_scores: np.ndarray,
    feature_anomaly_matrix: np.ndarray,
    protected_mask: np.ndarray,
    threshold: float,
) -> List[Dict[str, Any]]:
    rows = []

    for row_index, anomaly_flag in enumerate(is_anomaly):
        if not bool(anomaly_flag):
            continue

        main_feature = get_main_feature_for_row(
            row_index=row_index,
            value_columns=value_columns,
            feature_scores=feature_scores,
            feature_anomaly_matrix=feature_anomaly_matrix,
        )

        anomaly_type = classify_anomaly_type(
            row_index=row_index,
            row_score=row_score,
            is_anomaly=is_anomaly,
            feature_anomaly_matrix=feature_anomaly_matrix,
            threshold=threshold,
        )

        feature_values = {}
        row_feature_scores = {}
        row_feature_status = {}

        for column_index, column in enumerate(value_columns):
            feature_values[column] = safe_float(df.iloc[row_index][column])
            row_feature_scores[column] = safe_float(
                feature_scores[row_index, column_index]
            )

            if protected_mask[row_index, column_index]:
                row_feature_status[column] = "protected"
            elif feature_anomaly_matrix[row_index, column_index]:
                row_feature_status[column] = "anomaly"
            else:
                row_feature_status[column] = "normal"

        score = safe_float(row_score[row_index])

        rows.append(
            {
                "date": date_keys[row_index],
                "score": score,
                "status": "anomaly",
                "main_feature": main_feature,
                "top_variable": main_feature,
                "type": anomaly_type,
                "anomaly_type": anomaly_type,
                "description": build_anomaly_description(
                    anomaly_type=anomaly_type,
                    main_feature=main_feature,
                    score=score,
                    threshold=safe_float(threshold),
                ),
                "feature_values": feature_values,
                "feature_scores": row_feature_scores,
                "feature_status": row_feature_status,
            }
        )

    rows = sorted(
        rows,
        key=lambda item: item.get("score") or 0,
        reverse=True,
    )

    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank

    return rows


def build_anomaly_type_summary(
    anomaly_table: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    counter: Dict[str, int] = {}

    for row in anomaly_table:
        anomaly_type = row.get("anomaly_type") or row.get("type") or "기타"
        counter[anomaly_type] = counter.get(anomaly_type, 0) + 1

    result = []

    for anomaly_type, count in counter.items():
        result.append(
            {
                "type": anomaly_type,
                "count": int(count),
            }
        )

    result = sorted(
        result,
        key=lambda item: item["count"],
        reverse=True,
    )

    return result


def get_top_variable(
    anomaly_table: List[Dict[str, Any]],
    feature_contribution: List[Dict[str, Any]],
) -> Optional[str]:
    if anomaly_table:
        counter: Dict[str, int] = {}

        for row in anomaly_table:
            feature = row.get("main_feature") or row.get("top_variable")

            if not feature:
                continue

            counter[feature] = counter.get(feature, 0) + 1

        if counter:
            return sorted(
                counter.items(),
                key=lambda item: item[1],
                reverse=True,
            )[0][0]

    if feature_contribution:
        return feature_contribution[0].get("feature")

    return None


def get_top_anomaly_index(
    is_anomaly: np.ndarray,
    row_score: np.ndarray,
) -> Optional[int]:
    anomaly_indices = np.where(is_anomaly)[0]

    if len(anomaly_indices) == 0:
        return None

    top_index = anomaly_indices[
        int(np.nanargmax(row_score[anomaly_indices]))
    ]

    return int(top_index)


# =========================================================
# 14. 다운로드용 결과 행 생성
# =========================================================

def build_download_rows(
    dates: List[str],
    value_columns: List[str],
    df: pd.DataFrame,
    row_score: np.ndarray,
    is_anomaly: np.ndarray,
    feature_scores: np.ndarray,
    feature_anomaly_matrix: np.ndarray,
    protected_mask: np.ndarray,
    anomaly_table: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    anomaly_type_by_date = {}
    main_feature_by_date = {}

    for row in anomaly_table:
        date = row.get("date")
        anomaly_type_by_date[date] = row.get("anomaly_type")
        main_feature_by_date[date] = row.get("main_feature")

    rows = []

    for row_index, date in enumerate(dates):
        row = {
            "date": date,
            "anomaly_score": safe_float(row_score[row_index]),
            "is_anomaly": bool(is_anomaly[row_index]),
            "main_feature": main_feature_by_date.get(date),
            "anomaly_type": anomaly_type_by_date.get(date),
        }

        for column_index, column in enumerate(value_columns):
            row[f"{column}_value"] = safe_float(df.iloc[row_index][column])
            row[f"{column}_score"] = safe_float(
                feature_scores[row_index, column_index]
            )

            if protected_mask[row_index, column_index]:
                status = "protected"
            elif feature_anomaly_matrix[row_index, column_index]:
                status = "anomaly"
            else:
                status = "normal"

            row[f"{column}_status"] = status

        rows.append(row)

    return rows


# =========================================================
# 15. 전체 이상탐지 실행
# =========================================================

def run_anomaly_detection(
    df: pd.DataFrame,
    date_column: str = "date",
    value_columns: Optional[List[str]] = None,
    method: str = "auto",
    sensitivity: str = "medium",
    frequency: Optional[str] = None,
    protected_dates: Optional[List[Any]] = None,
    protected_date_map: Optional[Dict[str, List[Any]]] = None,
) -> Dict[str, Any]:
    sensitivity = normalize_sensitivity(sensitivity)

    prepared_df, detected_value_columns = prepare_anomaly_dataframe(
        df=df,
        date_column=date_column,
        value_columns=value_columns,
    )

    values = prepared_df[detected_value_columns].to_numpy(dtype=float)
    dates = [format_date(value) for value in prepared_df[date_column]]
    date_keys = [normalize_date_key(value) for value in prepared_df[date_column]]

    detector_result = run_detector(
        values=values,
        method=method,
        sensitivity=sensitivity,
        frequency=frequency,
    )

    feature_scores = np.asarray(
        detector_result.get("feature_scores"),
        dtype=float,
    )

    feature_anomaly_matrix = np.asarray(
        detector_result.get("feature_anomaly_matrix"),
        dtype=bool,
    )

    if feature_scores.shape != values.shape:
        feature_scores = calculate_robust_z_matrix(values)

    threshold = float(
        detector_result.get("threshold")
        if detector_result.get("threshold") is not None
        else get_z_threshold(sensitivity)
    )

    if feature_anomaly_matrix.shape != values.shape:
        feature_anomaly_matrix = feature_scores >= threshold

    protected_mask = build_protected_mask(
        date_keys=date_keys,
        value_columns=detected_value_columns,
        protected_dates=protected_dates,
        protected_date_map=protected_date_map,
    )

    (
        masked_feature_scores,
        masked_feature_anomaly_matrix,
        final_row_score,
        final_is_anomaly,
    ) = apply_protected_mask(
        feature_scores=feature_scores,
        feature_anomaly_matrix=feature_anomaly_matrix,
        protected_mask=protected_mask,
    )

    anomaly_count = int(np.sum(final_is_anomaly))
    total_count = len(final_is_anomaly)
    anomaly_ratio = (
        anomaly_count / total_count * 100.0
        if total_count > 0
        else 0.0
    )

    top_index = get_top_anomaly_index(
        is_anomaly=final_is_anomaly,
        row_score=final_row_score,
    )

    if top_index is not None:
        top_anomaly_date = dates[top_index]
        top_anomaly_score = safe_float(final_row_score[top_index])
    else:
        top_anomaly_date = None
        top_anomaly_score = None

    anomaly_points = build_feature_point_payload(
        df=prepared_df,
        date_keys=dates,
        value_columns=detected_value_columns,
        feature_scores=masked_feature_scores,
        point_mask=masked_feature_anomaly_matrix,
    )

    protected_points = build_feature_point_payload(
        df=prepared_df,
        date_keys=dates,
        value_columns=detected_value_columns,
        feature_scores=feature_scores,
        point_mask=protected_mask,
    )

    feature_contribution = build_feature_contribution(
        feature_scores=masked_feature_scores,
        feature_anomaly_matrix=masked_feature_anomaly_matrix,
        value_columns=detected_value_columns,
    )

    anomaly_table = build_anomaly_table(
        df=prepared_df,
        date_keys=dates,
        value_columns=detected_value_columns,
        row_score=final_row_score,
        is_anomaly=final_is_anomaly,
        feature_scores=masked_feature_scores,
        feature_anomaly_matrix=masked_feature_anomaly_matrix,
        protected_mask=protected_mask,
        threshold=threshold,
    )

    anomaly_type_summary = build_anomaly_type_summary(anomaly_table)

    top_variable = get_top_variable(
        anomaly_table=anomaly_table,
        feature_contribution=feature_contribution,
    )

    if top_index is not None:
        top_anomaly_contribution = build_row_contribution_payload(
            row_index=top_index,
            df=prepared_df,
            date_keys=dates,
            value_columns=detected_value_columns,
            feature_scores=masked_feature_scores,
            feature_anomaly_matrix=masked_feature_anomaly_matrix,
            protected_mask=protected_mask,
        )
    else:
        top_anomaly_contribution = {
            "date": None,
            "items": [],
        }

    score_timeline = build_score_timeline_payload(
        dates=dates,
        row_score=final_row_score,
        is_anomaly=final_is_anomaly,
        threshold=threshold,
    )

    heatmap = build_heatmap_payload(
        dates=dates,
        value_columns=detected_value_columns,
        feature_scores=masked_feature_scores,
    )

    download_rows = build_download_rows(
        dates=dates,
        value_columns=detected_value_columns,
        df=prepared_df,
        row_score=final_row_score,
        is_anomaly=final_is_anomaly,
        feature_scores=masked_feature_scores,
        feature_anomaly_matrix=masked_feature_anomaly_matrix,
        protected_mask=protected_mask,
        anomaly_table=anomaly_table,
    )

    extra = detector_result.get("extra") or {}

    summary = {
        "method": detector_result.get("method"),
        "resolved_method": detector_result.get("resolved_method"),
        "sensitivity": sensitivity,
        "sensitivity_label": get_sensitivity_label(sensitivity),
        "threshold": safe_float(threshold),

        "data_count": total_count,
        "variable_count": len(detected_value_columns),
        "anomaly_count": anomaly_count,
        "anomaly_ratio": safe_float(anomaly_ratio),

        "top_variable": top_variable,
        "top_anomaly_date": top_anomaly_date,
        "top_anomaly_score": top_anomaly_score,
    }

    return {
        "summary": summary,

        "method": detector_result.get("method"),
        "resolved_method": detector_result.get("resolved_method"),
        "sensitivity": sensitivity,
        "sensitivity_label": get_sensitivity_label(sensitivity),
        "threshold": safe_float(threshold),
        "message": detector_result.get("message", ""),

        "date": dates,
        "value_columns": detected_value_columns,
        "series": build_series_payload(
            df=prepared_df,
            value_columns=detected_value_columns,
        ),

        "score": serialize_values(final_row_score),
        "raw_score": serialize_values(detector_result.get("score", final_row_score)),
        "is_anomaly": serialize_bool_values(final_is_anomaly),

        "feature_scores": build_feature_scores_payload(
            feature_scores=masked_feature_scores,
            value_columns=detected_value_columns,
        ),
        "raw_feature_scores": build_feature_scores_payload(
            feature_scores=feature_scores,
            value_columns=detected_value_columns,
        ),
        "feature_anomaly_matrix": build_feature_anomaly_payload(
            feature_anomaly_matrix=masked_feature_anomaly_matrix,
            value_columns=detected_value_columns,
        ),
        "protected_mask": build_feature_anomaly_payload(
            feature_anomaly_matrix=protected_mask,
            value_columns=detected_value_columns,
        ),

        "anomaly_count": anomaly_count,
        "anomaly_ratio": safe_float(anomaly_ratio),
        "top_variable": top_variable,
        "top_anomaly_date": top_anomaly_date,
        "top_anomaly_score": top_anomaly_score,

        "anomaly_points": anomaly_points,
        "protected_points": protected_points,

        "feature_contribution": feature_contribution,
        "variable_summary": feature_contribution,
        "top_anomaly_contribution": top_anomaly_contribution,

        "score_timeline": score_timeline,
        "heatmap": heatmap,

        "anomaly_table": anomaly_table,
        "top_anomaly_table": anomaly_table[:20],
        "anomaly_type_summary": anomaly_type_summary,

        "download_rows": download_rows,

        "protected_dates": normalize_protected_dates(protected_dates),
        "protected_date_map": normalize_protected_date_map(protected_date_map),

        "extra": extra,
    }