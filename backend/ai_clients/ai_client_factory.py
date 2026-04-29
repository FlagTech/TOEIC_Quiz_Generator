"""
AI 客戶端工廠

提供統一介面建立不同的 AI 客戶端
"""

import importlib
from typing import Optional, Dict, Any
from backend.ai_clients.ai_client_base import AIClientBase
from backend.ai_clients.logger import get_logger
from backend.ai_clients.exceptions import InvalidRequestError

logger = get_logger(__name__)

# Provider 配置映射
PROVIDER_CONFIG = {
    "ollama": {
        "module": "backend.ai_clients.ollama_client_new",
        "class": "OllamaVocabularyClient",
        "requires_api_key": False,
        "default_params": {"host": "http://localhost:11434"}
    },
    "openai": {
        "module": "backend.ai_clients.openai_client",
        "class": "OpenAIVocabularyClient",
        "requires_api_key": True,
        "default_params": {}
    },
    "gemini": {
        "module": "backend.ai_clients.gemini_client",
        "class": "GeminiVocabularyClient",
        "requires_api_key": True,
        "default_params": {}
    }
}


class AIClientFactory:
    """AI 客戶端工廠類別"""

    @staticmethod
    def create_client(
        provider: str,
        model: str,
        api_key: Optional[str] = None,
        **kwargs
    ) -> AIClientBase:
        """
        建立 AI 客戶端

        Args:
            provider: 提供商名稱 ("ollama", "openai", "gemini")
            model: 模型名稱
            api_key: API 金鑰（Ollama 不需要）
            **kwargs: 其他參數

        Returns:
            AI 客戶端實例

        Raises:
            InvalidRequestError: 當提供商名稱無效或缺少必要參數時
        """
        provider = provider.lower()

        # 檢查 provider 是否支援
        if provider not in PROVIDER_CONFIG:
            supported = ", ".join(PROVIDER_CONFIG.keys())
            raise InvalidRequestError(
                message=f"不支援的提供商: {provider}。支援的提供商: {supported}",
                provider=provider
            )

        config = PROVIDER_CONFIG[provider]

        # 檢查是否需要 API key
        if config["requires_api_key"] and not api_key:
            raise InvalidRequestError(
                message=f"{provider.upper()} 需要提供 API key",
                provider=provider
            )

        # 動態導入模組和類別
        try:
            module = importlib.import_module(config["module"])
            client_class = getattr(module, config["class"])
        except (ImportError, AttributeError) as e:
            logger.error(f"無法載入 {provider} 客戶端: {e}")
            raise InvalidRequestError(
                message=f"無法載入 {provider} 客戶端模組",
                provider=provider,
                details={"error": str(e)}
            )

        # 準備初始化參數
        init_params = {"model": model}
        if api_key:
            init_params["api_key"] = api_key

        # 合併預設參數和自定義參數
        init_params.update(config["default_params"])
        init_params.update(kwargs)

        # 建立客戶端實例
        try:
            client = client_class(**init_params)
            logger.info(f"成功建立 {provider} 客戶端，模型: {model}")
            return client
        except Exception as e:
            logger.error(f"建立 {provider} 客戶端失敗: {e}")
            raise

    @staticmethod
    def get_available_providers() -> Dict[str, str]:
        """
        取得可用的提供商列表

        Returns:
            提供商字典 {id: 名稱}
        """
        return {
            "ollama": "Ollama (本地模型)",
            "openai": "OpenAI (GPT-4o, GPT-3.5 等)",
            "gemini": "Google Gemini (Gemini 2.5 等)"
        }

    @staticmethod
    def get_models_for_provider(provider: str) -> Dict[str, str]:
        """
        取得指定提供商的可用模型

        Args:
            provider: 提供商名稱

        Returns:
            模型字典 {id: 描述}
        """
        provider = provider.lower()

        if provider == "ollama":
            from backend.ai_clients.ollama_client_new import OllamaVocabularyClient
            return OllamaVocabularyClient.list_models()
        elif provider == "openai":
            from backend.ai_clients.openai_client import OpenAIVocabularyClient
            return OpenAIVocabularyClient.list_models()
        elif provider == "gemini":
            from backend.ai_clients.gemini_client import GeminiVocabularyClient
            return GeminiVocabularyClient.list_models()
        else:
            return {}

    @staticmethod
    def requires_api_key(provider: str) -> bool:
        """
        檢查提供商是否需要 API key

        Args:
            provider: 提供商名稱

        Returns:
            是否需要 API key
        """
        return provider.lower() in ["openai", "gemini"]

    @staticmethod
    def create_imagen_client(provider: str, api_key: Optional[str] = None):
        """
        建立圖片生成客戶端 (用於 TOEIC Part 1)

        Args:
            provider: 提供商名稱 ("openai", "gemini")
            api_key: API 金鑰

        Returns:
            圖片生成客戶端實例

        Raises:
            ValueError: 當提供商名稱無效或未提供 API key 時
        """
        provider = provider.lower()

        if provider == "openai":
            # OpenAI 使用標準的 OpenAI 客戶端（DALL-E）
            from openai import OpenAI
            if not api_key:
                raise ValueError("OpenAI 需要提供 API key")
            return OpenAI(api_key=api_key)

        elif provider == "gemini":
            from backend.ai_clients.gemini_imagen_client import GeminiImagenClient
            if not api_key:
                raise ValueError("Google Gemini 需要提供 API key")
            return GeminiImagenClient(api_key=api_key)

        else:
            raise ValueError(f"不支援的圖片生成提供商: {provider}。支援的提供商: openai, gemini")

    @staticmethod
    def create_tts_client(
        provider: str,
        api_key: Optional[str] = None,
        model: str = "flash",
        voice: str = "Puck"
    ):
        """
        建立 TTS（文字轉語音）客戶端 (用於 TOEIC Part 1-4)

        Args:
            provider: 提供商名稱 ("openai", "gemini")
            api_key: API 金鑰
            model: 模型名稱（Gemini: "flash" 或 "pro"; OpenAI: "tts-1" 或 "tts-1-hd"）
            voice: 聲音名稱

        Returns:
            TTS 客戶端實例

        Raises:
            ValueError: 當提供商名稱無效或未提供 API key 時
        """
        provider = provider.lower()

        if provider == "openai":
            # OpenAI 使用標準的 OpenAI 客戶端
            from openai import OpenAI
            if not api_key:
                raise ValueError("OpenAI 需要提供 API key")
            return OpenAI(api_key=api_key)

        elif provider == "gemini":
            from backend.ai_clients.gemini_tts_client import GeminiTTSClient
            if not api_key:
                raise ValueError("Google Gemini 需要提供 API key")
            return GeminiTTSClient(api_key=api_key, model=model, voice=voice)

        else:
            raise ValueError(f"不支援的 TTS 提供商: {provider}。支援的提供商: openai, gemini")

    @staticmethod
    def create_live_client(
        provider: str,
        api_key: Optional[str] = None,
        system_instruction: Optional[str] = None
    ):
        """
        建立 Live API 即時對話客戶端 (用於 AI 口說家教)

        Args:
            provider: 提供商名稱 ("openai", "gemini")
            api_key: API 金鑰
            system_instruction: 系統指令

        Returns:
            Live API 客戶端實例

        Raises:
            ValueError: 當提供商名稱無效或未提供 API key 時
        """
        provider = provider.lower()

        if provider == "openai":
            # OpenAI 使用標準的 OpenAI 客戶端（Realtime API）
            from openai import OpenAI
            if not api_key:
                raise ValueError("OpenAI 需要提供 API key")
            return OpenAI(api_key=api_key)

        elif provider == "gemini":
            from backend.ai_clients.gemini_live_client import GeminiLiveClient
            if not api_key:
                raise ValueError("Google Gemini 需要提供 API key")
            return GeminiLiveClient(api_key=api_key, system_instruction=system_instruction)

        else:
            raise ValueError(f"不支援的 Live API 提供商: {provider}。支援的提供商: openai, gemini")
