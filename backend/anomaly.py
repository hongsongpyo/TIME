# =========================================================
# TIME - backend/anomaly.py
# ---------------------------------------------------------
# 역할
# 1. 다변량 시계열 데이터에 대한 이상탐지 수행
# 2. Z-score, IQR, STL Residual, Isolation Forest 기반 탐지 제공
# 3. method="auto"일 때 데이터 조건에 따라 적절한 탐지 방법 자동 선택
# 4. anomaly score, 이상 여부, 변수별 기여도, 이상 시점 테이블 생성
# 5. 사용자가 특이치로 보호한 날짜는 이상치 판정에서 제외
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

        return round(value, 4)
    except Exception:
        return None


def serialize_values(values: Any) -> List[Optional[float]]:
    serialized = []

    for value in list(values):
        serialized.append(safe_float(value))

    return serialized


def serialize_bool_values(values: Any) -> List[bool]:
    return [bool(value) for value in list(values)]


def format_date(value: Any) -> str:
    timestamp = pd.Timestamp(value)

    if timestamp.hour == 0 and timestamp.minute == 0 and timestamp.second == 0:
        return timestamp.strftime("%Y-%m-%d")

    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def normalize_score(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)

    if len(values) == 0:
        return values

    min_value = np.nanmin(values)
    max_value = np.nanmax(values)

    if not np.isfinite(min_value) or not np.isfinite(max_value):
        return np.zeros_like(values, dtype=float)

    if max_value - min_value == 0:
        return np.zeros_like(values, dtype=float)

    return (values - min_value) / (max_value - min_value)


# =========================================================
# 2. 민감도 설정
# ---------------------------------------------------------
# low    : 보수적으로 탐지, 이상치 적게 탐지
# medium : 기본값
# high   : 민감하게 탐지, 이상치 많이 탐지
# =========================================================

def get_z_threshold(sensitivity: str) -> float:
    sensitivity = str(sensitivity or "medium").lower()

    if sensitivity == "low":
        return 4.0

    if sensitivity == "high":
        return 2.5

    return 3.0


def get_iqr_multiplier(sensitivity: str) -> float:
    sensitivity = str(sensitivity or "medium").lower()

    if sensitivity == "low":
        return 2.0

    if sensitivity == "high":
        return 1.0

    return 1.5


def get_contamination(sensitivity: str, data_length: int) -> float:
    sensitivity = str(sensitivity or "medium").lower()

    if sensitivity == "low":
        contamination = 0.03
    elif sensitivity == "high":
        contamination = 0.10
    else:
        contamination = 0.05

    if data_length < 20:
        contamination = min(contamination, 0.10)

    return max(0.01, min(contamination, 0.20))


# =========================================================
# 3. 입력 데이터 정리
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

    working_df = df.copy()

    working_df[date_column] = pd.to_datetime(
        working_df[date_column],
        errors="coerce",
    )

    working_df = working_df.dropna(subset=[date_column])
    working_df = working_df.sort_values(date_column)
    working_df = working_df.drop_duplicates(subset=[date_column], keep="last")
    working_df = working_df.reset_index(drop=True)

    if working_df.empty:
        raise ValueError("유효한 날짜 데이터가 없습니다.")

    if value_columns is None:
        value_columns = []

        for column in working_df.columns:
            if column == date_column:
                continue

            numeric = pd.to_numeric(working_df[column], errors="coerce")

            if numeric.notna().sum() > 0:
                value_columns.append(column)

    value_columns = [
        column for column in value_columns
        if column in working_df.columns and column != date_column
    ]

    if not value_columns:
        raise ValueError("이상탐지에 사용할 숫자형 컬럼을 찾을 수 없습니다.")

    for column in value_columns:
        working_df[column] = pd.to_numeric(
            working_df[column],
            errors="coerce",
        )

    working_df[value_columns] = (
        working_df[value_columns]
        .interpolate(method="linear", limit_direction="both")
        .ffill()
        .bfill()
    )

    working_df = working_df.dropna(subset=value_columns, how="all")
    working_df[value_columns] = working_df[value_columns].fillna(
        working_df[value_columns].median(numeric_only=True)
    )

    working_df[value_columns] = working_df[value_columns].fillna(0)

    if len(working_df) < 3:
        raise ValueError("이상탐지를 수행하기에는 데이터가 너무 적습니다.")

    return working_df, value_columns


