/* =========================================================
   TIME - frontend/js/storage.js
---------------------------------------------------------
역할
1. 페이지 간 데이터 저장
2. CSV 데이터 저장
3. horizon 저장
4. 특이치 정보 저장
5. 분석 결과 저장
6. 분석 모드 저장
7. 이상탐지 옵션 저장
========================================================= */


/* =========================================================
   1. Storage Key
========================================================= */

const STORAGE_KEYS = {
  TABLE_DATA: "time_table_data",
  COLUMN_NAMES: "time_column_names",
  HORIZON: "time_horizon",
  PROTECTED_CELLS: "time_protected_cells",
  ANALYSIS_RESULT: "time_analysis_result",

  ANALYSIS_MODE: "time_analysis_mode",
  ANOMALY_OPTIONS: "time_anomaly_options",
};


/* =========================================================
   2. 기본값
========================================================= */

const DEFAULT_ANALYSIS_MODE = "forecast";

const DEFAULT_ANOMALY_OPTIONS = {
  method: "auto",
  sensitivity: "medium",
};


/* =========================================================
   3. 공통 저장 함수
========================================================= */

function setStorage(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function getStorage(key, defaultValue = null) {
  const raw = localStorage.getItem(key);

  if (!raw) {
    return defaultValue;
  }

  try {
    return JSON.parse(raw);
  } catch (error) {
    console.error("Storage parsing error:", error);
    return defaultValue;
  }
}

function removeStorage(key) {
  localStorage.removeItem(key);
}


/* =========================================================
   4. CSV 테이블 데이터 저장
========================================================= */

function saveTableData(data) {
  setStorage(STORAGE_KEYS.TABLE_DATA, data);
}

function loadTableData() {
  return getStorage(STORAGE_KEYS.TABLE_DATA, []);
}


/* =========================================================
   5. 컬럼명 저장
========================================================= */

function saveColumnNames(columns) {
  setStorage(STORAGE_KEYS.COLUMN_NAMES, columns);
}

function loadColumnNames() {
  return getStorage(STORAGE_KEYS.COLUMN_NAMES, []);
}


/* =========================================================
   6. horizon 저장
========================================================= */

function saveHorizon(horizon) {
  setStorage(STORAGE_KEYS.HORIZON, horizon);
}

function loadHorizon() {
  return getStorage(STORAGE_KEYS.HORIZON, 12);
}


/* =========================================================
   7. 특이치(보호 셀) 저장
---------------------------------------------------------
형태 예시:
[
  {
    row: 3,
    column: "value"
  }
]
========================================================= */

function saveProtectedCells(cells) {
  setStorage(STORAGE_KEYS.PROTECTED_CELLS, cells || []);
}

function loadProtectedCells() {
  return getStorage(STORAGE_KEYS.PROTECTED_CELLS, []);
}


/* =========================================================
   8. 분석 결과 저장
========================================================= */

function saveAnalysisResult(result) {
  setStorage(STORAGE_KEYS.ANALYSIS_RESULT, result);
}

function loadAnalysisResult() {
  return getStorage(STORAGE_KEYS.ANALYSIS_RESULT, null);
}

function clearAnalysisResult() {
  removeStorage(STORAGE_KEYS.ANALYSIS_RESULT);
}


/* =========================================================
   9. 분석 모드 저장
---------------------------------------------------------
사용 가능 값:
- forecast : 기존 시계열 예측
- anomaly  : 신규 시계열 이상탐지
========================================================= */

function normalizeAnalysisMode(mode) {
  const modeText = String(mode || DEFAULT_ANALYSIS_MODE)
    .trim()
    .toLowerCase();

  if (modeText === "anomaly") {
    return "anomaly";
  }

  return "forecast";
}

function saveAnalysisMode(mode) {
  setStorage(
    STORAGE_KEYS.ANALYSIS_MODE,
    normalizeAnalysisMode(mode)
  );
}

function loadAnalysisMode() {
  const mode = getStorage(
    STORAGE_KEYS.ANALYSIS_MODE,
    DEFAULT_ANALYSIS_MODE
  );

  return normalizeAnalysisMode(mode);
}


/* =========================================================
   10. 이상탐지 옵션 저장
---------------------------------------------------------
형태:
{
  method: "auto" | "isolation_forest" | "zscore" | "iqr" | "stl_residual",
  sensitivity: "low" | "medium" | "high"
}
========================================================= */

function normalizeAnomalyMethod(method) {
  const methodText = String(method || DEFAULT_ANOMALY_OPTIONS.method)
    .trim()
    .toLowerCase();

  const allowedMethods = [
    "auto",
    "isolation_forest",
    "zscore",
    "iqr",
    "stl_residual",
  ];

  if (allowedMethods.includes(methodText)) {
    return methodText;
  }

  return DEFAULT_ANOMALY_OPTIONS.method;
}

function normalizeAnomalySensitivity(sensitivity) {
  const sensitivityText = String(
    sensitivity || DEFAULT_ANOMALY_OPTIONS.sensitivity
  )
    .trim()
    .toLowerCase();

  const allowedSensitivities = [
    "low",
    "medium",
    "high",
  ];

  if (allowedSensitivities.includes(sensitivityText)) {
    return sensitivityText;
  }

  return DEFAULT_ANOMALY_OPTIONS.sensitivity;
}

function normalizeAnomalyOptions(options) {
  if (!options || typeof options !== "object") {
    return {
      ...DEFAULT_ANOMALY_OPTIONS,
    };
  }

  return {
    method: normalizeAnomalyMethod(options.method),
    sensitivity: normalizeAnomalySensitivity(options.sensitivity),
  };
}

function saveAnomalyOptions(options) {
  setStorage(
    STORAGE_KEYS.ANOMALY_OPTIONS,
    normalizeAnomalyOptions(options)
  );
}

function loadAnomalyOptions() {
  const options = getStorage(
    STORAGE_KEYS.ANOMALY_OPTIONS,
    DEFAULT_ANOMALY_OPTIONS
  );

  return normalizeAnomalyOptions(options);
}


/* =========================================================
   11. 전체 데이터 초기화
========================================================= */

function clearAllStorage() {
  Object.values(STORAGE_KEYS).forEach((key) => {
    localStorage.removeItem(key);
  });
}


/* =========================================================
   12. 업로드 이후 기본 분석 설정 초기화
---------------------------------------------------------
upload.js에서 새 CSV 업로드 후 기본값을 넣고 싶을 때 사용 가능
========================================================= */

function resetAnalysisSettings() {
  saveHorizon(12);
  saveProtectedCells([]);
  saveAnalysisMode(DEFAULT_ANALYSIS_MODE);
  saveAnomalyOptions(DEFAULT_ANOMALY_OPTIONS);
  clearAnalysisResult();
}


/* =========================================================
   13. 전역 객체 등록
========================================================= */

window.TIMEStorage = {
  saveTableData,
  loadTableData,

  saveColumnNames,
  loadColumnNames,

  saveHorizon,
  loadHorizon,

  saveProtectedCells,
  loadProtectedCells,

  saveAnalysisResult,
  loadAnalysisResult,
  clearAnalysisResult,

  saveAnalysisMode,
  loadAnalysisMode,

  saveAnomalyOptions,
  loadAnomalyOptions,

  resetAnalysisSettings,
  clearAllStorage,
};