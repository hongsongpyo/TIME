# =========================================================
# TIME - backend/forecasting.py
# =========================================================

from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from statsmodels.tsa.holtwinters import ExponentialSmoothing, SimpleExpSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

try:
    from sktime.forecasting.arima import AutoARIMA
except Exception:
    AutoARIMA = None


SEASONAL_PERIOD = 12
TEST_RATIO = 0.2


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
    return [safe_float(value) for value in list(values)]


def split_train_test(series: pd.Series) -> Tuple[pd.Series, pd.Series]:
    data_length = len(series)

    if data_length < 5:
        raise ValueError("예측을 수행하기에는 데이터가 너무 적습니다. 최소 5개 이상의 데이터가 필요합니다.")

    test_size = max(1, int(data_length * TEST_RATIO))

    if data_length - test_size < 2:
        test_size = data_length - 2

    train = series.iloc[:-test_size]
    test = series.iloc[-test_size:]

    return train, test


def resolve_horizon(
    horizon: Union[int, str],
    test: pd.Series,
) -> int:
    if horizon == "auto":
        return len(test)

    horizon_value = int(horizon)

    if horizon_value <= 0:
        raise ValueError("시평 horizon은 1 이상이어야 합니다.")

    return horizon_value


def build_failed_result(
    model_name: str,
    validation_length: int,
    error: Exception,
) -> Dict[str, Any]:
    return {
        "model": model_name,
        "validation_pred": [None for _ in range(validation_length)],
        "future_pred": [],
        "aic": None,
        "bic": None,
        "success": False,
        "message": str(error),
    }


def forecast_naive(
    train: pd.Series,
    test: pd.Series,
    horizon: int,
) -> Dict[str, Any]:
    last_value = train.iloc[-1]
    validation_pred = np.repeat(last_value, len(test))
    future_pred = np.repeat(last_value, horizon)

    return {
        "model": "Naive",
        "validation_pred": serialize_array(validation_pred),
        "future_pred": serialize_array(future_pred),
        "aic": None,
        "bic": None,
        "success": True,
        "message": "Naive validation and future forecast completed.",
    }


def forecast_exponential_smoothing(
    train: pd.Series,
    test: pd.Series,
    horizon: int,
) -> Dict[str, Any]:
    try:
        model = SimpleExpSmoothing(
            train,
            initialization_method="estimated",
        ).fit(optimized=True)

        validation_pred = model.forecast(len(test))
        future_pred = model.forecast(horizon)

        return {
            "model": "Exponential Smoothing",
            "validation_pred": serialize_array(validation_pred),
            "future_pred": serialize_array(future_pred),
            "aic": safe_float(getattr(model, "aic", None)),
            "bic": safe_float(getattr(model, "bic", None)),
            "success": True,
            "message": "Exponential smoothing validation and future forecast completed.",
        }

    except Exception as error:
        return build_failed_result("Exponential Smoothing", len(test), error)


def forecast_holt_winters(
    train: pd.Series,
    test: pd.Series,
    horizon: int,
) -> Dict[str, Any]:
    try:
        use_seasonal = len(train) >= SEASONAL_PERIOD * 2

        model = ExponentialSmoothing(
            train,
            trend="add",
            seasonal="add" if use_seasonal else None,
            seasonal_periods=SEASONAL_PERIOD if use_seasonal else None,
            initialization_method="estimated",
        ).fit(optimized=True)

        validation_pred = model.forecast(len(test))
        future_pred = model.forecast(horizon)

        return {
            "model": "Holt-Winters",
            "validation_pred": serialize_array(validation_pred),
            "future_pred": serialize_array(future_pred),
            "aic": safe_float(getattr(model, "aic", None)),
            "bic": safe_float(getattr(model, "bic", None)),
            "success": True,
            "message": "Holt-Winters validation and future forecast completed.",
        }

    except Exception as error:
        return build_failed_result("Holt-Winters", len(test), error)


