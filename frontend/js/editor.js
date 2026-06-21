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
7. 이상탐지 방식 / 민감도 옵션 관리
8. 다변량 시계열 이상탐지 실행 후 result.html로 이동
9. 기존 forecast/horizon 요소가 남아 있어도 오류 없이 동작
10. 전역 변수 충돌 방지
========================================================= */

(function () {
  "use strict";


  /* =========================================================
     1. 전역 상태
  ========================================================= */

  let tableData = [];
  let columnNames = [];
  let protectedCells = [];
  let specialMode = false;

  const analysisMode = "anomaly";

  let anomalyOptions = {
    method: "auto",
    sensitivity: "medium",
  };

  let tableHead = null;
  let tableBody = null;

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

    anomalyModeButton = document.getElementById("anomalyModeButton");
    anomalyOptionPanel = document.getElementById("anomalyOptionPanel");
    anomalyMethodSelect = document.getElementById("anomalyMethodSelect");
    anomalySensitivitySelect = document.getElementById("anomalySensitivitySelect");

    editorStatus = document.getElementById("editorStatus");
    runAnalysisButton = document.getElementById("runAnalysisButton");

    try {
      checkRequiredModules();

      bindEditorEvents();
      loadEditorData();
      normalizeTableDataByColumns();
      renderTable();
      updateAnalysisModeUI();
      updateAnomalyOptionUI();

      if (tableData.length > 0) {
        setEditorStatus("데이터를 확인한 뒤 이상탐지를 실행하세요.");
      }
    } catch (error) {
      console.error(error);
      setEditorStatus(error.message || "데이터 편집 화면을 불러오는 중 오류가 발생했습니다.");
    }
  });


  /* =========================================================
     3. 필수 모듈 확인
  ========================================================= */

  function checkRequiredModules() {
    if (!window.TIMEStorage) {
      throw new Error("Storage 모듈을 찾을 수 없습니다. storage.js 연결을 확인하세요.");
    }

    if (!window.TIMEApi) {
      throw new Error("API 모듈을 찾을 수 없습니다. api.js 연결을 확인하세요.");
    }
  }


  /* =========================================================
     4. 이벤트 연결
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

    if (anomalyModeButton) {
      anomalyModeButton.addEventListener("click", () => {
        setEditorStatus("현재 분석 모드는 이상탐지입니다.");
        saveCurrentState();
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

    if (anomalyMethodSelect) {
      anomalyMethodSelect.addEventListener("change", () => {
        anomalyOptions.method = normalizeAnomalyMethod(anomalyMethodSelect.value);
        saveCurrentState();
        setEditorStatus("이상탐지 방식이 변경되었습니다.");
      });
    }

    if (anomalySensitivitySelect) {
      anomalySensitivitySelect.addEventListener("change", () => {
        anomalyOptions.sensitivity = normalizeAnomalySensitivity(
          anomalySensitivitySelect.value
        );
        saveCurrentState();
        setEditorStatus("이상탐지 민감도가 변경되었습니다.");
      });
    }

    window.addEventListener("beforeunload", () => {
      saveCurrentState();
    });
  }


  /* =========================================================
     5. 데이터 불러오기
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

    if (typeof window.TIMEStorage.loadAnalysisMode === "function") {
      const savedMode = window.TIMEStorage.loadAnalysisMode();

      if (savedMode !== "anomaly") {
        window.TIMEStorage.saveAnalysisMode("anomaly");
      }
    }

    if (typeof window.TIMEStorage.loadAnomalyOptions === "function") {
      anomalyOptions = window.TIMEStorage.loadAnomalyOptions();
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
     6. 데이터 정규화
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
        normalizedRow[columnName] =
          row && row[columnName] !== undefined && row[columnName] !== null
            ? row[columnName]
            : "";
      });

      return normalizedRow;
    });

    protectedCells = normalizeProtectedCells(protectedCells);
  }

  function normalizeProtectedCells(cells) {
    if (!Array.isArray(cells)) {
      return [];
    }

    return cells
      .filter((cell) => {
        if (!cell) {
          return false;
        }

        const rowIndex = Number(cell.row);
        const columnName = String(cell.column || "");

        return (
          Number.isInteger(rowIndex) &&
          rowIndex >= 0 &&
          rowIndex < tableData.length &&
          columnNames.includes(columnName)
        );
      })
      .map((cell) => {
        return {
          row: Number(cell.row),
          column: String(cell.column),
        };
      });
  }


  /* =========================================================
     7. 표 렌더링
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
      th.title = "컬럼명을 클릭해서 수정할 수 있습니다.";

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

        td.contentEditable = specialMode ? "false" : "true";
        td.textContent = row[columnName] ?? "";
        td.dataset.rowIndex = String(rowIndex);
        td.dataset.columnIndex = String(columnIndex);
        td.dataset.columnName = columnName;

        if (isProtectedCell(rowIndex, columnName)) {
          td.classList.add("special-cell");
          td.title = "사용자가 보호한 특이치 셀입니다.";
        } else if (specialMode) {
          td.title = "클릭하면 특이치 보호 셀로 지정됩니다.";
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
     8. 셀 값 수정
  ========================================================= */

  function handleCellEdit(event) {
    if (specialMode) {
      return;
    }

    const td = event.target;
    const rowIndex = Number(td.dataset.rowIndex);
    const columnName = td.dataset.columnName;

    if (!tableData[rowIndex]) return;

    tableData[rowIndex][columnName] = td.textContent.trim();

    clearPreviousAnalysisResult();
    saveCurrentState();
  }

  function handleCellClick(event) {
    if (!specialMode) return;

    event.preventDefault();

    const td = event.target;
    const rowIndex = Number(td.dataset.rowIndex);
    const columnName = td.dataset.columnName;

    toggleProtectedCell(rowIndex, columnName);
    clearPreviousAnalysisResult();
    saveCurrentState();
    renderTable();
  }

  function handleCellKeyDown(event) {
    if (event.key === "Enter") {
      event.preventDefault();
      event.target.blur();
    }

    if (event.key === "Escape") {
      event.preventDefault();
      event.target.blur();
      renderTable();
    }
  }


  /* =========================================================
     9. 컬럼명 수정
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

    clearPreviousAnalysisResult();
    saveCurrentState();
    renderTable();
  }

  function handleHeaderKeyDown(event) {
    if (event.key === "Enter") {
      event.preventDefault();
      event.target.blur();
    }

    if (event.key === "Escape") {
      event.preventDefault();
      event.target.blur();
      renderTable();
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
     10. 행 추가
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

    clearPreviousAnalysisResult();
    saveCurrentState();
    renderTable();

    setEditorStatus("새 행이 추가되었습니다.");
  }


  /* =========================================================
     11. 열 추가
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

    clearPreviousAnalysisResult();
    saveCurrentState();
    renderTable();

    setEditorStatus("새 열이 추가되었습니다.");
  }


  /* =========================================================
     12. 특이치 설정 모드
  ========================================================= */

  function handleToggleSpecialMode() {
    specialMode = !specialMode;

    const specialModeButton = document.getElementById("specialModeButton");

    if (specialModeButton) {
      specialModeButton.classList.toggle("active", specialMode);
    }

    renderTable();

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
    if (
      !Number.isInteger(Number(rowIndex)) ||
      Number(rowIndex) < 0 ||
      Number(rowIndex) >= tableData.length ||
      !columnNames.includes(columnName)
    ) {
      return;
    }

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
     13. 분석 모드 UI
  ========================================================= */

  function updateAnalysisModeUI() {
    if (anomalyModeButton) {
      anomalyModeButton.classList.add("active");
    }

    if (anomalyOptionPanel) {
      anomalyOptionPanel.hidden = false;
    }

    if (runAnalysisButton) {
      runAnalysisButton.textContent = "이상탐지 실행";
    }

    if (typeof window.TIMEStorage.saveAnalysisMode === "function") {
      window.TIMEStorage.saveAnalysisMode("anomaly");
    }
  }


  /* =========================================================
     14. 이상탐지 옵션
  ========================================================= */

  function normalizeAnomalyMethod(method) {
    if (
      window.TIMEStorage &&
      typeof window.TIMEStorage.normalizeAnomalyMethod === "function"
    ) {
      return window.TIMEStorage.normalizeAnomalyMethod(method);
    }

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
    if (
      window.TIMEStorage &&
      typeof window.TIMEStorage.normalizeAnomalySensitivity === "function"
    ) {
      return window.TIMEStorage.normalizeAnomalySensitivity(sensitivity);
    }

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
    if (
      window.TIMEStorage &&
      typeof window.TIMEStorage.normalizeAnomalyOptions === "function"
    ) {
      return window.TIMEStorage.normalizeAnomalyOptions(options);
    }

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
     15. 자동 이상탐지 실행
  ========================================================= */

  async function handleRunAnalysis() {
    if (isAnalyzing) {
      return;
    }

    normalizeTableDataByColumns();

    if (!validateBeforeAnalysis()) {
      return;
    }

    anomalyOptions = getCurrentAnomalyOptions();

    try {
      isAnalyzing = true;
      setRunAnalysisButtonState(true);

      setEditorStatus("다변량 시계열 이상탐지를 실행하는 중입니다...");

      saveCurrentState();

      let result = null;

      if (
        window.TIMEApi &&
        typeof window.TIMEApi.runAnomalyAnalysis === "function"
      ) {
        result = await window.TIMEApi.runAnomalyAnalysis(
          tableData,
          protectedCells,
          anomalyOptions
        );
      } else {
        result = await window.TIMEApi.runAnalysis(
          tableData,
          protectedCells,
          anomalyOptions
        );
      }

      window.TIMEStorage.saveAnalysisResult(result);

      if (typeof window.TIMEStorage.saveSelectedAnomalyView === "function") {
        window.TIMEStorage.saveSelectedAnomalyView("timeline");
      }

      setEditorStatus("이상탐지 완료. 결과 화면으로 이동합니다.");

      window.location.href = "./result.html";
    } catch (error) {
      console.error(error);
      setEditorStatus(error.message || "이상탐지 중 오류가 발생했습니다.");
    } finally {
      isAnalyzing = false;
      setRunAnalysisButtonState(false);
    }
  }

  function validateBeforeAnalysis() {
    if (!tableData || tableData.length === 0) {
      setEditorStatus("분석할 데이터가 없습니다. CSV 파일을 먼저 업로드하세요.");
      return false;
    }

    if (!columnNames || columnNames.length === 0) {
      setEditorStatus("분석할 컬럼이 없습니다.");
      return false;
    }

    if (columnNames.length < 2) {
      setEditorStatus("날짜 컬럼과 숫자형 변수 컬럼이 최소 1개 이상 필요합니다.");
      return false;
    }

    const nonEmptyRowCount = tableData.filter((row) => {
      return columnNames.some((columnName) => {
        return String(row[columnName] ?? "").trim() !== "";
      });
    }).length;

    if (nonEmptyRowCount === 0) {
      setEditorStatus("분석할 값이 없습니다.");
      return false;
    }

    return true;
  }

  function setRunAnalysisButtonState(isRunning) {
    if (!runAnalysisButton) return;

    runAnalysisButton.disabled = isRunning;

    if (isRunning) {
      runAnalysisButton.textContent = "이상탐지 중...";
      return;
    }

    runAnalysisButton.textContent = "이상탐지 실행";
  }


  /* =========================================================
     16. 현재 상태 저장
  ========================================================= */

  function saveCurrentState() {
    normalizeTableDataByColumns();

    window.TIMEStorage.saveTableData(tableData);
    window.TIMEStorage.saveColumnNames(columnNames);
    window.TIMEStorage.saveProtectedCells(protectedCells);

    if (typeof window.TIMEStorage.saveHorizon === "function") {
      window.TIMEStorage.saveHorizon(12);
    }

    if (typeof window.TIMEStorage.saveAnalysisMode === "function") {
      window.TIMEStorage.saveAnalysisMode("anomaly");
    }

    if (typeof window.TIMEStorage.saveAnomalyOptions === "function") {
      window.TIMEStorage.saveAnomalyOptions(getCurrentAnomalyOptions());
    }
  }

  function clearPreviousAnalysisResult() {
    if (
      window.TIMEStorage &&
      typeof window.TIMEStorage.resetOnlyAnalysisResult === "function"
    ) {
      window.TIMEStorage.resetOnlyAnalysisResult();
      return;
    }

    if (
      window.TIMEStorage &&
      typeof window.TIMEStorage.clearAnalysisResult === "function"
    ) {
      window.TIMEStorage.clearAnalysisResult();
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
})();