/* =========================================================
   TIME - frontend/js/editor.js
---------------------------------------------------------
역할
1. localStorage에 저장된 CSV 데이터를 표로 렌더링
2. 셀 값 수정
3. 컬럼명 수정
4. 행 추가
5. 열 추가
6. 특이치 설정 모드 관리
7. 예측 모드 / 이상탐지 모드 관리
8. 시평 직접 입력 / Test 데이터 길이와 동일 옵션 관리
9. 이상탐지 방식 / 민감도 옵션 관리
10. 자동 분석 실행 후 result.html로 이동
========================================================= */


/* =========================================================
   1. 전역 상태
========================================================= */

let tableData = [];
let columnNames = [];
let protectedCells = [];
let specialMode = false;

let analysisMode = "forecast";

let anomalyOptions = {
  method: "auto",
  sensitivity: "medium",
};

let tableHead = null;
let tableBody = null;

let horizonInput = null;
let autoHorizonInput = null;
let horizonPanel = null;

let forecastModeButton = null;
let anomalyModeButton = null;

let anomalyOptionPanel = null;
let anomalyMethodSelect = null;
let anomalySensitivitySelect = null;

let editorStatus = null;
let runAnalysisButton = null;

let isAnalyzing = false;


/* =========================================================
   2. 초기화
========================================================= */

document.addEventListener("DOMContentLoaded", () => {
  tableHead = document.getElementById("tableHead");
  tableBody = document.getElementById("tableBody");

  horizonInput = document.getElementById("horizonInput");
  autoHorizonInput = document.getElementById("autoHorizonInput");
  horizonPanel = document.getElementById("horizonPanel");

  forecastModeButton = document.getElementById("forecastModeButton");
  anomalyModeButton = document.getElementById("anomalyModeButton");

  anomalyOptionPanel = document.getElementById("anomalyOptionPanel");
  anomalyMethodSelect = document.getElementById("anomalyMethodSelect");
  anomalySensitivitySelect = document.getElementById("anomalySensitivitySelect");

  editorStatus = document.getElementById("editorStatus");
  runAnalysisButton = document.getElementById("runAnalysisButton");

  bindEditorEvents();
  loadEditorData();
  normalizeTableDataByColumns();
  renderTable();
  updateHorizonInputState();
  updateAnalysisModeUI();
  updateAnomalyOptionUI();
});


/* =========================================================
   3. 이벤트 연결
========================================================= */

function bindEditorEvents() {
  const backButton = document.getElementById("backButton");
  const addRowButton = document.getElementById("addRowButton");
  const addColumnButton = document.getElementById("addColumnButton");
  const specialModeButton = document.getElementById("specialModeButton");

  if (backButton) {
    backButton.addEventListener("click", () => {
      saveCurrentState();
      window.location.href = "./upload.html";
    });
  }

  if (forecastModeButton) {
    forecastModeButton.addEventListener("click", () => {
      handleChangeAnalysisMode("forecast");
    });
  }

  if (anomalyModeButton) {
    anomalyModeButton.addEventListener("click", () => {
      handleChangeAnalysisMode("anomaly");
    });
  }

  if (addRowButton) {
    addRowButton.addEventListener("click", handleAddRow);
  }

  if (addColumnButton) {
    addColumnButton.addEventListener("click", handleAddColumn);
  }

  if (specialModeButton) {
    specialModeButton.addEventListener("click", handleToggleSpecialMode);
  }

  if (runAnalysisButton) {
    runAnalysisButton.addEventListener("click", handleRunAnalysis);
  }

  if (horizonInput) {
    horizonInput.addEventListener("change", () => {
      saveCurrentState();
    });
  }

  if (autoHorizonInput) {
    autoHorizonInput.addEventListener("change", () => {
      updateHorizonInputState();
      saveCurrentState();
    });
  }

  if (anomalyMethodSelect) {
    anomalyMethodSelect.addEventListener("change", () => {
      anomalyOptions.method = normalizeAnomalyMethod(anomalyMethodSelect.value);
      saveCurrentState();
    });
  }

  if (anomalySensitivitySelect) {
    anomalySensitivitySelect.addEventListener("change", () => {
      anomalyOptions.sensitivity = normalizeAnomalySensitivity(
        anomalySensitivitySelect.value
      );
      saveCurrentState();
    });
  }

  window.addEventListener("beforeunload", () => {
    saveCurrentState();
  });
}


