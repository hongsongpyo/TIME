/* =========================================================
   TIME - frontend/js/result.js
---------------------------------------------------------
역할
1. localStorage에 저장된 분석 결과 불러오기
2. summary.mode 기준으로 forecast/anomaly 결과 화면 분기
3. 예측 모드 요약 카드, Plotly 예측 그래프, 모델 성능표 렌더링
4. 이상탐지 모드 요약 카드, 이상탐지 그래프, 해석, 기여도, 이상 시점표 렌더링
5. 뒤로가기 버튼 처리
========================================================= */


/* =========================================================
   1. 전역 상태
========================================================= */

let analysisResult = null;

let resultPageTitle = null;
let resultPageDescription = null;

let summaryCards = null;
let metricsTableBody = null;

let forecastResultSection = null;
let anomalyResultSection = null;

let anomalyInterpretationList = null;
let featureContributionTableBody = null;
let anomalyTableBody = null;

let resultStatus = null;


/* =========================================================
   2. 초기화
========================================================= */

document.addEventListener("DOMContentLoaded", () => {
  resultPageTitle = document.getElementById("resultPageTitle");
  resultPageDescription = document.getElementById("resultPageDescription");

  summaryCards = document.getElementById("summaryCards");
  metricsTableBody = document.getElementById("metricsTableBody");

  forecastResultSection = document.getElementById("forecastResultSection");
  anomalyResultSection = document.getElementById("anomalyResultSection");

  anomalyInterpretationList = document.getElementById("anomalyInterpretationList");
  featureContributionTableBody = document.getElementById("featureContributionTableBody");
  anomalyTableBody = document.getElementById("anomalyTableBody");

  resultStatus = document.getElementById("resultStatus");

  bindResultEvents();
  loadResultData();
  renderResultPage();
});


/* =========================================================
   3. 이벤트 연결
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
   4. 분석 결과 불러오기
========================================================= */

function loadResultData() {
  if (
    !window.TIMEStorage ||
    typeof window.TIMEStorage.loadAnalysisResult !== "function"
  ) {
    setResultStatus("저장소 모듈을 찾을 수 없습니다.");
    return;
  }

  analysisResult = window.TIMEStorage.loadAnalysisResult();

  if (!analysisResult) {
    setResultStatus("분석 결과가 없습니다. 데이터 편집 화면에서 자동 분석을 먼저 실행하세요.");
  }
}


/* =========================================================
   5. 결과 화면 렌더링 분기
========================================================= */

function renderResultPage() {
  if (!analysisResult) {
    hideForecastSection();
    hideAnomalySection();
    return;
  }

  const mode = getResultMode(analysisResult);

  if (mode === "anomaly") {
    renderAnomalyResultPage();
    return;
  }

  renderForecastResultPage();
}

function getResultMode(result) {
  const summary = result.summary || {};
  const mode = String(summary.mode || "").toLowerCase();

  if (mode === "anomaly") {
    return "anomaly";
  }

  if (
    result.anomaly_series ||
    result.multivariate_series ||
    result.anomaly_table ||
    result.raw_anomaly_result
  ) {
    return "anomaly";
  }

  return "forecast";
}


/* =========================================================
   6. Section 표시/숨김
========================================================= */

function showForecastSection() {
  if (forecastResultSection) {
    forecastResultSection.hidden = false;
  }
}

function hideForecastSection() {
  if (forecastResultSection) {
    forecastResultSection.hidden = true;
  }
}

function showAnomalySection() {
  if (anomalyResultSection) {
    anomalyResultSection.hidden = false;
  }
}

function hideAnomalySection() {
  if (anomalyResultSection) {
    anomalyResultSection.hidden = true;
  }
}


/* =========================================================
   7. 예측 결과 화면 렌더링
========================================================= */

function renderForecastResultPage() {
  showForecastSection();
  hideAnomalySection();

  if (resultPageTitle) {
    resultPageTitle.textContent = "예측 결과 시각화";
  }

  if (resultPageDescription) {
    resultPageDescription.textContent =
      "legend를 클릭하면 원하는 그래프만 켜고 끌 수 있습니다.";
  }

  renderForecastSummaryCards(analysisResult.summary || {});

  if (
    window.TIMEChart &&
    typeof window.TIMEChart.renderForecastChart === "function"
  ) {
    window.TIMEChart.renderForecastChart("forecastChart", analysisResult);
  } else {
    setResultStatus("예측 그래프 모듈을 찾을 수 없습니다.");
  }

  renderMetricsDashboard(analysisResult.metrics_dashboard || []);

  setResultStatus("예측 분석 결과가 표시되었습니다.");
}


/* =========================================================
   8. 이상탐지 결과 화면 렌더링
========================================================= */

