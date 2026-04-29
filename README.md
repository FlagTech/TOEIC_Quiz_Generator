# TOEIC Quiz Generator

AI 驅動的 TOEIC 練習系統，前端使用 Vue 3，後端使用 FastAPI。專案目前分成兩條主要使用流程：

- 題型測驗：依 Part 1-7 單獨生成、作答、批改與看詳解
- 模擬測驗：分開生成 Listening 全卷或 Reading 全卷，支援背景任務、接續進度、歷史記錄與 PDF 匯出

目前前端設定頁與主要使用流程以 `Google Gemini` 為核心。閱讀題生成的後端 schema 仍保留 provider 欄位，但這份程式碼中的前端與聽力流程實際上都以 Gemini 為主。

## 功能概覽

### 題型測驗

- Part 1：照片描述，生成圖片與四個語音選項
- Part 2：應答問題，生成題幹與三個語音選項
- Part 3：簡短對話，生成對話音檔、三題題組與逐題詳解
- Part 4：簡短獨白，生成獨白音檔、三題題組與逐題詳解
- Part 5：句子填空
- Part 6：段落填空
- Part 7：單篇閱讀、多篇閱讀

### 模擬測驗

- Listening 全卷背景生成：Part 1-4
- Reading 全卷背景生成：Part 5-7
- 任務狀態輪詢、失敗後接續、取消任務
- 測驗歷史記錄與資料夾分類
- Reading 測驗可匯出 PDF 題本或答案版

### 其他能力

- 單題或整份測驗詳解生成
- Gemini API Key 與模型設定頁
- 深色模式
- Part 1 圖片與音檔、Part 2-4 音檔快取

## 目前架構

### 前端

前端位於 `frontend/`，是 Vite + Vue 3 + TypeScript SPA。

- `src/main.ts`
  - 建立 Vue app
  - 掛載 Pinia、`pinia-plugin-persistedstate`、`vue-toastification`
- `src/router/index.ts`
  - 三個頁面路由：`/`、`/full-test`、`/settings`
  - 透過 `meta.title` 更新分頁標題
- `src/views/QuizView.vue`
  - 題型測驗主頁
  - 管理 Part 1-7 的生成、作答、詳解、背景任務接續與測驗記錄
- `src/views/FullTestView.vue`
  - Listening / Reading 全卷模擬測驗
  - 管理背景任務輪詢、接續、結果頁、PDF 匯出與資料夾
- `src/views/SettingsView.vue`
  - Gemini API Key 與模型設定
  - 目前 UI 固定走 Gemini
- `src/stores/settings.ts`
  - 使用 Pinia 儲存主題、Gemini API Key、預設模型
  - API Key 額外寫入 `localStorage`
- `src/services/api.ts`
  - Axios API client
  - 封裝 `/api/toeic` 與 `/api/listening` 呼叫

### 後端

後端位於 `backend/`，由 `backend.main:app` 啟動。

- `main.py`
  - 建立 FastAPI app
  - 註冊 CORS
  - 掛載 `/images/part1` 與 `/audio` 靜態檔案
  - 註冊 `reading` 與 `listening` 路由
  - 若存在 `frontend/dist`，會把 SPA 掛到根路徑
- `database.py`
  - SQLite 連線、`SessionLocal`、`Base`、`init_db()`
- `models.py`
  - `QuizJob`：背景任務狀態與結果
  - `QuizFolder`：資料夾
  - `QuizLog`：測驗記錄、payload、score
- `schemas.py`
  - 題型生成、完整測驗、任務狀態、資料夾、記錄、PDF 匯出 schema

### API 模組分工

- `backend/routers/reading.py`
  - `/api/toeic/*`
  - Reading 題型生成
  - Reading / Listening 全卷背景任務
  - 詳解生成
  - 資料夾與測驗記錄 CRUD
  - PDF 匯出
- `backend/routers/listening.py`
  - `/api/listening/*`
  - Part 1-4 題型生成
  - 題型測驗背景任務
  - 聽力詳解生成
  - 音檔切分與音訊處理

### Prompt 與 AI 客戶端

- `backend/prompt_engine/`
  - `reading_prompts.py`、`listening_prompts.py`、`explanation_prompts.py`
  - `prompt_manager.py` 作為統一入口
  - `toeic_response_schemas.py` 定義 Gemini schema-based response
- `backend/ai_clients/`
  - `gemini_client.py`：文字生成
  - `gemini_imagen_client.py`：圖片生成
  - `gemini_tts_client.py`：TTS 生成
  - `ai_client_factory.py`：抽象工廠

### 資料與持久化

- SQLite：`data/quiz_data.db`
- Part 1 圖片：`data/listening_images/`
- 音檔快取：`data/audio_cache/`
- 前端 localStorage：
  - 設定頁模型與主題
  - 題型測驗背景 job id
  - 模擬測驗側邊欄 metadata 與當前 job 狀態

## 執行流程

### 開發模式

- 前端由 Vite 跑在 `http://localhost:5174`
- 後端預設跑在 `http://localhost:8001`
- Vite 會代理：
  - `/api`
  - `/audio`
  - `/images`

