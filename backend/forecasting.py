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


def normalize_seasonal_period(period: Any) -> Optional[int]:
    try:
        period_value = int(period)

        if period_value < 2:
            return None

        return period_value

    except Exception:
        return None


def split_train_test(series: pd.Series) -> Tuple[pd.Series, pd.Series]:
    data_length = len(series)

    if data_length < 5:
        raise ValueError("예측을 수행하기에는 데이터가 너무 적습니다.")

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


def resolve_validation_length(
    horizon: int,
    test: pd.Series,
) -> int:
    return max(1, min(horizon, len(test)))


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
    horizon: int,
) -> Dict[str, Any]:
    validation_length = resolve_validation_length(horizon, test)

    last_value = train.iloc[-1]
    validation_pred = np.repeat(last_value, validation_length)

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
    horizon: int,
) -> Dict[str, Any]:
    validation_length = resolve_validation_length(horizon, test)

    try:
        model = SimpleExpSmoothing(
            train,
            initialization_method="estimated",
        ).fit(optimized=True)

        validation_pred = model.forecast(validation_length)

        return {
            "model": "Exponential Smoothing",
            "validation_pred": serialize_array(validation_pred),
            "aic": safe_float(getattr(model, "aic", None)),
            "bic": safe_float(getattr(model, "bic", None)),
            "success": True,
            "message": "Exponential smoothing validation forecast completed.",
        }

    except Exception as error:
        return build_failed_result(
            "Exponential Smoothing",
            validation_length,
            error,
        )


def forecast_holt_winters(
    train: pd.Series,
    test: pd.Series,
    horizon: int,
    seasonal_period: Optional[int],
) -> Dict[str, Any]:
    validation_length = resolve_validation_length(horizon, test)

    try:
        use_seasonal = (
            seasonal_period is not None
            and len(train) >= seasonal_period * 2
        )

        model = ExponentialSmoothing(
            train,
            trend="add",
            seasonal="add" if use_seasonal else None,
            seasonal_periods=seasonal_period if use_seasonal else None,
            initialization_method="estimated",
        ).fit(optimized=True)

        validation_pred = model.forecast(validation_length)

        return {
            "model": "Holt-Winters",
            "validation_pred": serialize_array(validation_pred),
            "aic": safe_float(getattr(model, "aic", None)),
            "bic": safe_float(getattr(model, "bic", None)),
            "success": True,
            "message": (
                f"Holt-Winters validation forecast completed. "
                f"seasonal_period={seasonal_period}"
            ),
        }

    except Exception as error:
        return build_failed_result(
            "Holt-Winters",
            validation_length,
            error,
        )


def forecast_arima_fallback(
    train: pd.Series,
    test: pd.Series,
    horizon: int,
) -> Dict[str, Any]:
    validation_length = resolve_validation_length(horizon, test)

    try:
        model = SARIMAX(
            train,
            order=(1, 1, 1),
            enforce_stationarity=False,
            enforce_invertibility=False,
        ).fit(
            disp=False,
            maxiter=20,
        )

        validation_pred = model.forecast(validation_length)

        return {
            "model": "AutoARIMA",
            "validation_pred": serialize_array(validation_pred),
            "aic": safe_float(getattr(model, "aic", None)),
            "bic": safe_float(getattr(model, "bic", None)),
            "success": True,
            "message": "Fallback ARIMA validation forecast completed.",
        }

    except Exception as error:
        print("ARIMA FALLBACK ERROR:", error)

        return forecast_naive(
            train=train,
            test=test,
            horizon=horizon,
        )


def forecast_auto_arima(
    train: pd.Series,
    test: pd.Series,
    horizon: int,
    seasonal_period: Optional[int],
) -> Dict[str, Any]:
    validation_length = resolve_validation_length(horizon, test)

    try:
        if AutoARIMA is not None:
            use_seasonal = (
                seasonal_period is not None
                and len(train) >= seasonal_period * 2
            )

            model = AutoARIMA(
                start_p=1,
                start_q=1,
                max_p=1,
                max_q=1,
                d=1,

                start_P=0,
                start_Q=0,
                max_P=1,
                max_Q=1,
                max_D=1,

                sp=seasonal_period if use_seasonal else 1,
                seasonal=use_seasonal,
                max_order=4,

                suppress_warnings=True,
                stepwise=True,
                error_action="ignore",
                trace=False,

                n_jobs=1,
                maxiter=20,
            )

            train_for_arima = pd.Series(
                train.values,
                index=pd.RangeIndex(len(train)),
            )

            model.fit(train_for_arima)

            validation_fh = list(range(1, validation_length + 1))
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
                "message": (
                    f"AutoARIMA validation forecast completed. "
                    f"order={order}, seasonal_order={seasonal_order}, "
                    f"seasonal_period={seasonal_period}"
                ),
            }

        return forecast_arima_fallback(
            train=train,
            test=test,
            horizon=horizon,
        )

    except Exception as error:
        print("AutoARIMA ERROR:", error)

        return forecast_arima_fallback(
            train=train,
            test=test,
            horizon=horizon,
        )


def run_all_forecasts(
    df: pd.DataFrame,
    horizon: Union[int, str],
    frequency: Optional[str] = None,
    value_column: str = "value_preprocessed",
    seasonal_period: Optional[int] = None,
) -> Dict[str, Any]:
    if value_column not in df.columns:
        raise ValueError(f"{value_column} 컬럼을 찾을 수 없습니다.")

    seasonal_period = normalize_seasonal_period(seasonal_period)

    series = pd.Series(
        df[value_column].values,
        index=df["date"],
    )

    series = pd.to_numeric(series, errors="coerce")
    series = series.interpolate(method="linear").ffill().bfill()

    if len(series) < 5:
        raise ValueError("예측을 수행하기에는 데이터가 너무 적습니다.")

    train, test = split_train_test(series)

    horizon_value = resolve_horizon(
        horizon=horizon,
        test=test,
    )

    validation_length = resolve_validation_length(
        horizon=horizon_value,
        test=test,
    )

    test_dates = [
        date.strftime("%Y-%m-%d")
        for date in test.index
    ]

    validation_dates = [
        date.strftime("%Y-%m-%d")
        for date in test.index[:validation_length]
    ]

    model_results = {}

    model_results["AutoARIMA"] = forecast_auto_arima(
        train=train,
        test=test,
        horizon=horizon_value,
        seasonal_period=seasonal_period,
    )

    model_results["Holt-Winters"] = forecast_holt_winters(
        train=train,
        test=test,
        horizon=horizon_value,
        seasonal_period=seasonal_period,
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
        "train_dates": [
            date.strftime("%Y-%m-%d")
            for date in train.index
        ],

        "test_values": serialize_array(test.values),
        "test_dates": test_dates,

        "validation_dates": validation_dates,
        "validation_length": validation_length,

        "seasonal_period": seasonal_period,
        "horizon": horizon_value,

        "model_results": model_results,
    }