# =========================================================
# 4. Robust Z-score 계산
# ---------------------------------------------------------
# 평균/표준편차 기반 Z-score보다 이상치에 덜 민감하도록
# median, MAD 기반 robust z-score를 사용
# =========================================================

def calculate_robust_z_matrix(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)

    median = np.nanmedian(values, axis=0)
    mad = np.nanmedian(np.abs(values - median), axis=0)

    robust_scale = 1.4826 * mad

    std = np.nanstd(values, axis=0)
    robust_scale = np.where(robust_scale == 0, std, robust_scale)
    robust_scale = np.where(robust_scale == 0, 1.0, robust_scale)

    z_matrix = np.abs((values - median) / robust_scale)

    z_matrix = np.nan_to_num(
        z_matrix,
        nan=0.0,
        posinf=0.0,
        neginf=0.0,
    )

    return z_matrix


# =========================================================
# 5. Z-score 기반 이상탐지
# =========================================================

def detect_by_zscore(
    values: np.ndarray,
    sensitivity: str,
) -> Dict[str, Any]:
    z_matrix = calculate_robust_z_matrix(values)
    row_score = np.max(z_matrix, axis=1)

    threshold = get_z_threshold(sensitivity)
    is_anomaly = row_score >= threshold

    return {
        "method": "Z-score",
        "score": row_score,
        "threshold": threshold,
        "is_anomaly": is_anomaly,
        "feature_scores": z_matrix,
    }


# =========================================================
# 6. IQR 기반 이상탐지
# =========================================================

def detect_by_iqr(
    values: np.ndarray,
    sensitivity: str,
) -> Dict[str, Any]:
    values = np.asarray(values, dtype=float)

    q1 = np.nanpercentile(values, 25, axis=0)
    q3 = np.nanpercentile(values, 75, axis=0)
    iqr = q3 - q1

    iqr = np.where(iqr == 0, np.nanstd(values, axis=0), iqr)
    iqr = np.where(iqr == 0, 1.0, iqr)

    multiplier = get_iqr_multiplier(sensitivity)

    lower_bound = q1 - multiplier * iqr
    upper_bound = q3 + multiplier * iqr

    lower_excess = np.maximum(0, lower_bound - values) / iqr
    upper_excess = np.maximum(0, values - upper_bound) / iqr

    feature_scores = np.maximum(lower_excess, upper_excess)
    feature_scores = np.nan_to_num(
        feature_scores,
        nan=0.0,
        posinf=0.0,
        neginf=0.0,
    )

    row_score = np.max(feature_scores, axis=1)
    is_anomaly = row_score > 0

    return {
        "method": "IQR",
        "score": row_score,
        "threshold": 0.0,
        "is_anomaly": is_anomaly,
        "feature_scores": feature_scores,
    }


# =========================================================
# 7. STL Residual 기반 이상탐지
# ---------------------------------------------------------
# 각 변수별로 추세/계절성을 제거한 residual의 robust z-score를 계산
# =========================================================

