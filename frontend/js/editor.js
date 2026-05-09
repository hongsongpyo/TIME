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
7. 자동 분석 실행 후 result.html로 이동
========================================================= */

let tableData = [];
let columnNames = [];
let protectedCells = [];
let specialMode = false;

let tableHead = null;
let tableBody = null;
let horizonInput = null;
let editorStatus = null;


/* =========================================================
   1. 초기화
========================================================= */

document.addEventListener("DOMContentLoaded", () => {
  tableHead = document.getElementById("tableHead");
  tableBody = document.getElementById("tableBody");
  horizonInput = document.getElementById("horizonInput");
  editorStatus = document.getElementById("editorStatus");

  bindEditorEvents();
  loadEditorData();
  renderTable();
});


/* =========================================================
   2. 이벤트 연결
========================================================= */

function bindEditorEvents() {
  const backButton = document.getElementById("backButton");
  const addRowButton = document.getElementById("addRowButton");
  const addColumnButton = document.getElementById("addColumnButton");
  const specialModeButton = document.getElementById("specialModeButton");
  const runAnalysisButton = document.getElementById("runAnalysisButton");

  if (backButton) {
    backButton.addEventListener("click", () => {
      saveCurrentState();
      window.location.href = "./upload.html";
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
}


/* =========================================================
   3. 데이터 불러오기
========================================================= */

function loadEditorData() {
  tableData = window.TIMEStorage.loadTableData();
  columnNames = window.TIMEStorage.loadColumnNames();
  protectedCells = window.TIMEStorage.loadProtectedCells();

  const horizon = window.TIMEStorage.loadHorizon();

  if (horizonInput) {
    horizonInput.value = horizon || 12;
  }

  if (!tableData || tableData.length === 0) {
    setEditorStatus("업로드된 데이터가 없습니다. 업로드 화면으로 돌아가 CSV를 선택하세요.");
    tableData = [];
  }

  if ((!columnNames || columnNames.length === 0) && tableData.length > 0) {
    columnNames = Object.keys(tableData[0]);
  }
}


/* =========================================================
   4. 표 렌더링
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
   5. 셀 값 수정
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
   6. 컬럼명 수정
========================================================= */

function handleColumnNameEdit(event) {
  const th = event.target;
  const columnIndex = Number(th.dataset.columnIndex);
  const oldColumnName = columnNames[columnIndex];
  let newColumnName = th.textContent.trim();

  if (!newColumnName) {
    newColumnName = oldColumnName;
  }

  if (columnNames.includes(newColumnName) && newColumnName !== oldColumnName) {
    setEditorStatus("이미 존재하는 컬럼명입니다.");
    th.textContent = oldColumnName;
    return;
  }

  columnNames[columnIndex] = newColumnName;

  tableData = tableData.map((row) => {
    const newRow = {};

    columnNames.forEach((column) => {
      if (column === newColumnName) {
        newRow[column] = row[oldColumnName] ?? "";
      } else {
        newRow[column] = row[column] ?? "";
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


/* =========================================================
   7. 행 추가
========================================================= */

function handleAddRow() {
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
   8. 열 추가
========================================================= */

function handleAddColumn() {
  let newColumnName = `new_column_${columnNames.length + 1}`;

  while (columnNames.includes(newColumnName)) {
    newColumnName = `new_column_${columnNames.length + 1}_${Date.now()}`;
  }

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
   9. 특이치 설정
========================================================= */

function handleToggleSpecialMode() {
  specialMode = !specialMode;

  const specialModeButton = document.getElementById("specialModeButton");

  if (specialModeButton) {
    specialModeButton.classList.toggle("active", specialMode);
    specialModeButton.textContent = specialMode ? "특이치 설정 중" : "특이치 설정";
  }

  setEditorStatus(
    specialMode
      ? "특이치 설정 모드입니다. 셀을 클릭하면 특이치로 지정/해제됩니다."
      : "특이치 설정 모드가 해제되었습니다."
  );
}

function isProtectedCell(rowIndex, columnName) {
  return protectedCells.some((cell) => {
    return cell.row === rowIndex && cell.column === columnName;
  });
}

function toggleProtectedCell(rowIndex, columnName) {
  const exists = isProtectedCell(rowIndex, columnName);

  if (exists) {
    protectedCells = protectedCells.filter((cell) => {
      return !(cell.row === rowIndex && cell.column === columnName);
    });
  } else {
    protectedCells.push({
      row: rowIndex,
      column: columnName,
    });
  }
}


/* =========================================================
   10. 자동 분석 실행
========================================================= */

async function handleRunAnalysis() {
  saveCurrentState();

  if (!tableData || tableData.length === 0) {
    setEditorStatus("분석할 데이터가 없습니다.");
    return;
  }

  const horizon = Number(horizonInput.value);

  if (!horizon || horizon <= 0) {
    setEditorStatus("시평은 1 이상의 숫자로 입력하세요.");
    return;
  }

  try {
    setEditorStatus("자동 분석을 실행하는 중입니다...");

    const result = await window.TIMEApi.runAnalysis(
      tableData,
      horizon,
      protectedCells
    );

    window.TIMEStorage.saveAnalysisResult(result);

    setEditorStatus("분석 완료. 결과 화면으로 이동합니다.");
    window.location.href = "./result.html";
  } catch (error) {
    console.error(error);
    setEditorStatus(error.message || "자동 분석 중 오류가 발생했습니다.");
  }
}


/* =========================================================
   11. 현재 상태 저장
========================================================= */

function saveCurrentState() {
  const horizon = horizonInput ? Number(horizonInput.value) : 12;

  window.TIMEStorage.saveTableData(tableData);
  window.TIMEStorage.saveColumnNames(columnNames);
  window.TIMEStorage.saveHorizon(horizon);
  window.TIMEStorage.saveProtectedCells(protectedCells);
}


/* =========================================================
   12. 상태 메시지
========================================================= */

function setEditorStatus(message) {
  if (editorStatus) {
    editorStatus.textContent = message;
  }
}