"""
Google Gemini 客戶端模組

提供 Google Gemini API 的整合功能
"""

from typing import Optional, Type
from google import genai
from google.genai import types
from pydantic import BaseModel
from backend.ai_clients.ai_client_base import AIClientBase
from backend.ai_clients.logger import get_logger
from backend.ai_clients.config import APIKeyManager
from backend.ai_clients.exceptions import ConnectionError

logger = get_logger(__name__)


class GeminiVocabularyClient(AIClientBase):
    """Google Gemini 單字處理客戶端"""

    # Google Gemini 最新模型列表 (2025)
    AVAILABLE_MODELS = {
        "gemini-3-pro-preview": "Gemini 3 Pro Preview - 旗艦多模態/推理",
        "gemini-3-flash-preview": "Gemini 3 Flash Preview - 高速推理",
        "gemini-2.5-pro": "Gemini 2.5 Pro - 高品質/強推理",
        "gemini-2.5-flash": "Gemini 2.5 Flash - 平衡速度與品質",
        "gemini-2.5-flash-lite": "Gemini 2.5 Flash-Lite - 高性價比",
        "gemini-2.0-flash": "Gemini 2.0 Flash - 平衡多模態",
        "gemini-2.0-flash-lite": "Gemini 2.0 Flash-Lite - 輕量快速",
    }

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash-lite"):
        """
        初始化 Google Gemini 客戶端

        Args:
            api_key: Google API 金鑰（若為 None 則從環境變數讀取）
            model: 使用的模型名稱
        """
        super().__init__()

        # 使用 APIKeyManager 取得 API key
        self.api_key = APIKeyManager.get_gemini_key(api_key)
        self.model = model
        self.client = genai.Client(api_key=self.api_key)
        logger.info(f"初始化 Gemini 客戶端，模型: {model}")

    def test_connection(self) -> bool:
        """
        測試 Google Gemini 連接

        Returns:
            連接是否成功
        """
        try:
            # 使用簡單的請求測試連接
            response = self.client.models.generate_content(
                model=self.model,
                contents="Hello",
                config=types.GenerateContentConfig(
                    max_output_tokens=5,
                    temperature=1,
                )
            )
            logger.info("Gemini 連接測試成功")
            return True
        except Exception as e:
            logger.error(f"Gemini 連接失敗: {e}")
            raise ConnectionError(message=str(e), provider="gemini")

    def _generate_response(self, prompt: str) -> str:
        """
        使用 Google Gemini API 生成回應

        Args:
            prompt: 提示詞

        Returns:
            AI 生成的回應文字
        """
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=1,  
            )
        )

        return response.text

    def generate_with_schema(
        self,
        prompt: str,
        response_schema: Type[BaseModel],
        temperature: float = 1,
        max_tokens: int = 8000,
        system_instruction: Optional[str] = None
    ) -> str:
        """
        使用 Pydantic schema 強制結構化 JSON 輸出（Gemini 專屬功能）

        Args:
            prompt: 提示詞
            response_schema: Pydantic BaseModel 類別，定義期望的 JSON 結構
            temperature: 溫度參數（0.0-1.0）
            max_tokens: 最大輸出 token 數
            system_instruction: 系統指令（可選）

        Returns:
            符合 schema 的 JSON 字串
        """
        if system_instruction is None:
            system_instruction = "你是一個專業的 TOEIC 英語教師。請用繁體中文和英文回答。"

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
                response_json_schema=response_schema.model_json_schema(),
                system_instruction=system_instruction
            )
        )

        return response.text

    @classmethod
    def list_models(cls):
        """列出可用的模型"""
        return cls.AVAILABLE_MODELS
