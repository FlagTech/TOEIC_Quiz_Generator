"""
AI 客戶端抽象基類 - TOEIC Quiz Generator

提供統一介面支援多個 AI 提供商（Ollama、OpenAI、Google Gemini）
用於 TOEIC 測驗題目生成
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import json
import re
from backend.prompt_engine import prompt_manager
from backend.ai_clients.logger import get_logger
from backend.ai_clients.exceptions import JSONParseError

# 取得 logger
logger = get_logger(__name__)


class AIClientBase(ABC):
    """AI 客戶端抽象基類"""

    def __init__(self):
        """初始化基類"""
        pass  # TOEIC Quiz Generator 不需要分類功能

    @abstractmethod
    def test_connection(self) -> bool:
        """
        測試 AI 服務連接

        Returns:
            連接是否成功
        """
        pass

    @abstractmethod
    def _generate_response(self, prompt: str) -> str:
        """
        生成回應（由子類實作）

        Args:
            prompt: 提示詞

        Returns:
            AI 生成的回應文字
        """
        pass

    def _create_prompt(self, word: str, current_data: Dict, fields_to_fill: Dict[str, bool] = None) -> str:
        """
        建立提示詞

        Args:
            word: 英文單字或自訂 prompt
            current_data: 目前的單字資料
            fields_to_fill: 要填充的欄位字典

        Returns:
            格式化的提示詞
        """
        # 如果 word 包含特殊標記，表示是自訂 prompt（如字幕解說），直接返回
        if prompt_manager.is_custom_prompt(word):
            return word

        # 預設填充所有欄位
        if fields_to_fill is None:
            fields_to_fill = {
                'chinese_definition': True,
                'category': True,
                'parts_of_speech': True,
                'word_forms': True,
                'examples': True,
                'ai_insights': False
            }

        # 使用 PromptManager 生成單字卡 Prompt
        return prompt_manager.get_word_card_prompt(
            word=word,
            categories=self.categories,
            fields_to_fill=fields_to_fill
        )

    def _extract_json_from_code_block(self, response_text: str) -> str:
        """
        從代碼區塊中提取 JSON（處理 ```json 或 ``` 標記）

        Args:
            response_text: AI 回應文字

        Returns:
            提取後的文字（可能還不是有效 JSON）
        """
        if '```json' in response_text:
            json_start = response_text.find('```json') + 7
            json_end = response_text.find('```', json_start)
            return response_text[json_start:json_end].strip()
        elif '```' in response_text:
            json_start = response_text.find('```') + 3
            json_end = response_text.find('```', json_start)
            return response_text[json_start:json_end].strip()
        return response_text

    def _extract_json_object(self, response_text: str) -> str:
        """
        提取 JSON 物件（找到第一個 { 到最後一個 }）

        Args:
            response_text: AI 回應文字

        Returns:
            提取的 JSON 物件字串
        """
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start != -1 and json_end > json_start:
            return response_text[json_start:json_end]
        return response_text

    def _parse_with_regex(self, response_text: str) -> Optional[Dict]:
        """
        使用正則表達式提取 ai_insights 欄位（用於 fallback）

        Args:
            response_text: AI 回應文字

        Returns:
            包含 ai_insights 的字典，若失敗則返回 None
        """
        # 匹配 "ai_insights": "..." 或 "ai_insights": """..."""
        pattern = r'"ai_insights"\s*:\s*"((?:[^"\\]|\\.|\\n)*)"'
        match = re.search(pattern, response_text, re.DOTALL)

        if match:
            ai_insights_raw = match.group(1)
            # 手動處理轉義序列
            ai_insights = ai_insights_raw.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')
            logger.info("使用正則表達式成功提取 ai_insights")
            return {"ai_insights": ai_insights}

        return None

    def _manual_parse(self, response_text: str) -> Optional[Dict]:
        """
        手動解析 JSON（最後的 fallback 方法）

        Args:
            response_text: AI 回應文字

        Returns:
            包含 ai_insights 的字典，若失敗則返回 None
        """
        # 找到 ai_insights 的值（從第一個雙引號到最後一個雙引號之前的 }）
        insights_start = response_text.find('"ai_insights"')
        if insights_start != -1:
            # 找到 : 後的第一個 "
            value_start = response_text.find('"', response_text.find(':', insights_start)) + 1
            # 找到對應的結束引號（要考慮轉義）
            value_end = self._find_closing_quote(response_text, value_start)

            if value_end != -1:
                ai_insights = response_text[value_start:value_end]
                logger.info("手動提取成功")
                return {"ai_insights": ai_insights}

        return None

    def _extract_json_from_response(self, response_text: str) -> Optional[Dict]:
        """
        從回應中提取 JSON（使用多層 fallback 策略）

        Args:
            response_text: AI 回應文字

        Returns:
            解析後的 JSON 字典，若失敗則返回 None
        """
        try:
            # 步驟 1: 移除代碼區塊標記
            cleaned_text = self._extract_json_from_code_block(response_text)

            # 步驟 2: 提取 JSON 物件
            json_text = self._extract_json_object(cleaned_text)

            # 步驟 3: 嘗試標準解析
            return json.loads(json_text)

        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析錯誤: {e}，嘗試寬容解析...")

            # Fallback 1: 使用正則表達式提取
            result = self._parse_with_regex(response_text)
            if result:
                return result

            # Fallback 2: 手動解析
            result = self._manual_parse(response_text)
            if result:
                return result

            # 所有方法都失敗
            logger.error(f"所有 JSON 解析方法都失敗，回應內容: {response_text[:300]}...")
            return None

        except Exception as e:
            logger.error(f"解析過程發生未預期錯誤: {e}")
            return None

    def _find_closing_quote(self, text: str, start: int) -> int:
        """
        找到字符串中配對的結束引號位置（考慮轉義）

        Args:
            text: 要搜索的文字
            start: 開始位置（引號之後）

        Returns:
            結束引號的位置，若找不到返回 -1
        """
        i = start
        while i < len(text):
            if text[i] == '\\':
                # 跳過轉義字符
                i += 2
                continue
            if text[i] == '"':
                return i
            i += 1
        return -1

    def process_word(
        self,
        word: str,
        current_data: Dict,
        max_retries: int = 3,
        fields_to_fill: Dict[str, bool] = None
    ) -> Optional[Dict]:
        """
        處理單字，使用 AI 模型生成完整資訊

        Args:
            word: 英文單字
            current_data: 目前的單字資料
            max_retries: 最大重試次數
            fields_to_fill: 要填充的欄位字典

        Returns:
            更新後的單字資料，若失敗則返回 None
        """
        prompt = self._create_prompt(word, current_data, fields_to_fill)

        # 檢查是否為字幕解說（不需要 JSON 格式）
        is_subtitle_explanation = prompt_manager.is_custom_prompt(word)

        # 決定必要欄位
        if fields_to_fill is None:
            required_fields = ['chinese_definition', 'category', 'parts_of_speech', 'word_forms', 'examples']
        else:
            required_fields = [field for field, should_fill in fields_to_fill.items() if should_fill]

        for attempt in range(max_retries):
            try:
                # 生成回應
                response_text = self._generate_response(prompt)

                # 如果是字幕解說，直接返回純文本
                if is_subtitle_explanation:
                    # 清理回應文本（移除可能的 markdown 代碼塊標記）
                    cleaned_text = response_text.strip()
                    if cleaned_text.startswith('```'):
                        # 移除開頭的 ```markdown 或 ```
                        lines = cleaned_text.split('\n')
                        if lines[0].startswith('```'):
                            lines = lines[1:]
                        # 移除結尾的 ```
                        if lines and lines[-1].strip() == '```':
                            lines = lines[:-1]
                        cleaned_text = '\n'.join(lines)

                    logger.info("字幕解說生成成功（純文本格式）")
                    return {"ai_insights": cleaned_text.strip()}

                # 解析 JSON（單字卡模式）
                result = self._extract_json_from_response(response_text)

                if result is None:
                    logger.warning(f"嘗試 {attempt + 1}/{max_retries}: JSON 解析失敗")
                    continue

                # 驗證必要欄位
                if all(field in result for field in required_fields):
                    # 驗證分類是否在允許的列表中
                    if 'category' in result and result['category'] not in self.categories:
                        # 使用預設分類
                        result['category'] = self.categories[0]

                    return result
                else:
                    missing = [f for f in required_fields if f not in result]
                    logger.warning(f"嘗試 {attempt + 1}/{max_retries}: 回應缺少欄位: {missing}")

            except Exception as e:
                logger.warning(f"嘗試 {attempt + 1}/{max_retries}: 錯誤 - {e}")

        logger.error(f"處理失敗: {word}")
        return None

    def get_provider_name(self) -> str:
        """
        取得提供商名稱

        Returns:
            提供商名稱
        """
        return self.__class__.__name__.replace('VocabularyClient', '')