/* =========================================================
   4. 데이터 불러오기
========================================================= */

function loadEditorData() {
  tableData = window.TIMEStorage.loadTableData();
  columnNames = window.TIMEStorage.loadColumnNames();
  protectedCells = window.TIMEStorage.loadProtectedCells();

  if (!Array.isArray(tableData)) {
    tableData = [];
  }

  if (!Array.isArray(columnNames)) {
    columnNames = [];
  }

  if (!Array.isArray(protectedCells)) {
    protectedCells = [];
  }

  const horizon = window.TIMEStorage.loadHorizon();

  if (horizonInput) {
    if (horizon === "auto") {
      horizonInput.value = 12;

      if (autoHorizonInput) {
        autoHorizonInput.checked = true;
      }
    } else {
      horizonInput.value = horizon || 12;

      if (autoHorizonInput) {
        autoHorizonInput.checked = false;
      }
    }
  }

  if (typeof window.TIMEStorage.loadAnalysisMode === "function") {
    analysisMode = window.TIMEStorage.loadAnalysisMode();
  } else {
    analysisMode = "forecast";
  }

  if (typeof window.TIMEStorage.loadAnomalyOptions === "function") {
    anomalyOptions = window.TIMEStorage.loadAnomalyOptions();
  } else {
    anomalyOptions = {
      method: "auto",
      sensitivity: "medium",
    };
  }

  anomalyOptions = normalizeAnomalyOptions(anomalyOptions);

  if (!tableData || tableData.length === 0) {
    setEditorStatus("업로드된 데이터가 없습니다. 업로드 화면으로 돌아가 CSV를 선택하세요.");
    tableData = [];
  }

  if ((!columnNames || columnNames.length === 0) && tableData.length > 0) {
    columnNames = Object.keys(tableData[0]);
  }
}


/* =========================================================
   5. 데이터 정규화
========================================================= */

function normalizeTableDataByColumns() {
  if (!Array.isArray(columnNames)) {
    columnNames = [];
  }

  if (!Array.isArray(tableData)) {
    tableData = [];
  }

  if (columnNames.length === 0 && tableData.length > 0) {
    columnNames = Object.keys(tableData[0]);
  }

  tableData = tableData.map((row) => {
    const normalizedRow = {};

    columnNames.forEach((columnName) => {
      normalizedRow[columnName] = row && row[columnName] !== undefined
        ? row[columnName]
        : "";
    });

    return normalizedRow;
  });

  protectedCells = protectedCells.filter((cell) => {
    return (
      cell &&
      Number.isInteger(Number(cell.row)) &&
      Number(cell.row) >= 0 &&
      Number(cell.row) < tableData.length &&
      columnNames.includes(cell.column)
    );
  });
}


/* =========================================================
   6. 표 렌더링
========================================================= */

function renderTable() {
  renderTableHead();
  renderTableBody();
}

function renderTableHead() {
  if (!tableHead) return;

  tableHead.innerHTML = "";

  const headerRow = document.createElement("tr");

  columnNames.forEach((columnName, columnIndex) => {
    const th = document.createElement("th");
    th.contentEditable = "true";
    th.textContent = columnName;
    th.dataset.columnIndex = String(columnIndex);

    th.addEventListener("blur", handleColumnNameEdit);
    th.addEventListener("keydown", handleHeaderKeyDown);

    headerRow.appendChild(th);
  });

  tableHead.appendChild(headerRow);
}