def infer_stl_period(data_length: int, frequency: Optional[str] = None) -> int:
    if data_length < 8:
        return 2

    if frequency:
        freq = str(frequency).upper()

        if freq.startswith("D"):
            period = 7
        elif freq.startswith("W"):
            period = 52
        elif freq.startswith("M"):
            period = 12
        elif freq.startswith("Q"):
            period = 4
        else:
            period = min(7, max(2, data_length // 4))
    else:
        period = min(7, max(2, data_length // 4))

    if data_length < period * 2:
        period = max(2, data_length // 2)

    return max(2, int(period))


def calculate_stl_residuals(
    values: np.ndarray,
    period: int,
) -> np.ndarray:
    residuals = []

    for column_index in range(values.shape[1]):
        series = pd.Series(values[:, column_index], dtype=float)

        try:
            if STL is None or len(series) < period * 2:
                rolling = series.rolling(
                    window=period,
                    center=True,
                    min_periods=1,
                ).mean()

                residual = series - rolling
            else:
                stl = STL(
                    series,
                    period=period,
                    robust=True,
                )

                result = stl.fit()
                residual = pd.Series(result.resid)

        except Exception:
            rolling = series.rolling(
                window=period,
                center=True,
                min_periods=1,
            ).mean()

            residual = series - rolling

        residuals.append(residual.values)

    return np.column_stack(residuals)


def detect_by_stl_residual(
    values: np.ndarray,
    sensitivity: str,
    frequency: Optional[str] = None,
) -> Dict[str, Any]:
    period = infer_stl_period(
        data_length=len(values),
        frequency=frequency,
    )

    residual_matrix = calculate_stl_residuals(
        values=values,
        period=period,
    )

    z_matrix = calculate_robust_z_matrix(residual_matrix)
    row_score = np.max(z_matrix, axis=1)

    threshold = get_z_threshold(sensitivity)
    is_anomaly = row_score >= threshold

    return {
        "method": "STL Residual",
        "score": row_score,
        "threshold": threshold,
        "is_anomaly": is_anomaly,
        "feature_scores": z_matrix,
        "period": period,
    }


# =========================================================
# 8. Isolation Forest 기반 이상탐지
# =========================================================

def detect_by_isolation_forest(
    values: np.ndarray,
    sensitivity: str,
    random_state: int = 42,
) -> Dict[str, Any]:
    if IsolationForest is None or StandardScaler is None:
        fallback_result = detect_by_zscore(
            values=values,
            sensitivity=sensitivity,
        )
        fallback_result["method"] = "Z-score"
        fallback_result["message"] = (
            "scikit-learn을 사용할 수 없어 Z-score 방식으로 대체했습니다."
        )
        return fallback_result

    values = np.asarray(values, dtype=float)
    data_length = len(values)

    scaler = StandardScaler()
    scaled_values = scaler.fit_transform(values)

    contamination = get_contamination(
        sensitivity=sensitivity,
        data_length=data_length,
    )

    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=random_state,
    )

    labels = model.fit_predict(scaled_values)

    # decision_function 값이 작을수록 이상치에 가까움
    raw_score = -model.decision_function(scaled_values)
    normalized_score = normalize_score(raw_score)

    is_anomaly = labels == -1

    if np.any(is_anomaly):
        threshold = float(np.min(normalized_score[is_anomaly]))
    else:
        threshold = float(np.percentile(normalized_score, 95))

    # Isolation Forest 자체는 변수별 기여도를 직접 제공하지 않으므로
    # 표준화된 값의 절대 크기를 변수별 이상 기여도 proxy로 사용
    feature_scores = np.abs(scaled_values)
    feature_scores = np.nan_to_num(
        feature_scores,
        nan=0.0,
        posinf=0.0,
        neginf=0.0,
    )

    return {
        "method": "Isolation Forest",
        "score": normalized_score,
        "threshold": threshold,
        "is_anomaly": is_anomaly,
        "feature_scores": feature_scores,
        "contamination": contamination,
    }


# =========================================================
# 9. 탐지 방법 선택
# =========================================================

def resolve_method(
    method: str,
    data_length: int,
    column_count: int,
) -> str:
    method = str(method or "auto").lower()

    method_aliases = {
        "z": "zscore",
        "z_score": "zscore",
        "z-score": "zscore",
        "iqr": "iqr",
        "stl": "stl_residual",
        "stl_residual": "stl_residual",
        "residual": "stl_residual",
        "isolation": "isolation_forest",
        "isolationforest": "isolation_forest",
        "isolation_forest": "isolation_forest",
    }

    if method != "auto":
        return method_aliases.get(method, "zscore")

    if column_count >= 2 and data_length >= 20:
        return "isolation_forest"

    if data_length >= 14:
        return "stl_residual"

    return "zscore"


def run_detector(
    method: str,
    values: np.ndarray,
    sensitivity: str,
    frequency: Optional[str] = None,
) -> Dict[str, Any]:
    if method == "iqr":
        return detect_by_iqr(
            values=values,
            sensitivity=sensitivity,
        )

    if method == "stl_residual":
        return detect_by_stl_residual(
            values=values,
            sensitivity=sensitivity,
            frequency=frequency,
        )

    if method == "isolation_forest":
        return detect_by_isolation_forest(
            values=values,
            sensitivity=sensitivity,
        )

    return detect_by_zscore(
        values=values,
        sensitivity=sensitivity,
    )


# =========================================================
# 10. 보호 날짜 적용
# ---------------------------------------------------------
# 사용자가 특이치로 지정한 날짜는 이상탐지 결과에서 제외
# =========================================================

def normalize_protected_dates(
    protected_dates: Optional[List[Any]],
) -> List[str]:
    if not protected_dates:
        return []

    normalized = []

    for value in protected_dates:
        try:
            normalized.append(format_date(value))
        except Exception:
            continue

    return normalized


def apply_protected_dates(
    dates: List[str],
    is_anomaly: np.ndarray,
    protected_dates: Optional[List[Any]] = None,
) -> np.ndarray:
    protected_date_set = set(normalize_protected_dates(protected_dates))

    if not protected_date_set:
        return is_anomaly

    adjusted = np.array(is_anomaly, dtype=bool)

    for index, date_value in enumerate(dates):
        if date_value in protected_date_set:
            adjusted[index] = False

    return adjusted


# =========================================================
# 11. 변수별 기여도 및 이상 시점 테이블 생성
# =========================================================

def build_feature_contribution(
    value_columns: List[str],
    feature_scores: np.ndarray,
    is_anomaly: np.ndarray,
) -> List[Dict[str, Any]]:
    if len(value_columns) == 0:
        return []

    if feature_scores.size == 0:
        return []

    if np.any(is_anomaly):
        target_scores = feature_scores[is_anomaly]
    else:
        target_scores = feature_scores

    contribution_rows = []

    for column_index, column_name in enumerate(value_columns):
        column_scores = target_scores[:, column_index]

        contribution_rows.append(
            {
                "feature": str(column_name),
                "mean_score": safe_float(np.mean(column_scores)),
                "max_score": safe_float(np.max(column_scores)),
                "anomaly_count": int(
                    np.sum(
                        feature_scores[:, column_index]
                        == np.max(feature_scores, axis=1)
                    )
                    if np.any(is_anomaly)
                    else 0
                ),
            }
        )

    contribution_rows = sorted(
        contribution_rows,
        key=lambda row: row["mean_score"] if row["mean_score"] is not None else -1,
        reverse=True,
    )

    return contribution_rows


def build_anomaly_table(
    dates: List[str],
    values: np.ndarray,
    value_columns: List[str],
    score: np.ndarray,
    feature_scores: np.ndarray,
    is_anomaly: np.ndarray,
) -> List[Dict[str, Any]]:
    table_rows = []

    for row_index, is_row_anomaly in enumerate(is_anomaly):
        if not is_row_anomaly:
            continue

        feature_score_row = feature_scores[row_index]

        if len(feature_score_row) > 0:
            main_feature_index = int(np.argmax(feature_score_row))
            main_feature = value_columns[main_feature_index]
        else:
            main_feature = "-"

        feature_values = {}

        for column_index, column_name in enumerate(value_columns):
            feature_values[str(column_name)] = safe_float(
                values[row_index, column_index]
            )

        table_rows.append(
            {
                "date": dates[row_index],
                "score": safe_float(score[row_index]),
                "status": "anomaly",
                "main_feature": str(main_feature),
                "feature_values": feature_values,
            }
        )

    table_rows = sorted(
        table_rows,
        key=lambda row: row["score"] if row["score"] is not None else -1,
        reverse=True,
    )

    return table_rows


def build_anomaly_points(
    dates: List[str],
    values: np.ndarray,
    value_columns: List[str],
    score: np.ndarray,
    is_anomaly: np.ndarray,
) -> Dict[str, Any]:
    anomaly_indexes = np.where(is_anomaly)[0]

    if len(anomaly_indexes) == 0:
        return {
            "date": [],
            "score": [],
            "features": {},
        }

    features = {}

    for column_index, column_name in enumerate(value_columns):
        features[str(column_name)] = serialize_values(
            values[anomaly_indexes, column_index]
        )

    return {
        "date": [dates[index] for index in anomaly_indexes],
        "score": serialize_values(score[anomaly_indexes]),
        "features": features,
    }


# =========================================================
# 12. 전체 이상탐지 실행 함수
# ---------------------------------------------------------
# analysis.py에서 호출할 메인 함수
# =========================================================

def run_anomaly_detection(
    df: pd.DataFrame,
    date_column: str = "date",
    value_columns: Optional[List[str]] = None,
    method: str = "auto",
    sensitivity: str = "medium",
    frequency: Optional[str] = None,
    protected_dates: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    prepared_df, detected_value_columns = prepare_anomaly_dataframe(
        df=df,
        date_column=date_column,
        value_columns=value_columns,
    )

    dates = [
        format_date(value)
        for value in prepared_df[date_column]
    ]

    values = prepared_df[detected_value_columns].to_numpy(dtype=float)

    resolved_method = resolve_method(
        method=method,
        data_length=len(prepared_df),
        column_count=len(detected_value_columns),
    )

    detector_result = run_detector(
        method=resolved_method,
        values=values,
        sensitivity=sensitivity,
        frequency=frequency,
    )

    score = np.asarray(detector_result.get("score", []), dtype=float)
    threshold = detector_result.get("threshold")
    is_anomaly = np.asarray(detector_result.get("is_anomaly", []), dtype=bool)
    feature_scores = np.asarray(detector_result.get("feature_scores", []), dtype=float)

    is_anomaly = apply_protected_dates(
        dates=dates,
        is_anomaly=is_anomaly,
        protected_dates=protected_dates,
    )

    anomaly_count = int(np.sum(is_anomaly))
    anomaly_ratio = (anomaly_count / len(prepared_df)) * 100 if len(prepared_df) else 0

    feature_contribution = build_feature_contribution(
        value_columns=detected_value_columns,
        feature_scores=feature_scores,
        is_anomaly=is_anomaly,
    )

    anomaly_table = build_anomaly_table(
        dates=dates,
        values=values,
        value_columns=detected_value_columns,
        score=score,
        feature_scores=feature_scores,
        is_anomaly=is_anomaly,
    )

    anomaly_points = build_anomaly_points(
        dates=dates,
        values=values,
        value_columns=detected_value_columns,
        score=score,
        is_anomaly=is_anomaly,
    )

    series = {}

    for column_index, column_name in enumerate(detected_value_columns):
        series[str(column_name)] = serialize_values(values[:, column_index])

    feature_score_payload = {}

    for column_index, column_name in enumerate(detected_value_columns):
        feature_score_payload[str(column_name)] = serialize_values(
            feature_scores[:, column_index]
        )

    top_anomaly_date = None
    top_anomaly_score = None

    if anomaly_table:
        top_anomaly_date = anomaly_table[0].get("date")
        top_anomaly_score = anomaly_table[0].get("score")

    return {
        "method": detector_result.get("method"),
        "resolved_method": resolved_method,
        "sensitivity": sensitivity,
        "threshold": safe_float(threshold),
        "message": detector_result.get("message", ""),

        "date": dates,
        "value_columns": [str(column) for column in detected_value_columns],
        "series": series,

        "score": serialize_values(score),
        "is_anomaly": serialize_bool_values(is_anomaly),
        "feature_scores": feature_score_payload,

        "anomaly_count": anomaly_count,
        "anomaly_ratio": safe_float(anomaly_ratio),
        "top_anomaly_date": top_anomaly_date,
        "top_anomaly_score": top_anomaly_score,

        "anomaly_points": anomaly_points,
        "feature_contribution": feature_contribution,
        "anomaly_table": anomaly_table,

        "extra": {
            "period": detector_result.get("period"),
            "contamination": safe_float(detector_result.get("contamination")),
        },
    }