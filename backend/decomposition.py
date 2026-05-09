# =========================================================
# TIME - backend/decomposition.py
# ---------------------------------------------------------
# 역할
# 1. 전처리된 시계열 데이터를 추세, 주기/계절성, 노이즈로 분해
# 2. Plotly 그래프에 사용할 수 있는 리스트 형태로 반환
# 3. 데이터가 짧거나 주기 추정이 어려운 경우에도 안전하게 처리
# =========================================================

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import seasonal_decompose, STL


# =========================================================
# 1. 값 직렬화
# =========================================================

def serialize_values(series: pd.Series) -> List[Optional[float]]:
    values = []

    for value in series:
        if pd.isna(value) or np.isinf(value):
            values.append(None)
        else:
            values.append(float(value))

    return values


# =========================================================
# 2. 주기 추정
# ---------------------------------------------------------
# frequency 값과 데이터 길이를 기준으로 대략적인 period 결정
# =========================================================

def infer_period(frequency: Optional[str], data_length: int) -> int:
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
    elif freq.startswith("Y") or freq.startswith("A"):
        period = 2
    else:
        period = min(7, max(2, data_length // 3))

    if data_length < period * 2:
        period = max(2, data_length // 2)

    return max(2, int(period))


# =========================================================
# 3. 이동평균 기반 fallback 분해
# ---------------------------------------------------------
# seasonal_decompose나 STL이 실패할 경우 사용
# =========================================================

def moving_average_decomposition(
    series: pd.Series,
    period: int,
) -> Dict[str, pd.Series]:
    trend = series.rolling(
        window=period,
        min_periods=1,
        center=True,
    ).mean()

    detrended = series - trend

    seasonal_pattern = detrended.groupby(np.arange(len(detrended)) % period).transform(
        "mean"
    )

    seasonal = pd.Series(
        seasonal_pattern.values,
        index=series.index,
    )

    residual = series - trend - seasonal

    return {
        "trend": trend,
        "seasonal": seasonal,
        "residual": residual,
    }


# =========================================================
# 4. STL 분해
# =========================================================

def stl_decomposition(
    series: pd.Series,
    period: int,
) -> Dict[str, pd.Series]:
    stl = STL(
        series,
        period=period,
        robust=True,
    )

    result = stl.fit()

    return {
        "trend": pd.Series(result.trend, index=series.index),
        "seasonal": pd.Series(result.seasonal, index=series.index),
        "residual": pd.Series(result.resid, index=series.index),
    }


# =========================================================
# 5. seasonal_decompose 분해
# =========================================================

def classical_decomposition(
    series: pd.Series,
    period: int,
) -> Dict[str, pd.Series]:
    result = seasonal_decompose(
        series,
        model="additive",
        period=period,
        extrapolate_trend="freq",
    )

    return {
        "trend": pd.Series(result.trend, index=series.index),
        "seasonal": pd.Series(result.seasonal, index=series.index),
        "residual": pd.Series(result.resid, index=series.index),
    }


# =========================================================
# 6. 전체 분해 실행
# =========================================================

def decompose_time_series(
    df: pd.DataFrame,
    frequency: Optional[str] = None,
    value_column: str = "value_preprocessed",
) -> Dict[str, Any]:
    if value_column not in df.columns:
        raise ValueError(f"{value_column} 컬럼을 찾을 수 없습니다.")

    series = pd.Series(df[value_column].values, index=df["date"])
    series = pd.to_numeric(series, errors="coerce")
    series = series.interpolate(method="linear").ffill().bfill()

    data_length = len(series)

    if data_length < 4:
        empty_values = [None for _ in range(data_length)]

        return {
            "period": None,
            "method": "none",
            "trend": empty_values,
            "seasonal": empty_values,
            "residual": empty_values,
        }

    period = infer_period(frequency, data_length)

    try:
        components = stl_decomposition(series, period)
        method = "STL"
    except Exception:
        try:
            components = classical_decomposition(series, period)
            method = "Classical"
        except Exception:
            components = moving_average_decomposition(series, period)
            method = "MovingAverage"

    return {
        "period": period,
        "method": method,
        "trend": serialize_values(components["trend"]),
        "seasonal": serialize_values(components["seasonal"]),
        "residual": serialize_values(components["residual"]),
    }