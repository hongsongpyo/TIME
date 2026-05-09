/* =========================================================
   TIME - frontend/js/api.js
---------------------------------------------------------
역할
1. FastAPI 서버 주소 관리
2. CSV 업로드 API 요청
3. 자동 분석 API 요청
4. API 응답/에러 공통 처리
========================================================= */


/* =========================================================
   1. API 기본 설정
========================================================= */

const API_BASE_URL = "https://time-api.onrender.com";


/* =========================================================
   2. 공통 응답 처리
========================================================= */

async function handleResponse(response) {
  let data = null;

  try {
    data = await response.json();
  } catch (error) {
    throw new Error("서버 응답을 읽을 수 없습니다.");
  }

  if (!response.ok) {
    const message = data.detail || "요청 처리 중 오류가 발생했습니다.";
    throw new Error(message);
  }

  return data;
}


/* =========================================================
   3. 서버 상태 확인
========================================================= */

async function checkServerHealth() {
  const response = await fetch(`${API_BASE_URL}/health`);
  return handleResponse(response);
}


/* =========================================================
   4. CSV 업로드 요청
---------------------------------------------------------
upload.html에서 사용
========================================================= */

async function uploadCSV(file) {
  if (!file) {
    throw new Error("업로드할 CSV 파일이 없습니다.");
  }

  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/upload-csv`, {
    method: "POST",
    body: formData,
  });

  return handleResponse(response);
}


/* =========================================================
   5. 자동 분석 요청
---------------------------------------------------------
editor.html에서 사용
========================================================= */

async function runAnalysis(tableData, horizon, protectedCells) {
  if (!tableData || tableData.length === 0) {
    throw new Error("분석할 데이터가 없습니다.");
  }

  const payload = {
    data: tableData,
    horizon: Number(horizon),
    protected_cells: protectedCells || [],
  };

  const response = await fetch(`${API_BASE_URL}/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  return handleResponse(response);
}


/* =========================================================
   6. 전역 객체 등록
========================================================= */

window.TIMEApi = {
  API_BASE_URL,
  checkServerHealth,
  uploadCSV,
  runAnalysis,
};