# =========================================================
# TIME - backend/preprocessing.py
# ---------------------------------------------------------
# 역할
# 1. 편집된 표 데이터를 시계열 데이터로 변환
# 2. 날짜 컬럼 / 수요 컬럼 자동 탐색
# 3. 결측치 탐지 및 보간
# 4. 이상치 탐지 및 보정
# 5. 사용자가 지정한 특이치는 이상치 처리에서 제외
# 6. 다변량 이상탐지를 위한 숫자형 컬럼 자동 탐색 및 전처리
# =========================================================

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# =========================================================
# 1. 기본 유틸
# =========================================================

def safe_to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def safe_to_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def clean_empty_rows(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.replace("", np.nan)
    df = df.dropna(how="all")
    return df.reset_index(drop=True)


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


def serialize_series_dates(series: pd.Series) -> List[str]:
    dates = []

    for value in series:
        try:
            timestamp = pd.Timestamp(value)

            if (
                timestamp.hour == 0
                and timestamp.minute == 0
                and timestamp.second == 0
            ):
                dates.append(timestamp.strftime("%Y-%m-%d"))
            else:
                dates.append(timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        except Exception:
            dates.append("")

    return dates


def serialize_values(series: pd.Series) -> List[Optional[float]]:
    values = []

    for value in series:
        if pd.isna(value) or np.isinf(value):
            values.append(None)
        else:
            values.append(float(value))

    return values


def normalize_date_string(value: Any) -> Optional[str]:
    try:
        timestamp = pd.Timestamp(value)

        if pd.isna(timestamp):
            return None

        if (
            timestamp.hour == 0
            and timestamp.minute == 0
            and timestamp.second == 0
        ):
            return timestamp.strftime("%Y-%m-%d")

        return timestamp.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


# =========================================================
# 2. 날짜 컬럼 자동 탐색
# =========================================================

def detect_date_column(df: pd.DataFrame) -> str:
    best_column = None
    best_score = -1

    for column in df.columns:
        parsed = safe_to_datetime(df[column])
        score = parsed.notna().sum()

        column_name = str(column).lower()

        if "date" in column_name or "time" in column_name:
            score += 5

        if column_name in ["ds", "datetime", "timestamp"]:
            score += 5

        if score > best_score:
            best_score = score
            best_column = column

    if best_column is None or best_score <= 0:
        raise ValueError("날짜 컬럼을 자동으로 찾을 수 없습니다.")

    return best_column


# =========================================================
# 3. 단변량 값 컬럼 자동 탐색
# ---------------------------------------------------------
# 예측 모드에서 사용할 대표 value 컬럼 1개 선택
# =========================================================

def detect_value_column(df: pd.DataFrame, date_column: str) -> str:
    best_column = None
    best_score = -1

    for column in df.columns:
        if column == date_column:
            continue

        numeric = safe_to_numeric(df[column])
        score = numeric.notna().sum()

        column_name = str(column).lower()

        if any(
            keyword in column_name
            for keyword in ["value", "demand", "sales", "target", "y"]
        ):
            score += 5

        if score > best_score:
            best_score = score
            best_column = column

    if best_column is None or best_score <= 0:
        raise ValueError("수요 값 컬럼을 자동으로 찾을 수 없습니다.")

    return best_column


# =========================================================
# 4. 다변량 숫자형 컬럼 자동 탐색
# ---------------------------------------------------------
# 이상탐지 모드에서 사용할 모든 숫자형 컬럼 선택
# =========================================================

def detect_numeric_columns(
    df: pd.DataFrame,
    date_column: str,
    min_valid_ratio: float = 0.3,
) -> List[str]:
    numeric_columns = []

    row_count = len(df)

    if row_count == 0:
        return numeric_columns

    for column in df.columns:
        if column == date_column:
            continue

        numeric = safe_to_numeric(df[column])
        valid_count = numeric.notna().sum()
        valid_ratio = valid_count / row_count

        if valid_count > 0 and valid_ratio >= min_valid_ratio:
            numeric_columns.append(column)

    if not numeric_columns:
        for column in df.columns:
            if column == date_column:
                continue

            numeric = safe_to_numeric(df[column])

            if numeric.notna().sum() > 0:
                numeric_columns.append(column)

    if not numeric_columns:
        raise ValueError("이상탐지에 사용할 숫자형 컬럼을 찾을 수 없습니다.")

    return numeric_columns


# =========================================================
# 5. 특이치 보호 날짜 생성
# ---------------------------------------------------------
# protected_cells는 editor.js에서 전달됨
# 형태:
# [
#   {"row": 3, "column": "demand"}
# ]
# =========================================================

def build_protected_dates(
    raw_df: pd.DataFrame,
    date_column: str,
    value_column: str,
    protected_cells: List[Dict[str, Any]],
) -> List[pd.Timestamp]:
    protected_dates = []

    if protected_cells is None:
        protected_cells = []

    for cell in protected_cells:
        row_index = cell.get("row")
        column_name = cell.get("column")

        if column_name != value_column:
            continue

        if row_index is None:
            continue

        try:
            row_index = int(row_index)
        except Exception:
            continue

        if row_index < 0 or row_index >= len(raw_df):
            continue

        date_value = raw_df.iloc[row_index][date_column]
        parsed_date = pd.to_datetime(date_value, errors="coerce")

        if pd.notna(parsed_date):
            protected_dates.append(pd.Timestamp(parsed_date))

    return protected_dates


def build_protected_date_map(
    raw_df: pd.DataFrame,
    date_column: str,
    value_columns: List[str],
    protected_cells: List[Dict[str, Any]],
) -> Dict[str, List[pd.Timestamp]]:
    if protected_cells is None:
        protected_cells = []

    protected_map = {
        str(column): []
        for column in value_columns
    }

    value_column_set = set(str(column) for column in value_columns)

    for cell in protected_cells:
        row_index = cell.get("row")
        column_name = cell.get("column")

        if column_name is None:
            continue

        column_name = str(column_name)

        if column_name not in value_column_set:
            continue

        if row_index is None:
            continue

        try:
            row_index = int(row_index)
        except Exception:
            continue

        if row_index < 0 or row_index >= len(raw_df):
            continue

        date_value = raw_df.iloc[row_index][date_column]
        parsed_date = pd.to_datetime(date_value, errors="coerce")

        if pd.notna(parsed_date):
            protected_map[column_name].append(pd.Timestamp(parsed_date))

    return protected_map


def flatten_protected_dates(
    protected_date_map: Dict[str, List[pd.Timestamp]],
) -> List[pd.Timestamp]:
    protected_dates = []

    for dates in protected_date_map.values():
        protected_dates.extend(dates)

    unique_dates = sorted(set(protected_dates))

    return unique_dates


# =========================================================
# 6. 단변량 시계열 DataFrame 생성
# =========================================================

def build_time_series_dataframe(
    data: List[Dict[str, Any]],
    protected_cells: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    if protected_cells is None:
        protected_cells = []

    raw_df = pd.DataFrame(data)
    raw_df = clean_empty_rows(raw_df)

    if raw_df.empty:
        raise ValueError("분석 가능한 데이터가 없습니다.")

    date_column = detect_date_column(raw_df)
    value_column = detect_value_column(raw_df, date_column)

    protected_dates = build_protected_dates(
        raw_df=raw_df,
        date_column=date_column,
        value_column=value_column,
        protected_cells=protected_cells,
    )

    df = raw_df[[date_column, value_column]].copy()
    df.columns = ["date", "value"]

    df["date"] = safe_to_datetime(df["date"])
    df["value"] = safe_to_numeric(df["value"])

    df = df.dropna(subset=["date"])
    df = df.sort_values("date")
    df = df.drop_duplicates(subset=["date"], keep="last")
    df = df.reset_index(drop=True)

    if df.empty:
        raise ValueError("유효한 날짜 데이터가 없습니다.")

    metadata = {
        "date_column": str(date_column),
        "value_column": str(value_column),
        "protected_dates": [
            date.strftime("%Y-%m-%d")
            for date in protected_dates
        ],
        "original_count": len(raw_df),
        "valid_count": len(df),
    }

    return df, metadata


# =========================================================
# 7. 다변량 시계열 DataFrame 생성
# =========================================================

def build_multivariate_time_series_dataframe(
    data: List[Dict[str, Any]],
    protected_cells: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    if protected_cells is None:
        protected_cells = []

    raw_df = pd.DataFrame(data)
    raw_df = clean_empty_rows(raw_df)

    if raw_df.empty:
        raise ValueError("분석 가능한 데이터가 없습니다.")

    date_column = detect_date_column(raw_df)
    value_columns = detect_numeric_columns(raw_df, date_column)

    protected_date_map = build_protected_date_map(
        raw_df=raw_df,
        date_column=date_column,
        value_columns=value_columns,
        protected_cells=protected_cells,
    )

    selected_columns = [date_column] + value_columns
    df = raw_df[selected_columns].copy()

    df = df.rename(columns={date_column: "date"})

    df["date"] = safe_to_datetime(df["date"])

    for column in value_columns:
        df[column] = safe_to_numeric(df[column])

    df = df.dropna(subset=["date"])
    df = df.sort_values("date")
    df = df.drop_duplicates(subset=["date"], keep="last")
    df = df.reset_index(drop=True)

    if df.empty:
        raise ValueError("유효한 날짜 데이터가 없습니다.")

    protected_dates = flatten_protected_dates(protected_date_map)

    metadata = {
        "date_column": str(date_column),
        "value_columns": [str(column) for column in value_columns],
        "protected_date_map": {
            str(column): [
                date.strftime("%Y-%m-%d")
                for date in dates
            ]
            for column, dates in protected_date_map.items()
        },
        "protected_dates": [
            date.strftime("%Y-%m-%d")
            for date in protected_dates
        ],
        "original_count": len(raw_df),
        "valid_count": len(df),
    }

    return df, metadata


# =========================================================
# 8. 주기 자동 추정
# =========================================================

def infer_frequency(df: pd.DataFrame) -> Optional[str]:
    if df is None or df.empty:
        return None

    if "date" not in df.columns:
        return None

    if len(df) < 3:
        return None

    dates = pd.to_datetime(df["date"], errors="coerce")
    dates = dates.dropna().sort_values()

    if len(dates) < 3:
        return None

    try:
        frequency = pd.infer_freq(dates)

        if frequency:
            return frequency
    except Exception:
        pass

    date_diff = dates.diff().dropna()

    if date_diff.empty:
        return None

    median_diff = date_diff.median()

    seconds = median_diff.total_seconds()

    if seconds <= 0:
        return None

    day_seconds = 24 * 60 * 60
    hour_seconds = 60 * 60
    minute_seconds = 60

    if abs(seconds - minute_seconds) <= 5:
        return "min"

    if abs(seconds - hour_seconds) <= 60:
        return "H"

    if abs(seconds - day_seconds) <= hour_seconds:
        return "D"

    if abs(seconds - 7 * day_seconds) <= day_seconds:
        return "W"

    if 27 * day_seconds <= seconds <= 32 * day_seconds:
        return "MS"

    if 80 * day_seconds <= seconds <= 100 * day_seconds:
        return "QS"

    if 350 * day_seconds <= seconds <= 380 * day_seconds:
        return "YS"

    return None


def should_regularize_frequency(frequency: Optional[str]) -> bool:
    if not frequency:
        return False

    freq = str(frequency).upper()

    allowed_prefixes = [
        "T",
        "MIN",
        "H",
        "D",
        "W",
        "M",
        "MS",
        "Q",
        "QS",
        "Y",
        "YS",
        "A",
        "AS",
    ]

    return any(freq.startswith(prefix) for prefix in allowed_prefixes)


# =========================================================
# 9. 날짜 인덱스 정규화
# ---------------------------------------------------------
# 날짜가 일부 누락된 경우, 추정된 frequency에 맞춰 날짜를 채우고
# 이후 결측치로 처리
# =========================================================

def regularize_time_index(
    df: pd.DataFrame,
    frequency: Optional[str],
) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    if "date" not in df.columns:
        return df

    if not should_regularize_frequency(frequency):
        return df.reset_index(drop=True)

    try:
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df = df.sort_values("date")
        df = df.drop_duplicates(subset=["date"], keep="last")

        full_index = pd.date_range(
            start=df["date"].min(),
            end=df["date"].max(),
            freq=frequency,
        )

        if len(full_index) < len(df):
            return df.reset_index(drop=True)

        regularized = (
            df.set_index("date")
            .reindex(full_index)
            .rename_axis("date")
            .reset_index()
        )

        return regularized.reset_index(drop=True)
    except Exception:
        return df.reset_index(drop=True)


# =========================================================
# 10. 결측치 처리
# =========================================================

def fill_missing_series(series: pd.Series) -> pd.Series:
    filled = pd.to_numeric(series, errors="coerce")

    filled = filled.interpolate(
        method="linear",
        limit_direction="both",
    )

    filled = filled.ffill().bfill()

    if filled.isna().any():
        median_value = filled.median()

        if pd.isna(median_value):
            median_value = 0

        filled = filled.fillna(median_value)

    return filled


def fill_missing_multivariate(
    df: pd.DataFrame,
    value_columns: List[str],
) -> pd.DataFrame:
    filled_df = df.copy()

    for column in value_columns:
        filled_df[column] = fill_missing_series(filled_df[column])

    return filled_df


# =========================================================
# 11. 단변량 이상치 탐지
# ---------------------------------------------------------
# forecast 전처리에서만 사용
# 이상탐지 모드에서는 anomaly.py에서 별도로 탐지
# =========================================================

def detect_outlier_mask(
    series: pd.Series,
    protected_dates: Optional[List[str]] = None,
    dates: Optional[pd.Series] = None,
) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")

    if len(values) < 5:
        return pd.Series(False, index=series.index)

    median = values.median()
    mad = np.median(np.abs(values - median))

    if mad == 0 or pd.isna(mad):
        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        iqr = q3 - q1

        if iqr == 0 or pd.isna(iqr):
            return pd.Series(False, index=series.index)

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        mask = (values < lower_bound) | (values > upper_bound)
    else:
        robust_z = np.abs((values - median) / (1.4826 * mad))
        mask = robust_z > 3.5

    mask = pd.Series(mask, index=series.index).fillna(False)

    if protected_dates and dates is not None:
        protected_set = set(protected_dates)

        for index, date_value in dates.items():
            date_string = normalize_date_string(date_value)

            if date_string in protected_set:
                mask.loc[index] = False

    return mask


def replace_outliers_with_interpolation(
    series: pd.Series,
    outlier_mask: pd.Series,
) -> pd.Series:
    cleaned = pd.to_numeric(series, errors="coerce").copy()
    cleaned.loc[outlier_mask] = np.nan

    cleaned = cleaned.interpolate(
        method="linear",
        limit_direction="both",
    )

    cleaned = cleaned.ffill().bfill()

    if cleaned.isna().any():
        median_value = cleaned.median()

        if pd.isna(median_value):
            median_value = 0

        cleaned = cleaned.fillna(median_value)

    return cleaned


# =========================================================
# 12. 포인트 직렬화용 DataFrame 생성
# =========================================================

def build_point_dataframe(
    df: pd.DataFrame,
    mask: pd.Series,
    value_column: str = "value_filled",
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", value_column])

    if mask is None or len(mask) != len(df):
        return pd.DataFrame(columns=["date", value_column])

    points = df.loc[mask, ["date", value_column]].copy()

    return points.reset_index(drop=True)


def build_protected_point_dataframe(
    df: pd.DataFrame,
    protected_dates: List[str],
    value_column: str = "value_filled",
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", value_column])

    if not protected_dates:
        return pd.DataFrame(columns=["date", value_column])

    protected_set = set(protected_dates)

    mask = df["date"].apply(
        lambda value: normalize_date_string(value) in protected_set
    )

    points = df.loc[mask, ["date", value_column]].copy()

    return points.reset_index(drop=True)


# =========================================================
# 13. 단변량 시계열 전처리
# ---------------------------------------------------------
# 기존 forecasting/decomposition/metrics 흐름과 호환
# analysis.py의 기존 run_time_series_analysis에서 사용
# =========================================================

def preprocess_time_series(
    data: List[Dict[str, Any]],
    protected_cells: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if protected_cells is None:
        protected_cells = []

    df, metadata = build_time_series_dataframe(
        data=data,
        protected_cells=protected_cells,
    )

    frequency = infer_frequency(df)

    df = regularize_time_index(
        df=df,
        frequency=frequency,
    )

    protected_dates = metadata.get("protected_dates", [])

    df["value_original"] = pd.to_numeric(
        df["value"],
        errors="coerce",
    )

    missing_mask = df["value_original"].isna()

    df["value_filled"] = fill_missing_series(df["value_original"])

    outlier_mask = detect_outlier_mask(
        series=df["value_filled"],
        protected_dates=protected_dates,
        dates=df["date"],
    )

    df["value_preprocessed"] = replace_outliers_with_interpolation(
        series=df["value_filled"],
        outlier_mask=outlier_mask,
    )

    missing_points = build_point_dataframe(
        df=df,
        mask=missing_mask,
        value_column="value_filled",
    )

    outlier_points = build_point_dataframe(
        df=df,
        mask=outlier_mask,
        value_column="value_filled",
    )

    protected_points = build_protected_point_dataframe(
        df=df,
        protected_dates=protected_dates,
        value_column="value_filled",
    )

    summary = {
        "date_column": metadata.get("date_column"),
        "value_column": metadata.get("value_column"),

        "frequency": frequency,

        "original_count": metadata.get("original_count"),
        "valid_count": metadata.get("valid_count"),
        "final_count": len(df),

        "missing_count": int(missing_mask.sum()),
        "outlier_count": int(outlier_mask.sum()),
        "protected_count": len(protected_dates),

        "protected_dates": protected_dates,
    }

    return {
        "df": df,

        "summary": summary,

        "date": serialize_series_dates(df["date"]),
        "original_value": serialize_values(df["value_original"]),
        "filled_value": serialize_values(df["value_filled"]),
        "preprocessed_value": serialize_values(df["value_preprocessed"]),

        "missing_points": missing_points,
        "outlier_points": outlier_points,
        "protected_points": protected_points,
    }


# =========================================================
# 14. 다변량 시계열 전처리
# ---------------------------------------------------------
# 신규 anomaly.py / analysis.py 이상탐지 흐름에서 사용
# =========================================================

def preprocess_multivariate_time_series(
    data: List[Dict[str, Any]],
    protected_cells: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if protected_cells is None:
        protected_cells = []

    df, metadata = build_multivariate_time_series_dataframe(
        data=data,
        protected_cells=protected_cells,
    )

    frequency = infer_frequency(df)

    df = regularize_time_index(
        df=df,
        frequency=frequency,
    )

    value_columns = metadata.get("value_columns", [])

    if not value_columns:
        raise ValueError("다변량 이상탐지에 사용할 숫자형 컬럼이 없습니다.")

    original_df = df.copy()

    for column in value_columns:
        original_df[column] = pd.to_numeric(
            original_df[column],
            errors="coerce",
        )

    missing_mask_df = original_df[value_columns].isna()
    missing_count = int(missing_mask_df.sum().sum())

    filled_df = fill_missing_multivariate(
        df=original_df,
        value_columns=value_columns,
    )

    protected_dates = metadata.get("protected_dates", [])

    summary = {
        "date_column": metadata.get("date_column"),
        "value_columns": value_columns,

        "frequency": frequency,

        "original_count": metadata.get("original_count"),
        "valid_count": metadata.get("valid_count"),
        "final_count": len(filled_df),

        "missing_count": missing_count,
        "outlier_count": None,
        "protected_count": len(protected_dates),

        "protected_dates": protected_dates,
        "protected_date_map": metadata.get("protected_date_map", {}),
    }

    date_values = serialize_series_dates(filled_df["date"])

    original_values = {}

    for column in value_columns:
        original_values[str(column)] = serialize_values(original_df[column])

    filled_values = {}

    for column in value_columns:
        filled_values[str(column)] = serialize_values(filled_df[column])

    return {
        "df": filled_df,

        "summary": summary,

        "date": date_values,
        "value_columns": value_columns,

        "original_values": original_values,
        "filled_values": filled_values,

        "missing_count": missing_count,
        "protected_dates": protected_dates,
        "protected_date_map": metadata.get("protected_date_map", {}),
    }