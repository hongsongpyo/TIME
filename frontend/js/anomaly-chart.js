/* =========================================================
   TIME - frontend/js/anomaly-chart.js
---------------------------------------------------------
역할
1. 다변량 시계열 이상탐지 결과 그래프 렌더링
2. 변수별 시계열 + 이상 시점 marker 표시
3. anomaly score + threshold line 표시
4. 변수별 이상 기여도 그래프 표시
5. anomaly score 분포 그래프 표시
========================================================= */

(function () {
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

  function hasValues(values) {
    return Array.isArray(values) && values.some((value) => {
      return value !== null && value !== undefined && value !== "";
    });
  }

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
        l: 56,
        r: 28,
        t: titleText ? 56 : 24,
        b: 56,
      },
      hovermode: "x unified",
      legend: {
        orientation: "h",
        x: 0,
        y: -0.2,
      },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      xaxis: {
        showgrid: true,
        zeroline: false,
      },
      yaxis: {
        showgrid: true,
        zeroline: false,
      },
    };
  }

  function buildPlotConfig() {
    return {
      responsive: true,
      displaylogo: false,
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

  function makeMarkerTrace(name, x, y, visible = true) {
    return {
      type: "scatter",
      mode: "markers",
      name,
      x: safeArray(x),
      y: safeArray(y),
      visible: visible === true ? true : "legendonly",
      marker: {
        size: 10,
        symbol: "diamond",
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
     2. 다변량 시계열 + 이상 시점 그래프
  ========================================================= */

  function buildMultivariateLineTraces(multivariateSeries) {
    const traces = [];

    const dates = safeArray(multivariateSeries.date);
    const valueColumns = safeArray(multivariateSeries.value_columns);
    const series = safeObject(multivariateSeries.series);

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

  function buildAnomalyMarkerTraces(multivariateSeries) {
    const traces = [];

    const valueColumns = safeArray(multivariateSeries.value_columns);
    const anomalyPoints = safeObject(multivariateSeries.anomaly_points);
    const anomalyDates = safeArray(anomalyPoints.date);
    const anomalyFeatures = safeObject(anomalyPoints.features);

    if (anomalyDates.length === 0) {
      return traces;
    }

    valueColumns.forEach((featureName, index) => {
      const values = safeArray(anomalyFeatures[featureName]);

      if (!hasValues(values)) {
        return;
      }

      traces.push(
        makeMarkerTrace(
          `${featureName} 이상 시점`,
          anomalyDates,
          values,
          index < 5
        )
      );
    });

    return traces;
  }

  function renderMultivariateAnomalyChart(elementId, anomalyResult) {
    const multivariateSeries = safeObject(anomalyResult.multivariate_series);

    const traces = [
      ...buildMultivariateLineTraces(multivariateSeries),
      ...buildAnomalyMarkerTraces(multivariateSeries),
    ];

    if (traces.length === 0) {
      renderEmptyChart(
        elementId,
        "표시할 다변량 시계열 데이터가 없습니다."
      );
      return;
    }

    const layout = buildBaseLayout("Multivariate Time Series Anomaly Detection");

    layout.xaxis = {
      title: "Date",
      showgrid: true,
      zeroline: false,
    };

    layout.yaxis = {
      title: "Value",
      showgrid: true,
      zeroline: false,
    };

    Plotly.newPlot(
      elementId,
      traces,
      layout,
      buildPlotConfig()
    );
  }


  /* =========================================================
     3. Anomaly Score 그래프
  ========================================================= */

  function buildScoreLineTrace(anomalySeries) {
    return makeLineTrace(
      "Anomaly Score",
      anomalySeries.date,
      anomalySeries.score,
      true
    );
  }

  function buildThresholdTrace(anomalySeries) {
    const dates = safeArray(anomalySeries.date);
    let thresholdValues = safeArray(anomalySeries.threshold_values);

    if (thresholdValues.length === 0 && dates.length > 0) {
      thresholdValues = dates.map(() => anomalySeries.threshold);
    }

    return {
      type: "scatter",
      mode: "lines",
      name: "Threshold",
      x: dates,
      y: thresholdValues,
      line: {
        dash: "dash",
      },
      connectgaps: true,
      hovertemplate: "%{x}<br>%{y}<extra>Threshold</extra>",
    };
  }

  function buildScoreAnomalyMarkerTrace(anomalySeries) {
    const dates = safeArray(anomalySeries.date);
    const scores = safeArray(anomalySeries.score);
    const isAnomaly = safeArray(anomalySeries.is_anomaly);

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
      true
    );
  }

  function renderAnomalyScoreChart(elementId, anomalyResult) {
    const anomalySeries = safeObject(anomalyResult.anomaly_series);

    const dates = safeArray(anomalySeries.date);
    const scores = safeArray(anomalySeries.score);

    if (dates.length === 0 || !hasValues(scores)) {
      renderEmptyChart(
        elementId,
        "표시할 anomaly score 데이터가 없습니다."
      );
      return;
    }

    const traces = [
      buildScoreLineTrace(anomalySeries),
    ];

    if (
      anomalySeries.threshold !== null &&
      anomalySeries.threshold !== undefined
    ) {
      traces.push(buildThresholdTrace(anomalySeries));
    }

    traces.push(buildScoreAnomalyMarkerTrace(anomalySeries));

    const layout = buildBaseLayout("Anomaly Score over Time");

    layout.xaxis = {
      title: "Date",
      showgrid: true,
      zeroline: false,
    };

    layout.yaxis = {
      title: "Anomaly Score",
      showgrid: true,
      zeroline: false,
    };

    Plotly.newPlot(
      elementId,
      traces,
      layout,
      buildPlotConfig()
    );
  }


  /* =========================================================
     4. 변수별 이상 기여도 그래프
  ========================================================= */

  function renderFeatureContributionChart(elementId, anomalyResult) {
    const rows = safeArray(anomalyResult.feature_contribution);

    if (rows.length === 0) {
      renderEmptyChart(
        elementId,
        "표시할 변수별 기여도 데이터가 없습니다."
      );
      return;
    }

    const sortedRows = [...rows].sort((a, b) => {
      const aScore = Number(a.contribution_ratio ?? a.mean_score ?? 0);
      const bScore = Number(b.contribution_ratio ?? b.mean_score ?? 0);
      return aScore - bScore;
    });

    const features = sortedRows.map((row) => String(row.feature || "-"));
    const ratios = sortedRows.map((row) => {
      const value = row.contribution_ratio ?? row.mean_score ?? 0;
      return Number(value) || 0;
    });

    const trace = makeBarTrace(
      "Contribution",
      ratios,
      features,
      "h"
    );

    const layout = buildBaseLayout("Feature Contribution");

    layout.margin = {
      l: 120,
      r: 28,
      t: 56,
      b: 48,
    };

    layout.xaxis = {
      title: "Contribution / Mean Score",
      showgrid: true,
      zeroline: false,
    };

    layout.yaxis = {
      title: "Feature",
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
     5. Anomaly Score 분포 그래프
  ========================================================= */

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

  function renderScoreDistributionChart(elementId, anomalyResult) {
    const scoreDistribution = safeObject(anomalyResult.score_distribution);

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
    };

    Plotly.newPlot(
      elementId,
      [trace],
      layout,
      buildPlotConfig()
    );
  }


  /* =========================================================
     6. 통합 렌더링 함수
  ========================================================= */

  function renderAllAnomalyCharts(anomalyResult) {
    renderMultivariateAnomalyChart("anomalyChart", anomalyResult);
    renderAnomalyScoreChart("anomalyScoreChart", anomalyResult);
    renderFeatureContributionChart("featureContributionChart", anomalyResult);
    renderScoreDistributionChart("scoreDistributionChart", anomalyResult);
  }


  /* =========================================================
     7. 전역 객체 등록
  ========================================================= */

  window.TIMEAnomalyChart = {
    renderMultivariateAnomalyChart,
    renderAnomalyScoreChart,
    renderFeatureContributionChart,
    renderScoreDistributionChart,
    renderAllAnomalyCharts,
  };
})();