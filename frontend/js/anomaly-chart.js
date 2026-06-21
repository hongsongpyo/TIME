/* =========================================================
   TIME - frontend/js/anomaly-chart.js
---------------------------------------------------------
역할
1. 다변량 시계열 이상탐지 결과 그래프 렌더링
2. 전체 시계열 + 변수별 이상 시점 marker 표시
3. 사용자가 지정한 특이치 보호점 protected marker 표시
4. anomaly score + threshold line 표시
5. 변수별 이상 기여도 그래프 표시
6. 선택한 이상 시점의 변수별 기여도 그래프 표시
7. 변수 × 시간 이상도 heatmap 표시
8. 이상 유형 요약 그래프 표시
9. result.html 메뉴형 대시보드와 연결
========================================================= */

(function () {
  "use strict";


  /* =========================================================
     1. 기본 유틸
  ========================================================= */

  function hasPlotly() {
    return typeof Plotly !== "undefined";
  }

  function safeArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function safeObject(value) {
    return value && typeof value === "object" && !Array.isArray(value)
      ? value
      : {};
  }

  function safeNumber(value, fallback = 0) {
    const numberValue = Number(value);

    if (!Number.isFinite(numberValue)) {
      return fallback;
    }

    return numberValue;
  }

  function hasValues(values) {
    return Array.isArray(values) && values.some((value) => {
      return value !== null &&
        value !== undefined &&
        value !== "" &&
        Number.isFinite(Number(value));
    });
  }

  function formatValue(value, digits = 4) {
    if (value === null || value === undefined || value === "") {
      return "-";
    }

    const numberValue = Number(value);

    if (Number.isFinite(numberValue)) {
      return numberValue
        .toFixed(digits)
        .replace(/\.?0+$/, "");
    }

    return String(value);
  }

  function getFirstDefined(...values) {
    for (const value of values) {
      if (value !== undefined && value !== null) {
        return value;
      }
    }

    return null;
  }

  function normalizeDateString(value) {
    if (value === null || value === undefined) {
      return "";
    }

    return String(value);
  }


  /* =========================================================
     2. Plotly 공통 설정
  ========================================================= */

  function buildBaseLayout(titleText = "") {
    return {
      title: {
        text: titleText,
        x: 0,
        xanchor: "left",
        font: {
          size: 16,
        },
      },
      autosize: true,
      margin: {
        l: 64,
        r: 28,
        t: titleText ? 56 : 24,
        b: 72,
      },
      hovermode: "x unified",
      legend: {
        orientation: "h",
        x: 0,
        y: -0.24,
      },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      xaxis: {
        showgrid: true,
        zeroline: false,
        automargin: true,
      },
      yaxis: {
        showgrid: true,
        zeroline: false,
        automargin: true,
      },
    };
  }

  function buildPlotConfig() {
    return {
      responsive: true,
      displaylogo: false,
      scrollZoom: true,
      modeBarButtonsToRemove: [
        "lasso2d",
        "select2d",
      ],
    };
  }

  function renderEmptyChart(elementId, message) {
    const target = document.getElementById(elementId);

    if (!target) {
      return;
    }

    if (!hasPlotly()) {
      target.innerHTML = `<p class="result-status">${message}</p>`;
      return;
    }

    const layout = buildBaseLayout();

    layout.xaxis = {
      visible: false,
    };

    layout.yaxis = {
      visible: false,
    };

    layout.annotations = [
      {
        text: message,
        x: 0.5,
        y: 0.5,
        xref: "paper",
        yref: "paper",
        showarrow: false,
        font: {
          size: 14,
        },
      },
    ];

    Plotly.newPlot(
      elementId,
      [],
      layout,
      buildPlotConfig()
    );
  }

  function purgeChart(elementId) {
    if (!hasPlotly()) {
      return;
    }

    const target = document.getElementById(elementId);

    if (!target) {
      return;
    }

    try {
      Plotly.purge(elementId);
    } catch (error) {
      // 이미 비어 있는 chart면 무시
    }
  }


  /* =========================================================
     3. Trace 생성 유틸
  ========================================================= */

  function makeLineTrace(name, x, y, visible = true) {
    return {
      type: "scatter",
      mode: "lines",
      name,
      x: safeArray(x),
      y: safeArray(y),
      visible: visible === true ? true : "legendonly",
      connectgaps: true,
      hovertemplate: "%{x}<br>%{y}<extra>" + name + "</extra>",
    };
  }

  function makeMarkerTrace(
    name,
    x,
    y,
    symbol = "diamond",
    visible = true,
    size = 10
  ) {
    return {
      type: "scatter",
      mode: "markers",
      name,
      x: safeArray(x),
      y: safeArray(y),
      visible: visible === true ? true : "legendonly",
      marker: {
        size,
        symbol,
        line: {
          width: 1,
        },
      },
      hovertemplate: "%{x}<br>%{y}<extra>" + name + "</extra>",
    };
  }

  function makeBarTrace(name, x, y, orientation = "v") {
    return {
      type: "bar",
      name,
      x: safeArray(x),
      y: safeArray(y),
      orientation,
      hovertemplate:
        orientation === "h"
          ? "%{y}<br>%{x}<extra>" + name + "</extra>"
          : "%{x}<br>%{y}<extra>" + name + "</extra>",
    };
  }


  /* =========================================================
     4. 결과 구조 정규화
  ---------------------------------------------------------
  새 analysis.py 응답 구조:
  {
    summary: {},
    time_series: {},
    anomaly: {},
    anomaly_result: {},
    score_timeline: {},
    heatmap: {},
    feature_contribution: [],
    top_anomaly_contribution: {},
    anomaly_type_summary: []
  }
  ========================================================= */

  function getRawAnomalyResult(result) {
    const root = safeObject(result);

    return safeObject(
      root.anomaly_result ||
      root.raw_anomaly_result ||
      safeObject(root.anomaly).raw_anomaly_result
    );
  }

  function getAnomalySection(result) {
    return safeObject(safeObject(result).anomaly);
  }

  function getTimeSeriesSection(result) {
    return safeObject(safeObject(result).time_series);
  }

  function getSummary(result) {
    return safeObject(safeObject(result).summary);
  }

  function getDataQuality(result) {
    return safeObject(safeObject(result).data_quality);
  }

  function getDateList(result) {
    const root = safeObject(result);
    const raw = getRawAnomalyResult(result);
    const timeSeries = getTimeSeriesSection(result);
    const anomaly = getAnomalySection(result);
    const scoreTimeline = safeObject(root.score_timeline || anomaly.score_timeline);

    return safeArray(
      timeSeries.date ||
      scoreTimeline.date ||
      root.date ||
      raw.date
    );
  }

  function getValueColumns(result) {
    const root = safeObject(result);
    const raw = getRawAnomalyResult(result);
    const timeSeries = getTimeSeriesSection(result);
    const summary = getSummary(result);
    const dataQuality = getDataQuality(result);

    return safeArray(
      timeSeries.value_columns ||
      summary.value_columns ||
      summary.numeric_columns ||
      dataQuality.value_columns ||
      root.value_columns ||
      raw.value_columns
    );
  }

  function getSeriesMap(result) {
    const root = safeObject(result);
    const raw = getRawAnomalyResult(result);
    const timeSeries = getTimeSeriesSection(result);

    return safeObject(
      timeSeries.series ||
      timeSeries.preprocessed_values ||
      timeSeries.filled_values ||
      root.series ||
      raw.series
    );
  }

  function getFeatureScoresMap(result) {
    const root = safeObject(result);
    const raw = getRawAnomalyResult(result);
    const timeSeries = getTimeSeriesSection(result);

    return safeObject(
      timeSeries.feature_scores ||
      root.feature_scores ||
      raw.feature_scores
    );
  }

  function getFeatureAnomalyMatrix(result) {
    const root = safeObject(result);
    const raw = getRawAnomalyResult(result);
    const timeSeries = getTimeSeriesSection(result);

    return safeObject(
      timeSeries.feature_anomaly_matrix ||
      root.feature_anomaly_matrix ||
      raw.feature_anomaly_matrix
    );
  }

  function getAnomalyPoints(result) {
    const root = safeObject(result);
    const raw = getRawAnomalyResult(result);
    const timeSeries = getTimeSeriesSection(result);

    return safeObject(
      timeSeries.anomaly_points ||
      root.anomaly_points ||
      raw.anomaly_points
    );
  }

  function getProtectedPoints(result) {
    const root = safeObject(result);
    const raw = getRawAnomalyResult(result);
    const timeSeries = getTimeSeriesSection(result);

    return safeObject(
      timeSeries.protected_points_by_feature ||
      root.protected_points ||
      raw.protected_points
    );
  }

  function getFeaturePointObject(pointPayload, featureName) {
    const payload = safeObject(pointPayload);
    const features = safeObject(payload.features);
    const featurePayload = features[featureName];

    if (
      featurePayload &&
      typeof featurePayload === "object" &&
      !Array.isArray(featurePayload)
    ) {
      return {
        date: safeArray(featurePayload.date),
        value: safeArray(featurePayload.value),
        score: safeArray(featurePayload.score),
      };
    }

    if (Array.isArray(featurePayload)) {
      return {
        date: safeArray(payload.date),
        value: featurePayload,
        score: safeArray(payload.score),
      };
    }

    return {
      date: [],
      value: [],
      score: [],
    };
  }


  /* =========================================================
     5. 전체 시계열 그래프
  ========================================================= */

  function buildMultivariateLineTraces(result) {
    const traces = [];

    const dates = getDateList(result);
    const valueColumns = getValueColumns(result);
    const series = getSeriesMap(result);

    valueColumns.forEach((featureName, index) => {
      const values = safeArray(series[featureName]);

      if (!hasValues(values)) {
        return;
      }

      traces.push(
        makeLineTrace(
          String(featureName),
          dates,
          values,
          index < 5
        )
      );
    });

    return traces;
  }

  function buildAnomalyMarkerTraces(result) {
    const traces = [];

    const valueColumns = getValueColumns(result);
    const anomalyPoints = getAnomalyPoints(result);

    if (!anomalyPoints || Object.keys(anomalyPoints).length === 0) {
      return traces;
    }

    valueColumns.forEach((featureName, index) => {
      const featurePoints = getFeaturePointObject(anomalyPoints, featureName);

      if (
        featurePoints.date.length === 0 ||
        !hasValues(featurePoints.value)
      ) {
        return;
      }

      traces.push(
        makeMarkerTrace(
          `${featureName} 이상 시점`,
          featurePoints.date,
          featurePoints.value,
          "diamond",
          index < 5,
          10
        )
      );
    });

    return traces;
  }

  function buildProtectedMarkerTraces(result) {
    const traces = [];

    const valueColumns = getValueColumns(result);
    const protectedPoints = getProtectedPoints(result);

    if (!protectedPoints || Object.keys(protectedPoints).length === 0) {
      return traces;
    }

    valueColumns.forEach((featureName, index) => {
      const featurePoints = getFeaturePointObject(protectedPoints, featureName);

      if (
        featurePoints.date.length === 0 ||
        !hasValues(featurePoints.value)
      ) {
        return;
      }

      traces.push(
        makeMarkerTrace(
          `${featureName} 특이치 설정`,
          featurePoints.date,
          featurePoints.value,
          "star",
          index < 5,
          13
        )
      );
    });

    return traces;
  }

  function renderMultivariateAnomalyChart(elementId, result) {
    const traces = [
      ...buildMultivariateLineTraces(result),
      ...buildAnomalyMarkerTraces(result),
      ...buildProtectedMarkerTraces(result),
    ];

    if (traces.length === 0) {
      renderEmptyChart(
        elementId,
        "표시할 다변량 시계열 데이터가 없습니다."
      );
      return;
    }

    const layout = buildBaseLayout("전체 시계열 및 이상 시점");

    layout.xaxis = {
      title: "Date",
      showgrid: true,
      zeroline: false,
      rangeslider: {
        visible: true,
      },
      automargin: true,
    };

    layout.yaxis = {
      title: "Value",
      showgrid: true,
      zeroline: false,
      automargin: true,
    };

    Plotly.newPlot(
      elementId,
      traces,
      layout,
      buildPlotConfig()
    );
  }


  /* =========================================================
     6. Anomaly Score 그래프
  ========================================================= */

  function getScoreTimeline(result) {
    const root = safeObject(result);
    const raw = getRawAnomalyResult(result);
    const anomaly = getAnomalySection(result);
    const summary = getSummary(result);

    const scoreTimeline = safeObject(
      root.score_timeline ||
      anomaly.score_timeline ||
      raw.score_timeline
    );

    const dates = safeArray(
      scoreTimeline.date ||
      root.date ||
      raw.date ||
      getDateList(result)
    );

    const scores = safeArray(
      scoreTimeline.score ||
      root.score ||
      raw.score
    );

    const isAnomaly = safeArray(
      scoreTimeline.is_anomaly ||
      root.is_anomaly ||
      raw.is_anomaly
    );

    const threshold = getFirstDefined(
      summary.threshold,
      root.threshold,
      anomaly.threshold,
      raw.threshold
    );

    let thresholdValues = safeArray(scoreTimeline.threshold);

    if (
      thresholdValues.length === 0 &&
      dates.length > 0 &&
      threshold !== null &&
      threshold !== undefined
    ) {
      thresholdValues = dates.map(() => threshold);
    }

    return {
      date: dates,
      score: scores,
      is_anomaly: isAnomaly,
      threshold,
      threshold_values: thresholdValues,
    };
  }

  function buildScoreLineTrace(scoreTimeline) {
    return makeLineTrace(
      "Anomaly Score",
      scoreTimeline.date,
      scoreTimeline.score,
      true
    );
  }

  function buildThresholdTrace(scoreTimeline) {
    return {
      type: "scatter",
      mode: "lines",
      name: "Threshold",
      x: safeArray(scoreTimeline.date),
      y: safeArray(scoreTimeline.threshold_values),
      line: {
        dash: "dash",
      },
      connectgaps: true,
      hovertemplate: "%{x}<br>%{y}<extra>Threshold</extra>",
    };
  }

  function buildScoreAnomalyMarkerTrace(scoreTimeline) {
    const dates = safeArray(scoreTimeline.date);
    const scores = safeArray(scoreTimeline.score);
    const isAnomaly = safeArray(scoreTimeline.is_anomaly);

    const anomalyDates = [];
    const anomalyScores = [];

    const minLength = Math.min(
      dates.length,
      scores.length,
      isAnomaly.length
    );

    for (let index = 0; index < minLength; index += 1) {
      if (Boolean(isAnomaly[index])) {
        anomalyDates.push(dates[index]);
        anomalyScores.push(scores[index]);
      }
    }

    return makeMarkerTrace(
      "Detected Anomaly",
      anomalyDates,
      anomalyScores,
      "diamond",
      true,
      10
    );
  }

  function renderAnomalyScoreChart(elementId, result) {
    const scoreTimeline = getScoreTimeline(result);

    const dates = safeArray(scoreTimeline.date);
    const scores = safeArray(scoreTimeline.score);

    if (dates.length === 0 || !hasValues(scores)) {
      renderEmptyChart(
        elementId,
        "표시할 anomaly score 데이터가 없습니다."
      );
      return;
    }

    const traces = [
      buildScoreLineTrace(scoreTimeline),
    ];

    if (
      scoreTimeline.threshold !== null &&
      scoreTimeline.threshold !== undefined &&
      hasValues(scoreTimeline.threshold_values)
    ) {
      traces.push(buildThresholdTrace(scoreTimeline));
    }

    traces.push(buildScoreAnomalyMarkerTrace(scoreTimeline));

    const layout = buildBaseLayout("Anomaly Score Timeline");

    layout.xaxis = {
      title: "Date",
      showgrid: true,
      zeroline: false,
      rangeslider: {
        visible: true,
      },
      automargin: true,
    };

    layout.yaxis = {
      title: "Anomaly Score",
      showgrid: true,
      zeroline: false,
      automargin: true,
    };

    Plotly.newPlot(
      elementId,
      traces,
      layout,
      buildPlotConfig()
    );
  }


  /* =========================================================
     7. 변수 기여도 그래프
  ========================================================= */

  function getFeatureContributionRows(result) {
    const root = safeObject(result);
    const raw = getRawAnomalyResult(result);
    const anomaly = getAnomalySection(result);

    return safeArray(
      root.feature_contribution ||
      anomaly.feature_contribution ||
      anomaly.variable_summary ||
      raw.feature_contribution
    );
  }

  function getTopAnomalyContribution(result) {
    const root = safeObject(result);
    const raw = getRawAnomalyResult(result);
    const anomaly = getAnomalySection(result);

    return safeObject(
      root.top_anomaly_contribution ||
      anomaly.top_anomaly_contribution ||
      raw.top_anomaly_contribution
    );
  }

  function getAnomalyTable(result) {
    const root = safeObject(result);
    const raw = getRawAnomalyResult(result);
    const anomaly = getAnomalySection(result);

    return safeArray(
      root.anomaly_table ||
      anomaly.anomaly_table ||
      raw.anomaly_table
    );
  }

  function findAnomalyRowByDate(result, selectedDate) {
    const rows = getAnomalyTable(result);

    if (!selectedDate) {
      return null;
    }

    const targetDate = normalizeDateString(selectedDate);

    return rows.find((row) => {
      return normalizeDateString(row.date) === targetDate;
    }) || null;
  }

  function buildRowContributionFromTable(row) {
    if (!row) {
      return {
        date: null,
        items: [],
      };
    }

    const featureScores = safeObject(row.feature_scores);
    const featureValues = safeObject(row.feature_values);
    const featureStatus = safeObject(row.feature_status);

    const items = Object.keys(featureScores).map((feature) => {
      return {
        feature,
        variable: feature,
        score: safeNumber(featureScores[feature], 0),
        value: featureValues[feature],
        status: featureStatus[feature] || "normal",
      };
    });

    const scoreSum = items.reduce((sum, item) => {
      return sum + safeNumber(item.score, 0);
    }, 0);

    items.forEach((item) => {
      item.contribution_ratio = scoreSum > 0
        ? safeNumber(item.score, 0) / scoreSum * 100
        : 0;
    });

    items.sort((a, b) => {
      return safeNumber(b.score, 0) - safeNumber(a.score, 0);
    });

    items.forEach((item, index) => {
      item.rank = index + 1;
    });

    return {
      date: row.date,
      items,
    };
  }

  function getContributionRowsForChart(result, selectedDate = null) {
    const selectedRow = findAnomalyRowByDate(result, selectedDate);

    if (selectedRow) {
      return buildRowContributionFromTable(selectedRow).items;
    }

    const topContribution = getTopAnomalyContribution(result);

    if (Array.isArray(topContribution.items) && topContribution.items.length > 0) {
      return topContribution.items;
    }

    return getFeatureContributionRows(result);
  }

  function renderFeatureContributionChart(elementId, result, selectedDate = null) {
    const rows = getContributionRowsForChart(result, selectedDate);

    if (rows.length === 0) {
      renderEmptyChart(
        elementId,
        "표시할 변수별 기여도 데이터가 없습니다."
      );
      return;
    }

    const sortedRows = [...rows].sort((a, b) => {
      const aRank = Number(a.rank ?? 999999);
      const bRank = Number(b.rank ?? 999999);

      if (aRank !== bRank) {
        return bRank - aRank;
      }

      const aScore = Number(
        a.contribution_ratio ??
        a.score ??
        a.mean_score ??
        0
      );

      const bScore = Number(
        b.contribution_ratio ??
        b.score ??
        b.mean_score ??
        0
      );

      return aScore - bScore;
    });

    const features = sortedRows.map((row) => {
      return String(row.feature || row.variable || row.column || "-");
    });

    const values = sortedRows.map((row) => {
      return Number(
        row.contribution_ratio ??
        row.score ??
        row.mean_score ??
        0
      ) || 0;
    });

    const trace = makeBarTrace(
      selectedDate ? "Selected anomaly contribution" : "Contribution",
      values,
      features,
      "h"
    );

    const title = selectedDate
      ? `선택 시점 변수 기여도: ${selectedDate}`
      : "변수별 이상 기여도";

    const layout = buildBaseLayout(title);

    layout.margin = {
      l: 140,
      r: 28,
      t: 56,
      b: 56,
    };

    layout.xaxis = {
      title: "Contribution / Score",
      showgrid: true,
      zeroline: false,
      automargin: true,
    };

    layout.yaxis = {
      title: "Variable",
      automargin: true,
      showgrid: false,
      zeroline: false,
    };

    Plotly.newPlot(
      elementId,
      [trace],
      layout,
      buildPlotConfig()
    );
  }


  /* =========================================================
     8. Heatmap 그래프
  ========================================================= */

  function getHeatmapPayload(result) {
    const root = safeObject(result);
    const raw = getRawAnomalyResult(result);
    const anomaly = getAnomalySection(result);

    const heatmap = safeObject(
      root.heatmap ||
      anomaly.heatmap ||
      raw.heatmap
    );

    const dates = safeArray(
      heatmap.date ||
      getDateList(result)
    );

    const variables = safeArray(
      heatmap.variables ||
      heatmap.value_columns ||
      getValueColumns(result)
    );

    let z = safeArray(heatmap.z);

    if (z.length === 0) {
      const featureScores = getFeatureScoresMap(result);

      z = variables.map((variable) => {
        return safeArray(featureScores[variable]);
      });
    }

    return {
      date: dates,
      variables,
      z,
    };
  }

  function renderAnomalyHeatmapChart(elementId, result) {
    const heatmap = getHeatmapPayload(result);

    if (
      heatmap.date.length === 0 ||
      heatmap.variables.length === 0 ||
      heatmap.z.length === 0
    ) {
      renderEmptyChart(
        elementId,
        "표시할 heatmap 데이터가 없습니다."
      );
      return;
    }

    const trace = {
      type: "heatmap",
      x: heatmap.date,
      y: heatmap.variables,
      z: heatmap.z,
      hovertemplate:
        "Date=%{x}<br>Variable=%{y}<br>Score=%{z}<extra></extra>",
      colorbar: {
        title: "Score",
      },
    };

    const layout = buildBaseLayout("변수 × 시간 이상도 히트맵");

    layout.margin = {
      l: 120,
      r: 28,
      t: 56,
      b: 88,
    };

    layout.xaxis = {
      title: "Date",
      showgrid: false,
      zeroline: false,
      automargin: true,
    };

    layout.yaxis = {
      title: "Variable",
      showgrid: false,
      zeroline: false,
      automargin: true,
    };

    Plotly.newPlot(
      elementId,
      [trace],
      layout,
      buildPlotConfig()
    );
  }


  /* =========================================================
     9. 이상 유형 그래프
  ========================================================= */

  function getAnomalyTypeSummary(result) {
    const root = safeObject(result);
    const raw = getRawAnomalyResult(result);
    const anomaly = getAnomalySection(result);

    const existing = safeArray(
      root.anomaly_type_summary ||
      anomaly.anomaly_type_summary ||
      raw.anomaly_type_summary
    );

    if (existing.length > 0) {
      return existing;
    }

    const table = getAnomalyTable(result);
    const counter = {};

    table.forEach((row) => {
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

  function renderAnomalyTypeChart(elementId, result) {
    const rows = getAnomalyTypeSummary(result);

    if (rows.length === 0) {
      renderEmptyChart(
        elementId,
        "표시할 이상 유형 데이터가 없습니다."
      );
      return;
    }

    const types = rows.map((row) => String(row.type || "기타"));
    const counts = rows.map((row) => safeNumber(row.count, 0));

    const trace = makeBarTrace(
      "Count",
      types,
      counts,
      "v"
    );

    const layout = buildBaseLayout("이상 유형 요약");

    layout.xaxis = {
      title: "Anomaly Type",
      showgrid: false,
      zeroline: false,
      automargin: true,
    };

    layout.yaxis = {
      title: "Count",
      showgrid: true,
      zeroline: false,
      automargin: true,
    };

    Plotly.newPlot(
      elementId,
      [trace],
      layout,
      buildPlotConfig()
    );
  }


  /* =========================================================
     10. Score Distribution 그래프
  ---------------------------------------------------------
  result.html 새 구조에서는 기본 메뉴에 없지만,
  구버전 result.html 호환을 위해 유지
  ========================================================= */

  function getScoreDistribution(result) {
    const root = safeObject(result);
    const raw = getRawAnomalyResult(result);
    const scoreTimeline = getScoreTimeline(result);

    const existing = safeObject(
      root.score_distribution ||
      raw.score_distribution
    );

    if (
      Array.isArray(existing.bin_start) &&
      Array.isArray(existing.bin_end) &&
      Array.isArray(existing.count)
    ) {
      return existing;
    }

    const scores = safeArray(
      scoreTimeline.score ||
      root.score ||
      raw.score
    )
      .map((value) => Number(value))
      .filter((value) => Number.isFinite(value));

    if (scores.length === 0) {
      return {
        bin_start: [],
        bin_end: [],
        count: [],
      };
    }

    const binCount = Math.min(
      8,
      Math.max(4, Math.ceil(Math.sqrt(scores.length)))
    );

    const minScore = Math.min(...scores);
    const maxScore = Math.max(...scores);

    if (minScore === maxScore) {
      return {
        bin_start: [minScore],
        bin_end: [maxScore],
        count: [scores.length],
      };
    }

    const step = (maxScore - minScore) / binCount;
    const binStart = [];
    const binEnd = [];
    const count = [];

    for (let index = 0; index < binCount; index += 1) {
      const start = minScore + step * index;
      const end = index === binCount - 1
        ? maxScore
        : minScore + step * (index + 1);

      binStart.push(start);
      binEnd.push(end);
      count.push(0);
    }

    scores.forEach((score) => {
      let binIndex = Math.floor((score - minScore) / step);

      if (binIndex >= binCount) {
        binIndex = binCount - 1;
      }

      if (binIndex < 0) {
        binIndex = 0;
      }

      count[binIndex] += 1;
    });

    return {
      bin_start: binStart,
      bin_end: binEnd,
      count,
    };
  }

  function buildDistributionLabels(scoreDistribution) {
    const binStart = safeArray(scoreDistribution.bin_start);
    const binEnd = safeArray(scoreDistribution.bin_end);

    const minLength = Math.min(binStart.length, binEnd.length);
    const labels = [];

    for (let index = 0; index < minLength; index += 1) {
      labels.push(
        `${formatValue(binStart[index])} ~ ${formatValue(binEnd[index])}`
      );
    }

    return labels;
  }

  function renderScoreDistributionChart(elementId, result) {
    const scoreDistribution = getScoreDistribution(result);

    const labels = buildDistributionLabels(scoreDistribution);
    const counts = safeArray(scoreDistribution.count);

    if (labels.length === 0 || !hasValues(counts)) {
      renderEmptyChart(
        elementId,
        "표시할 score 분포 데이터가 없습니다."
      );
      return;
    }

    const trace = makeBarTrace(
      "Count",
      labels,
      counts,
      "v"
    );

    const layout = buildBaseLayout("Anomaly Score Distribution");

    layout.xaxis = {
      title: "Score Range",
      showgrid: false,
      zeroline: false,
      automargin: true,
    };

    layout.yaxis = {
      title: "Count",
      showgrid: true,
      zeroline: false,
      automargin: true,
    };

    Plotly.newPlot(
      elementId,
      [trace],
      layout,
      buildPlotConfig()
    );
  }


  /* =========================================================
     11. 메뉴 view별 렌더링
  ========================================================= */

  function renderView(view, result, options = {}) {
    const selectedDate = options.selectedDate || null;

    if (view === "timeline") {
      renderMultivariateAnomalyChart("anomalyMainChart", result);
      return;
    }

    if (view === "score") {
      renderAnomalyScoreChart("anomalyScoreChart", result);
      return;
    }

    if (view === "contribution") {
      renderFeatureContributionChart(
        "featureContributionChart",
        result,
        selectedDate
      );
      return;
    }

    if (view === "heatmap") {
      renderAnomalyHeatmapChart("anomalyHeatmapChart", result);
      return;
    }

    if (view === "type") {
      renderAnomalyTypeChart("anomalyTypeChart", result);
      return;
    }
  }

  function resizeVisibleCharts() {
    if (!hasPlotly()) {
      return;
    }

    const chartIds = [
      "anomalyMainChart",
      "anomalyScoreChart",
      "featureContributionChart",
      "anomalyHeatmapChart",
      "anomalyTypeChart",
      "scoreDistributionChart",
    ];

    chartIds.forEach((chartId) => {
      const element = document.getElementById(chartId);

      if (!element || element.offsetParent === null) {
        return;
      }

      try {
        Plotly.Plots.resize(element);
      } catch (error) {
        // hidden 상태였던 chart resize 실패는 무시
      }
    });
  }

  function renderAllAnomalyCharts(result) {
    if (document.getElementById("anomalyMainChart")) {
      renderMultivariateAnomalyChart("anomalyMainChart", result);
    }

    if (document.getElementById("anomalyScoreChart")) {
      renderAnomalyScoreChart("anomalyScoreChart", result);
    }

    if (document.getElementById("featureContributionChart")) {
      renderFeatureContributionChart("featureContributionChart", result);
    }

    if (document.getElementById("anomalyHeatmapChart")) {
      renderAnomalyHeatmapChart("anomalyHeatmapChart", result);
    }

    if (document.getElementById("anomalyTypeChart")) {
      renderAnomalyTypeChart("anomalyTypeChart", result);
    }

    // 구버전 result.html 호환
    if (document.getElementById("anomalyChart")) {
      renderMultivariateAnomalyChart("anomalyChart", result);
    }

    if (document.getElementById("scoreDistributionChart")) {
      renderScoreDistributionChart("scoreDistributionChart", result);
    }
  }


  /* =========================================================
     12. 전역 객체 등록
  ========================================================= */

  window.TIMEAnomalyChart = {
    renderEmptyChart,
    purgeChart,

    renderMultivariateAnomalyChart,
    renderAnomalyScoreChart,
    renderFeatureContributionChart,
    renderAnomalyHeatmapChart,
    renderAnomalyTypeChart,
    renderScoreDistributionChart,

    renderView,
    resizeVisibleCharts,
    renderAllAnomalyCharts,

    getDateList,
    getValueColumns,
    getSeriesMap,
    getScoreTimeline,
    getFeatureContributionRows,
    getTopAnomalyContribution,
    getAnomalyTable,
    getAnomalyTypeSummary,
    getHeatmapPayload,
  };
})();