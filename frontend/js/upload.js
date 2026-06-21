/* =========================================================
   TIME - frontend/js/upload.js
---------------------------------------------------------
역할
1. upload.html의 CSV 파일 선택 감지
2. FastAPI /upload-csv로 CSV 전송
3. 응답받은 컬럼명과 행 데이터를 localStorage에 저장
4. 새 파일 업로드 시 기존 분석 결과 / 분석 모드 / 이상탐지 옵션 초기화
5. 업로드 성공 시 editor.html로 이동
========================================================= */


/* =========================================================
   1. 전역 변수
========================================================= */

let csvFileInput = null;
let uploadStatus = null;


/* =========================================================
   2. 초기화
========================================================= */

document.addEventListener("DOMContentLoaded", () => {
  csvFileInput = document.getElementById("csvFileInput");
  uploadStatus = document.getElementById("uploadStatus");

  if (!csvFileInput) {
    console.error("csvFileInput을 찾을 수 없습니다.");
    return;
  }

  csvFileInput.addEventListener("change", handleCSVUpload);
});


/* =========================================================
   3. CSV 업로드 처리
========================================================= */

async function handleCSVUpload(event) {
  const file = event.target.files[0];

  if (!file) {
    setUploadStatus("CSV 파일이 선택되지 않았습니다.");
    return;
  }

  if (!isCSVFile(file)) {
    setUploadStatus("CSV 파일만 업로드할 수 있습니다.");
    resetFileInput();
    return;
  }

  try {
    setUploadStatus("CSV 파일을 업로드하는 중입니다...");

    const result = await window.TIMEApi.uploadCSV(file);

    validateUploadResult(result);

    resetStorageForNewUpload();

    window.TIMEStorage.saveColumnNames(result.columns);
    window.TIMEStorage.saveTableData(result.rows);

    setUploadStatus("업로드 완료. 데이터 편집 화면으로 이동합니다.");

    window.location.href = "./editor.html";
  } catch (error) {
    console.error(error);
    setUploadStatus(error.message || "CSV 업로드 중 오류가 발생했습니다.");
    resetFileInput();
  }
}


/* =========================================================
   4. 파일 검증
========================================================= */

function isCSVFile(file) {
  if (!file || !file.name) {
    return false;
  }

  return file.name.toLowerCase().endsWith(".csv");
}


/* =========================================================
   5. 업로드 결과 검증
========================================================= */

function validateUploadResult(result) {
  if (!result) {
    throw new Error("서버에서 업로드 결과를 받지 못했습니다.");
  }

  if (!Array.isArray(result.columns) || result.columns.length === 0) {
    throw new Error("CSV 컬럼 정보를 읽을 수 없습니다.");
  }

  if (!Array.isArray(result.rows) || result.rows.length === 0) {
    throw new Error("CSV 데이터가 비어 있습니다.");
  }
}


/* =========================================================
   6. 새 업로드 기준 Storage 초기화
---------------------------------------------------------
새 CSV를 업로드하면 기존 분석 결과와 옵션이 남아 있으면 안 되므로
전체 저장소를 초기화한 뒤 기본 분석 설정을 다시 저장
========================================================= */

function resetStorageForNewUpload() {
  window.TIMEStorage.clearAllStorage();

  if (typeof window.TIMEStorage.resetAnalysisSettings === "function") {
    window.TIMEStorage.resetAnalysisSettings();
    return;
  }

  // 구버전 storage.js와의 안전한 호환
  window.TIMEStorage.saveHorizon(12);
  window.TIMEStorage.saveProtectedCells([]);

  if (typeof window.TIMEStorage.saveAnalysisMode === "function") {
    window.TIMEStorage.saveAnalysisMode("forecast");
  }

  if (typeof window.TIMEStorage.saveAnomalyOptions === "function") {
    window.TIMEStorage.saveAnomalyOptions({
      method: "auto",
      sensitivity: "medium",
    });
  }
}


/* =========================================================
   7. input 초기화
========================================================= */

function resetFileInput() {
  if (csvFileInput) {
    csvFileInput.value = "";
  }
}


/* =========================================================
   8. 상태 메시지
========================================================= */

function setUploadStatus(message) {
  if (uploadStatus) {
    uploadStatus.textContent = message;
  }
}