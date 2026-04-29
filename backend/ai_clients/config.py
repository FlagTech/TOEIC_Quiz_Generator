"""
AI 客戶端配置管理

集中管理 API Key、環境變數和客戶端配置
"""

import os
from typing import Optional
from backend.ai_clients.exceptions import AuthenticationError


class APIKeyManager:
    """API Key 管理器 - 統一處理 API key 的取得和驗證"""

    @staticmethod
    def get_openai_key(api_key: Optional[str] = None) -> str:
        """
        取得 OpenAI API Key

        Args:
            api_key: 明確指定的 API key（優先使用）

        Returns:
            有效的 API key

        Raises:
            AuthenticationError: 當 API key 未設定時
        """
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise AuthenticationError(
                message="OpenAI API key 未設定。請傳入 api_key 參數或設定 OPENAI_API_KEY 環境變數",
                provider="openai"
            )
        return key

    @staticmethod
    def get_gemini_key(api_key: Optional[str] = None) -> str:
        """
        取得 Google Gemini API Key

        Args:
            api_key: 明確指定的 API key（優先使用）

        Returns:
            有效的 API key

        Raises:
            AuthenticationError: 當 API key 未設定時
        """
        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise AuthenticationError(
                message="Google Gemini API key 未設定。請傳入 api_key 參數或設定 GEMINI_API_KEY 環境變數",
                provider="gemini"
            )
        return key

    @staticmethod
    def get_ollama_host(host: Optional[str] = None) -> str:
        """
        取得 Ollama 服務地址

        Args:
            host: 明確指定的 host 地址（優先使用）

        Returns:
            Ollama 服務地址（預設 http://localhost:11434）
        """
        return host or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"

    @staticmethod
    def requires_api_key(provider: str) -> bool:
        """
        檢查提供商是否需要 API key

        Args:
            provider: 提供商名稱（ollama, openai, gemini）

        Returns:
            是否需要 API key
        """
        return provider.lower() in ["openai", "gemini"]


class ClientConfig:
    """客戶端配置類別 - 儲存常用配置參數"""

    # OpenAI 配置
    OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
    OPENAI_DEFAULT_TEMPERATURE = 0.3
    OPENAI_DEFAULT_MAX_TOKENS = 1500

    # Gemini 配置
    GEMINI_DEFAULT_MODEL = "gemini-2.5-flash-lite"
    GEMINI_DEFAULT_TEMPERATURE = 1.0
    GEMINI_DEFAULT_MAX_TOKENS = 8000

    # Ollama 配置
    OLLAMA_DEFAULT_MODEL = "llama3.1:latest"
    OLLAMA_DEFAULT_TEMPERATURE = 1.0
    OLLAMA_DEFAULT_MAX_TOKENS = 2500

    # TTS 配置
    GEMINI_TTS_DEFAULT_MODEL = "gemini-2.5-flash-preview-tts"
    GEMINI_TTS_DEFAULT_VOICE = "Puck"
    OPENAI_TTS_DEFAULT_MODEL = "tts-1"
    OPENAI_TTS_DEFAULT_VOICE = "alloy"

    # Imagen 配置
    GEMINI_IMAGEN_MODEL = "gemini-2.5-flash-image"
    GEMINI_IMAGEN_DEFAULT_ASPECT_RATIO = "1:1"

    # Live API 配置
    GEMINI_LIVE_DEFAULT_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"
    OPENAI_REALTIME_DEFAULT_MODEL = "gpt-4o-realtime-preview"

    # 共用配置
    DEFAULT_TEST_PROMPT = "Hello"
    DEFAULT_TEST_MAX_TOKENS = 5
    DEFAULT_CONNECTION_TIMEOUT = 30  # 秒

    @classmethod
    def get_default_config(cls, provider: str, client_type: str = "text") -> dict:
        """
        取得指定提供商和客戶端類型的預設配置

        Args:
            provider: 提供商名稱（ollama, openai, gemini）
            client_type: 客戶端類型（text, tts, imagen, live）

        Returns:
            包含預設配置的字典
        """
        provider = provider.lower()
        client_type = client_type.lower()

        if client_type == "text":
            if provider == "openai":
                return {
                    "model": cls.OPENAI_DEFAULT_MODEL,
                    "temperature": cls.OPENAI_DEFAULT_TEMPERATURE,
                    "max_tokens": cls.OPENAI_DEFAULT_MAX_TOKENS
                }
            elif provider == "gemini":
                return {
                    "model": cls.GEMINI_DEFAULT_MODEL,
                    "temperature": cls.GEMINI_DEFAULT_TEMPERATURE,
                    "max_tokens": cls.GEMINI_DEFAULT_MAX_TOKENS
                }
            elif provider == "ollama":
                return {
                    "model": cls.OLLAMA_DEFAULT_MODEL,
                    "temperature": cls.OLLAMA_DEFAULT_TEMPERATURE,
                    "max_tokens": cls.OLLAMA_DEFAULT_MAX_TOKENS
                }

        elif client_type == "tts":
            if provider == "gemini":
                return {
                    "model": cls.GEMINI_TTS_DEFAULT_MODEL,
                    "voice": cls.GEMINI_TTS_DEFAULT_VOICE
                }
            elif provider == "openai":
                return {
                    "model": cls.OPENAI_TTS_DEFAULT_MODEL,
                    "voice": cls.OPENAI_TTS_DEFAULT_VOICE
                }

        return {}
