/* =========================================================
   TIME - frontend/js/result.js
---------------------------------------------------------
역할
1. localStorage에 저장된 이상탐지 분석 결과 불러오기
2. 이상탐지 요약 카드 렌더링
3. 메뉴형 대시보드 제어
4. 전체 시계열 / 이상 점수 / 변수 기여도 / 히트맵 / 이상 목록 / 이상 유형 / 데이터 품질 렌더링
5. 이상 목록 행 클릭 시 해당 시점의 변수 기여도 그래프 표시
6. 이상탐지 결과 CSV 다운로드
7. 뒤로가기 버튼 처리
8. 전역 변수 충돌 방지
========================================================= */

(function () {
  "use strict";


  /* =========================================================
     1. 전역 상태
  ========================================================= */

  let analysisResult = null;
  let selectedView = "timeline";
  let selectedAnomalyDate = null;

  let resultPageTitle = null;
  let resultPageDescription = null;

  let summaryCards = null;
  let anomalyViewMenu = null;

  let anomalyInterpretationList = null;
  let featureContributionTableBody = null;
  let anomalyTableBody = null;
  let anomalyTypeTableBody = null;
  let dataQualityCards = null;
  let dataQualityTableBody = null;
  let selectedAnomalyDescription = null;

  let downloadAnomalyCsvButton = null;
  let resultStatus = null;


  /* =========================================================
     2. 초기화
  ========================================================= */

  document.addEventListener("DOMContentLoaded", () => {
    resultPageTitle = document.getElementById("resultPageTitle");
    resultPageDescription = document.getElementById("resultPageDescription");

    summaryCards = document.getElementById("summaryCards");
    anomalyViewMenu = document.getElementById("anomalyViewMenu");

    anomalyInterpretationList = document.getElementById("anomalyInterpretationList");
    featureContributionTableBody = document.getElementById("featureContributionTableBody");
    anomalyTableBody = document.getElementById("anomalyTableBody");
    anomalyTypeTableBody = document.getElementById("anomalyTypeTableBody");
    dataQualityCards = document.getElementById("dataQualityCards");
    dataQualityTableBody = document.getElementById("dataQualityTableBody");
    selectedAnomalyDescription = document.getElementById("selectedAnomalyDescription");

    downloadAnomalyCsvButton = document.getElementById("downloadAnomalyCsvButton");
    resultStatus = document.getElementById("resultStatus");

    try {
      checkRequiredModules();
      bindResultEvents();
      loadResultData();

      if (!analysisResult) {
        setResultStatus("분석 결과가 없습니다. 데이터 편집 화면에서 이상탐지를 먼저 실행하세요.");
        return;
      }

      initializeSelectedState();
      renderResultPage();
    } catch (error) {
      console.error(error);
      setResultStatus(error.message || "결과 화면을 불러오는 중 오류가 발생했습니다.");
    }
  });


  /* =========================================================
     3. 필수 모듈 확인
  ========================================================= */

  function checkRequiredModules() {
    if (!window.TIMEStorage) {
      throw new Error("Storage 모듈을 찾을 수 없습니다. storage.js 연결을 확인하세요.");
    }

    if (!window.TIMEAnomalyChart) {
      throw new Error("이상탐지 차트 모듈을 찾을 수 없습니다. anomaly-chart.js 연결을 확인하세요.");
    }
  }


  /* =========================================================
     4. 이벤트 연결
  ========================================================= */

  function bindResultEvents() {
    const backButton = document.getElementById("backButton");

    if (backButton) {
      backButton.addEventListener("click", () => {
        window.location.href = "./editor.html";
      });
    }

    if (anomalyViewMenu) {
      anomalyViewMenu.addEventListener("click", handleViewMenuClick);
    }

    if (downloadAnomalyCsvButton) {
      downloadAnomalyCsvButton.addEventListener("click", handleDownloadAnomalyCsv);
    }

    window.addEventListener("resize", () => {
      if (
        window.TIMEAnomalyChart &&
        typeof window.TIMEAnomalyChart.resizeVisibleCharts === "function"
      ) {
        window.TIMEAnomalyChart.resizeVisibleCharts();
      }
    });
  }


  /* =========================================================
     5. 분석 결과 불러오기
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
      setResultStatus("분석 결과가 없습니다. 데이터 편집 화면에서 이상탐지를 먼저 실행하세요.");
    }
  }


  /* =========================================================
     6. 선택 상태 초기화
  ========================================================= */

  function initializeSelectedState() {
    if (
      window.TIMEStorage &&
      typeof window.TIMEStorage.loadSelectedAnomalyView === "function"
    ) {
      selectedView = window.TIMEStorage.loadSelectedAnomalyView();
    } else {
      selectedView = "timeline";
    }

    selectedView = normalizeAnomalyView(selectedView);

    if (
      window.TIMEStorage &&
      typeof window.TIMEStorage.loadSelectedAnomalyDate === "function"
    ) {
      selectedAnomalyDate = window.TIMEStorage.loadSelectedAnomalyDate();
    }

    const anomalyTable = getAnomalyTableRows();

    if (!selectedAnomalyDate && anomalyTable.length > 0) {
      selectedAnomalyDate = anomalyTable[0].date || null;
    }
  }


  /* =========================================================
     7. 결과 화면 렌더링
  ========================================================= */

  function renderResultPage() {
    if (!analysisResult) {
      return;
    }

    if (resultPageTitle) {
      resultPageTitle.textContent = "다변량 시계열 이상탐지 결과";
    }

    if (resultPageDescription) {
      resultPageDescription.textContent =
        "상단 요약 카드로 전체 결과를 확인하고, 아래 메뉴에서 원하는 그래프를 선택해 확인하세요.";
    }

    renderSummaryCards(getSummary());
    renderAnomalyInterpretation(buildAnomalyInterpretation());
    renderFeatureContributionTable(getFeatureContributionRows());
    renderAnomalyTable(getAnomalyTableRows());
    renderAnomalyTypeTable(getAnomalyTypeSummary());
    renderDataQuality();
    updateSelectedAnomalyDescription();

    switchAnomalyView(selectedView, {
      shouldSave: false,
    });

    setResultStatus("이상탐지 분석 결과가 표시되었습니다.");
  }


  /* =========================================================
     8. 메뉴 클릭 처리
  ========================================================= */

  function handleViewMenuClick(event) {
    const button = event.target.closest("[data-view]");

    if (!button) {
      return;
    }

    const view = button.dataset.view;

    switchAnomalyView(view, {
      shouldSave: true,
    });
  }

  function switchAnomalyView(view, options = {}) {
    selectedView = normalizeAnomalyView(view);

    updateViewMenuUI(selectedView);
    updateViewPanelUI(selectedView);

    if (
      options.shouldSave !== false &&
      window.TIMEStorage &&
      typeof window.TIMEStorage.saveSelectedAnomalyView === "function"
    ) {
      window.TIMEStorage.saveSelectedAnomalyView(selectedView);
    }

    renderSelectedView(selectedView);

    setTimeout(() => {
      if (
        window.TIMEAnomalyChart &&
        typeof window.TIMEAnomalyChart.resizeVisibleCharts === "function"
      ) {
        window.TIMEAnomalyChart.resizeVisibleCharts();
      }
    }, 80);
  }

  function updateViewMenuUI(view) {
    const buttons = document.querySelectorAll(".chart-menu-button[data-view]");

    buttons.forEach((button) => {
      button.classList.toggle("active", button.dataset.view === view);
    });
  }

  function updateViewPanelUI(view) {
    const panels = document.querySelectorAll("[data-view-panel]");

    panels.forEach((panel) => {
      const isActive = panel.dataset.viewPanel === view;

      panel.classList.toggle("active", isActive);
      panel.hidden = !isActive;
    });
  }

  function renderSelectedView(view) {
    if (
      !window.TIMEAnomalyChart ||
      typeof window.TIMEAnomalyChart.renderView !== "function"
    ) {
      setResultStatus("이상탐지 차트 모듈을 찾을 수 없습니다.");
      return;
    }

    if (
      view === "timeline" ||
      view === "score" ||
      view === "contribution" ||
      view === "heatmap" ||
      view === "type"
    ) {
      window.TIMEAnomalyChart.renderView(
        view,
        analysisResult,
        {
          selectedDate: selectedAnomalyDate,
        }
      );
    }

    if (view === "contribution") {
      updateSelectedAnomalyDescription();
    }
  }


  /* =========================================================
     9. View 정규화
  ========================================================= */

  function normalizeAnomalyView(view) {
    const viewText = String(view || "timeline")
      .trim()
      .toLowerCase();

    const allowedViews = [
      "timeline",
      "score",
      "contribution",
      "heatmap",
      "table",
      "type",
      "quality",
    ];

    if (allowedViews.includes(viewText)) {
      return viewText;
    }

    return "timeline";
  }


  /* =========================================================
     10. Summary 렌더링
  ========================================================= */

  function getSummary() {
    return safeObject(analysisResult.summary);
  }

  function renderSummaryCards(summary) {
    if (!summaryCards) return;

    const cards = [
      {
        label: "Method",
        value: summary.method || summary.resolved_method || "-",
      },
      {
        label: "Sensitivity",
        value: formatSensitivity(summary.sensitivity_label || summary.sensitivity),
      },
      {
        label: "Data Count",
        value: formatValue(summary.data_count || summary.final_count),
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
        label: "Top Variable",
        value: summary.top_variable || "-",
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
        label: "Missing",
        value: formatValue(summary.missing_count),
      },
      {
        label: "Special",
        value: formatValue(summary.protected_count),
      },
    ];

    summaryCards.innerHTML = cards
      .map((card) => makeSummaryCard(card.label, card.value))
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
     11. 해석 문구 생성 및 렌더링
  ========================================================= */

  function buildAnomalyInterpretation() {
    if (!analysisResult) {
      return [];
    }

    if (Array.isArray(analysisResult.interpretation)) {
      return analysisResult.interpretation;
    }

    if (Array.isArray(analysisResult.anomaly_interpretation)) {
      return analysisResult.anomaly_interpretation;
    }

    const summary = getSummary();

    const messages = [];

    messages.push({
      title: "탐지 방식",
      message: `${summary.method || summary.resolved_method || "auto"} 방식으로 다변량 시계열 이상탐지를 수행했습니다.`,
    });

    messages.push({
      title: "민감도",
      message: `${formatSensitivity(summary.sensitivity_label || summary.sensitivity)} 기준으로 threshold를 적용했습니다.`,
    });

    messages.push({
      title: "이상 비율",
      message: `전체 ${formatValue(summary.data_count || summary.final_count)}개 시점 중 ${formatValue(summary.anomaly_count)}개가 이상으로 탐지되었습니다.`,
    });

    if (summary.top_variable) {
      messages.push({
        title: "주요 이상 변수",
        message: `${summary.top_variable} 변수가 이상탐지에 가장 크게 기여했습니다.`,
      });
    }

    if (summary.top_anomaly_date) {
      messages.push({
        title: "최고 이상 시점",
        message: `${summary.top_anomaly_date} 시점에서 가장 높은 이상 점수가 나타났습니다.`,
      });
    }

    const dataQuality = getDataQuality();

    if (dataQuality.missing_count || dataQuality.protected_count) {
      messages.push({
        title: "데이터 품질",
        message: `결측치 ${formatValue(dataQuality.missing_count)}개, 사용자가 보호한 특이치 셀 ${formatValue(dataQuality.protected_count)}개가 반영되었습니다.`,
      });
    }

    return messages;
  }

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
     12. 변수 기여도 테이블
  ========================================================= */

  function getFeatureContributionRows() {
    if (!analysisResult) {
      return [];
    }

    const anomaly = safeObject(analysisResult.anomaly);
    const raw = safeObject(analysisResult.anomaly_result);

    return safeArray(
      analysisResult.feature_contribution ||
      analysisResult.variable_summary ||
      anomaly.feature_contribution ||
      anomaly.variable_summary ||
      raw.feature_contribution
    );
  }

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
        const feature = row.feature || row.variable || row.column || "-";

        const countValue =
          row.anomaly_count ??
          row.main_count ??
          row.count ??
          row.main_feature_count ??
          0;

        return `
          <tr>
            <td>${formatValue(rank)}</td>
            <td>${escapeHtml(feature)}</td>
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
     13. 이상 목록 테이블
  ========================================================= */

  function getAnomalyTableRows() {
    if (!analysisResult) {
      return [];
    }

    const anomaly = safeObject(analysisResult.anomaly);
    const raw = safeObject(analysisResult.anomaly_result);

    return safeArray(
      analysisResult.top_anomaly_table ||
      analysisResult.anomaly_table ||
      anomaly.top_anomaly_table ||
      anomaly.anomaly_table ||
      raw.top_anomaly_table ||
      raw.anomaly_table
    );
  }

  function renderAnomalyTable(anomalyTable) {
    if (!anomalyTableBody) return;

    if (!Array.isArray(anomalyTable) || anomalyTable.length === 0) {
      anomalyTableBody.innerHTML = `
        <tr>
          <td colspan="6">탐지된 이상 시점이 없습니다.</td>
        </tr>
      `;
      return;
    }

    anomalyTableBody.innerHTML = anomalyTable
      .map((row, index) => {
        const rank = row.rank ?? index + 1;
        const date = row.date || "-";
        const score = row.score;
        const topVariable =
          row.top_variable ||
          row.main_feature ||
          row.top_feature ||
          row.feature ||
          "-";

        const anomalyType =
          row.anomaly_type ||
          row.type ||
          "이상";

        const description =
          row.description ||
          makeSimpleAnomalyDescription(topVariable, score);

        const isSelected =
          selectedAnomalyDate &&
          String(selectedAnomalyDate) === String(date);

        return `
          <tr
            class="clickable-row ${isSelected ? "selected-row" : ""}"
            data-anomaly-date="${escapeHtml(date)}"
          >
            <td>${formatValue(rank)}</td>
            <td>${escapeHtml(date)}</td>
            <td>${formatValue(score)}</td>
            <td>${escapeHtml(topVariable)}</td>
            <td>
              <span class="anomaly-badge warning">
                ${escapeHtml(anomalyType)}
              </span>
            </td>
            <td>${escapeHtml(description)}</td>
          </tr>
        `;
      })
      .join("");

    anomalyTableBody
      .querySelectorAll("[data-anomaly-date]")
      .forEach((rowElement) => {
        rowElement.addEventListener("click", () => {
          const date = rowElement.dataset.anomalyDate;
          handleSelectAnomalyDate(date);
        });
      });
  }

  function handleSelectAnomalyDate(date) {
    selectedAnomalyDate = date || null;

    if (
      window.TIMEStorage &&
      typeof window.TIMEStorage.saveSelectedAnomalyDate === "function"
    ) {
      window.TIMEStorage.saveSelectedAnomalyDate(selectedAnomalyDate);
    }

    renderAnomalyTable(getAnomalyTableRows());
    updateSelectedAnomalyDescription();

    switchAnomalyView("contribution", {
      shouldSave: true,
    });
  }

  function makeSimpleAnomalyDescription(topVariable, score) {
    return `${topVariable} 변수가 주요 원인으로 나타났습니다. score=${formatValue(score)}`;
  }


  /* =========================================================
     14. 선택 이상 시점 설명
  ========================================================= */

  function updateSelectedAnomalyDescription() {
    if (!selectedAnomalyDescription) {
      return;
    }

    const row = findAnomalyRowByDate(selectedAnomalyDate);

    if (!row) {
      selectedAnomalyDescription.textContent =
        "이상 목록에서 특정 시점을 선택하면 해당 시점의 변수별 기여도가 표시됩니다.";
      return;
    }

    const topVariable =
      row.top_variable ||
      row.main_feature ||
      row.feature ||
      "-";

    const anomalyType =
      row.anomaly_type ||
      row.type ||
      "이상";

    selectedAnomalyDescription.textContent =
      `${row.date} 시점은 ${anomalyType}으로 분류되었고, 주요 변수는 ${topVariable}, score는 ${formatValue(row.score)}입니다.`;
  }

  function findAnomalyRowByDate(date) {
    if (!date) {
      return null;
    }

    const rows = getAnomalyTableRows();

    return rows.find((row) => {
      return String(row.date) === String(date);
    }) || null;
  }


  /* =========================================================
     15. 이상 유형 테이블
  ========================================================= */

  function getAnomalyTypeSummary() {
    if (!analysisResult) {
      return [];
    }

    const anomaly = safeObject(analysisResult.anomaly);
    const raw = safeObject(analysisResult.anomaly_result);

    const existing = safeArray(
      analysisResult.anomaly_type_summary ||
      anomaly.anomaly_type_summary ||
      raw.anomaly_type_summary
    );

    if (existing.length > 0) {
      return existing;
    }

    const counter = {};

    getAnomalyTableRows().forEach((row) => {
      const type = row.anomaly_type || row.type || "기타";
      counter[type] = (counter[type] || 0) + 1;
    });

    return Object.keys(counter).map((type) => {
      return {
        type,
        count: counter[type],
      };
    });
  }

  function renderAnomalyTypeTable(rows) {
    if (!anomalyTypeTableBody) return;

    if (!Array.isArray(rows) || rows.length === 0) {
      anomalyTypeTableBody.innerHTML = `
        <tr>
          <td colspan="2">표시할 이상 유형 데이터가 없습니다.</td>
        </tr>
      `;
      return;
    }

    anomalyTypeTableBody.innerHTML = rows
      .map((row) => {
        return `
          <tr>
            <td>${escapeHtml(row.type || "기타")}</td>
            <td>${formatValue(row.count)}</td>
          </tr>
        `;
      })
      .join("");
  }


  /* =========================================================
     16. 데이터 품질 렌더링
  ========================================================= */

  function getDataQuality() {
    return safeObject(analysisResult.data_quality);
  }

  function renderDataQuality() {
    const quality = getDataQuality();
    const summary = getSummary();

    renderDataQualityCards(quality, summary);
    renderDataQualityTable(quality);
  }

  function renderDataQualityCards(quality, summary) {
    if (!dataQualityCards) return;

    const cards = [
      {
        label: "Date Column",
        value: quality.date_column || summary.date_column || "-",
      },
      {
        label: "Frequency",
        value: quality.frequency || summary.frequency || "-",
      },
      {
        label: "Original Rows",
        value: formatValue(quality.original_count || summary.original_count),
      },
      {
        label: "Final Rows",
        value: formatValue(quality.final_count || summary.final_count),
      },
      {
        label: "Missing",
        value: formatValue(quality.missing_count || summary.missing_count),
      },
      {
        label: "Protected",
        value: formatValue(quality.protected_count || summary.protected_count),
      },
    ];

    dataQualityCards.innerHTML = cards
      .map((card) => makeQualityCard(card.label, card.value))
      .join("");
  }

  function makeQualityCard(label, value) {
    return `
      <div class="quality-card">
        <div class="quality-label">${escapeHtml(label)}</div>
        <div class="quality-value">${escapeHtml(String(value))}</div>
      </div>
    `;
  }

  function renderDataQualityTable(quality) {
    if (!dataQualityTableBody) return;

    const columns =
      safeArray(quality.value_columns).length > 0
        ? safeArray(quality.value_columns)
        : safeArray(quality.numeric_columns);

    const missingByColumn = safeObject(quality.missing_by_column);
    const protectedDateMap = safeObject(quality.protected_date_map);

    if (columns.length === 0) {
      dataQualityTableBody.innerHTML = `
        <tr>
          <td colspan="3">표시할 데이터 품질 정보가 없습니다.</td>
        </tr>
      `;
      return;
    }

    dataQualityTableBody.innerHTML = columns
      .map((column) => {
        const protectedCount = safeArray(protectedDateMap[column]).length;

        return `
          <tr>
            <td>${escapeHtml(column)}</td>
            <td>${formatValue(missingByColumn[column] || 0)}</td>
            <td>${formatValue(protectedCount)}</td>
          </tr>
        `;
      })
      .join("");
  }


  /* =========================================================
     17. CSV 다운로드
  ========================================================= */

  function handleDownloadAnomalyCsv() {
    const rows = getDownloadRows();

    if (!rows || rows.length === 0) {
      setResultStatus("다운로드할 이상탐지 결과가 없습니다.");
      return;
    }

    const csvText = convertRowsToCSV(rows);
    const blob = new Blob(
      ["\ufeff" + csvText],
      {
        type: "text/csv;charset=utf-8;",
      }
    );

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    const timestamp = new Date()
      .toISOString()
      .slice(0, 19)
      .replaceAll(":", "-");

    link.href = url;
    link.download = `time_anomaly_result_${timestamp}.csv`;
    link.style.display = "none";

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url);

    setResultStatus("이상탐지 결과 CSV가 다운로드되었습니다.");
  }

  function getDownloadRows() {
    if (!analysisResult) {
      return [];
    }

    const anomaly = safeObject(analysisResult.anomaly);
    const raw = safeObject(analysisResult.anomaly_result);

    return safeArray(
      analysisResult.download_rows ||
      anomaly.download_rows ||
      raw.download_rows
    );
  }

  function convertRowsToCSV(rows) {
    if (!Array.isArray(rows) || rows.length === 0) {
      return "";
    }

    const columns = collectCSVColumns(rows);

    const header = columns
      .map((column) => escapeCSVValue(column))
      .join(",");

    const body = rows
      .map((row) => {
        return columns
          .map((column) => escapeCSVValue(row[column]))
          .join(",");
      })
      .join("\n");

    return `${header}\n${body}`;
  }

  function collectCSVColumns(rows) {
    const columnSet = new Set();

    rows.forEach((row) => {
      Object.keys(row || {}).forEach((column) => {
        columnSet.add(column);
      });
    });

    return Array.from(columnSet);
  }

  function escapeCSVValue(value) {
    if (value === null || value === undefined) {
      return "";
    }

    const text = String(value);

    if (
      text.includes(",") ||
      text.includes('"') ||
      text.includes("\n") ||
      text.includes("\r")
    ) {
      return `"${text.replaceAll('"', '""')}"`;
    }

    return text;
  }


  /* =========================================================
     18. 공통 유틸
  ========================================================= */

  function safeArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function safeObject(value) {
    return value && typeof value === "object" && !Array.isArray(value)
      ? value
      : {};
  }

  function formatValue(value) {
    if (value === null || value === undefined || value === "") {
      return "-";
    }

    if (typeof value === "number") {
      if (!Number.isFinite(value)) {
        return "-";
      }

      return Number(value)
        .toFixed(4)
        .replace(/\.?0+$/, "");
    }

    const numericValue = Number(value);

    if (Number.isFinite(numericValue) && String(value).trim() !== "") {
      return numericValue
        .toFixed(4)
        .replace(/\.?0+$/, "");
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

    if (Math.abs(numericValue) <= 1) {
      numericValue *= 100;
    }

    return `${numericValue.toFixed(2).replace(/\.?0+$/, "")}%`;
  }

  function formatSensitivity(value) {
    const text = String(value || "medium").toLowerCase();

    if (text === "low" || text === "낮음") {
      return "낮음";
    }

    if (text === "high" || text === "높음") {
      return "높음";
    }

    return "보통";
  }

  function setResultStatus(message) {
    if (resultStatus) {
      resultStatus.textContent = message;
    }
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
})();