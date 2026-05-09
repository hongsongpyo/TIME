# =========================================================
# TIME - backend/preprocessing.py
# ---------------------------------------------------------
# 역할
# 1. 편집된 표 데이터를 시계열 데이터로 변환
# 2. 날짜 컬럼 / 수요 컬럼 자동 탐색
# 3. 결측치 탐지 및 보간
# 4. 이상치 탐지 및 보정
# 5. 사용자가 지정한 특이치는 이상치 처리에서 제외
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


def serialize_series_dates(series: pd.Series) -> List[str]:
    return [pd.Timestamp(value).strftime("%Y-%m-%d") for value in series]


def serialize_values(series: pd.Series) -> List[Optional[float]]:
    values = []

    for value in series:
        if pd.isna(value):
            values.append(None)
        else:
            values.append(float(value))

    return values


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

        if score > best_score:
            best_score = score
            best_column = column

    if best_column is None or best_score <= 0:
        raise ValueError("날짜 컬럼을 자동으로 찾을 수 없습니다.")

    return best_column


# =========================================================
# 3. 수요 컬럼 자동 탐색
# ---------------------------------------------------------
# 숫자로 변환 가능한 값이 가장 많은 컬럼을 수요 컬럼으로 판단
# date/time 컬럼은 제외
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

        if any(keyword in column_name for keyword in ["value", "demand", "sales", "y"]):
            score += 5

        if score > best_score:
            best_score = score
            best_column = column

    if best_column is None or best_score <= 0:
        raise ValueError("수요 값 컬럼을 자동으로 찾을 수 없습니다.")

    return best_column


# =========================================================
# 4. 특이치 보호 날짜 생성
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


# =========================================================
# 5. 시계열 DataFrame 생성
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
            date.strftime("%Y-%m-%d") for date in protected_dates
        ],
        "original_count": len(raw_df),
        "valid_count": len(df),
    }

    return df, metadata


# =========================================================
# 6. 주기 자동 추정
# =========================================================

def infer_frequency(df: pd.DataFrame) -> Optional[str]:
    if len(df) < 3:
        return None

    try:
        frequency = pd.infer_freq(df["date"])

        if frequency:
            return frequency
    except Exception:
        pass

    date_diff = df["date"].sort_values().diff().dropna()

    if date_diff.empty:
        return None

    median_diff = date_diff.median()

    if median_diff <= pd.Timedelta(days=1):
        return "D"

    if median_diff <= pd.Timedelta(days=7):
        return "W"

    if median_diff <= pd.Timedelta(days=31):
        return "MS"

    if median_diff <= pd.Timedelta(days=92):
        return "QS"

    return "YS"


# =========================================================
# 7. 결측 timestamp 생성
# =========================================================

def make_regular_time_index(df: pd.DataFrame) -> Tuple[pd.DataFrame, Optional[str]]:
    df = df.copy()

    frequency = infer_frequency(df)

    if not frequency:
        return df, None

    full_index = pd.date_range(
        start=df["date"].min(),
        end=df["date"].max(),
        freq=frequency,
    )

    df = df.set_index("date").reindex(full_index)
    df.index.name = "date"
    df = df.reset_index()

    return df, frequency


# =========================================================
# 8. 결측치 보간
# =========================================================

def fill_missing_values(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    df = df.copy()

    original_missing_mask = df["value"].isna()
    missing_dates = df.loc[original_missing_mask, "date"].tolist()

    if df["value"].notna().sum() == 0:
        raise ValueError("수요 값이 모두 비어 있습니다.")

    df["value_filled"] = df["value"].interpolate(method="linear")
    df["value_filled"] = df["value_filled"].ffill()
    df["value_filled"] = df["value_filled"].bfill()

    info = {
        "missing_count": int(original_missing_mask.sum()),
        "missing_dates": [date.strftime("%Y-%m-%d") for date in missing_dates],
    }

    return df, info


# =========================================================
# 9. 이상치 탐지
# ---------------------------------------------------------
# IQR 기준 사용
# 특이치 보호 날짜는 이상치 탐지에서 제외
# =========================================================

def detect_outliers_iqr(
    df: pd.DataFrame,
    protected_dates: List[str],
) -> Tuple[pd.Series, Dict[str, Any]]:
    values = df["value_filled"].copy()

    q1 = values.quantile(0.25)
    q3 = values.quantile(0.75)
    iqr = q3 - q1

    if iqr == 0 or pd.isna(iqr):
        mask = pd.Series(False, index=df.index)
    else:
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        mask = (values < lower_bound) | (values > upper_bound)

    protected_set = set(protected_dates)

    protected_mask = df["date"].dt.strftime("%Y-%m-%d").isin(protected_set)

    mask = mask & (~protected_mask)

    info = {
        "outlier_count": int(mask.sum()),
        "outlier_dates": df.loc[mask, "date"].dt.strftime("%Y-%m-%d").tolist(),
        "protected_count": int(protected_mask.sum()),
        "protected_dates": df.loc[protected_mask, "date"].dt.strftime("%Y-%m-%d").tolist(),
    }

    return mask, info


# =========================================================
# 10. 이상치 보정
# ---------------------------------------------------------
# 이상치 값을 NaN 처리 후 선형 보간
# =========================================================

def correct_outliers(
    df: pd.DataFrame,
    outlier_mask: pd.Series,
) -> pd.DataFrame:
    df = df.copy()

    df["value_preprocessed"] = df["value_filled"]

    df.loc[outlier_mask, "value_preprocessed"] = np.nan

    df["value_preprocessed"] = df["value_preprocessed"].interpolate(method="linear")
    df["value_preprocessed"] = df["value_preprocessed"].ffill()
    df["value_preprocessed"] = df["value_preprocessed"].bfill()

    return df


# =========================================================
# 11. 전체 전처리 실행
# =========================================================

def preprocess_time_series(
    data: List[Dict[str, Any]],
    protected_cells: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    df, metadata = build_time_series_dataframe(
        data=data,
        protected_cells=protected_cells or [],
    )

    regular_df, frequency = make_regular_time_index(df)

    filled_df, missing_info = fill_missing_values(regular_df)

    outlier_mask, outlier_info = detect_outliers_iqr(
        df=filled_df,
        protected_dates=metadata["protected_dates"],
    )

    processed_df = correct_outliers(
        df=filled_df,
        outlier_mask=outlier_mask,
    )

    processed_df["is_missing"] = processed_df["date"].dt.strftime("%Y-%m-%d").isin(
        missing_info["missing_dates"]
    )
    processed_df["is_outlier"] = outlier_mask
    processed_df["is_protected"] = processed_df["date"].dt.strftime("%Y-%m-%d").isin(
        metadata["protected_dates"]
    )

    summary = {
        **metadata,
        "frequency": frequency,
        **missing_info,
        **outlier_info,
        "final_count": len(processed_df),
    }

    return {
        "df": processed_df,
        "summary": summary,
        "date": serialize_series_dates(processed_df["date"]),
        "original_value": serialize_values(processed_df["value"]),
        "filled_value": serialize_values(processed_df["value_filled"]),
        "preprocessed_value": serialize_values(processed_df["value_preprocessed"]),
        "missing_points": processed_df.loc[
            processed_df["is_missing"], ["date", "value_filled"]
        ],
        "outlier_points": processed_df.loc[
            processed_df["is_outlier"], ["date", "value_filled"]
        ],
        "protected_points": processed_df.loc[
            processed_df["is_protected"], ["date", "value_filled"]
        ],
    }