/* =========================================================
   TIME - frontend/js/storage.js
---------------------------------------------------------
역할
1. 페이지 간 데이터 저장
2. CSV 데이터 저장
3. 기존 horizon 저장 함수 호환 유지
4. 특이치 보호 셀 저장
5. 이상탐지 분석 결과 저장
6. 이상탐지 옵션 저장
7. 결과 페이지 메뉴 선택 상태 저장
8. 전역 변수 충돌 방지
========================================================= */

(function () {
  "use strict";


  /* =========================================================
     1. Storage Key
  ========================================================= */

  const STORAGE_KEYS = {
    TABLE_DATA: "time_table_data",
    COLUMN_NAMES: "time_column_names",

    // 기존 예측 기능 호환용
    HORIZON: "time_horizon",

    PROTECTED_CELLS: "time_protected_cells",
    ANALYSIS_RESULT: "time_analysis_result",

    // 현재는 anomaly 전용
    ANALYSIS_MODE: "time_analysis_mode",
    ANOMALY_OPTIONS: "time_anomaly_options",

    // result.html 메뉴형 그래프 선택 상태
    SELECTED_ANOMALY_VIEW: "time_selected_anomaly_view",
    SELECTED_ANOMALY_DATE: "time_selected_anomaly_date",
  };


  /* =========================================================
     2. 기본값
  ========================================================= */

  const DEFAULT_ANALYSIS_MODE = "anomaly";

  const DEFAULT_ANOMALY_OPTIONS = {
    method: "auto",
    sensitivity: "medium",
  };

  const DEFAULT_ANOMALY_VIEW = "timeline";


  /* =========================================================
     3. 공통 저장 함수
  ========================================================= */

  function setStorage(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      console.error("Storage save error:", error);
    }
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
    try {
      localStorage.removeItem(key);
    } catch (error) {
      console.error("Storage remove error:", error);
    }
  }


  /* =========================================================
     4. CSV 테이블 데이터 저장
  ========================================================= */

  function saveTableData(data) {
    setStorage(STORAGE_KEYS.TABLE_DATA, Array.isArray(data) ? data : []);
  }

  function loadTableData() {
    return getStorage(STORAGE_KEYS.TABLE_DATA, []);
  }


  /* =========================================================
     5. 컬럼명 저장
  ========================================================= */

  function saveColumnNames(columns) {
    setStorage(STORAGE_KEYS.COLUMN_NAMES, Array.isArray(columns) ? columns : []);
  }

  function loadColumnNames() {
    return getStorage(STORAGE_KEYS.COLUMN_NAMES, []);
  }


  /* =========================================================
     6. horizon 저장
  ---------------------------------------------------------
  현재 이상탐지에서는 사용하지 않지만,
  기존 editor.js / upload.js 호환을 위해 유지
  ========================================================= */

  function saveHorizon(horizon) {
    if (horizon === "auto") {
      setStorage(STORAGE_KEYS.HORIZON, "auto");
      return;
    }

    const horizonValue = Number(horizon);

    if (!Number.isFinite(horizonValue) || horizonValue <= 0) {
      setStorage(STORAGE_KEYS.HORIZON, 12);
      return;
    }

    setStorage(STORAGE_KEYS.HORIZON, Math.floor(horizonValue));
  }

  function loadHorizon() {
    return getStorage(STORAGE_KEYS.HORIZON, 12);
  }


  /* =========================================================
     7. 특이치 보호 셀 저장
  ---------------------------------------------------------
  형태 예시:
  [
    {
      row: 3,
      column: "energy"
    }
  ]

  중요:
  - 셀 단위 보호
  - 같은 행 전체를 보호하지 않음
  ========================================================= */

  function normalizeProtectedCells(cells) {
    if (!Array.isArray(cells)) {
      return [];
    }

    return cells
      .filter((cell) => {
        if (!cell) {
          return false;
        }

        const rowNumber = Number(cell.row);

        return (
          Number.isInteger(rowNumber) &&
          rowNumber >= 0 &&
          cell.column !== undefined &&
          cell.column !== null &&
          String(cell.column).trim() !== ""
        );
      })
      .map((cell) => {
        return {
          row: Number(cell.row),
          column: String(cell.column),
        };
      });
  }

  function saveProtectedCells(cells) {
    setStorage(
      STORAGE_KEYS.PROTECTED_CELLS,
      normalizeProtectedCells(cells)
    );
  }

  function loadProtectedCells() {
    return normalizeProtectedCells(
      getStorage(STORAGE_KEYS.PROTECTED_CELLS, [])
    );
  }


  /* =========================================================
     8. 분석 결과 저장
  ========================================================= */

  function saveAnalysisResult(result) {
    setStorage(STORAGE_KEYS.ANALYSIS_RESULT, result || null);
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
  현재 프로젝트는 이상탐지 전용이므로,
  forecast가 들어와도 anomaly로 저장
  ========================================================= */

  function normalizeAnalysisMode(mode) {
    const modeText = String(mode || DEFAULT_ANALYSIS_MODE)
      .trim()
      .toLowerCase();

    if (
      modeText === "anomaly" ||
      modeText === "anomaly_detection" ||
      modeText === "detect" ||
      modeText === "outlier" ||
      modeText === "이상탐지"
    ) {
      return "anomaly";
    }

    return "anomaly";
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
     10. 이상탐지 방법 정규화
  ---------------------------------------------------------
  사용 가능 값:
  - auto
  - isolation_forest
  - zscore
  - iqr
  - stl_residual
  ========================================================= */

  function normalizeAnomalyMethod(method) {
    const methodText = String(method || DEFAULT_ANOMALY_OPTIONS.method)
      .trim()
      .toLowerCase();

    const aliasMap = {
      "자동": "auto",
      "오토": "auto",
      "isolationforest": "isolation_forest",
      "isolation forest": "isolation_forest",
      "격리숲": "isolation_forest",
      "z-score": "zscore",
      "z score": "zscore",
      "z스코어": "zscore",
      "stl": "stl_residual",
      "stl residual": "stl_residual",
      "잔차": "stl_residual",
    };

    const normalizedMethod = aliasMap[methodText] || methodText;

    const allowedMethods = [
      "auto",
      "isolation_forest",
      "zscore",
      "iqr",
      "stl_residual",
    ];

    if (allowedMethods.includes(normalizedMethod)) {
      return normalizedMethod;
    }

    return DEFAULT_ANOMALY_OPTIONS.method;
  }


  /* =========================================================
     11. 이상탐지 민감도 정규화
  ---------------------------------------------------------
  low    : 낮음  → threshold 높음 → 확실한 이상만 탐지
  medium : 보통
  high   : 높음  → threshold 낮음 → 더 많이 탐지
  ========================================================= */

  function normalizeAnomalySensitivity(sensitivity) {
    const sensitivityText = String(
      sensitivity || DEFAULT_ANOMALY_OPTIONS.sensitivity
    )
      .trim()
      .toLowerCase();

    const highValues = [
      "high",
      "높음",
      "민감",
      "높은",
    ];

    const mediumValues = [
      "medium",
      "normal",
      "보통",
      "중간",
      "기본",
    ];

    const lowValues = [
      "low",
      "낮음",
      "낮은",
    ];

    if (highValues.includes(sensitivityText)) {
      return "high";
    }

    if (lowValues.includes(sensitivityText)) {
      return "low";
    }

    if (mediumValues.includes(sensitivityText)) {
      return "medium";
    }

    return DEFAULT_ANOMALY_OPTIONS.sensitivity;
  }

  function getSensitivityLabel(sensitivity) {
    const normalizedSensitivity = normalizeAnomalySensitivity(sensitivity);

    if (normalizedSensitivity === "high") {
      return "높음";
    }

    if (normalizedSensitivity === "low") {
      return "낮음";
    }

    return "보통";
  }


  /* =========================================================
     12. 이상탐지 옵션 저장
  ---------------------------------------------------------
  형태:
  {
    method: "auto",
    sensitivity: "medium"
  }
  ========================================================= */

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

  function saveAnomalyMethod(method) {
    const options = loadAnomalyOptions();
    options.method = normalizeAnomalyMethod(method);
    saveAnomalyOptions(options);
  }

  function loadAnomalyMethod() {
    return loadAnomalyOptions().method;
  }

  function saveAnomalySensitivity(sensitivity) {
    const options = loadAnomalyOptions();
    options.sensitivity = normalizeAnomalySensitivity(sensitivity);
    saveAnomalyOptions(options);
  }

  function loadAnomalySensitivity() {
    return loadAnomalyOptions().sensitivity;
  }


  /* =========================================================
     13. Result 페이지 메뉴 상태 저장
  ---------------------------------------------------------
  사용 가능 view:
  - timeline
  - score
  - contribution
  - heatmap
  - table
  - type
  - quality
  ========================================================= */

  function normalizeAnomalyView(view) {
    const viewText = String(view || DEFAULT_ANOMALY_VIEW)
      .trim()
      .toLowerCase();

    const allowedViews = [
      "timeline",
      "score",
      "contribution",
      "heatmap",
      "table",
      "type",
      "quality",
    ];

    if (allowedViews.includes(viewText)) {
      return viewText;
    }

    return DEFAULT_ANOMALY_VIEW;
  }

  function saveSelectedAnomalyView(view) {
    setStorage(
      STORAGE_KEYS.SELECTED_ANOMALY_VIEW,
      normalizeAnomalyView(view)
    );
  }

  function loadSelectedAnomalyView() {
    const view = getStorage(
      STORAGE_KEYS.SELECTED_ANOMALY_VIEW,
      DEFAULT_ANOMALY_VIEW
    );

    return normalizeAnomalyView(view);
  }

  function saveSelectedAnomalyDate(date) {
    if (date === null || date === undefined || String(date).trim() === "") {
      removeStorage(STORAGE_KEYS.SELECTED_ANOMALY_DATE);
      return;
    }

    setStorage(STORAGE_KEYS.SELECTED_ANOMALY_DATE, String(date));
  }

  function loadSelectedAnomalyDate() {
    return getStorage(STORAGE_KEYS.SELECTED_ANOMALY_DATE, null);
  }

  function clearSelectedAnomalyDate() {
    removeStorage(STORAGE_KEYS.SELECTED_ANOMALY_DATE);
  }


  /* =========================================================
     14. 전체 데이터 초기화
  ========================================================= */

  function clearAllStorage() {
    Object.values(STORAGE_KEYS).forEach((key) => {
      removeStorage(key);
    });
  }


  /* =========================================================
     15. 업로드 이후 기본 분석 설정 초기화
  ---------------------------------------------------------
  upload.js에서 새 CSV 업로드 후 기본값을 넣고 싶을 때 사용
  ========================================================= */

  function resetAnalysisSettings() {
    saveHorizon(12);
    saveProtectedCells([]);
    saveAnalysisMode(DEFAULT_ANALYSIS_MODE);
    saveAnomalyOptions(DEFAULT_ANOMALY_OPTIONS);
    saveSelectedAnomalyView(DEFAULT_ANOMALY_VIEW);
    clearSelectedAnomalyDate();
    clearAnalysisResult();
  }


  /* =========================================================
     16. 분석 관련 설정만 초기화
  ---------------------------------------------------------
  CSV 데이터는 유지하고 분석 결과/옵션만 초기화할 때 사용
  ========================================================= */

  function resetOnlyAnalysisResult() {
    clearAnalysisResult();
    saveSelectedAnomalyView(DEFAULT_ANOMALY_VIEW);
    clearSelectedAnomalyDate();
  }


  /* =========================================================
     17. 전역 객체 등록
  ========================================================= */

  window.TIMEStorage = {
    STORAGE_KEYS,

    saveTableData,
    loadTableData,

    saveColumnNames,
    loadColumnNames,

    // 기존 호환용
    saveHorizon,
    loadHorizon,

    saveProtectedCells,
    loadProtectedCells,
    normalizeProtectedCells,

    saveAnalysisResult,
    loadAnalysisResult,
    clearAnalysisResult,

    saveAnalysisMode,
    loadAnalysisMode,
    normalizeAnalysisMode,

    saveAnomalyOptions,
    loadAnomalyOptions,

    saveAnomalyMethod,
    loadAnomalyMethod,

    saveAnomalySensitivity,
    loadAnomalySensitivity,

    normalizeAnomalyMethod,
    normalizeAnomalySensitivity,
    normalizeAnomalyOptions,
    getSensitivityLabel,

    saveSelectedAnomalyView,
    loadSelectedAnomalyView,

    saveSelectedAnomalyDate,
    loadSelectedAnomalyDate,
    clearSelectedAnomalyDate,

    resetAnalysisSettings,
    resetOnlyAnalysisResult,
    clearAllStorage,
  };
})();