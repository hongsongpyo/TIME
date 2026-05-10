# =========================================================
# TIME - backend/forecasting.py
# =========================================================

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from statsmodels.tsa.holtwinters import ExponentialSmoothing, SimpleExpSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

try:
    from sktime.forecasting.arima import AutoARIMA
except Exception:
    AutoARIMA = None


SEASONAL_PERIOD = 12


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


def split_train_test(
    series: pd.Series,
    horizon: int,
) -> Tuple[pd.Series, pd.Series]:
    data_length = len(series)
    horizon = int(horizon)

    if horizon <= 0:
        raise ValueError("시평 horizon은 1 이상이어야 합니다.")

    if data_length < 4:
        raise ValueError("예측을 수행하기에는 데이터가 너무 적습니다.")

    test_size = min(horizon, data_length - 2)

    train = series.iloc[:-test_size]
    test = series.iloc[-test_size:]

    return train, test


def build_failed_result(
    model_name: str,
    validation_length: int,
    error: Exception,
) -> Dict[str, Any]:
    return {
        "model": model_name,
        "validation_pred": [None for _ in range(validation_length)],
        "aic": None,
        "bic": None,
        "success": False,
        "message": str(error),
    }


def forecast_naive(
    train: pd.Series,
    test: pd.Series,
) -> Dict[str, Any]:
    last_value = train.iloc[-1]
    validation_pred = np.repeat(last_value, len(test))

    return {
        "model": "Naive",
        "validation_pred": serialize_array(validation_pred),
        "aic": None,
        "bic": None,
        "success": True,
        "message": "Naive validation forecast completed.",
    }


def forecast_exponential_smoothing(
    train: pd.Series,
    test: pd.Series,
) -> Dict[str, Any]:
    try:
        model = SimpleExpSmoothing(
            train,
            initialization_method="estimated",
        ).fit(optimized=True)

        validation_pred = model.forecast(len(test))

        return {
            "model": "Exponential Smoothing",
            "validation_pred": serialize_array(validation_pred),
            "aic": safe_float(getattr(model, "aic", None)),
            "bic": safe_float(getattr(model, "bic", None)),
            "success": True,
            "message": "Exponential smoothing validation forecast completed.",
        }

    except Exception as error:
        return build_failed_result("Exponential Smoothing", len(test), error)


def forecast_holt_winters(
    train: pd.Series,
    test: pd.Series,
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

        return {
            "model": "Holt-Winters",
            "validation_pred": serialize_array(validation_pred),
            "aic": safe_float(getattr(model, "aic", None)),
            "bic": safe_float(getattr(model, "bic", None)),
            "success": True,
            "message": "Holt-Winters validation forecast completed.",
        }

    except Exception as error:
        return build_failed_result("Holt-Winters", len(test), error)


def forecast_arima_fallback(
    train: pd.Series,
    test: pd.Series,
) -> Dict[str, Any]:
    try:
        model = SARIMAX(
            train,
            order=(1, 1, 1),
            enforce_stationarity=False,
            enforce_invertibility=False,
        ).fit(disp=False, maxiter=50)

        validation_pred = model.forecast(len(test))

        return {
            "model": "AutoARIMA",
            "validation_pred": serialize_array(validation_pred),
            "aic": safe_float(getattr(model, "aic", None)),
            "bic": safe_float(getattr(model, "bic", None)),
            "success": True,
            "message": "Fallback ARIMA(1,1,1) completed.",
        }

    except Exception as error:
        print("ARIMA FALLBACK ERROR:", error)
        return forecast_naive(train, test)


def forecast_auto_arima(
    train: pd.Series,
    test: pd.Series,
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
            validation_pred = model.predict(fh=validation_fh)

            fitted_params = model.get_fitted_params()

            order = fitted_params.get("order", None)
            seasonal_order = fitted_params.get("seasonal_order", None)
            aic = fitted_params.get("aic", None)
            bic = fitted_params.get("bic", None)

            return {
                "model": "AutoARIMA",
                "validation_pred": serialize_array(validation_pred),
                "aic": safe_float(aic),
                "bic": safe_float(bic),
                "success": True,
                "message": f"AutoARIMA completed. order={order}, seasonal_order={seasonal_order}",
            }

        return forecast_arima_fallback(train, test)

    except Exception as error:
        print("AutoARIMA ERROR:", error)
        return forecast_arima_fallback(train, test)


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

    validation_dates = [date.strftime("%Y-%m-%d") for date in test.index]

    model_results = {}

    model_results["AutoARIMA"] = forecast_auto_arima(
        train=train,
        test=test,
    )

    model_results["Holt-Winters"] = forecast_holt_winters(
        train=train,
        test=test,
    )

    model_results["Exponential Smoothing"] = forecast_exponential_smoothing(
        train=train,
        test=test,
    )

    model_results["Naive"] = forecast_naive(
        train=train,
        test=test,
    )

    return {
        "train_values": serialize_array(train.values),
        "test_values": serialize_array(test.values),
        "train_dates": [date.strftime("%Y-%m-%d") for date in train.index],
        "test_dates": validation_dates,
        "seasonal_period": SEASONAL_PERIOD,
        "model_results": model_results,
    }