function renderTableBody() {
  if (!tableBody) return;

  tableBody.innerHTML = "";

  tableData.forEach((row, rowIndex) => {
    const tr = document.createElement("tr");

    columnNames.forEach((columnName, columnIndex) => {
      const td = document.createElement("td");

      td.contentEditable = "true";
      td.textContent = row[columnName] ?? "";
      td.dataset.rowIndex = String(rowIndex);
      td.dataset.columnIndex = String(columnIndex);
      td.dataset.columnName = columnName;

      if (isProtectedCell(rowIndex, columnName)) {
        td.classList.add("special-cell");
      }

      td.addEventListener("click", handleCellClick);
      td.addEventListener("blur", handleCellEdit);
      td.addEventListener("keydown", handleCellKeyDown);

      tr.appendChild(td);
    });

    tableBody.appendChild(tr);
  });
}


/* =========================================================
   7. 셀 값 수정
========================================================= */

function handleCellEdit(event) {
  const td = event.target;
  const rowIndex = Number(td.dataset.rowIndex);
  const columnName = td.dataset.columnName;

  if (!tableData[rowIndex]) return;

  tableData[rowIndex][columnName] = td.textContent.trim();
  saveCurrentState();
}

function handleCellClick(event) {
  if (!specialMode) return;

  event.preventDefault();

  const td = event.target;
  const rowIndex = Number(td.dataset.rowIndex);
  const columnName = td.dataset.columnName;

  toggleProtectedCell(rowIndex, columnName);
  saveCurrentState();
  renderTable();
}

function handleCellKeyDown(event) {
  if (event.key === "Enter") {
    event.preventDefault();
    event.target.blur();
  }
}


/* =========================================================
   8. 컬럼명 수정
========================================================= */

function handleColumnNameEdit(event) {
  const th = event.target;
  const columnIndex = Number(th.dataset.columnIndex);

  if (
    !Number.isInteger(columnIndex) ||
    columnIndex < 0 ||
    columnIndex >= columnNames.length
  ) {
    renderTable();
    return;
  }

  const oldColumnName = columnNames[columnIndex];
  let newColumnName = th.textContent.trim();

  if (!newColumnName) {
    newColumnName = oldColumnName;
  }

  newColumnName = makeUniqueColumnName(newColumnName, columnIndex);

  if (newColumnName === oldColumnName) {
    th.textContent = oldColumnName;
    return;
  }

  columnNames[columnIndex] = newColumnName;

  tableData = tableData.map((row) => {
    const newRow = {};

    columnNames.forEach((columnName) => {
      if (columnName === newColumnName) {
        newRow[columnName] = row[oldColumnName] ?? "";
      } else {
        newRow[columnName] = row[columnName] ?? "";
      }
    });

    return newRow;
  });

  protectedCells = protectedCells.map((cell) => {
    if (cell.column === oldColumnName) {
      return {
        ...cell,
        column: newColumnName,
      };
    }

    return cell;
  });

  saveCurrentState();
  renderTable();
}

function handleHeaderKeyDown(event) {
  if (event.key === "Enter") {
    event.preventDefault();
    event.target.blur();
  }
}

function makeUniqueColumnName(columnName, currentIndex = -1) {
  let baseName = String(columnName || "column").trim();

  if (!baseName) {
    baseName = "column";
  }

  const existingNames = columnNames.filter((_, index) => {
    return index !== currentIndex;
  });

  if (!existingNames.includes(baseName)) {
    return baseName;
  }

  let count = 1;
  let candidate = `${baseName}_${count}`;

  while (existingNames.includes(candidate)) {
    count += 1;
    candidate = `${baseName}_${count}`;
  }

  return candidate;
}


/* =========================================================
   9. 행 추가
========================================================= */

function handleAddRow() {
  if (columnNames.length === 0) {
    columnNames = ["date", "value"];
  }

  const newRow = {};

  columnNames.forEach((columnName) => {
    newRow[columnName] = "";
  });

  tableData.push(newRow);

  saveCurrentState();
  renderTable();

  setEditorStatus("새 행이 추가되었습니다.");
}


/* =========================================================
   10. 열 추가
========================================================= */

function handleAddColumn() {
  const newColumnName = makeUniqueColumnName("new_column");

  columnNames.push(newColumnName);

  tableData = tableData.map((row) => {
    return {
      ...row,
      [newColumnName]: "",
    };
  });

  saveCurrentState();
  renderTable();

  setEditorStatus("새 열이 추가되었습니다.");
}


