/* =========================================================
   TIME - frontend/js/api.js
---------------------------------------------------------
역할
1. FastAPI 서버 주소 관리
2. CSV 업로드 API 요청
3. 자동 분석 API 요청
4. 예측 / 이상탐지 mode 분기용 payload 생성
5. API 응답/에러 공통 처리
6. 전역 변수 충돌 방지
========================================================= */

(function () {
  "use strict";

  /* =========================================================
     1. API 기본 설정
  ========================================================= */

  const API_BASE_URL = "https://time-api-ocdq.onrender.com";


  /* =========================================================
     2. 기본값
  ========================================================= */

  const DEFAULT_ANALYSIS_MODE = "forecast";

  const DEFAULT_ANOMALY_OPTIONS = {
    method: "auto",
    sensitivity: "medium",
  };


  /* =========================================================
     3. 공통 응답 처리
  ========================================================= */

  async function handleResponse(response) {
    let data = null;

    try {
      data = await response.json();
    } catch (error) {
      throw new Error("서버 응답을 읽을 수 없습니다.");
    }

    if (!response.ok) {
      let message = "요청 처리 중 오류가 발생했습니다.";

      if (typeof data.detail === "string") {
        message = data.detail;
      } else if (Array.isArray(data.detail)) {
        message = data.detail
          .map((err) => {
            const loc = err.loc ? err.loc.join(".") : "";
            return `${loc}: ${err.msg}`;
          })
          .join("\n");
      } else if (data.detail && typeof data.detail === "object") {
        message = JSON.stringify(data.detail, null, 2);
      }

      throw new Error(message);
    }

    return data;
  }


  /* =========================================================
     4. 분석 모드 정규화
  ========================================================= */

  function normalizeAnalysisMode(mode) {
    const modeText = String(mode || DEFAULT_ANALYSIS_MODE)
      .trim()
      .toLowerCase();

    if (modeText === "anomaly") {
      return "anomaly";
    }

    return "forecast";
  }

  function isAnalysisMode(value) {
    const text = String(value || "")
      .trim()
      .toLowerCase();

    return text === "forecast" || text === "anomaly";
  }


  /* =========================================================
     5. Horizon 정규화
  ========================================================= */

  function normalizeHorizon(horizon, mode) {
    const normalizedMode = normalizeAnalysisMode(mode);

    if (normalizedMode === "anomaly") {
      return 1;
    }

    if (horizon === "auto") {
      return "auto";
    }

    const horizonValue = Number(horizon);

    if (!Number.isFinite(horizonValue) || horizonValue <= 0) {
      return 12;
    }

    return Math.floor(horizonValue);
  }


  /* =========================================================
     6. 이상탐지 옵션 정규화
  ========================================================= */

  function normalizeAnomalyMethod(method) {
    const methodText = String(method || DEFAULT_ANOMALY_OPTIONS.method)
      .trim()
      .toLowerCase();

    const allowedMethods = [
      "auto",
      "isolation_forest",
      "zscore",
      "iqr",
      "stl_residual",
    ];

    if (allowedMethods.includes(methodText)) {
      return methodText;
    }

    return DEFAULT_ANOMALY_OPTIONS.method;
  }

  function normalizeAnomalySensitivity(sensitivity) {
    const sensitivityText = String(
      sensitivity || DEFAULT_ANOMALY_OPTIONS.sensitivity
    )
      .trim()
      .toLowerCase();

    const allowedSensitivities = [
      "low",
      "medium",
      "high",
    ];

    if (allowedSensitivities.includes(sensitivityText)) {
      return sensitivityText;
    }

    return DEFAULT_ANOMALY_OPTIONS.sensitivity;
  }

  function normalizeAnomalyOptions(options) {
    if (!options || typeof options !== "object") {
      return {
        ...DEFAULT_ANOMALY_OPTIONS,
      };
    }

    return {
      method: normalizeAnomalyMethod(options.method),
      sensitivity: normalizeAnomalySensitivity(options.sensitivity),
    };
  }


  /* =========================================================
     7. 특이치 보호 셀 정규화
  ========================================================= */

  function normalizeProtectedCells(protectedCells) {
    if (!Array.isArray(protectedCells)) {
      return [];
    }

    return protectedCells
      .filter((cell) => {
        if (!cell) {
          return false;
        }

        const rowNumber = Number(cell.row);

        return (
          Number.isInteger(rowNumber) &&
          rowNumber >= 0 &&
          cell.column !== undefined &&
          cell.column !== null &&
          String(cell.column).trim() !== ""
        );
      })
      .map((cell) => {
        return {
          row: Number(cell.row),
          column: String(cell.column),
        };
      });
  }


  /* =========================================================
     8. 기존 호출 방식 호환 처리
  ---------------------------------------------------------
  신규 호출:
    runAnalysis(tableData, mode, horizon, protectedCells, anomalyOptions)

  기존 호출:
    runAnalysis(tableData, horizon, protectedCells)
  ========================================================= */

  function parseRunAnalysisArguments(
    modeOrHorizon,
    horizonOrProtectedCells,
    protectedCellsOrAnomalyOptions,
    anomalyOptionsArg
  ) {
    if (isAnalysisMode(modeOrHorizon)) {
      return {
        mode: normalizeAnalysisMode(modeOrHorizon),
        horizon: horizonOrProtectedCells,
        protectedCells: protectedCellsOrAnomalyOptions,
        anomalyOptions: anomalyOptionsArg,
      };
    }

    return {
      mode: "forecast",
      horizon: modeOrHorizon,
      protectedCells: horizonOrProtectedCells,
      anomalyOptions: DEFAULT_ANOMALY_OPTIONS,
    };
  }


  /* =========================================================
     9. 서버 상태 확인
  ========================================================= */

  async function checkServerHealth() {
    const response = await fetch(`${API_BASE_URL}/health`);
    return handleResponse(response);
  }


  /* =========================================================
     10. CSV 업로드 요청
  ---------------------------------------------------------
  upload.html에서 사용
  ========================================================= */

  async function uploadCSV(file) {
    if (!file) {
      throw new Error("업로드할 CSV 파일이 없습니다.");
    }

    if (!file.name || !file.name.toLowerCase().endsWith(".csv")) {
      throw new Error("CSV 파일만 업로드할 수 있습니다.");
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
     11. 자동 분석 요청
  ---------------------------------------------------------
  editor.html에서 사용

  신규 호출 형태:
  runAnalysis(
    tableData,
    mode,
    horizon,
    protectedCells,
    anomalyOptions
  )
  ========================================================= */

  async function runAnalysis(
    tableData,
    modeOrHorizon = "forecast",
    horizonOrProtectedCells = 12,
    protectedCellsOrAnomalyOptions = [],
    anomalyOptionsArg = DEFAULT_ANOMALY_OPTIONS
  ) {
    if (!Array.isArray(tableData) || tableData.length === 0) {
      throw new Error("분석할 데이터가 없습니다.");
    }

    const parsedArgs = parseRunAnalysisArguments(
      modeOrHorizon,
      horizonOrProtectedCells,
      protectedCellsOrAnomalyOptions,
      anomalyOptionsArg
    );

    const normalizedMode = normalizeAnalysisMode(parsedArgs.mode);
    const normalizedHorizon = normalizeHorizon(
      parsedArgs.horizon,
      normalizedMode
    );
    const normalizedProtectedCells = normalizeProtectedCells(
      parsedArgs.protectedCells
    );
    const normalizedAnomalyOptions = normalizeAnomalyOptions(
      parsedArgs.anomalyOptions
    );

    if (
      normalizedMode === "forecast" &&
      normalizedHorizon !== "auto" &&
      (!Number(normalizedHorizon) || Number(normalizedHorizon) <= 0)
    ) {
      throw new Error("시평은 1 이상의 숫자이거나 auto여야 합니다.");
    }

    const payload = {
      data: tableData,
      mode: normalizedMode,
      horizon: normalizedHorizon,
      protected_cells: normalizedProtectedCells,
      anomaly_options: normalizedAnomalyOptions,
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
     12. 예측 전용 요청 함수
  ========================================================= */

  async function runForecastAnalysis(
    tableData,
    horizon = 12,
    protectedCells = []
  ) {
    return runAnalysis(
      tableData,
      "forecast",
      horizon,
      protectedCells,
      DEFAULT_ANOMALY_OPTIONS
    );
  }


  /* =========================================================
     13. 이상탐지 전용 요청 함수
  ========================================================= */

  async function runAnomalyAnalysis(
    tableData,
    protectedCells = [],
    anomalyOptions = DEFAULT_ANOMALY_OPTIONS
  ) {
    return runAnalysis(
      tableData,
      "anomaly",
      1,
      protectedCells,
      anomalyOptions
    );
  }


  /* =========================================================
     14. 전역 객체 등록
  ========================================================= */

  window.TIMEApi = {
    API_BASE_URL,

    checkServerHealth,
    uploadCSV,

    runAnalysis,
    runForecastAnalysis,
    runAnomalyAnalysis,
  };
})();