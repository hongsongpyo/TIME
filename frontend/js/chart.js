/* =========================================================
   TIME - frontend/js/chart.js
---------------------------------------------------------
역할
1. result.html의 Plotly 통합 인터랙션 그래프 생성
2. Train / Test / 모델별 검증 예측을 기본 표시
3. 미래 예측, 원본, 전처리, 추세, 계절성, 잔차는 legend에서 선택 표시
4. 결측치, 이상치, 특이치 포인트 표시
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
    mode: "lines+markers",
    name,
    x: x || [],
    y: y || [],
    visible: visible === true ? true : "legendonly",
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
    visible: visible === true ? true : "legendonly",
    marker: {
      size: 10,
      symbol,
      line: {
        width: 1,
      },
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
   2. Train / Test Trace 생성
========================================================= */

function buildTrainTestTraces(forecast) {
  const traces = [];

  if (!forecast) {
    return traces;
  }

  if (hasValues(forecast.train_values)) {
    traces.push(
      makeLineTrace(
        "y_train",
        forecast.train_dates,
        forecast.train_values,
        true
      )
    );
  }

  if (hasValues(forecast.validation_actual)) {
    traces.push(
      makeLineTrace(
        "y_test",
        forecast.validation_dates,
        forecast.validation_actual,
        true
      )
    );
  }

  return traces;
}


/* =========================================================
   3. 모델별 검증 예측 Trace 생성
---------------------------------------------------------
test 구간 위에 예측값을 그려 실제 y_test와 비교할 수 있게 함
========================================================= */

function buildValidationPredictionTraces(forecast) {
  const traces = [];

  if (!forecast || !forecast.validation) {
    return traces;
  }

  const modelOrder = [
    "AutoARIMA",
    "Holt-Winters",
    "Exponential Smoothing",
    "Naive",
  ];

  modelOrder.forEach((modelName) => {
    const modelValidation = forecast.validation[modelName];

    if (!modelValidation || !hasValues(modelValidation.value)) {
      return;
    }

    traces.push(
      makeLineTrace(
        `${modelName} Validation`,
        modelValidation.date,
        modelValidation.value,
        true
      )
    );
  });

  return traces;
}


/* =========================================================
   4. 모델별 미래 예측 Trace 생성
---------------------------------------------------------
미래 예측은 기본 숨김 처리
legend 클릭 시 확인 가능
========================================================= */

function buildFuturePredictionTraces(forecast) {
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
    const modelFuture = forecast.future[modelName];

    if (!modelFuture || !hasValues(modelFuture.value)) {
      return;
    }

    traces.push(
      makeLineTrace(
        `${modelName} Future`,
        modelFuture.date,
        modelFuture.value,
        false
      )
    );
  });

  return traces;
}


/* =========================================================
   5. 원본/전처리/포인트 Trace 생성
========================================================= */

function buildDataAndPointTraces(timeSeries) {
  const traces = [];

  if (!timeSeries) {
    return traces;
  }

  if (hasValues(timeSeries.original)) {
    traces.push(
      makeLineTrace(
        "Original Data",
        timeSeries.date,
        timeSeries.original,
        false
      )
    );
  }

  if (hasValues(timeSeries.preprocessed)) {
    traces.push(
      makeLineTrace(
        "Preprocessed Data",
        timeSeries.date,
        timeSeries.preprocessed,
        false
      )
    );
  }

  if (timeSeries.missing_points) {
    traces.push(
      makeMarkerTrace(
        "Missing Points",
        getPointX(timeSeries.missing_points),
        getPointY(timeSeries.missing_points),
        "x",
        false
      )
    );
  }

  if (timeSeries.outlier_points) {
    traces.push(
      makeMarkerTrace(
        "Outliers",
        getPointX(timeSeries.outlier_points),
        getPointY(timeSeries.outlier_points),
        "diamond",
        false
      )
    );
  }

  if (timeSeries.protected_points) {
    traces.push(
      makeMarkerTrace(
        "Special Points",
        getPointX(timeSeries.protected_points),
        getPointY(timeSeries.protected_points),
        "star",
        false
      )
    );
  }

  return traces;
}


/* =========================================================
   6. 분해 Trace 생성
---------------------------------------------------------
추세는 원 데이터 스케일이라 기본 표시 가능
계절성/잔차는 스케일 차이가 커질 수 있어 기본 숨김
========================================================= */

function buildDecompositionTraces(decomposition) {
  const traces = [];

  if (!decomposition) {
    return traces;
  }

  if (hasValues(decomposition.trend)) {
    traces.push(
      makeLineTrace(
        "Trend",
        decomposition.date,
        decomposition.trend,
        false
      )
    );
  }

  if (hasValues(decomposition.seasonal)) {
    traces.push(
      makeLineTrace(
        "Seasonality",
        decomposition.date,
        decomposition.seasonal,
        false
      )
    );
  }

  if (hasValues(decomposition.residual)) {
    traces.push(
      makeLineTrace(
        "Noise / Residual",
        decomposition.date,
        decomposition.residual,
        false
      )
    );
  }

  return traces;
}


/* =========================================================
   7. 통합 그래프 Trace 생성
========================================================= */

function buildTimeSeriesTraces(result) {
  const traces = [];

  const timeSeries = result.time_series || {};
  const decomposition = result.decomposition || {};
  const forecast = result.forecast || {};

  buildTrainTestTraces(forecast).forEach((trace) => traces.push(trace));
  buildValidationPredictionTraces(forecast).forEach((trace) => traces.push(trace));
  buildFuturePredictionTraces(forecast).forEach((trace) => traces.push(trace));
  buildDataAndPointTraces(timeSeries).forEach((trace) => traces.push(trace));
  buildDecompositionTraces(decomposition).forEach((trace) => traces.push(trace));

  return traces;
}


/* =========================================================
   8. 그래프 레이아웃
========================================================= */

function buildChartLayout(result) {
  const summary = result.summary || {};

  return {
    title: {
      text: `Train/Test 예측 검증${summary.best_model ? " - Best Model: " + summary.best_model : ""}`,
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
      y: -0.32,
      x: 0,
    },
    margin: {
      l: 60,
      r: 30,
      t: 60,
      b: 140,
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
   9. 그래프 렌더링
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
   10. 전역 객체 등록
========================================================= */

window.TIMEChart = {
  renderForecastChart,
};