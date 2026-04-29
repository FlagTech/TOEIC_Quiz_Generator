"""
資料庫連接與會話管理模組
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# 資料庫檔案路徑 - 使用獨立的測驗資料庫
DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "quiz_data.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# 建立資料庫引擎
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite 需要此參數
)

# 建立資料庫會話類別
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 建立 ORM 基類
Base = declarative_base()


def get_db():
    """
    取得資料庫會話

    Yields:
        SessionLocal: 資料庫會話物件
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    初始化資料庫，建立所有資料表
    """
    from backend import models  # 導入模型以確保它們被註冊
    Base.metadata.create_all(bind=engine)


