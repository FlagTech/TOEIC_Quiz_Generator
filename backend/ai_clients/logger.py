"""
AI 客戶端統一日誌系統

提供標準化的日誌配置和管理
"""

import logging
import sys
from typing import Optional


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    取得或建立標準化的日誌記錄器

    Args:
        name: 日誌記錄器名稱（通常使用模組名稱）
        level: 日誌級別（預設 INFO）

    Returns:
        配置好的日誌記錄器

    Examples:
        >>> logger = get_logger(__name__)
        >>> logger.info("這是一條訊息")
        >>> logger.error("這是錯誤訊息")
    """
    logger = logging.getLogger(name)

    # 避免重複添加 handler
    if not logger.handlers:
        # 建立控制台 handler
        handler = logging.StreamHandler(sys.stdout)

        # 設定格式（包含時間、模組名、級別、訊息）
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)

        # 添加 handler 到 logger
        logger.addHandler(handler)

        # 設定日誌級別
        if level is None:
            level = logging.INFO
        logger.setLevel(level)

        # 防止日誌向上傳播（避免重複）
        logger.propagate = False

    return logger


def set_log_level(logger: logging.Logger, level: int):
    """
    設定日誌級別

    Args:
        logger: 日誌記錄器
        level: 日誌級別（logging.DEBUG, INFO, WARNING, ERROR, CRITICAL）
    """
    logger.setLevel(level)


# 預設的 AI 客戶端日誌記錄器
ai_client_logger = get_logger('ai_clients')