function renderAnomalyResultPage() {
  hideForecastSection();
  showAnomalySection();

  if (resultPageTitle) {
    resultPageTitle.textContent = "이상탐지 결과 시각화";
  }

  if (resultPageDescription) {
    resultPageDescription.textContent =
      "다변량 시계열의 이상 시점, anomaly score, 변수별 기여도를 확인합니다.";
  }

  renderAnomalySummaryCards(analysisResult.summary || {});

  if (
    window.TIMEAnomalyChart &&
    typeof window.TIMEAnomalyChart.renderAllAnomalyCharts === "function"
  ) {
    window.TIMEAnomalyChart.renderAllAnomalyCharts(analysisResult);
  } else {
    setResultStatus("이상탐지 그래프 모듈을 찾을 수 없습니다.");
  }

  renderAnomalyInterpretation(getAnomalyInterpretation());
  renderFeatureContributionTable(getFeatureContributionRows());
  renderAnomalyTable(getAnomalyTableRows());

  setResultStatus("이상탐지 분석 결과가 표시되었습니다.");
}


/* =========================================================
   9. 예측 요약 카드 렌더링
========================================================= */

function renderForecastSummaryCards(summary) {
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
      return makeSummaryCard(card.label, card.value);
    })
    .join("");
}


/* =========================================================
   10. 이상탐지 요약 카드 렌더링
========================================================= */

function renderAnomalySummaryCards(summary) {
  if (!summaryCards) return;

  const methodText =
    summary.method ||
    summary.resolved_method ||
    summary.detector ||
    "-";

  const cards = [
    {
      label: "Method",
      value: methodText,
    },
    {
      label: "Sensitivity",
      value: formatSensitivity(summary.sensitivity),
    },
    {
      label: "Data Count",
      value: formatValue(summary.data_count),
    },
    {
      label: "Variables",
      value: formatValue(summary.variable_count),
    },
    {
      label: "Anomaly Count",
      value: formatValue(summary.anomaly_count),
    },
    {
      label: "Anomaly Ratio",
      value: formatPercentSmart(summary.anomaly_ratio),
    },
    {
      label: "Threshold",
      value: formatValue(summary.threshold),
    },
    {
      label: "Top Anomaly",
      value: summary.top_anomaly_date || "-",
    },
    {
      label: "Top Score",
      value: formatValue(summary.top_anomaly_score),
    },
    {
      label: "Special",
      value: formatValue(summary.protected_count),
    },
  ];

  summaryCards.innerHTML = cards
    .map((card) => {
      return makeSummaryCard(card.label, card.value);
    })
    .join("");
}

function makeSummaryCard(label, value) {
  return `
    <div class="summary-card">
      <div class="summary-label">${escapeHtml(label)}</div>
      <div class="summary-value">${escapeHtml(String(value))}</div>
    </div>
  `;
}


/* =========================================================
   11. 모델별 성능 비교 대시보드 렌더링
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
   12. 이상탐지 해석 데이터 가져오기
========================================================= */

function getAnomalyInterpretation() {
  if (!analysisResult) {
    return [];
  }

  if (Array.isArray(analysisResult.interpretation)) {
    return analysisResult.interpretation;
  }

  if (Array.isArray(analysisResult.anomaly_interpretation)) {
    return analysisResult.anomaly_interpretation;
  }

  if (
    analysisResult.summary &&
    Array.isArray(analysisResult.summary.interpretation)
  ) {
    return analysisResult.summary.interpretation;
  }

  return [];
}


/* =========================================================
   13. 이상탐지 해석 렌더링
========================================================= */

function renderAnomalyInterpretation(interpretation) {
  if (!anomalyInterpretationList) return;

  if (!Array.isArray(interpretation) || interpretation.length === 0) {
    anomalyInterpretationList.innerHTML = `
      <li>표시할 이상탐지 해석 문구가 없습니다.</li>
    `;
    return;
  }

  anomalyInterpretationList.innerHTML = interpretation
    .map((message) => {
      if (typeof message === "string") {
        return `<li>${escapeHtml(message)}</li>`;
      }

      if (message && typeof message === "object") {
        const title = message.title || message.label || "해석";
        const text = message.message || message.text || message.description || "";

        return `
          <li>
            <strong>${escapeHtml(title)}</strong>
            ${text ? ` - ${escapeHtml(text)}` : ""}
          </li>
        `;
      }

      return `<li>${escapeHtml(String(message))}</li>`;
    })
    .join("");
}


/* =========================================================
   14. 변수별 이상 기여도 데이터 가져오기
========================================================= */

function getFeatureContributionRows() {
  if (!analysisResult) {
    return [];
  }

  if (Array.isArray(analysisResult.feature_contribution)) {
    return analysisResult.feature_contribution;
  }

  if (
    analysisResult.raw_anomaly_result &&
    Array.isArray(analysisResult.raw_anomaly_result.feature_contribution)
  ) {
    return analysisResult.raw_anomaly_result.feature_contribution;
  }

  return [];
}