/* =========================================================
   11. 특이치 설정 모드
========================================================= */

function handleToggleSpecialMode() {
  specialMode = !specialMode;

  const specialModeButton = document.getElementById("specialModeButton");

  if (specialModeButton) {
    specialModeButton.classList.toggle("active", specialMode);
  }

  if (specialMode) {
    setEditorStatus("특이치 설정 모드입니다. 보호할 셀을 클릭하세요.");
  } else {
    setEditorStatus("특이치 설정 모드가 해제되었습니다.");
  }
}

function isProtectedCell(rowIndex, columnName) {
  return protectedCells.some((cell) => {
    return Number(cell.row) === Number(rowIndex) && cell.column === columnName;
  });
}

function toggleProtectedCell(rowIndex, columnName) {
  const existingIndex = protectedCells.findIndex((cell) => {
    return Number(cell.row) === Number(rowIndex) && cell.column === columnName;
  });

  if (existingIndex >= 0) {
    protectedCells.splice(existingIndex, 1);
    setEditorStatus("특이치 지정이 해제되었습니다.");
    return;
  }

  protectedCells.push({
    row: Number(rowIndex),
    column: columnName,
  });

  setEditorStatus("선택한 셀이 특이치로 지정되었습니다.");
}


/* =========================================================
   12. 분석 모드
========================================================= */

function handleChangeAnalysisMode(mode) {
  analysisMode = normalizeAnalysisMode(mode);

  updateAnalysisModeUI();
  saveCurrentState();

  if (analysisMode === "forecast") {
    setEditorStatus("예측 모드입니다. 시평을 설정한 뒤 자동 분석을 실행하세요.");
  } else {
    setEditorStatus("이상탐지 모드입니다. 탐지 방식과 민감도를 설정한 뒤 자동 분석을 실행하세요.");
  }
}

function normalizeAnalysisMode(mode) {
  const modeText = String(mode || "forecast").trim().toLowerCase();

  if (modeText === "anomaly") {
    return "anomaly";
  }

  return "forecast";
}

function updateAnalysisModeUI() {
  analysisMode = normalizeAnalysisMode(analysisMode);

  if (forecastModeButton) {
    forecastModeButton.classList.toggle("active", analysisMode === "forecast");
  }

  if (anomalyModeButton) {
    anomalyModeButton.classList.toggle("active", analysisMode === "anomaly");
  }

  if (horizonPanel) {
    horizonPanel.hidden = analysisMode !== "forecast";
  }

  if (anomalyOptionPanel) {
    anomalyOptionPanel.hidden = analysisMode !== "anomaly";
  }

  if (runAnalysisButton) {
    runAnalysisButton.textContent =
      analysisMode === "anomaly"
        ? "이상탐지 실행"
        : "자동 분석 실행";
  }
}


/* =========================================================
   13. 이상탐지 옵션
========================================================= */

function normalizeAnomalyMethod(method) {
  const methodText = String(method || "auto").trim().toLowerCase();

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

  return "auto";
}

function normalizeAnomalySensitivity(sensitivity) {
  const sensitivityText = String(sensitivity || "medium").trim().toLowerCase();

  const allowedSensitivities = [
    "low",
    "medium",
    "high",
  ];

  if (allowedSensitivities.includes(sensitivityText)) {
    return sensitivityText;
  }

  return "medium";
}

function normalizeAnomalyOptions(options) {
  if (!options || typeof options !== "object") {
    return {
      method: "auto",
      sensitivity: "medium",
    };
  }

  return {
    method: normalizeAnomalyMethod(options.method),
    sensitivity: normalizeAnomalySensitivity(options.sensitivity),
  };
}

function updateAnomalyOptionUI() {
  anomalyOptions = normalizeAnomalyOptions(anomalyOptions);

  if (anomalyMethodSelect) {
    anomalyMethodSelect.value = anomalyOptions.method;
  }

  if (anomalySensitivitySelect) {
    anomalySensitivitySelect.value = anomalyOptions.sensitivity;
  }
}

