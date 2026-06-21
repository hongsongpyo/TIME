/* =========================================================
   TIME - frontend/js/upload.js
---------------------------------------------------------
역할
1. upload.html의 CSV 파일 선택 감지
2. FastAPI /upload-csv로 CSV 전송
3. 응답받은 컬럼명과 행 데이터를 localStorage에 저장
4. 새 파일 업로드 시 기존 분석 결과 / 이상탐지 옵션 초기화
5. 기본 분석 모드를 이상탐지로 설정
6. 업로드 성공 시 editor.html로 이동
7. 전역 변수 충돌 방지
========================================================= */

(function () {
  "use strict";


  /* =========================================================
     1. 전역 변수
  ========================================================= */

  let csvFileInput = null;
  let uploadStatus = null;


  /* =========================================================
     2. 기본값
  ========================================================= */

  const DEFAULT_ANOMALY_OPTIONS = {
    method: "auto",
    sensitivity: "medium",
  };

  const DEFAULT_ANALYSIS_MODE = "anomaly";
  const DEFAULT_ANOMALY_VIEW = "timeline";


  /* =========================================================
     3. 초기화
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
     4. CSV 업로드 처리
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
      checkRequiredModules();

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
     5. 필수 모듈 확인
  ========================================================= */

  function checkRequiredModules() {
    if (!window.TIMEApi || typeof window.TIMEApi.uploadCSV !== "function") {
      throw new Error("API 모듈을 찾을 수 없습니다. api.js 연결을 확인하세요.");
    }

    if (!window.TIMEStorage) {
      throw new Error("Storage 모듈을 찾을 수 없습니다. storage.js 연결을 확인하세요.");
    }
  }


  /* =========================================================
     6. 파일 검증
  ========================================================= */

  function isCSVFile(file) {
    if (!file || !file.name) {
      return false;
    }

    return file.name.toLowerCase().endsWith(".csv");
  }


  /* =========================================================
     7. 업로드 결과 검증
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
     8. 새 업로드 기준 Storage 초기화
  ---------------------------------------------------------
  새 CSV를 업로드하면 이전 CSV의 분석 결과, 특이치 셀,
  이상탐지 결과, 선택 메뉴 상태가 남아 있으면 안 됨.
  ========================================================= */

  function resetStorageForNewUpload() {
    if (typeof window.TIMEStorage.clearAllStorage === "function") {
      window.TIMEStorage.clearAllStorage();
    }

    if (typeof window.TIMEStorage.resetAnalysisSettings === "function") {
      window.TIMEStorage.resetAnalysisSettings();
      return;
    }

    resetStorageFallback();
  }


  /* =========================================================
     9. 구버전 storage.js 호환 초기화
  ========================================================= */

  function resetStorageFallback() {
    if (typeof window.TIMEStorage.saveHorizon === "function") {
      window.TIMEStorage.saveHorizon(12);
    }

    if (typeof window.TIMEStorage.saveProtectedCells === "function") {
      window.TIMEStorage.saveProtectedCells([]);
    }

    if (typeof window.TIMEStorage.clearAnalysisResult === "function") {
      window.TIMEStorage.clearAnalysisResult();
    }

    if (typeof window.TIMEStorage.saveAnalysisMode === "function") {
      window.TIMEStorage.saveAnalysisMode(DEFAULT_ANALYSIS_MODE);
    }

    if (typeof window.TIMEStorage.saveAnomalyOptions === "function") {
      window.TIMEStorage.saveAnomalyOptions(DEFAULT_ANOMALY_OPTIONS);
    }

    if (typeof window.TIMEStorage.saveSelectedAnomalyView === "function") {
      window.TIMEStorage.saveSelectedAnomalyView(DEFAULT_ANOMALY_VIEW);
    }

    if (typeof window.TIMEStorage.clearSelectedAnomalyDate === "function") {
      window.TIMEStorage.clearSelectedAnomalyDate();
    }
  }


  /* =========================================================
     10. input 초기화
  ========================================================= */

  function resetFileInput() {
    if (csvFileInput) {
      csvFileInput.value = "";
    }
  }


  /* =========================================================
     11. 상태 메시지
  ========================================================= */

  function setUploadStatus(message) {
    if (uploadStatus) {
      uploadStatus.textContent = message;
    }
  }
})();