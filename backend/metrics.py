# =========================================================
# TIME - backend/metrics.py
# ---------------------------------------------------------
# 역할
# 1. 모델별 예측 성능 지표 계산
# 2. MAE, MSE, RMSE, MAPE, SMAPE, MASE 계산
# 3. AIC, BIC 값 정리
# 4. 모델별 Rank 계산
# =========================================================

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


# =========================================================
# 1. 안전한 숫자 변환
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


# =========================================================
# 2. 기본 오차 지표
# =========================================================

def calculate_mae(y_true: np.ndarray, y_pred: np.ndarray) -> Optional[float]:
    if len(y_true) == 0 or len(y_pred) == 0:
        return None

    return safe_float(np.mean(np.abs(y_true - y_pred)))


def calculate_mse(y_true: np.ndarray, y_pred: np.ndarray) -> Optional[float]:
    if len(y_true) == 0 or len(y_pred) == 0:
        return None

    return safe_float(np.mean((y_true - y_pred) ** 2))


def calculate_rmse(y_true: np.ndarray, y_pred: np.ndarray) -> Optional[float]:
    mse = calculate_mse(y_true, y_pred)

    if mse is None:
        return None

    return safe_float(np.sqrt(mse))


def calculate_mape(y_true: np.ndarray, y_pred: np.ndarray) -> Optional[float]:
    if len(y_true) == 0 or len(y_pred) == 0:
        return None

    mask = y_true != 0

    if not np.any(mask):
        return None

    value = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100

    return safe_float(value)


def calculate_smape(y_true: np.ndarray, y_pred: np.ndarray) -> Optional[float]:
    if len(y_true) == 0 or len(y_pred) == 0:
        return None

    denominator = np.abs(y_true) + np.abs(y_pred)

    mask = denominator != 0

    if not np.any(mask):
        return None

    value = np.mean(
        2 * np.abs(y_pred[mask] - y_true[mask]) / denominator[mask]
    ) * 100

    return safe_float(value)


def calculate_mase(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_train: np.ndarray,
) -> Optional[float]:
    if len(y_true) == 0 or len(y_pred) == 0 or len(y_train) < 2:
        return None

    mae = np.mean(np.abs(y_true - y_pred))
    naive_error = np.mean(np.abs(np.diff(y_train)))

    if naive_error == 0:
        return None

    return safe_float(mae / naive_error)


# =========================================================
# 3. 모델별 전체 지표 계산
# =========================================================

def calculate_model_metrics(
    y_true: List[float],
    y_pred: List[float],
    y_train: List[float],
    aic: Optional[float] = None,
    bic: Optional[float] = None,
) -> Dict[str, Optional[float]]:
    y_true_array = np.array(y_true, dtype=float)
    y_pred_array = np.array(y_pred, dtype=float)
    y_train_array = np.array(y_train, dtype=float)

    min_length = min(len(y_true_array), len(y_pred_array))

    y_true_array = y_true_array[:min_length]
    y_pred_array = y_pred_array[:min_length]

    return {
        "mae": calculate_mae(y_true_array, y_pred_array),
        "mse": calculate_mse(y_true_array, y_pred_array),
        "rmse": calculate_rmse(y_true_array, y_pred_array),
        "mape": calculate_mape(y_true_array, y_pred_array),
        "smape": calculate_smape(y_true_array, y_pred_array),
        "mase": calculate_mase(y_true_array, y_pred_array, y_train_array),
        "aic": safe_float(aic),
        "bic": safe_float(bic),
    }


# =========================================================
# 4. 모델 Rank 계산
# ---------------------------------------------------------
# 기본 기준:
# 1순위 RMSE
# 2순위 MAPE
# 3순위 AIC
# 4순위 BIC
# =========================================================

def get_rank_score(model_metrics: Dict[str, Any]) -> float:
    score = 0.0

    weights = {
        "rmse": 0.4,
        "mape": 0.3,
        "aic": 0.2,
        "bic": 0.1,
    }

    for key, weight in weights.items():
        value = model_metrics.get(key)

        if value is None:
            score += 1e9
        else:
            score += float(value) * weight

    return score


def rank_models(metrics_table: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ranked = sorted(
        metrics_table,
        key=lambda row: get_rank_score(row),
    )

    for index, row in enumerate(ranked):
        row["rank"] = index + 1

    return ranked


# =========================================================
# 5. 모델별 성능 비교표 생성
# =========================================================

def build_metrics_dashboard(
    model_results: Dict[str, Dict[str, Any]],
    y_train: List[float],
    y_test: List[float],
) -> List[Dict[str, Any]]:
    dashboard = []

    for model_name, result in model_results.items():
        y_pred = result.get("validation_pred", [])
        aic = result.get("aic")
        bic = result.get("bic")

        metrics = calculate_model_metrics(
            y_true=y_test,
            y_pred=y_pred,
            y_train=y_train,
            aic=aic,
            bic=bic,
        )

        dashboard.append(
            {
                "model": model_name,
                "mae": metrics["mae"],
                "mse": metrics["mse"],
                "rmse": metrics["rmse"],
                "mape": metrics["mape"],
                "smape": metrics["smape"],
                "mase": metrics["mase"],
                "aic": metrics["aic"],
                "bic": metrics["bic"],
            }
        )

    return rank_models(dashboard)


# =========================================================
# 6. Best Model 선택
# =========================================================

def get_best_model(metrics_dashboard: List[Dict[str, Any]]) -> Optional[str]:
    if not metrics_dashboard:
        return None

    ranked = rank_models(metrics_dashboard)

    return ranked[0].get("model")


# =========================================================
# 7. DataFrame 변환용
# =========================================================

def metrics_to_dataframe(metrics_dashboard: List[Dict[str, Any]]) -> pd.DataFrame:
    if not metrics_dashboard:
        return pd.DataFrame()

    columns = [
        "model",
        "mae",
        "mse",
        "rmse",
        "mape",
        "smape",
        "mase",
        "aic",
        "bic",
        "rank",
    ]

    return pd.DataFrame(metrics_dashboard)[columns]