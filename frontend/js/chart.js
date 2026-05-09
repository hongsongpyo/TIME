/* =========================================================
   TIME - frontend/js/chart.js
---------------------------------------------------------
역할
1. result.html의 Plotly 통합 인터랙션 그래프 생성
2. 원본 데이터, 전처리 데이터, 예측 모델, 추세, 주기, 잔차 표시
3. 결측치, 이상치, 특이치 포인트 표시
4. legend 클릭으로 원하는 그래프 ON/OFF
========================================================= */


/* =========================================================
   1. 기본 유틸
========================================================= */

function hasValues(values) {
  return Array.isArray(values) && values.some((value) => {
    return value !== null && value !== undefined && value !== "";
  });
}

function makeLineTrace(name, x, y, visible = true) {
  return {
    type: "scatter",
    mode: "lines",
    name,
    x: x || [],
    y: y || [],
    visible: visible ? true : "legendonly",
    connectgaps: true,
    hovertemplate: "%{x}<br>%{y}<extra>" + name + "</extra>",
  };
}

function makeMarkerTrace(name, x, y, symbol = "circle", visible = true) {
  return {
    type: "scatter",
    mode: "markers",
    name,
    x: x || [],
    y: y || [],
    visible: visible ? true : "legendonly",
    marker: {
      size: 9,
      symbol,
    },
    hovertemplate: "%{x}<br>%{y}<extra>" + name + "</extra>",
  };
}

function getPointX(points) {
  if (!points || !Array.isArray(points.date)) {
    return [];
  }

  return points.date;
}

function getPointY(points) {
  if (!points || !Array.isArray(points.value)) {
    return [];
  }

  return points.value;
}


/* =========================================================
   2. Forecast Trace 생성
========================================================= */

function buildForecastTraces(forecast) {
  const traces = [];

  if (!forecast || !forecast.future) {
    return traces;
  }

  const modelOrder = [
    "AutoARIMA",
    "Holt-Winters",
    "Exponential Smoothing",
    "Naive",
  ];

  modelOrder.forEach((modelName) => {
    const modelForecast = forecast.future[modelName];

    if (!modelForecast) {
      return;
    }

    if (!hasValues(modelForecast.value)) {
      return;
    }

    traces.push(
      makeLineTrace(
        `${modelName} 예측`,
        modelForecast.date,
        modelForecast.value,
        true
      )
    );
  });

  return traces;
}


/* =========================================================
   3. 통합 그래프 Trace 생성
========================================================= */

function buildTimeSeriesTraces(result) {
  const traces = [];

  const timeSeries = result.time_series || {};
  const decomposition = result.decomposition || {};
  const forecast = result.forecast || {};

  if (hasValues(timeSeries.original)) {
    traces.push(
      makeLineTrace(
        "원본 데이터",
        timeSeries.date,
        timeSeries.original,
        true
      )
    );
  }

  if (hasValues(timeSeries.preprocessed)) {
    traces.push(
      makeLineTrace(
        "전처리 데이터",
        timeSeries.date,
        timeSeries.preprocessed,
        true
      )
    );
  }

  if (timeSeries.missing_points) {
    traces.push(
      makeMarkerTrace(
        "결측치",
        getPointX(timeSeries.missing_points),
        getPointY(timeSeries.missing_points),
        "x",
        true
      )
    );
  }

  if (timeSeries.outlier_points) {
    traces.push(
      makeMarkerTrace(
        "이상치",
        getPointX(timeSeries.outlier_points),
        getPointY(timeSeries.outlier_points),
        "diamond",
        true
      )
    );
  }

  if (timeSeries.protected_points) {
    traces.push(
      makeMarkerTrace(
        "특이치",
        getPointX(timeSeries.protected_points),
        getPointY(timeSeries.protected_points),
        "star",
        true
      )
    );
  }

  buildForecastTraces(forecast).forEach((trace) => {
    traces.push(trace);
  });

  if (hasValues(decomposition.trend)) {
    traces.push(
      makeLineTrace(
        "추세",
        decomposition.date,
        decomposition.trend,
        "legendonly"
      )
    );
  }

  if (hasValues(decomposition.seasonal)) {
    traces.push(
      makeLineTrace(
        "주기/계절성",
        decomposition.date,
        decomposition.seasonal,
        "legendonly"
      )
    );
  }

  if (hasValues(decomposition.residual)) {
    traces.push(
      makeLineTrace(
        "노이즈/잔차",
        decomposition.date,
        decomposition.residual,
        "legendonly"
      )
    );
  }

  return traces;
}


/* =========================================================
   4. 그래프 레이아웃
========================================================= */

function buildChartLayout(result) {
  const summary = result.summary || {};

  return {
    title: {
      text: `예측 결과 시각화${summary.best_model ? " - Best Model: " + summary.best_model : ""}`,
      x: 0,
      xanchor: "left",
    },
    xaxis: {
      title: "Date",
      type: "date",
      rangeslider: {
        visible: true,
      },
    },
    yaxis: {
      title: "Value",
      zeroline: false,
    },
    legend: {
      orientation: "h",
      y: -0.28,
      x: 0,
    },
    margin: {
      l: 60,
      r: 30,
      t: 60,
      b: 120,
    },
    hovermode: "x unified",
  };
}

function buildChartConfig() {
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


/* =========================================================
   5. 그래프 렌더링
========================================================= */

function renderForecastChart(containerId, result) {
  const container = document.getElementById(containerId);

  if (!container) {
    console.error("그래프 컨테이너를 찾을 수 없습니다:", containerId);
    return;
  }

  if (!result) {
    container.innerHTML = "분석 결과가 없습니다.";
    return;
  }

  const traces = buildTimeSeriesTraces(result);
  const layout = buildChartLayout(result);
  const config = buildChartConfig();

  if (traces.length === 0) {
    container.innerHTML = "시각화할 데이터가 없습니다.";
    return;
  }

  Plotly.newPlot(container, traces, layout, config);
}


/* =========================================================
   6. 전역 객체 등록
========================================================= */

window.TIMEChart = {
  renderForecastChart,
};