"""
SQLAlchemy ORM 資料庫模型 - 測驗生成專用
只包含測驗相關的資料表模型
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from backend.database import Base


class QuizJob(Base):
    """
    題型測驗背景任務記錄
    用於追蹤長時間的題目生成任務狀態
    """
    __tablename__ = "quiz_jobs"

    job_id = Column(String, primary_key=True, index=True)          # 任務 ID
    job_type = Column(String, index=True)                          # 任務類型：listening / reading
    test_mode = Column(String, index=True)                         # 測驗模式：part1~part7
    status = Column(String, default="pending")                     # 狀態：pending / processing / completed / failed
    progress_json = Column(Text)                                   # 進度資訊（JSON 字串）
    message = Column(Text)                                         # 狀態訊息
    created_at = Column(DateTime, server_default=func.now())       # 建立時間
    completed_at = Column(DateTime)                                # 完成時間
    result_json = Column(Text)                                     # 結果資料（JSON 字串）


class QuizFolder(Base):
    """
    題型測驗資料夾
    用於組織和分類生成的測驗
    """
    __tablename__ = "quiz_folders"

    id = Column(String, primary_key=True, index=True)              # 資料夾 ID (UUID)
    name = Column(String, nullable=False)                          # 資料夾名稱
    color = Column(String, nullable=False)                         # 資料夾顏色（用於 UI 顯示）
    created_at = Column(DateTime, server_default=func.now())       # 建立時間
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())  # 更新時間


class QuizLog(Base):
    """
    題型測驗記錄
    儲存每次生成的測驗內容和作答結果
    """
    __tablename__ = "quiz_logs"
    __table_args__ = (
        # 為常用查詢建立索引
        Index('idx_quiz_log_mode', 'mode'),           # 按測驗模式查詢
        Index('idx_quiz_log_folder', 'folder_id'),    # 按資料夾查詢
        Index('idx_quiz_log_created', 'created_at'),  # 按建立時間查詢
    )

    id = Column(String, primary_key=True, index=True)                          # 測驗 ID (UUID)
    mode = Column(String, nullable=False)                                      # 測驗模式：part1-7
    title = Column(String, nullable=False)                                     # 測驗標題
    count = Column(Integer, nullable=False)                                    # 題目數量
    difficulty = Column(String, nullable=False)                                # 難度：easy / medium / hard
    folder_id = Column(String, ForeignKey("quiz_folders.id"), nullable=True)   # 所屬資料夾（可為空）
    payload_json = Column(Text)                                                # 測驗內容（JSON 字串）
    score_json = Column(Text)                                                  # 作答成績（JSON 字串）
    created_at = Column(DateTime, server_default=func.now())                   # 建立時間
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())  # 更新時間
