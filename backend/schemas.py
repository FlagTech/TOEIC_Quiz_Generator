"""
TOEIC Quiz Generator - Pydantic Request/Response Schemas
"""
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from datetime import datetime


# ========== TOEIC 閱讀測驗 Schemas (Part 5-7) ==========

class TOEICGenerateRequest(BaseModel):
    question_type: str
    count: int
    difficulty: Optional[str] = "medium"
    provider: str
    model: Optional[str] = None
    api_key: Optional[str] = None


class TOEICQuizResponse(BaseModel):
    questions: List[Any]
    question_type: str
    total_count: int


class TOEICAnswerSubmit(BaseModel):
    question_number: int
    user_answer: str
    correct_answer: str
    question_type: Optional[str] = None
    question_text: Optional[str] = None
    passage_style: Optional[str] = None
    passage: Optional[str] = None
    passages: Optional[List[str]] = None
    options: Optional[List[Any]] = None


class TOEICExplainRequest(BaseModel):
    answers: List[TOEICAnswerSubmit]
    provider: str
    model: Optional[str] = None
    api_key: Optional[str] = None


class TOEICExplanation(BaseModel):
    question_number: int
    user_answer: Optional[str] = None
    correct_answer: Optional[str] = None
    is_correct: bool
    explanation: str


# ========== 聽力測驗 Schemas (Part 1-4) ==========

class ListeningTestGenerateRequest(BaseModel):
    difficulty: Optional[str] = "medium"
    provider: str
    model: Optional[str] = None
    api_key: Optional[str] = None
    text_provider: Optional[str] = None
    text_model: Optional[str] = None
    text_api_key: Optional[str] = None
    media_provider: Optional[str] = None
    media_model: Optional[str] = None
    media_api_key: Optional[str] = None


class ListeningTestResponse(BaseModel):
    part1_questions: List[Any] = []
    part2_questions: List[Any] = []
    part3_questions: List[Any] = []
    part4_questions: List[Any] = []
    difficulty: str = "medium"
    total_count: int = 0


class ListeningTestJobStatus(BaseModel):
    job_id: str
    status: str
    progress: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ========== 閱讀測驗完整模擬 Schemas ==========

class ReadingTestGenerateRequest(BaseModel):
    difficulty: Optional[str] = "medium"
    provider: str
    model: Optional[str] = None
    api_key: Optional[str] = None


class ReadingTestResponse(BaseModel):
    part5_questions: List[Any] = []
    part6_questions: List[Any] = []
    part7_single_questions: List[Any] = []
    part7_multiple_questions: List[Any] = []
    difficulty: str = "medium"
    total_count: int = 0


class ReadingTestJobStatus(BaseModel):
    job_id: str
    status: str
    progress: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ========== 題型測驗背景任務 Schemas ==========

class QuizJobStatus(BaseModel):
    job_id: str
    status: str
    progress: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class QuizJobResult(BaseModel):
    questions: List[Any]
    question_type: Optional[str] = None
    total_count: Optional[int] = None


# ========== 資料夾管理 Schemas ==========

class QuizFolderCreateRequest(BaseModel):
    name: str
    color: str


class QuizFolderUpdateRequest(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None


class QuizFolderResponse(BaseModel):
    id: str
    name: str
    color: str
    created_at: Optional[datetime] = None


# ========== 測驗記錄 Schemas ==========

class QuizLogCreateRequest(BaseModel):
    mode: str
    title: str
    count: int
    difficulty: str
    folder_id: Optional[str] = None


class QuizLogUpdateRequest(BaseModel):
    title: Optional[str] = None
    folder_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    score: Optional[Dict[str, Any]] = None


class QuizLogSummary(BaseModel):
    id: str
    mode: str
    title: str
    count: int
    difficulty: str
    folder_id: Optional[str] = None
    created_at: Optional[datetime] = None
    score: Optional[Dict[str, Any]] = None


class QuizLogDetail(QuizLogSummary):
    payload: Optional[Dict[str, Any]] = None


# ========== PDF 匯出 Schemas ==========

class PDFExportRequest(BaseModel):
    test_data: Dict[str, Any]
    export_mode: str  # 'questions_only' | 'answer_key'
    include_user_answers: bool = False
