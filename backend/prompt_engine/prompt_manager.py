"""
Prompt 管理器 - TOEIC Quiz Generator

統一管理 TOEIC 測驗相關的 AI Prompt 模板
"""
from typing import Optional
from .reading_prompts import ReadingPrompts
from .explanation_prompts import ExplanationPrompts


class PromptManager:
    """Prompt 管理器，統一管理 TOEIC 測驗 AI Prompt"""

    def __init__(self):
        """初始化管理器"""
        self.reading_prompts = ReadingPrompts()
        self.explanation_prompts = ExplanationPrompts()

    # ==================== TOEIC 考題相關 ====================

    def get_toeic_sentence_prompt(self, count: int, difficulty: str = "medium", topic_hint: str = None) -> str:
        """
        取得 TOEIC 句子填空考題生成 Prompt

        Args:
            count: 題數
            difficulty: 難度 (easy/medium/hard)
            topic_hint: 主題提示（可選）

        Returns:
            格式化的 Prompt
        """
        return self.reading_prompts.get_part5_prompt(count, difficulty, topic_hint)

    def get_toeic_paragraph_prompt(
        self,
        count: int,
        difficulty: str = "medium",
        topic_hint: str = None,
        passage_style: str = None,
    ) -> str:
        """
        取得 TOEIC 段落填空考題生成 Prompt

        Args:
            count: 題數
            difficulty: 難度 (easy/medium/hard)
            topic_hint: 主題提示（可選），用於確保每次生成不同主題的文章

        Returns:
            格式化的 Prompt
        """
        return self.reading_prompts.get_part6_prompt(
            count,
            difficulty,
            topic_hint,
            passage_style,
        )

    def get_toeic_single_passage_prompt(
        self,
        count: int,
        difficulty: str = "medium",
        topic_hint: str = None,
        passage_style: str = None,
    ) -> str:
        """
        取得 TOEIC 單篇閱讀考題生成 Prompt

        Args:
            count: 題數
            difficulty: 難度 (easy/medium/hard)
            topic_hint: 主題提示（可選）

        Returns:
            格式化的 Prompt
        """
        return self.reading_prompts.get_part7_single_prompt(
            count,
            difficulty,
            topic_hint,
            passage_style,
        )

    def get_toeic_multiple_passage_prompt(
        self,
        count: int,
        difficulty: str = "medium",
        topic_hint: str = None,
        passage_style: str = None,
    ) -> str:
        """
        取得 TOEIC 多篇閱讀考題生成 Prompt

        Args:
            count: 題數
            difficulty: 難度 (easy/medium/hard)
            topic_hint: 主題提示（可選）

        Returns:
            格式化的 Prompt
        """
        return self.reading_prompts.get_part7_multiple_prompt(
            count,
            difficulty,
            topic_hint,
            passage_style,
        )

    def get_toeic_explanation_prompt(self, part_label: str, answer: dict) -> str:
        """
        取得 TOEIC 詳解生成 Prompt

        Args:
            part_label: 題型名稱（例如：Part 3 簡短對話）
            answer: 單題答題記錄

        Returns:
            格式化的 Prompt
        """
        return self.explanation_prompts.get_explanation_prompt(part_label, answer)
