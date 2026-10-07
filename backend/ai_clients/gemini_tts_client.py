"""
Google Gemini Text-to-Speech 客戶端

提供 Gemini TTS 模型的語音合成功能，用於 TOEIC Part 1-4 音訊生成
"""

import wave
from typing import Optional, Literal, List, Dict
from google import genai
from google.genai import types
from backend.ai_clients.logger import get_logger
from backend.ai_clients.config import APIKeyManager

logger = get_logger(__name__)


# 可用的聲音列表（Gemini TTS 支援清單）
AVAILABLE_VOICES = [
    "Achernar",
    "Achird",
    "Algenib",
    "Algieba",
    "Alnilam",
    "Aoede",
    "Autonoe",
    "Callirrhoe",
    "Charon",
    "Despina",
    "Enceladus",
    "Erinome",
    "Fenrir",
    "Gacrux",
    "Iapetus",
    "Kore",
    "Laomedeia",
    "Leda",
    "Orus",
    "Puck",
    "Pulcherrima",
    "Rasalgethi",
    "Sadachbia",
    "Sadaltager",
    "Schedar",
    "Sulafat",
    "Umbriel",
    "Vindemiatrix",
    "Zephyr",
    "Zubenelgenubi",
]

# Gemini 官方文件未提供性別分類，這裡維持既有專案慣用的聲音分組
MALE_VOICES = [
    "Puck",
    "Charon",
    "Fenrir",
]
FEMALE_VOICES = [
    "Zephyr",
    "Kore",
    "Leda",
    "Aoede",
]


def pcm_to_wav(pcm_data: bytes, channels: int = 1, sample_rate: int = 24000, sample_width: int = 2) -> bytes:
    """
    將 PCM 音訊數據轉換為 WAV 格式

    Gemini TTS 返回的是原始 PCM 數據（24kHz, 單聲道, 16-bit），
    需要添加 WAV header 才能在瀏覽器中播放。

    Args:
        pcm_data: PCM 音訊數據（bytes）
        channels: 聲道數（預設 1 = 單聲道）
        sample_rate: 取樣率（預設 24000 Hz）
        sample_width: 樣本寬度（預設 2 = 16-bit）

    Returns:
        WAV 格式的音訊數據（bytes）
    """
    import io

    wav_buffer = io.BytesIO()

    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)

    return wav_buffer.getvalue()


def ensure_wav(audio_data: bytes) -> bytes:
    """
    確保音訊為 WAV 格式

    Gemini 3.8 TTS 預設回傳含 RIFF header 的 WAV；
    舊版 TTS 模型回傳原始 PCM，需要自行加上 WAV header。
    """
    if audio_data[:4] == b"RIFF":
        return audio_data
    return pcm_to_wav(audio_data, channels=1, sample_rate=24000, sample_width=2)


def build_style(
    style_prompt: Optional[str] = None,
    accent: Optional[str] = None,
    pace: Optional[str] = None,
) -> Optional[str]:
    """
    組合 speech_metadata.style 字串

    Gemini 3.8 TTS 會把輸入文字逐字念出，口音、語速等指示
    不能再寫在文字裡（舊版 Director's Notes），必須放在 speech_metadata.style。
    """
    if accent or pace:
        notes = []
        if accent:
            notes.append(f"{accent}.")
        if pace:
            notes.append(f"Read at a {pace} pace.")
        return " ".join(notes)
    return style_prompt


