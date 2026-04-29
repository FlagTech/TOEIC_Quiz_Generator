"""
Prompt 管理模組 - TOEIC Quiz Generator

集中管理 TOEIC 測驗相關的 AI Prompt 模板
"""

from .prompt_manager import PromptManager

# 建立全域 Prompt 管理器實例
prompt_manager = PromptManager()

__all__ = ['PromptManager', 'prompt_manager']
