"""
Google Gemini Flash Image 圖片生成客戶端

使用 gemini-2.5-flash-image 模型進行原生圖片生成，用於 TOEIC Part 1 題目生成
"""

import base64
from typing import Optional, Literal
from google import genai
from google.genai import types
from backend.ai_clients.logger import get_logger
from backend.ai_clients.config import APIKeyManager
from backend.ai_clients.exceptions import SafetyViolationError, InvalidRequestError

logger = get_logger(__name__)


AspectRatio = Literal["1:1", "3:4", "4:3", "9:16", "16:9"]


class GeminiImagenClient:
    """Google Gemini Flash Image 圖片生成客戶端"""

    MODEL_NAME = "gemini-2.5-flash-image"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = APIKeyManager.get_gemini_key(api_key)
        self.client = genai.Client(api_key=self.api_key)
        logger.info(f"初始化 Gemini Image 客戶端，模型: {self.MODEL_NAME}")

    def generate_image(
        self,
        prompt: str,
        number_of_images: int = 1,
        aspect_ratio: AspectRatio = "1:1",
    ) -> list[bytes]:
        """
        使用 gemini-2.5-flash-image 生成圖片

        Args:
            prompt: 英文圖片描述
            number_of_images: 要生成的圖片數量（1-4，每次一張各自呼叫 API）
            aspect_ratio: 圖片長寬比（作為提示描述，非 API 強制參數）

        Returns:
            圖片二進位資料列表

        Raises:
            SafetyViolationError: 圖片被安全過濾器阻擋
            InvalidRequestError: API 呼叫失敗
        """
        if number_of_images < 1 or number_of_images > 4:
            raise InvalidRequestError(
                message="number_of_images 必須在 1-4 之間",
                provider="gemini"
            )

        images: list[bytes] = []
        for _ in range(number_of_images):
            img_bytes = self._generate_single(prompt)
            images.append(img_bytes)
        return images

    def _generate_single(self, prompt: str) -> bytes:
        """呼叫一次 generate_content 並回傳圖片 bytes"""
        try:
            response = self.client.models.generate_content(
                model=self.MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                ),
            )

            candidate = response.candidates[0] if response.candidates else None
            if candidate is None:
                raise InvalidRequestError(message="回應無候選結果", provider="gemini")

            # finish_reason 為 SAFETY 時視為安全違規
            finish_reason = getattr(candidate.finish_reason, "name", None) or str(candidate.finish_reason)
            if finish_reason in ("SAFETY", "OTHER"):
                raise SafetyViolationError(
                    message="圖片生成被安全性過濾器阻止",
                    provider="gemini",
                    details={"finish_reason": finish_reason}
                )

            # 從 parts 中取出第一個含有 inline_data 的圖片
            for part in candidate.content.parts:
                if part.inline_data is not None:
                    return part.inline_data.data  # bytes

            raise InvalidRequestError(message="回應中未找到圖片資料", provider="gemini")

        except (SafetyViolationError, InvalidRequestError):
            raise
        except Exception as e:
            error_msg = str(e)
            if self._is_safety_violation(error_msg):
                logger.error(f"安全性檢查失敗: {error_msg}")
                raise SafetyViolationError(
                    message="圖片生成被安全性過濾器阻止",
                    provider="gemini",
                    details={"error": error_msg}
                )
            logger.error(f"圖片生成失敗: {error_msg}")
            raise InvalidRequestError(
                message="圖片生成失敗",
                provider="gemini",
                details={"error": error_msg}
            )

    def generate_image_base64(
        self,
        prompt: str,
        number_of_images: int = 1,
        aspect_ratio: AspectRatio = "1:1",
    ) -> list[str]:
        images = self.generate_image(prompt, number_of_images, aspect_ratio)
        return [base64.b64encode(img).decode("utf-8") for img in images]

    @staticmethod
    def _is_safety_violation(error_msg: str) -> bool:
        safety_keywords = ["safety", "blocked", "policy", "prohibited", "inappropriate", "offensive"]
        error_lower = error_msg.lower()
        return any(keyword in error_lower for keyword in safety_keywords)

    def test_connection(self) -> bool:
        try:
            self.generate_image("A simple red circle on white background", number_of_images=1)
            logger.info("Gemini Image 連接測試成功")
            return True
        except Exception as e:
            logger.error(f"Gemini Image 連接失敗: {e}")
            return False
