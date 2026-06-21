/* =========================================================
   TIME - frontend/js/anomaly-chart.js
---------------------------------------------------------
역할
1. 다변량 시계열 이상탐지 결과 그래프 렌더링
2. 변수별 시계열 + 변수별 이상 시점 marker 표시
3. 사용자가 지정한 특이치 보호점 protected marker 표시
4. anomaly score + threshold line 표시
5. 변수별 이상 기여도 그래프 표시
6. anomaly score 분포 그래프 표시
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

    const numericValue = Number(value);

    if (Number.isFinite(numericValue) && String(value).trim() !== "") {
      return numericValue.toFixed(4).replace(/\.?0+$/, "");
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
        b: 72,
      },
      hovermode: "x unified",
      legend: {
        orientation: "h",
        x: 0,
        y: -0.22,
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
     2. 결과 구조 정규화
  ---------------------------------------------------------
  새 backend/anomaly.py 구조:
  {
    date: [...],
    value_columns: [...],
    series: { feature: [...] },
    anomaly_points: {
      features: {
        feature: { date: [...], value: [...], score: [...] }
      }
    },
    protected_points: {
      features: {
        feature: { date: [...], value: [...], score: [...] }
      }
    }
  }

  기존 anomaly_metrics.py 구조도 최대한 호환
  ========================================================= */

  function getRawAnomalyResult(anomalyResult) {
    return safeObject(anomalyResult.raw_anomaly_result);
  }

  function getDateList(anomalyResult) {
    const raw = getRawAnomalyResult(anomalyResult);
    const multivariateSeries = safeObject(anomalyResult.multivariate_series);

    return safeArray(
      anomalyResult.date ||
      raw.date ||
      multivariateSeries.date
    );
  }

  function getValueColumns(anomalyResult) {
    const raw = getRawAnomalyResult(anomalyResult);
    const multivariateSeries = safeObject(anomalyResult.multivariate_series);

    return safeArray(
      anomalyResult.value_columns ||
      raw.value_columns ||
      multivariateSeries.value_columns
    );
  }

  function getSeriesMap(anomalyResult) {
    const raw = getRawAnomalyResult(anomalyResult);
    const multivariateSeries = safeObject(anomalyResult.multivariate_series);

    return safeObject(
      anomalyResult.series ||
      raw.series ||
      multivariateSeries.series
    );
  }

  function getAnomalyPoints(anomalyResult) {
    const raw = getRawAnomalyResult(anomalyResult);
    const multivariateSeries = safeObject(anomalyResult.multivariate_series);

    return safeObject(
      anomalyResult.anomaly_points ||
      raw.anomaly_points ||
      multivariateSeries.anomaly_points
    );
  }

  function getProtectedPoints(anomalyResult) {
    const raw = getRawAnomalyResult(anomalyResult);
    const multivariateSeries = safeObject(anomalyResult.multivariate_series);

    return safeObject(
      anomalyResult.protected_points ||
      raw.protected_points ||
      multivariateSeries.protected_points
    );
  }

  function getFeaturePointObject(pointPayload, featureName) {
    const features = safeObject(pointPayload.features);
    const featurePayload = features[featureName];

    if (featurePayload && typeof featurePayload === "object" && !Array.isArray(featurePayload)) {
      return {
        date: safeArray(featurePayload.date),
        value: safeArray(featurePayload.value),
        score: safeArray(featurePayload.score),
      };
    }

    /*
      구버전 호환:
      anomaly_points = {
        date: [...],
        features: {
          energy: [...]
        }
      }
    */
    if (Array.isArray(featurePayload)) {
      return {
        date: safeArray(pointPayload.date),
        value: featurePayload,
        score: safeArray(pointPayload.score),
      };
    }

    return {
      date: [],
      value: [],
      score: [],
    };
  }


  /* =========================================================
     3. 다변량 시계열 line trace
  ========================================================= */

  function buildMultivariateLineTraces(anomalyResult) {
    const traces = [];

    const dates = getDateList(anomalyResult);
    const valueColumns = getValueColumns(anomalyResult);
    const series = getSeriesMap(anomalyResult);

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


  /* =========================================================
     4. 변수별 anomaly marker trace
  ---------------------------------------------------------
  핵심 수정:
  이제 anomaly row 전체가 아니라,
  anomaly_points.features[feature].date/value 기준으로
  해당 변수에만 marker를 표시한다.
  ========================================================= */

  function buildAnomalyMarkerTraces(anomalyResult) {
    const traces = [];

    const valueColumns = getValueColumns(anomalyResult);
    const anomalyPoints = getAnomalyPoints(anomalyResult);

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


  /* =========================================================
     5. 사용자가 지정한 특이치 protected marker trace
  ---------------------------------------------------------
  Editor에서 특이치 설정한 셀을 별도 star marker로 표시한다.
  anomaly 판정에서 제외된 protected point와 시각적으로 구분 가능.
  ========================================================= */

  function buildProtectedMarkerTraces(anomalyResult) {
    const traces = [];

    const valueColumns = getValueColumns(anomalyResult);
    const protectedPoints = getProtectedPoints(anomalyResult);

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


  /* =========================================================
     6. 다변량 이상탐지 통합 그래프
  ========================================================= */

  function renderMultivariateAnomalyChart(elementId, anomalyResult) {
    const traces = [
      ...buildMultivariateLineTraces(anomalyResult),
      ...buildAnomalyMarkerTraces(anomalyResult),
      ...buildProtectedMarkerTraces(anomalyResult),
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
     7. Anomaly score 데이터 정규화
  ========================================================= */

  function getAnomalySeries(anomalyResult) {
    const raw = getRawAnomalyResult(anomalyResult);
    const anomalySeries = safeObject(anomalyResult.anomaly_series);

    const dates = safeArray(
      anomalySeries.date ||
      anomalyResult.date ||
      raw.date
    );

    const scores = safeArray(
      anomalySeries.score ||
      anomalyResult.score ||
      raw.score
    );

    const isAnomaly = safeArray(
      anomalySeries.is_anomaly ||
      anomalyResult.is_anomaly ||
      raw.is_anomaly
    );

    const threshold =
      anomalySeries.threshold ??
      anomalyResult.threshold ??
      raw.threshold ??
      safeObject(anomalyResult.summary).threshold ??
      null;

    let thresholdValues = safeArray(anomalySeries.threshold_values);

    if (thresholdValues.length === 0 && dates.length > 0 && threshold !== null && threshold !== undefined) {
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


  /* =========================================================
     8. Anomaly Score 그래프
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
    return {
      type: "scatter",
      mode: "lines",
      name: "Threshold",
      x: safeArray(anomalySeries.date),
      y: safeArray(anomalySeries.threshold_values),
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
      "diamond",
      true,
      10
    );
  }

  function renderAnomalyScoreChart(elementId, anomalyResult) {
    const anomalySeries = getAnomalySeries(anomalyResult);

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
      anomalySeries.threshold !== undefined &&
      hasValues(anomalySeries.threshold_values)
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
     9. 변수별 이상 기여도 그래프
  ========================================================= */

  function getFeatureContributionRows(anomalyResult) {
    const raw = getRawAnomalyResult(anomalyResult);

    return safeArray(
      anomalyResult.feature_contribution ||
      raw.feature_contribution
    );
  }

  function renderFeatureContributionChart(elementId, anomalyResult) {
    const rows = getFeatureContributionRows(anomalyResult);

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

      const aScore = Number(a.contribution_ratio ?? a.mean_score ?? 0);
      const bScore = Number(b.contribution_ratio ?? b.mean_score ?? 0);

      return aScore - bScore;
    });

    const features = sortedRows.map((row) => String(row.feature || row.column || "-"));
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
     10. Score distribution 데이터 생성
  ========================================================= */

  function getScoreDistribution(anomalyResult) {
    const raw = getRawAnomalyResult(anomalyResult);
    const existing = safeObject(anomalyResult.score_distribution);

    if (
      Array.isArray(existing.bin_start) &&
      Array.isArray(existing.bin_end) &&
      Array.isArray(existing.count)
    ) {
      return existing;
    }

    const scores = safeArray(
      anomalyResult.score ||
      raw.score ||
      safeObject(anomalyResult.anomaly_series).score
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

    const binCount = Math.min(8, Math.max(4, Math.ceil(Math.sqrt(scores.length))));
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


  /* =========================================================
     11. Anomaly Score 분포 그래프
  ========================================================= */

  function renderScoreDistributionChart(elementId, anomalyResult) {
    const scoreDistribution = getScoreDistribution(anomalyResult);

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
     12. 전체 이상탐지 차트 렌더링
  ========================================================= */

  function renderAllAnomalyCharts(anomalyResult) {
    renderMultivariateAnomalyChart("anomalyChart", anomalyResult);
    renderAnomalyScoreChart("anomalyScoreChart", anomalyResult);
    renderFeatureContributionChart("featureContributionChart", anomalyResult);
    renderScoreDistributionChart("scoreDistributionChart", anomalyResult);
  }


  /* =========================================================
     13. 전역 객체 등록
  ========================================================= */

  window.TIMEAnomalyChart = {
    renderMultivariateAnomalyChart,
    renderAnomalyScoreChart,
    renderFeatureContributionChart,
    renderScoreDistributionChart,
    renderAllAnomalyCharts,
  };
})();