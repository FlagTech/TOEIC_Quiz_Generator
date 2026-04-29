"""
TOEIC 題目生成的 Pydantic Response Schemas

這些 schemas 用於 Gemini API 的 response_json_schema 參數，
確保 AI 生成的 JSON 格式完全符合預期結構。
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class TOEICOptionSchema(BaseModel):
    """TOEIC 選項 Schema（通用）"""
    label: str = Field(description="Option label: A, B, C, or D")
    text: str = Field(description="Option text content")


# ==================== 聽力測驗 Schemas ====================

class Part1GeneratedResponse(BaseModel):
    """Part 1 Vision AI 生成回應"""
    correct_description: str = Field(description="Correct description")
    distractor_1: str = Field(description="Distractor option 1")
    distractor_2: str = Field(description="Distractor option 2")
    distractor_3: str = Field(description="Distractor option 3")


class Part2GeneratedResponse(BaseModel):
    """Part 2 生成回應"""
    question: str = Field(description="Question text")
    options: List[TOEICOptionSchema] = Field(description="Three options (A, B, C)")
    correct_answer: Literal["A", "B", "C"] = Field(description="Correct answer")


class ListeningQuestionSchema(BaseModel):
    """聽力測驗問題 Schema（Part 3, 4 通用）"""
    question_text: str = Field(description="Question text")
    options: List[TOEICOptionSchema] = Field(description="Four options")
    correct_answer: Literal["A", "B", "C", "D"] = Field(description="Correct answer")


# ==================== 閱讀測驗 Schemas ====================

class TOEICQuestionSchema(BaseModel):
    """TOEIC 題目 Schema（單題）"""
    question_number: int = Field(description="Question number")
    question_type: str = Field(description="Question type: sentence / paragraph / single_passage / multiple_passage")
    question_text: str = Field(
        description=(
            "Question text or sentence. "
            "For paragraph type, this must contain the full passage as Markdown text, "
            "with its paragraph and document structure preserved."
        )
    )
    blank_position: Optional[int] = Field(None, description="Blank position (for paragraph type only)")
    passage_style: Optional[str] = Field(
        None,
        description=(
            "Passage style (for paragraph/single/multiple types), such as email, notice, memo, "
            "article, schedule, advertisement, or invoice"
        )
    )
    passage: Optional[str] = Field(
        None,
        description=(
            "Passage content for single_passage type. "
            "Must be Markdown-formatted text with its paragraph and document structure preserved. "
            "For structured documents like invoices, schedules, notices, memos, or emails, "
            "do not flatten everything into a single line."
        )
    )
    passages: Optional[List[str]] = Field(
        None,
        description=(
            "Multiple passage content list for multiple_passage type. "
            "Each passage item must be Markdown-formatted text with its paragraph and document structure preserved."
        )
    )
    options: List[TOEICOptionSchema] = Field(description="Four options")
    correct_answer: str = Field(description="Correct answer: A, B, C, or D")


class TOEICQuestionsResponseSchema(BaseModel):
    """TOEIC 題目生成回應 Schema（多題）"""
    questions: List[TOEICQuestionSchema] = Field(description="List of questions")


class TOEICExplanationItemSchema(BaseModel):
    """TOEIC 單題詳解 Schema"""
    question_number: int = Field(description="題號")
    is_correct: bool = Field(description="使用者是否答對")
    explanation: str = Field(description="詳細解說，包含正確答案原因、其他選項錯誤原因、相關文法或詞彙知識點")


class TOEICExplanationsResponseSchema(BaseModel):
    """TOEIC 詳解生成回應 Schema（多題）"""
    explanations: List[TOEICExplanationItemSchema] = Field(description="詳解列表")