function getCurrentAnomalyOptions() {
  const method = anomalyMethodSelect
    ? anomalyMethodSelect.value
    : anomalyOptions.method;

  const sensitivity = anomalySensitivitySelect
    ? anomalySensitivitySelect.value
    : anomalyOptions.sensitivity;

  return normalizeAnomalyOptions({
    method,
    sensitivity,
  });
}


/* =========================================================
   14. 시평 설정
========================================================= */

function updateHorizonInputState() {
  if (!horizonInput || !autoHorizonInput) return;

  if (autoHorizonInput.checked) {
    horizonInput.disabled = true;
  } else {
    horizonInput.disabled = false;
  }
}

function getCurrentHorizon() {
  if (autoHorizonInput && autoHorizonInput.checked) {
    return "auto";
  }

  if (!horizonInput) {
    return 12;
  }

  const horizonValue = Number(horizonInput.value);

  if (!Number.isFinite(horizonValue) || horizonValue <= 0) {
    return 12;
  }

  return Math.floor(horizonValue);
}


/* =========================================================
   15. 자동 분석 실행
========================================================= */

async function handleRunAnalysis() {
  if (isAnalyzing) {
    return;
  }

  normalizeTableDataByColumns();

  if (!tableData || tableData.length === 0) {
    setEditorStatus("분석할 데이터가 없습니다. CSV 파일을 먼저 업로드하세요.");
    return;
  }

  if (!columnNames || columnNames.length === 0) {
    setEditorStatus("분석할 컬럼이 없습니다.");
    return;
  }

  analysisMode = normalizeAnalysisMode(analysisMode);
  anomalyOptions = getCurrentAnomalyOptions();

  const horizon = getCurrentHorizon();

  if (analysisMode === "forecast" && horizon !== "auto") {
    if (!Number(horizon) || Number(horizon) <= 0) {
      setEditorStatus("시평은 1 이상의 숫자이거나 auto여야 합니다.");
      return;
    }
  }

  try {
    isAnalyzing = true;
    setRunAnalysisButtonState(true);

    if (analysisMode === "anomaly") {
      setEditorStatus("시계열 이상탐지를 실행하는 중입니다...");
    } else {
      setEditorStatus("시계열 예측 분석을 실행하는 중입니다...");
    }

    saveCurrentState();

    const result = await window.TIMEApi.runAnalysis(
      tableData,
      analysisMode,
      horizon,
      protectedCells,
      anomalyOptions
    );

    window.TIMEStorage.saveAnalysisResult(result);

    setEditorStatus("분석 완료. 결과 화면으로 이동합니다.");

    window.location.href = "./result.html";
  } catch (error) {
    console.error(error);
    setEditorStatus(error.message || "자동 분석 중 오류가 발생했습니다.");
  } finally {
    isAnalyzing = false;
    setRunAnalysisButtonState(false);
  }
}

function setRunAnalysisButtonState(isRunning) {
  if (!runAnalysisButton) return;

  runAnalysisButton.disabled = isRunning;

  if (isRunning) {
    runAnalysisButton.textContent =
      analysisMode === "anomaly"
        ? "이상탐지 중..."
        : "분석 중...";
    return;
  }

  runAnalysisButton.textContent =
    analysisMode === "anomaly"
      ? "이상탐지 실행"
      : "자동 분석 실행";
}


/* =========================================================
   16. 현재 상태 저장
========================================================= */

function saveCurrentState() {
  normalizeTableDataByColumns();

  window.TIMEStorage.saveTableData(tableData);
  window.TIMEStorage.saveColumnNames(columnNames);
  window.TIMEStorage.saveProtectedCells(protectedCells);
  window.TIMEStorage.saveHorizon(getCurrentHorizon());

  if (typeof window.TIMEStorage.saveAnalysisMode === "function") {
    window.TIMEStorage.saveAnalysisMode(analysisMode);
  }

  if (typeof window.TIMEStorage.saveAnomalyOptions === "function") {
    window.TIMEStorage.saveAnomalyOptions(getCurrentAnomalyOptions());
  }
}


/* =========================================================
   17. 상태 메시지
========================================================= */

function setEditorStatus(message) {
  if (editorStatus) {
    editorStatus.textContent = message;
  }
}