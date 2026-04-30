"""
TOEIC 測驗生成 - FastAPI 主程式
專注於 AI 驅動的 TOEIC 模擬測驗生成，支援完整 7 種題型
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

from backend.database import init_db
from backend.routers import reading, listening

logging.getLogger("uvicorn.access").disabled = True

# 建立 FastAPI 應用程式
app = FastAPI(
    title="TOEIC 測驗生成",
    description="AI 驅動的 TOEIC 模擬測驗生成器，支援 Reading (Part 5-7) 和 Listening (Part 1-4) 完整題型",
    version="1.0.0"
)

# 設定 CORS - 允許前端跨域請求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 開發環境允許所有來源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 掛載靜態檔案 - 聽力測驗的圖片和音檔
os.makedirs("data/listening_images", exist_ok=True)
os.makedirs("data/audio_cache", exist_ok=True)
app.mount("/images/part1", StaticFiles(directory="data/listening_images"), name="listening_images")
app.mount("/audio", StaticFiles(directory="data/audio_cache"), name="audio_cache")

# 註冊路由 - 只註冊測驗相關路由
app.include_router(reading.router)   # 閱讀測驗 (Part 5-7)
app.include_router(listening.router) # 聽力測驗 (Part 1-4)

# SPA 前端靜態檔案目錄 (Vue dist)
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
SPA_DIST_DIR = os.path.join(BASE_DIR, 'frontend', 'dist')

# 掛載 SPA 到根路徑，但要在 API 路由之後，這樣 /api/* 仍然有效
if os.path.isdir(SPA_DIST_DIR):
    app.mount('/', StaticFiles(directory=SPA_DIST_DIR, html=True), name='spa')


@app.on_event("startup")
async def startup_event():
    """
    應用程式啟動時執行的初始化操作
    """
    print(">>> 正在啟動 TOEIC 測驗生成...")

    # 初始化資料庫（建立測驗相關資料表）
    print(">>> 初始化資料庫...")
    init_db()

    print(">>> 系統啟動完成！")
    print(">>> API 文件：http://localhost:8001/docs")
    print(">>> 前端介面：http://localhost:5174")


@app.get("/health")
async def health_check():
    """
    健康檢查端點

    Returns:
        dict: 系統狀態
    """
    return {
        "status": "healthy",
        "service": "TOEIC 測驗生成 API"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8001,  # 使用 8001 避免與原專案衝突
        reload=True,
        access_log=False
    )
