# =========================================================
# TIME - backend/forecasting.py
# ---------------------------------------------------------
# 역할
# 1. 전처리된 시계열 데이터를 학습/검증 데이터로 분리
# 2. horizon 만큼 마지막 데이터를 test 데이터로 사용
# 3. train 데이터로 모델 학습
# 4. test 구간에 대한 validation 예측만 생성
# 5. AutoARIMA, Holt-Winters, Exponential Smoothing, Naive 비교
# 6. AIC, BIC 값 반환
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


def serialize_array(values: Any) -> List[Optional[float]]:
    result = []

    for value in list(values):
        result.append(safe_float(value))

    return result


# =========================================================
# 2. 계절 주기 추정
# =========================================================

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


# =========================================================
# 3. Train / Test 분리
# ---------------------------------------------------------
# 사용자가 설정한 horizon 만큼 마지막 데이터를 test로 사용
# =========================================================

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


# =========================================================
# 4. Naive Forecast
# =========================================================

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


# =========================================================
# 5. Exponential Smoothing
# =========================================================

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


# =========================================================
# 6. Holt-Winters Forecast
# =========================================================

def forecast_holt_winters(
    train: pd.Series,
    test: pd.Series,
    seasonal_period: int,
) -> Dict[str, Any]:
    try:
        use_seasonal = seasonal_period >= 2 and len(train) >= seasonal_period * 2

        model = ExponentialSmoothing(
            train,
            trend="add",
            seasonal="add" if use_seasonal else None,
            seasonal_periods=seasonal_period if use_seasonal else None,
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


# =========================================================
# 7. AutoARIMA Forecast
# ---------------------------------------------------------
# sktime AutoARIMA 사용
# SARIMA 계절성 탐색 포함
# sp는 최대 12로 제한
# =========================================================

def forecast_auto_arima(
    train: pd.Series,
    test: pd.Series,
    seasonal_period: int,
) -> Dict[str, Any]:
    try:
        if AutoARIMA is not None:
            # 과제 데이터는 계절성이 있다고 가정
            # 단, sp가 1 이하이면 기본 월별 계절성 12로 보정
            sp = int(seasonal_period)

            if sp < 2:
                sp = 12

            # 계산량 폭증 방지를 위해 최대 12까지만 사용
            sp = min(sp, 12)

            # SARIMA는 최소 2주기 이상 데이터가 있을 때 안정적
            # 데이터가 너무 짧으면 AutoARIMA 내부 오류 가능성이 커서 sp를 완화
            if len(train) < sp * 2:
                sp = max(2, min(4, len(train) // 2))

            model = AutoARIMA(
                max_p=2,
                max_q=2,
                max_d=2,

                # SARIMA 고정
                seasonal=True,
                sp=sp,

                max_P=1,
                max_Q=1,
                max_D=1,
                max_order=4,

                # 계산 시간 감소 옵션
                stepwise=True,
                error_action="ignore",
                suppress_warnings=True,
                trace=False,
                n_jobs=1,
                information_criterion="aic",
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
                "model": "AutoARIMA-SARIMA",
                "validation_pred": serialize_array(validation_pred),
                "aic": safe_float(aic),
                "bic": safe_float(bic),
                "success": True,
                "message": f"SARIMA AutoARIMA completed. order={order}, seasonal_order={seasonal_order}",
            }

        # AutoARIMA를 사용할 수 없을 때만 고정 SARIMAX fallback
        sp = int(seasonal_period)

        if sp < 2:
            sp = 12

        sp = min(sp, 12)

        model = SARIMAX(
            train,
            order=(1, 1, 1),
            seasonal_order=(1, 1, 1, sp),
            enforce_stationarity=False,
            enforce_invertibility=False,
        ).fit(disp=False)

        validation_pred = model.forecast(len(test))

        return {
            "model": "AutoARIMA-SARIMA",
            "validation_pred": serialize_array(validation_pred),
            "aic": safe_float(getattr(model, "aic", None)),
            "bic": safe_float(getattr(model, "bic", None)),
            "success": True,
            "message": "Fallback SARIMAX seasonal validation completed.",
        }

    except Exception as error:
        return build_failed_result("AutoARIMA-SARIMA", len(test), error)

# =========================================================
# 8. 실패 결과 생성
# =========================================================

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

    validation_dates = [date.strftime("%Y-%m-%d") for date in test.index]

    model_results = {}

    model_results["AutoARIMA"] = forecast_auto_arima(
        train=train,
        test=test,
        seasonal_period=seasonal_period,
    )

    model_results["Holt-Winters"] = forecast_holt_winters(
        train=train,
        test=test,
        seasonal_period=seasonal_period,
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
        "seasonal_period": seasonal_period,
        "model_results": model_results,
    }