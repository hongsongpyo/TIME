/* =========================================================
   TIME - frontend/js/api.js
---------------------------------------------------------
역할
1. FastAPI 서버 주소 관리
2. CSV 업로드 API 요청
3. 다변량 시계열 이상탐지 API 요청
4. 민감도 / 탐지 방법 payload 생성
5. API 응답/에러 공통 처리
6. 기존 호출 방식과의 호환성 유지
7. 전역 변수 충돌 방지
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

  const DEFAULT_ANALYSIS_MODE = "anomaly";

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
  ---------------------------------------------------------
  현재 웹앱은 이상탐지 전용으로 변경
  기존 코드가 forecast를 보내도 anomaly로 처리
  ========================================================= */

  function normalizeAnalysisMode(mode) {
    const modeText = String(mode || DEFAULT_ANALYSIS_MODE)
      .trim()
      .toLowerCase();

    if (
      modeText === "anomaly" ||
      modeText === "anomaly_detection" ||
      modeText === "detect" ||
      modeText === "outlier" ||
      modeText === "이상탐지"
    ) {
      return "anomaly";
    }

    return "anomaly";
  }


  /* =========================================================
     5. 이상탐지 방법 정규화
  ========================================================= */

  function normalizeAnomalyMethod(method) {
    const methodText = String(method || DEFAULT_ANOMALY_OPTIONS.method)
      .trim()
      .toLowerCase();

    const aliasMap = {
      "자동": "auto",
      "오토": "auto",
      "isolationforest": "isolation_forest",
      "isolation forest": "isolation_forest",
      "격리숲": "isolation_forest",
      "z-score": "zscore",
      "z score": "zscore",
      "z스코어": "zscore",
      "stl": "stl_residual",
      "stl residual": "stl_residual",
      "잔차": "stl_residual",
    };

    const normalizedMethod = aliasMap[methodText] || methodText;

    const allowedMethods = [
      "auto",
      "isolation_forest",
      "zscore",
      "iqr",
      "stl_residual",
    ];

    if (allowedMethods.includes(normalizedMethod)) {
      return normalizedMethod;
    }

    return DEFAULT_ANOMALY_OPTIONS.method;
  }


  /* =========================================================
     6. 민감도 정규화
  ---------------------------------------------------------
  low    : 낮음  → threshold 높음 → 확실한 이상만 탐지
  medium : 보통
  high   : 높음  → threshold 낮음 → 더 많이 탐지
  ========================================================= */

  function normalizeAnomalySensitivity(sensitivity) {
    const sensitivityText = String(
      sensitivity || DEFAULT_ANOMALY_OPTIONS.sensitivity
    )
      .trim()
      .toLowerCase();

    const highValues = [
      "high",
      "높음",
      "민감",
      "높은",
    ];

    const mediumValues = [
      "medium",
      "normal",
      "보통",
      "중간",
      "기본",
    ];

    const lowValues = [
      "low",
      "낮음",
      "낮은",
    ];

    if (highValues.includes(sensitivityText)) {
      return "high";
    }

    if (lowValues.includes(sensitivityText)) {
      return "low";
    }

    if (mediumValues.includes(sensitivityText)) {
      return "medium";
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
  ---------------------------------------------------------
  형태:
  [
    {
      row: 3,
      column: "energy"
    }
  ]

  특정 셀 단위 보호를 유지한다.
  같은 행 전체를 보호하지 않는다.
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
  권장 신규 호출:
    runAnalysis(tableData, protectedCells, anomalyOptions)

  기존 호출:
    runAnalysis(tableData, horizon, protectedCells)

  추가 호환 호출:
    runAnalysis(tableData, "anomaly", horizon, protectedCells, anomalyOptions)
  ========================================================= */

  function looksLikeProtectedCells(value) {
    return Array.isArray(value);
  }

  function looksLikeAnomalyOptions(value) {
    return (
      value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      (
        value.method !== undefined ||
        value.sensitivity !== undefined
      )
    );
  }

  function parseRunAnalysisArguments(args) {
    const first = args[0];
    const second = args[1];
    const third = args[2];
    const fourth = args[3];

    // runAnalysis(tableData, protectedCells, anomalyOptions)
    if (looksLikeProtectedCells(first)) {
      return {
        mode: "anomaly",
        horizon: 1,
        protectedCells: first,
        anomalyOptions: looksLikeAnomalyOptions(second)
          ? second
          : DEFAULT_ANOMALY_OPTIONS,
      };
    }

    // runAnalysis(tableData, "anomaly", horizon, protectedCells, anomalyOptions)
    if (typeof first === "string") {
      return {
        mode: normalizeAnalysisMode(first),
        horizon: second || 1,
        protectedCells: looksLikeProtectedCells(third) ? third : [],
        anomalyOptions: looksLikeAnomalyOptions(fourth)
          ? fourth
          : DEFAULT_ANOMALY_OPTIONS,
      };
    }

    // 기존 호출: runAnalysis(tableData, horizon, protectedCells)
    return {
      mode: "anomaly",
      horizon: 1,
      protectedCells: looksLikeProtectedCells(second) ? second : [],
      anomalyOptions: looksLikeAnomalyOptions(third)
        ? third
        : DEFAULT_ANOMALY_OPTIONS,
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
     11. 자동 이상탐지 요청
  ---------------------------------------------------------
  editor.html에서 사용

  권장 호출:
    runAnalysis(
      tableData,
      protectedCells,
      {
        method: "auto",
        sensitivity: "medium"
      }
    )
  ========================================================= */

  async function runAnalysis(tableData, ...args) {
    if (!Array.isArray(tableData) || tableData.length === 0) {
      throw new Error("분석할 데이터가 없습니다.");
    }

    const parsedArgs = parseRunAnalysisArguments(args);

    const normalizedMode = normalizeAnalysisMode(parsedArgs.mode);
    const normalizedProtectedCells = normalizeProtectedCells(
      parsedArgs.protectedCells
    );
    const normalizedAnomalyOptions = normalizeAnomalyOptions(
      parsedArgs.anomalyOptions
    );

    const payload = {
      data: tableData,

      // 현재 백엔드는 anomaly 전용
      mode: normalizedMode,

      // 기존 main.py / editor.js 호환용
      horizon: 1,

      protected_cells: normalizedProtectedCells,

      anomaly_options: normalizedAnomalyOptions,

      // main.py가 직접 method/sensitivity도 받을 수 있도록 중복 제공
      method: normalizedAnomalyOptions.method,
      sensitivity: normalizedAnomalyOptions.sensitivity,
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
     12. 이상탐지 전용 요청 함수
  ========================================================= */

  async function runAnomalyAnalysis(
    tableData,
    protectedCells = [],
    anomalyOptions = DEFAULT_ANOMALY_OPTIONS
  ) {
    return runAnalysis(
      tableData,
      protectedCells,
      anomalyOptions
    );
  }


  /* =========================================================
     13. 구버전 함수명 호환
  ---------------------------------------------------------
  예측 기능은 제거했지만, 기존 코드에서 runForecastAnalysis를
  호출하더라도 오류가 나지 않도록 anomaly 분석으로 연결한다.
  ========================================================= */

  async function runForecastAnalysis(
    tableData,
    horizon = 12,
    protectedCells = []
  ) {
    return runAnalysis(
      tableData,
      protectedCells,
      DEFAULT_ANOMALY_OPTIONS
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
    runAnomalyAnalysis,

    // 구버전 호환용
    runForecastAnalysis,

    normalizeAnomalyMethod,
    normalizeAnomalySensitivity,
    normalizeAnomalyOptions,
  };
})();