class GeminiTTSClient:
    """Google Gemini Text-to-Speech 客戶端"""

    # 模型名稱
    MODEL_FLASH = "gemini-3.8-flash-tts"      # 高品質版本（預設）
    MODEL_LITE = "gemini-3.8-flash-lite-tts"  # 低成本版本

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "flash",
        voice: str = "Puck",
    ):
        """
        初始化 Gemini TTS 客戶端

        Args:
            api_key: Google API 金鑰（若為 None 則從環境變數讀取）
            model: 使用的模型類型（flash: 高品質, lite: 低成本）或完整模型名稱
            voice: 聲音名稱（預設 Puck）
        """
        # 使用 APIKeyManager 取得 API key
        self.api_key = APIKeyManager.get_gemini_key(api_key)

        # 選擇模型（允許傳入完整模型名稱）
        if model == "flash":
            self.model = self.MODEL_FLASH
        elif model == "lite":
            self.model = self.MODEL_LITE
        else:
            self.model = model
        self.voice = voice

        # 初始化客戶端
        self.client = genai.Client(api_key=self.api_key)
        logger.info(f"初始化 Gemini TTS 客戶端，模型: {self.model}, 聲音: {voice}")

    def generate_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        style_prompt: Optional[str] = None,
        accent: Optional[str] = None,
        pace: Optional[str] = None,
    ) -> bytes:
        """
        將文字轉換為語音

        Args:
            text: 要轉換的文字（最多 4000 bytes）
            voice: 聲音名稱（若為 None 則使用初始化時的聲音）
            style_prompt: 風格提示詞（例如: "cheerful and optimistic"）- 與 accent/pace 互斥
            accent: 口音（例如: "American English accent", "British English accent"）
            pace: 語速（例如: "moderate", "slow", "fast"）

        Returns:
            WAV 格式的音訊二進位資料（24kHz, 單聲道）

        Raises:
            ValueError: 參數錯誤
            Exception: API 呼叫失敗
        """
        # 驗證文字長度
        if len(text.encode('utf-8')) > 4000:
            raise ValueError("文字長度超過 4000 bytes")

        # 使用指定的聲音或預設聲音
        selected_voice = voice or self.voice

        # 準備內容：文字逐字朗讀，口音與語速放在 speech_metadata.style
        style = build_style(style_prompt, accent, pace)
        content = types.Content(
            role="user",
            parts=[
                types.Part(
                    text=text,
                    speech_metadata=types.SpeechMetadata(style=style) if style else None,
                )
            ],
        )

        try:
            # 呼叫 API
            response = self.client.models.generate_content(
                model=self.model,
                contents=content,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(voice=selected_voice)
                    ),
                )
            )

            # 提取音訊資料
            # 音訊資料在 response.candidates[0].content.parts[0].inline_data.data
            if not response.candidates or not response.candidates[0].content.parts:
                raise Exception("API 回應中沒有音訊資料")

            audio_part = response.candidates[0].content.parts[0]
            if not hasattr(audio_part, 'inline_data'):
                raise Exception("API 回應中沒有 inline_data")

            # Gemini 3.8 TTS 輸出 WAV（24kHz, 單聲道, 16-bit）
            return ensure_wav(audio_part.inline_data.data)

        except Exception as e:
            raise Exception(f"語音生成失敗: {str(e)}")

    def generate_speech_file(
        self,
        text: str,
        output_path: str,
        voice: Optional[str] = None,
        style_prompt: Optional[str] = None,
        accent: Optional[str] = None,
        pace: Optional[str] = None,
    ) -> str:
        """
        將文字轉換為語音並儲存為檔案

        Args:
            text: 要轉換的文字
            output_path: 輸出檔案路徑（建議使用 .wav 副檔名）
            voice: 聲音名稱
            style_prompt: 風格提示詞
            accent: 口音
            pace: 語速

        Returns:
            輸出檔案路徑
        """
        audio_data = self.generate_speech(text, voice, style_prompt, accent, pace)

        # 儲存檔案
        with open(output_path, 'wb') as f:
            f.write(audio_data)

        return output_path

    def generate_multi_speaker_speech(
        self,
        conversation: List[Dict[str, str]],
        voice_mapping: Optional[Dict[str, str]] = None,
        style_prompt: Optional[str] = None,
        accent: Optional[str] = None,
        pace: Optional[str] = None,
    ) -> bytes:
        """
        生成多人對話語音（Gemini Multi-Speaker TTS）

        Args:
            conversation: 對話內容，格式為 [{"speaker": "Man", "text": "Hello"}, ...]
            voice_mapping: 說話者到聲音的映射，例如 {"Man": "Kore", "Woman": "Puck"}
            style_prompt: 整體風格提示詞（與 accent/pace 互斥）
            accent: 口音（例如: "American English accent", "British English accent"）
            pace: 語速（例如: "moderate", "slow", "fast"）

        Returns:
            WAV 格式的音訊二進位資料

        Raises:
            ValueError: 參數錯誤（超過 2 位說話者、文字過長等）
            Exception: API 呼叫失敗
        """
        # 預設聲音映射（男女聲）
        if voice_mapping is None:
            voice_mapping = {
                "Man": "Kore",      # 男聲 - 堅定
                "Woman": "Puck",    # 女聲 - 明亮
                "Man2": "Charon",   # 男聲 2 - 資訊性
                "Woman2": "Leda",   # 女聲 2 - 專業
            }

        # 收集所有獨特的說話者
        speakers = list(set([line['speaker'] for line in conversation]))

        # Gemini 目前最多支援 2 位說話者
        if len(speakers) > 2:
            raise ValueError(f"Gemini TTS 最多支援 2 位說話者，當前有 {len(speakers)} 位")

        # 每一句對話各自標上說話者與風格（speech_metadata）
        style = build_style(style_prompt, accent, pace)
        prompt = types.Content(
            role="user",
            parts=[
                types.Part(
                    text=line['text'],
                    speech_metadata=types.SpeechMetadata(speaker=line['speaker'], style=style),
                )
                for line in conversation
            ],
        )

        try:
            # 構建 speaker_voice_configs
            speaker_voice_configs = []
            for speaker in speakers:
                voice_name = voice_mapping.get(speaker, "Puck")
                speaker_voice_configs.append(
                    types.SpeakerVoiceConfig(
                        speaker=speaker,
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice_name,
                            )
                        )
                    )
                )

            # 呼叫 API
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                            speaker_voice_configs=speaker_voice_configs
                        )
                    )
                )
            )

            # 提取音訊資料
            if not response.candidates or not response.candidates[0].content.parts:
                raise Exception("API 回應中沒有音訊資料")

            audio_part = response.candidates[0].content.parts[0]
            if not hasattr(audio_part, 'inline_data'):
                raise Exception("API 回應中沒有 inline_data")

            return ensure_wav(audio_part.inline_data.data)

        except Exception as e:
            raise Exception(f"多人對話語音生成失敗: {str(e)}")

    def generate_multi_speaker_speech_file(
        self,
        conversation: List[Dict[str, str]],
        output_path: str,
        voice_mapping: Optional[Dict[str, str]] = None,
        style_prompt: Optional[str] = None,
        accent: Optional[str] = None,
        pace: Optional[str] = None,
    ) -> str:
        """
        生成多人對話語音並儲存為檔案

        Args:
            conversation: 對話內容，格式為 [{"speaker": "Man", "text": "Hello"}, ...]
            output_path: 輸出檔案路徑（建議使用 .wav 副檔名）
            voice_mapping: 說話者到聲音的映射
            style_prompt: 整體風格提示詞
            accent: 口音
            pace: 語速

        Returns:
            輸出檔案路徑
        """
        audio_data = self.generate_multi_speaker_speech(
            conversation=conversation,
            voice_mapping=voice_mapping,
            style_prompt=style_prompt,
            accent=accent,
            pace=pace
        )

        # 儲存檔案
        with open(output_path, 'wb') as f:
            f.write(audio_data)

        return output_path

    def test_connection(self) -> bool:
        """
        測試 Gemini TTS 連接

        Returns:
            連接是否成功
        """
        try:
            # 使用簡單的文字測試
            self.generate_speech("Hello, this is a test.")
            logger.info("Gemini TTS 連接測試成功")
            return True
        except Exception as e:
            logger.error(f"Gemini TTS 連接失敗: {e}")
            return False

    @classmethod
    def list_voices(cls) -> list[str]:
        """
        列出可用的聲音

        Returns:
            聲音名稱列表
        """
        return AVAILABLE_VOICES
