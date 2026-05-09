/* =========================================================
   TIME - frontend/js/result.js
---------------------------------------------------------
역할
1. localStorage에 저장된 분석 결과 불러오기
2. 요약 카드 렌더링
3. Plotly 통합 그래프 렌더링
4. 모델별 성능 비교 대시보드 렌더링
5. 뒤로가기 버튼 처리
========================================================= */

let analysisResult = null;

let summaryCards = null;
let metricsTableBody = null;
let resultStatus = null;


/* =========================================================
   1. 초기화
========================================================= */

document.addEventListener("DOMContentLoaded", () => {
  summaryCards = document.getElementById("summaryCards");
  metricsTableBody = document.getElementById("metricsTableBody");
  resultStatus = document.getElementById("resultStatus");

  bindResultEvents();
  loadResultData();
  renderResultPage();
});


/* =========================================================
   2. 이벤트 연결
========================================================= */

function bindResultEvents() {
  const backButton = document.getElementById("backButton");

  if (backButton) {
    backButton.addEventListener("click", () => {
      window.location.href = "./editor.html";
    });
  }
}


/* =========================================================
   3. 분석 결과 불러오기
========================================================= */

function loadResultData() {
  analysisResult = window.TIMEStorage.loadAnalysisResult();

  if (!analysisResult) {
    setResultStatus("분석 결과가 없습니다. 데이터 편집 화면에서 자동 분석을 먼저 실행하세요.");
  }
}


/* =========================================================
   4. 결과 화면 렌더링
========================================================= */

function renderResultPage() {
  if (!analysisResult) {
    return;
  }

  renderSummaryCards(analysisResult.summary || {});
  window.TIMEChart.renderForecastChart("forecastChart", analysisResult);
  renderMetricsDashboard(analysisResult.metrics_dashboard || []);

  setResultStatus("분석 결과가 표시되었습니다.");
}


/* =========================================================
   5. 요약 카드 렌더링
========================================================= */

function renderSummaryCards(summary) {
  if (!summaryCards) return;

  const cards = [
    {
      label: "Best Model",
      value: summary.best_model || "-",
    },
    {
      label: "Horizon",
      value: formatValue(summary.horizon),
    },
    {
      label: "Data Count",
      value: formatValue(summary.data_count),
    },
    {
      label: "Missing",
      value: formatValue(summary.missing_count),
    },
    {
      label: "Outlier",
      value: formatValue(summary.outlier_count),
    },
    {
      label: "Special",
      value: formatValue(summary.protected_count),
    },
  ];

  summaryCards.innerHTML = cards
    .map((card) => {
      return `
        <div class="summary-card">
          <div class="summary-label">${escapeHtml(card.label)}</div>
          <div class="summary-value">${escapeHtml(String(card.value))}</div>
        </div>
      `;
    })
    .join("");
}


/* =========================================================
   6. 모델별 성능 비교 대시보드 렌더링
========================================================= */

function renderMetricsDashboard(metricsDashboard) {
  if (!metricsTableBody) return;

  if (!Array.isArray(metricsDashboard) || metricsDashboard.length === 0) {
    metricsTableBody.innerHTML = `
      <tr>
        <td colspan="8">표시할 평가지표가 없습니다.</td>
      </tr>
    `;
    return;
  }

  metricsTableBody.innerHTML = metricsDashboard
    .map((row) => {
      return `
        <tr class="${Number(row.rank) === 1 ? "best-model-row" : ""}">
          <td>${escapeHtml(row.model || "-")}</td>
          <td>${formatValue(row.mae)}</td>
          <td>${formatValue(row.rmse)}</td>
          <td>${formatValue(row.mape)}</td>
          <td>${formatValue(row.smape)}</td>
          <td>${formatValue(row.aic)}</td>
          <td>${formatValue(row.bic)}</td>
          <td>${formatValue(row.rank)}</td>
        </tr>
      `;
    })
    .join("");
}


/* =========================================================
   7. 값 포맷
========================================================= */

function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      return "-";
    }

    return Number(value).toFixed(4).replace(/\.?0+$/, "");
  }

  return String(value);
}


/* =========================================================
   8. HTML Escape
========================================================= */

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


/* =========================================================
   9. 상태 메시지
========================================================= */

function setResultStatus(message) {
  if (resultStatus) {
    resultStatus.textContent = message;
  }
}