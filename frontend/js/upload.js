/* =========================================================
   TIME - frontend/js/upload.js
---------------------------------------------------------
역할
1. upload.html의 CSV 파일 선택 감지
2. FastAPI /upload-csv로 CSV 전송
3. 응답받은 컬럼명과 행 데이터를 localStorage에 저장
4. 업로드 성공 시 editor.html로 이동
========================================================= */

let csvFileInput = null;
let uploadStatus = null;

document.addEventListener("DOMContentLoaded", () => {
  csvFileInput = document.getElementById("csvFileInput");
  uploadStatus = document.getElementById("uploadStatus");

  if (!csvFileInput) {
    console.error("csvFileInput을 찾을 수 없습니다.");
    return;
  }

  csvFileInput.addEventListener("change", handleCSVUpload);
});

async function handleCSVUpload(event) {
  const file = event.target.files[0];

  if (!file) {
    setUploadStatus("CSV 파일이 선택되지 않았습니다.");
    return;
  }

  if (!file.name.toLowerCase().endsWith(".csv")) {
    setUploadStatus("CSV 파일만 업로드할 수 있습니다.");
    return;
  }

  try {
    setUploadStatus("CSV 파일을 업로드하는 중입니다...");

    const result = await window.TIMEApi.uploadCSV(file);

    window.TIMEStorage.clearAllStorage();
    window.TIMEStorage.saveColumnNames(result.columns);
    window.TIMEStorage.saveTableData(result.rows);
    window.TIMEStorage.saveHorizon(12);
    window.TIMEStorage.saveProtectedCells([]);

    setUploadStatus("업로드 완료. 데이터 편집 화면으로 이동합니다.");

    window.location.href = "./editor.html";
  } catch (error) {
    console.error(error);
    setUploadStatus(error.message || "CSV 업로드 중 오류가 발생했습니다.");
  }
}

function setUploadStatus(message) {
  if (uploadStatus) {
    uploadStatus.textContent = message;
  }
}