### 單機部署模式

當 `frontend/dist` 已存在時，`backend/main.py` 會把前端 build 結果掛到 `/`，由 FastAPI 直接提供 SPA 靜態檔。

## 技術棧

### Frontend

- Vue 3
- TypeScript
- Vite
- Pinia
- Vue Router
- Axios
- Vue Toastification
- Marked
- Chart.js / vue-chartjs
- Tailwind CSS 4

### Backend

- FastAPI
- SQLAlchemy
- SQLite
- Pydantic v2
- Google Gemini API
- ReportLab

## 環境需求

- Python `3.11+`
- Node.js `20.19+` 或 `22.12+`
- `uv`
- Google Gemini API Key
- `ffmpeg`
  - 聽力題型的音訊切分流程會呼叫 `ffmpeg`
  - 若系統沒有 `ffmpeg`，Part 1-4 的部分語音處理可能失敗

## 快速開始

### 1. 設定環境變數

複製 `.env.example` 為 `.env`：

```bash
GEMINI_API_KEY=AIza...
BACKEND_PORT=8001
```

說明：

- `GEMINI_API_KEY`
  - 後端使用的 Gemini API Key
  - 前端設定頁也會把使用者輸入的 Gemini Key 存到瀏覽器 `localStorage`
- `BACKEND_PORT`
  - Vite proxy 與啟動腳本使用的後端 port

### 2. 一鍵啟動

Windows 可直接執行：

```bat
setup_and_start.bat
```

腳本會：

1. 檢查 Python、Node.js、uv
2. 執行 `uv sync`
3. 安裝 `frontend` 的 npm 套件
4. 自動選擇可用後端 port（預設從 `8001` 起）
5. 開兩個視窗啟動 FastAPI 與 Vite

### 3. 手動啟動

後端：

```bash
uv sync
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload
```

前端：

```bash
cd frontend
npm install
npm run dev
```

啟動後：

- Frontend: `http://localhost:5174`
- Backend: `http://localhost:8001`
- API Docs: `http://localhost:8001/docs`

## 目錄結構

```text
TOEIC_Quiz_Generator/
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── ai_clients/
│   ├── prompt_engine/
│   ├── routers/
│   │   ├── listening.py
│   │   └── reading.py
│   └── utils/
│       ├── coco_caption_loader.py
│       └── pdf_generator.py
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── public/
│   └── src/
│       ├── App.vue
│       ├── main.ts
│       ├── assets/
│       ├── components/
│       ├── composables/
│       ├── router/
│       ├── services/
│       ├── stores/
│       ├── types/
│       └── views/
├── data/
│   ├── quiz_data.db
│   ├── coco_captions.json
│   ├── listening_images/
│   └── audio_cache/
├── prompts/
├── .env.example
├── pyproject.toml
└── setup_and_start.bat
```

## API 概覽

### 基礎端點

- `GET /health`
- `GET /docs`

### 題型測驗

- `POST /api/listening/generate-part1`
- `POST /api/listening/generate-part2`
- `POST /api/listening/generate-part3`
- `POST /api/listening/generate-part4`
- `POST /api/toeic/generate`
- `POST /api/toeic/explain`
- `POST /api/listening/explain`

### 背景任務

- 題型測驗
  - `POST /api/listening/generate-part{1..4}-job`
  - `GET /api/listening/generate-job/{job_id}`
  - `GET /api/listening/generate-job/{job_id}/result`
  - `POST /api/toeic/generate-job`
  - `GET /api/toeic/generate-job/{job_id}`
  - `GET /api/toeic/generate-job/{job_id}/result`
- 全卷模擬
  - `POST /api/toeic/listening-test/job`
  - `POST /api/toeic/listening-test/job/{job_id}/resume`
  - `DELETE /api/toeic/listening-test/job/{job_id}`
  - `POST /api/toeic/reading-test/job`
  - `POST /api/toeic/reading-test/job/{job_id}/resume`
  - `DELETE /api/toeic/reading-test/job/{job_id}`

### 記錄與輸出

- `GET/POST/PUT/DELETE /api/toeic/quiz-folders`
- `GET/POST/PUT/DELETE /api/toeic/quiz-logs`
- `POST /api/toeic/export-pdf`

## 目前實作上的重點

- 設定頁目前只暴露 Gemini 設定，前端主要流程固定使用 Gemini
- Listening 題型的 TTS 與 Part 1 媒體生成由 Gemini 處理
- Reading API schema 保留 provider / model 欄位，但目前專案主流程不是多 provider UI
- 完整模擬測驗的歷史記錄採混合儲存：
  - metadata 在 localStorage
  - test payload 與 score 同步到後端 `quiz_logs`

## 開發指令

```bash
uv sync
uv run uvicorn backend.main:app --reload --port 8001
```

```bash
cd frontend
npm install
npm run dev
npm run type-check
npm run build
```

## 授權

本專案目前未附正式授權條款；若要對外散佈或商用，請先補上授權與 API 使用政策說明。
