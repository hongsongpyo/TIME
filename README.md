# TIME

TIME는 CSV 기반 시계열 데이터 자동 분석 및 예측 웹 애플리케이션입니다.

사용자는 단변량 시계열 CSV 파일을 업로드하고,
직접 데이터를 수정한 뒤,
자동 시계열 분석 및 예측 결과를 인터랙션 그래프로 확인할 수 있습니다.

---

# 주요 기능

## 1. CSV 업로드

- 단변량 시계열 CSV 업로드
- 날짜 컬럼 자동 탐색
- 수요(value) 컬럼 자동 탐색

---

## 2. 데이터 편집

- 엑셀 형태 데이터 편집
- 행 추가
- 열 추가
- 셀 값 수정
- 컬럼명 수정
- 시평(horizon) 설정
- 특이치 보호 설정

특이치로 지정된 값은 이상치 처리에서 제외됩니다.

---

## 3. 자동 시계열 분석

자동으로 다음 과정을 수행합니다.

### 전처리

- 날짜 정렬
- 결측치 탐지
- 결측치 보간
- 이상치 탐지
- 이상치 보정
- 특이치 보호

### 시계열 분해

- 추세(Trend)
- 주기/계절성(Seasonality)
- 노이즈/잔차(Residual)

### 시계열 예측

- AutoARIMA
- Holt-Winters
- Exponential Smoothing
- Naive Forecast

---

## 4. 인터랙션 그래프

Plotly 기반 인터랙션 그래프 제공

다음 요소를 ON/OFF 할 수 있습니다.

- 원본 데이터
- 전처리 데이터
- 결측치
- 이상치
- 특이치
- AutoARIMA 예측
- Holt-Winters 예측
- Exponential Smoothing 예측
- Naive 예측
- 추세
- 주기/계절성
- 노이즈/잔차

---

## 5. 모델별 성능 비교 대시보드

다양한 평가지표를 통해 모델 성능 비교 가능

| Metric | Description |
|---|---|
| MAE | Mean Absolute Error |
| MSE | Mean Squared Error |
| RMSE | Root Mean Squared Error |
| MAPE | Mean Absolute Percentage Error |
| SMAPE | Symmetric MAPE |
| MASE | Mean Absolute Scaled Error |
| AIC | Akaike Information Criterion |
| BIC | Bayesian Information Criterion |

---

# 프로젝트 구조

```text
TIME/
├─ backend/
│  ├─ main.py
│  ├─ analysis.py
│  ├─ preprocessing.py
│  ├─ forecasting.py
│  ├─ decomposition.py
│  ├─ metrics.py
│  └─ requirements.txt
│
├─ frontend/
│  ├─ upload.html
│  ├─ editor.html
│  ├─ result.html
│  │
│  ├─ css/
│  │  └─ style.css
│  │
│  └─ js/
│     ├─ upload.js
│     ├─ editor.js
│     ├─ result.js
│     ├─ api.js
│     ├─ chart.js
│     └─ storage.js
│
├─ data/
│  └─ sample.csv
│
└─ README.md
```

---

# 설치 방법

## 1. Python 패키지 설치

```bash
pip install -r requirements.txt
```

---

## 2. FastAPI 서버 실행

backend 폴더에서 실행

```bash
uvicorn main:app --reload
```

서버 실행 주소:

```text
http://127.0.0.1:8000
```

---

## 3. 프론트엔드 실행

frontend/upload.html 파일을 브라우저에서 실행

추천:

- VSCode Live Server 사용

---

# 사용 방법

## 1단계

CSV 업로드

---

## 2단계

데이터 편집

- 값 수정
- 특이치 설정
- 시평 설정

---

## 3단계

자동 분석 실행

---

## 4단계

결과 확인

- 인터랙션 그래프
- 모델별 성능 비교 대시보드

---

# 사용 라이브러리

## Frontend

- HTML
- CSS
- JavaScript
- Plotly.js

## Backend

- FastAPI
- pandas
- numpy
- statsmodels
- pmdarima
- scikit-learn
- scipy

---

# 개발 환경

- Python 3.12
- FastAPI
- Plotly.js

---

# 제작

Made by Songpyo Hong