"""
AI 客戶端自定義異常

提供明確的異常類型，改善錯誤處理和除錯
"""


class AIClientException(Exception):
    """AI 客戶端基礎異常類別"""

    def __init__(self, message: str, provider: str = None, details: dict = None):
        """
        初始化異常

        Args:
            message: 錯誤訊息
            provider: AI 提供商名稱（ollama, openai, gemini）
            details: 額外的錯誤詳情
        """
        self.message = message
        self.provider = provider
        self.details = details or {}

        # 構建完整的錯誤訊息
        full_message = f"[{provider.upper()}] {message}" if provider else message
        if details:
            full_message += f" - Details: {details}"

        super().__init__(full_message)


class ConnectionError(AIClientException):
    """連接錯誤 - 無法連接到 AI 服務"""
    pass


class AuthenticationError(AIClientException):
    """認證錯誤 - API key 無效或缺失"""
    pass


class JSONParseError(AIClientException):
    """JSON 解析錯誤 - AI 回應格式不正確"""

    def __init__(self, message: str, response_text: str = None, provider: str = None):
        """
        初始化 JSON 解析錯誤

        Args:
            message: 錯誤訊息
            response_text: AI 原始回應文字
            provider: AI 提供商名稱
        """
        details = {}
        if response_text:
            # 只保留前 200 字元的回應內容（避免日誌過長）
            details['response_preview'] = response_text[:200] + ('...' if len(response_text) > 200 else '')

        super().__init__(message, provider, details)
        self.response_text = response_text


class SafetyViolationError(AIClientException):
    """安全性違規錯誤 - 內容被安全過濾器阻擋"""
    pass


class ModelNotFoundError(AIClientException):
    """模型未找到錯誤 - 指定的模型不存在"""
    pass


class RateLimitError(AIClientException):
    """速率限制錯誤 - API 請求次數超過限制"""
    pass


class QuotaExceededError(AIClientException):
    """配額超出錯誤 - API 使用配額已耗盡"""
    pass


class InvalidRequestError(AIClientException):
    """無效請求錯誤 - 請求參數不正確"""
    pass


class TimeoutError(AIClientException):
    """超時錯誤 - 請求超時"""
    pass