/* =========================================================
   15. 변수별 이상 기여도 테이블 렌더링
========================================================= */

function renderFeatureContributionTable(featureContribution) {
  if (!featureContributionTableBody) return;

  if (!Array.isArray(featureContribution) || featureContribution.length === 0) {
    featureContributionTableBody.innerHTML = `
      <tr>
        <td colspan="6">표시할 변수별 기여도 데이터가 없습니다.</td>
      </tr>
    `;
    return;
  }

  featureContributionTableBody.innerHTML = featureContribution
    .map((row, index) => {
      const rank = row.rank ?? index + 1;
      const countValue =
        row.main_count ??
        row.anomaly_count ??
        row.count ??
        row.main_feature_count ??
        null;

      return `
        <tr>
          <td>${formatValue(rank)}</td>
          <td>${escapeHtml(row.feature || row.column || "-")}</td>
          <td>${formatValue(row.mean_score)}</td>
          <td>${formatValue(row.max_score)}</td>
          <td>${formatPercentSmart(row.contribution_ratio)}</td>
          <td>${formatValue(countValue)}</td>
        </tr>
      `;
    })
    .join("");
}


/* =========================================================
   16. 이상 시점 테이블 데이터 가져오기
========================================================= */

function getAnomalyTableRows() {
  if (!analysisResult) {
    return [];
  }

  if (Array.isArray(analysisResult.anomaly_table)) {
    return analysisResult.anomaly_table;
  }

  if (
    analysisResult.raw_anomaly_result &&
    Array.isArray(analysisResult.raw_anomaly_result.anomaly_table)
  ) {
    return analysisResult.raw_anomaly_result.anomaly_table;
  }

  return [];
}


/* =========================================================
   17. 이상 시점 테이블 렌더링
========================================================= */

function renderAnomalyTable(anomalyTable) {
  if (!anomalyTableBody) return;

  if (!Array.isArray(anomalyTable) || anomalyTable.length === 0) {
    anomalyTableBody.innerHTML = `
      <tr>
        <td colspan="5">탐지된 이상 시점이 없습니다.</td>
      </tr>
    `;
    return;
  }

  anomalyTableBody.innerHTML = anomalyTable
    .map((row) => {
      const status = row.status || "anomaly";
      const mainFeature =
        row.main_feature ||
        row.top_feature ||
        row.feature ||
        "-";

      return `
        <tr>
          <td>${escapeHtml(row.date || "-")}</td>
          <td>${formatValue(row.score)}</td>
          <td>
            <span class="anomaly-badge ${getStatusClass(status)}">
              ${escapeHtml(status)}
            </span>
          </td>
          <td>${escapeHtml(mainFeature)}</td>
          <td>${formatFeatureValues(row.feature_values || row.values)}</td>
        </tr>
      `;
    })
    .join("");
}

function getStatusClass(status) {
  const statusText = String(status || "").toLowerCase();

  if (
    statusText === "normal" ||
    statusText === "정상"
  ) {
    return "normal";
  }

  return "warning";
}

function formatFeatureValues(featureValues) {
  if (!featureValues || typeof featureValues !== "object") {
    return "-";
  }

  const entries = Object.entries(featureValues);

  if (entries.length === 0) {
    return "-";
  }

  return entries
    .slice(0, 6)
    .map(([key, value]) => {
      return `
        <span class="feature-value-chip">
          ${escapeHtml(key)}: ${escapeHtml(formatValue(value))}
        </span>
      `;
    })
    .join("");
}


/* =========================================================
   18. 값 포맷
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

  const numericValue = Number(value);

  if (Number.isFinite(numericValue) && String(value).trim() !== "") {
    return numericValue.toFixed(4).replace(/\.?0+$/, "");
  }

  return String(value);
}

function formatPercentSmart(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  let numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return "-";
  }

  /*
    백엔드에서 0.12처럼 비율로 오면 12%로 표시하고,
    12처럼 퍼센트 값으로 오면 12% 그대로 표시한다.
  */
  if (Math.abs(numericValue) <= 1) {
    numericValue *= 100;
  }

  return `${numericValue.toFixed(2).replace(/\.?0+$/, "")}%`;
}

function formatSensitivity(value) {
  const text = String(value || "medium").toLowerCase();

  if (text === "low") {
    return "낮음";
  }

  if (text === "high") {
    return "높음";
  }

  return "보통";
}


/* =========================================================
   19. 상태 메시지
========================================================= */

function setResultStatus(message) {
  if (resultStatus) {
    resultStatus.textContent = message;
  }
}


/* =========================================================
   20. HTML Escape
========================================================= */

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}