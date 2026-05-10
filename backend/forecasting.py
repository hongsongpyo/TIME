# =========================================================
# TIME - backend/forecasting.py
# ---------------------------------------------------------
# 역할
# 1. 전처리된 시계열 데이터를 학습/검증 데이터로 분리
# 2. AutoARIMA, Holt-Winters, Exponential Smoothing, Naive 예측
# 3. 검증 구간 예측값과 미래 예측값 생성
# 4. AIC, BIC 값 반환
# =========================================================

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from statsmodels.tsa.holtwinters import ExponentialSmoothing, SimpleExpSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX


# =========================================================
# 1. pmdarima 선택 import
# ---------------------------------------------------------
# 설치 문제 발생 시에도 다른 모델은 실행 가능하도록 처리
# =========================================================

try:
    from pmdarima import auto_arima
except Exception:
    auto_arima = None

try:
    from sktime.forecasting.arima import AutoARIMA
except Exception:
    AutoARIMA = None


# =========================================================
# 2. 기본 유틸
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


def serialize_array(values: Any) -> List[Optional[float]]:
    result = []

    for value in list(values):
        result.append(safe_float(value))

    return result


def infer_seasonal_period(frequency: Optional[str], data_length: int) -> int:
    if data_length < 4:
        return 1

    if not frequency:
        return max(1, min(7, data_length // 3))

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
        period = 1

    if period < 2:
        return 1

    if data_length < period * 2:
        return 1

    return period


def get_future_dates(
    last_date: pd.Timestamp,
    horizon: int,
    frequency: Optional[str],
) -> List[str]:
    if frequency:
        try:
            dates = pd.date_range(
                start=last_date,
                periods=horizon + 1,
                freq=frequency,
            )[1:]

            return [date.strftime("%Y-%m-%d") for date in dates]
        except Exception:
            pass

    dates = pd.date_range(
        start=last_date + pd.Timedelta(days=1),
        periods=horizon,
        freq="D",
    )

    return [date.strftime("%Y-%m-%d") for date in dates]


# =========================================================
# 3. Train / Test 분리
# ---------------------------------------------------------
# 검증 길이는 데이터 길이의 20%, 최소 3개, 최대 horizon
# 데이터가 짧으면 최소한 작동하도록 보정
# =========================================================

def split_train_test(
    series: pd.Series,
    horizon: int,
) -> Tuple[pd.Series, pd.Series]:
    data_length = len(series)

    if data_length < 6:
        test_size = max(1, data_length // 3)
    else:
        test_size = max(3, int(data_length * 0.2))

    test_size = min(test_size, horizon, data_length - 2)

    if test_size < 1:
        test_size = 1

    train = series.iloc[:-test_size]
    test = series.iloc[-test_size:]

    return train, test


# =========================================================
# 4. Naive Forecast
# =========================================================

def forecast_naive(
    train: pd.Series,
    test: pd.Series,
    horizon: int,
) -> Dict[str, Any]:
    last_value = train.iloc[-1]

    validation_pred = np.repeat(last_value, len(test))
    future_pred = np.repeat(test.iloc[-1] if len(test) > 0 else last_value, horizon)

    return {
        "model": "Naive",
        "validation_pred": serialize_array(validation_pred),
        "future_pred": serialize_array(future_pred),
        "aic": None,
        "bic": None,
        "success": True,
        "message": "Naive forecast completed.",
    }


# =========================================================
# 5. Exponential Smoothing
# ---------------------------------------------------------
# SimpleExpSmoothing 기준
# =========================================================

def forecast_exponential_smoothing(
    train: pd.Series,
    test: pd.Series,
    full_series: pd.Series,
    horizon: int,
) -> Dict[str, Any]:
    try:
        validation_model = SimpleExpSmoothing(
            train,
            initialization_method="estimated",
        ).fit(optimized=True)

        validation_pred = validation_model.forecast(len(test))

        final_model = SimpleExpSmoothing(
            full_series,
            initialization_method="estimated",
        ).fit(optimized=True)

        future_pred = final_model.forecast(horizon)

        return {
            "model": "Exponential Smoothing",
            "validation_pred": serialize_array(validation_pred),
            "future_pred": serialize_array(future_pred),
            "aic": safe_float(getattr(final_model, "aic", None)),
            "bic": safe_float(getattr(final_model, "bic", None)),
            "success": True,
            "message": "Exponential smoothing completed.",
        }
    except Exception as error:
        return build_failed_result("Exponential Smoothing", len(test), horizon, error)


# =========================================================
# 6. Holt-Winters Forecast
# ---------------------------------------------------------
# 계절 주기가 충분하면 seasonal 포함
# 부족하면 trend만 사용
# =========================================================

def forecast_holt_winters(
    train: pd.Series,
    test: pd.Series,
    full_series: pd.Series,
    horizon: int,
    seasonal_period: int,
) -> Dict[str, Any]:
    try:
        use_seasonal = seasonal_period >= 2 and len(train) >= seasonal_period * 2

        validation_model = ExponentialSmoothing(
            train,
            trend="add",
            seasonal="add" if use_seasonal else None,
            seasonal_periods=seasonal_period if use_seasonal else None,
            initialization_method="estimated",
        ).fit(optimized=True)

        validation_pred = validation_model.forecast(len(test))

        final_model = ExponentialSmoothing(
            full_series,
            trend="add",
            seasonal="add" if use_seasonal and len(full_series) >= seasonal_period * 2 else None,
            seasonal_periods=seasonal_period if use_seasonal and len(full_series) >= seasonal_period * 2 else None,
            initialization_method="estimated",
        ).fit(optimized=True)

        future_pred = final_model.forecast(horizon)

        return {
            "model": "Holt-Winters",
            "validation_pred": serialize_array(validation_pred),
            "future_pred": serialize_array(future_pred),
            "aic": safe_float(getattr(final_model, "aic", None)),
            "bic": safe_float(getattr(final_model, "bic", None)),
            "success": True,
            "message": "Holt-Winters forecast completed.",
        }
    except Exception as error:
        return build_failed_result("Holt-Winters", len(test), horizon, error)


# =========================================================
# 7. AutoARIMA Forecast
# ---------------------------------------------------------
# pmdarima 사용 가능하면 auto_arima
# 불가능하면 SARIMAX(1,1,1) fallback
# =========================================================

def forecast_auto_arima(
    train: pd.Series,
    test: pd.Series,
    full_series: pd.Series,
    horizon: int,
    seasonal_period: int,
) -> Dict[str, Any]:
    try:
        if AutoARIMA is not None:
            use_seasonal = seasonal_period >= 2 and len(train) >= seasonal_period * 2
            sp = seasonal_period if use_seasonal else 1

            validation_model = AutoARIMA(
                max_p=3,
                max_q=3,
                max_d=2,
                max_P=1,
                max_Q=1,
                max_D=1,
                max_order=5,
                sp=sp,
                seasonal=use_seasonal,
                suppress_warnings=True,
            )

            validation_model.fit(train)

            validation_fh = list(range(1, len(test) + 1))
            validation_pred = validation_model.predict(fh=validation_fh)

            final_model = AutoARIMA(
                max_p=3,
                max_q=3,
                max_d=2,
                max_P=1,
                max_Q=1,
                max_D=1,
                max_order=5,
                sp=sp,
                seasonal=use_seasonal,
                suppress_warnings=True,
            )

            final_model.fit(full_series)

            future_fh = list(range(1, horizon + 1))
            future_pred = final_model.predict(fh=future_fh)

            fitted_params = final_model.get_fitted_params()
            order = fitted_params.get("order", None)
            seasonal_order = fitted_params.get("seasonal_order", None)

            aic = fitted_params.get("aic", None)
            bic = fitted_params.get("bic", None)

            return {
                "model": "AutoARIMA",
                "validation_pred": serialize_array(validation_pred),
                "future_pred": serialize_array(future_pred),
                "aic": safe_float(aic),
                "bic": safe_float(bic),
                "success": True,
                "message": f"AutoARIMA completed. order={order}, seasonal_order={seasonal_order}",
            }

        validation_model = SARIMAX(
            train,
            order=(1, 1, 1),
            enforce_stationarity=False,
            enforce_invertibility=False,
        ).fit(disp=False)

        validation_pred = validation_model.forecast(len(test))

        final_model = SARIMAX(
            full_series,
            order=(1, 1, 1),
            enforce_stationarity=False,
            enforce_invertibility=False,
        ).fit(disp=False)

        future_pred = final_model.forecast(horizon)

        return {
            "model": "AutoARIMA",
            "validation_pred": serialize_array(validation_pred),
            "future_pred": serialize_array(future_pred),
            "aic": safe_float(getattr(final_model, "aic", None)),
            "bic": safe_float(getattr(final_model, "bic", None)),
            "success": True,
            "message": "AutoARIMA fallback SARIMAX completed.",
        }

    except Exception as error:
        return build_failed_result("AutoARIMA", len(test), horizon, error)

# =========================================================
# 8. 실패 결과 생성
# =========================================================

def build_failed_result(
    model_name: str,
    validation_length: int,
    horizon: int,
    error: Exception,
) -> Dict[str, Any]:
    return {
        "model": model_name,
        "validation_pred": [None for _ in range(validation_length)],
        "future_pred": [None for _ in range(horizon)],
        "aic": None,
        "bic": None,
        "success": False,
        "message": str(error),
    }


# =========================================================
# 9. 전체 예측 실행
# =========================================================

def run_all_forecasts(
    df: pd.DataFrame,
    horizon: int,
    frequency: Optional[str] = None,
    value_column: str = "value_preprocessed",
) -> Dict[str, Any]:
    if value_column not in df.columns:
        raise ValueError(f"{value_column} 컬럼을 찾을 수 없습니다.")

    series = pd.Series(df[value_column].values, index=df["date"])
    series = pd.to_numeric(series, errors="coerce")
    series = series.interpolate(method="linear").ffill().bfill()

    if len(series) < 4:
        raise ValueError("예측을 수행하기에는 데이터가 너무 적습니다. 최소 4개 이상의 데이터가 필요합니다.")

    horizon = int(horizon)

    train, test = split_train_test(series, horizon)

    seasonal_period = infer_seasonal_period(frequency, len(series))

    last_date = pd.Timestamp(df["date"].iloc[-1])
    future_dates = get_future_dates(last_date, horizon, frequency)

    validation_dates = [date.strftime("%Y-%m-%d") for date in test.index]

    model_results = {}

    model_results["AutoARIMA"] = forecast_auto_arima(
        train=train,
        test=test,
        full_series=series,
        horizon=horizon,
        seasonal_period=seasonal_period,
    )

    model_results["Holt-Winters"] = forecast_holt_winters(
        train=train,
        test=test,
        full_series=series,
        horizon=horizon,
        seasonal_period=seasonal_period,
    )

    model_results["Exponential Smoothing"] = forecast_exponential_smoothing(
        train=train,
        test=test,
        full_series=series,
        horizon=horizon,
    )

    model_results["Naive"] = forecast_naive(
        train=train,
        test=test,
        horizon=horizon,
    )

    return {
        "train_values": serialize_array(train.values),
        "test_values": serialize_array(test.values),
        "train_dates": [date.strftime("%Y-%m-%d") for date in train.index],
        "test_dates": validation_dates,
        "future_dates": future_dates,
        "seasonal_period": seasonal_period,
        "model_results": model_results,
    }