def forecast_arima_fallback(
    train: pd.Series,
    test: pd.Series,
    horizon: int,
) -> Dict[str, Any]:
    try:
        model = SARIMAX(
            train,
            order=(1, 1, 1),
            enforce_stationarity=False,
            enforce_invertibility=False,
        ).fit(disp=False, maxiter=50)

        validation_pred = model.forecast(len(test))
        future_pred = model.forecast(horizon)

        return {
            "model": "AutoARIMA",
            "validation_pred": serialize_array(validation_pred),
            "future_pred": serialize_array(future_pred),
            "aic": safe_float(getattr(model, "aic", None)),
            "bic": safe_float(getattr(model, "bic", None)),
            "success": True,
            "message": "Fallback ARIMA(1,1,1) completed.",
        }

    except Exception as error:
        print("ARIMA FALLBACK ERROR:", error)
        return forecast_naive(train, test, horizon)


def forecast_auto_arima(
    train: pd.Series,
    test: pd.Series,
    horizon: int,
) -> Dict[str, Any]:
    try:
        if AutoARIMA is not None:
            model = AutoARIMA(
                max_p=2,
                max_q=2,
                sp=SEASONAL_PERIOD,
                suppress_warnings=True,
                stepwise=True,
                error_action="ignore",
                trace=False,
                n_jobs=1,
            )

            model.fit(train)

            validation_fh = list(range(1, len(test) + 1))
            future_fh = list(range(1, horizon + 1))

            validation_pred = model.predict(fh=validation_fh)
            future_pred = model.predict(fh=future_fh)

            fitted_params = model.get_fitted_params()

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

        return forecast_arima_fallback(train, test, horizon)

    except Exception as error:
        print("AutoARIMA ERROR:", error)
        return forecast_arima_fallback(train, test, horizon)


def make_future_dates(
    last_date: pd.Timestamp,
    horizon: int,
    frequency: Optional[str],
) -> List[str]:
    if frequency:
        freq = frequency
    else:
        freq = "MS"

    try:
        future_dates = pd.date_range(
            start=last_date,
            periods=horizon + 1,
            freq=freq,
        )[1:]
    except Exception:
        future_dates = pd.date_range(
            start=last_date,
            periods=horizon + 1,
            freq="MS",
        )[1:]

    return [date.strftime("%Y-%m-%d") for date in future_dates]


def run_all_forecasts(
    df: pd.DataFrame,
    horizon: Union[int, str],
    frequency: Optional[str] = None,
    value_column: str = "value_preprocessed",
) -> Dict[str, Any]:
    if value_column not in df.columns:
        raise ValueError(f"{value_column} 컬럼을 찾을 수 없습니다.")

    series = pd.Series(df[value_column].values, index=df["date"])
    series = pd.to_numeric(series, errors="coerce")
    series = series.interpolate(method="linear").ffill().bfill()

    if len(series) < 5:
        raise ValueError("예측을 수행하기에는 데이터가 너무 적습니다. 최소 5개 이상의 데이터가 필요합니다.")

    train, test = split_train_test(series)

    horizon_value = resolve_horizon(
        horizon=horizon,
        test=test,
    )

    validation_dates = [date.strftime("%Y-%m-%d") for date in test.index]
    future_dates = make_future_dates(
        last_date=series.index[-1],
        horizon=horizon_value,
        frequency=frequency,
    )

    model_results = {}

    model_results["AutoARIMA"] = forecast_auto_arima(
        train=train,
        test=test,
        horizon=horizon_value,
    )

    model_results["Holt-Winters"] = forecast_holt_winters(
        train=train,
        test=test,
        horizon=horizon_value,
    )

    model_results["Exponential Smoothing"] = forecast_exponential_smoothing(
        train=train,
        test=test,
        horizon=horizon_value,
    )

    model_results["Naive"] = forecast_naive(
        train=train,
        test=test,
        horizon=horizon_value,
    )

    return {
        "train_values": serialize_array(train.values),
        "test_values": serialize_array(test.values),
        "train_dates": [date.strftime("%Y-%m-%d") for date in train.index],
        "test_dates": validation_dates,
        "future_dates": future_dates,
        "seasonal_period": SEASONAL_PERIOD,
        "horizon": horizon_value,
        "model_results": model_results,
    }