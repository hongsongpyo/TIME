/* =========================================================
   TIME - frontend/js/storage.js
---------------------------------------------------------
역할
1. 페이지 간 데이터 저장
2. CSV 데이터 저장
3. horizon 저장
4. 특이치 정보 저장
5. 분석 결과 저장
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
};


/* =========================================================
   2. 공통 저장 함수
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
   3. CSV 테이블 데이터 저장
========================================================= */

function saveTableData(data) {
  setStorage(STORAGE_KEYS.TABLE_DATA, data);
}

function loadTableData() {
  return getStorage(STORAGE_KEYS.TABLE_DATA, []);
}


/* =========================================================
   4. 컬럼명 저장
========================================================= */

function saveColumnNames(columns) {
  setStorage(STORAGE_KEYS.COLUMN_NAMES, columns);
}

function loadColumnNames() {
  return getStorage(STORAGE_KEYS.COLUMN_NAMES, []);
}


/* =========================================================
   5. horizon 저장
========================================================= */

function saveHorizon(horizon) {
  setStorage(STORAGE_KEYS.HORIZON, horizon);
}

function loadHorizon() {
  return getStorage(STORAGE_KEYS.HORIZON, 12);
}


/* =========================================================
   6. 특이치(보호 셀) 저장
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
  setStorage(STORAGE_KEYS.PROTECTED_CELLS, cells);
}

function loadProtectedCells() {
  return getStorage(STORAGE_KEYS.PROTECTED_CELLS, []);
}


/* =========================================================
   7. 분석 결과 저장
========================================================= */

function saveAnalysisResult(result) {
  setStorage(STORAGE_KEYS.ANALYSIS_RESULT, result);
}

function loadAnalysisResult() {
  return getStorage(STORAGE_KEYS.ANALYSIS_RESULT, null);
}


/* =========================================================
   8. 전체 데이터 초기화
========================================================= */

function clearAllStorage() {
  Object.values(STORAGE_KEYS).forEach((key) => {
    localStorage.removeItem(key);
  });
}


/* =========================================================
   9. 전역 객체 등록
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

  clearAllStorage,
};