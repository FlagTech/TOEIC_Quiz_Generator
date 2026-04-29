# Prompt 管理模組

本資料夾統一管理所有 AI Prompt 模板，便於維護和未來擴展。

## 檔案結構

```
backend/prompts/
├── __init__.py                  # 模組初始化，匯出全域管理器
├── word_card_prompts.py         # 單字卡生成 Prompt
├── dictation_prompts.py         # 字幕聽打解說 Prompt
├── listening_prompts.py         # TOEIC 聽力題目生成 Prompt
├── reading_prompts.py           # TOEIC 閱讀題目生成 Prompt
├── explanation_prompts.py       # TOEIC 詳解 Prompt（單題生成）
├── toeic_topics.py              # TOEIC 主題清單與抽樣工具
├── toeic_response_schemas.py    # Gemini schema 用的回應格式
├── prompt_manager.py            # 中央管理器
└── README.md                    # 本說明文件
```

## 使用方式

### 1. 在後端使用

```python
from backend.prompts import prompt_manager

# 生成 TOEIC 詳解 Prompt（單題）
prompt = prompt_manager.get_toeic_explanation_prompt(
    part_label="Part 6 段落填空",
    answer={
        "question_number": 1,
        "question_text": "The memo will be sent to all staff ____ the end of the day.",
        "options": [
            {"label": "A", "text": "by"},
            {"label": "B", "text": "until"},
            {"label": "C", "text": "since"},
            {"label": "D", "text": "during"}
        ],
        "correct_answer": "A",
        "user_answer": "B"
    }
)

# 檢查是否為自訂 Prompt
is_custom = prompt_manager.is_custom_prompt(text)
```

### 2. 已整合的位置

- `backend/ai_clients/ai_client_base.py` - 使用 `prompt_manager` 生成單字卡 Prompt
- 所有 AI 客戶端（Ollama、OpenAI、Gemini）自動繼承此功能
- `backend/routers/listening.py` - 使用 `listening_prompts` 生成 Part 1-4 題目
- `backend/routers/reading.py` - 使用 `reading_prompts` 生成 Part 5-7 題目、`explanation_prompts` 生成詳解

### 3. 前端 Prompt

前端目前在 `DictationPracticeView.vue` 中直接構建字幕解說 Prompt。這些 Prompt 包含特殊標記（`【英文字幕學習解說】`），會被後端的 `is_custom_prompt()` 識別並直接傳回，不會被替換成 TOEIC 單字卡 Prompt。

## 新增功能的擴展方式

### 1. 新增新的 Prompt 類型

創建新的 Prompt 類別檔案，例如 `quiz_prompts.py`：

```python
"""
測驗題目生成 Prompt 模板
"""

class QuizPrompts:
    """測驗相關 Prompt 模板"""

    @staticmethod
    def get_multiple_choice_prompt(word: str, difficulty: str) -> str:
        """生成選擇題 Prompt"""
        prompt = f"""請為單字 "{word}" 生成一道{difficulty}難度的選擇題..."""
        return prompt
```

### 2. 在 PromptManager 中註冊

編輯 `prompt_manager.py`：

```python
from .quiz_prompts import QuizPrompts

class PromptManager:
    def __init__(self):
        self.word_card_prompts = WordCardPrompts()
        self.dictation_prompts = DictationPrompts()
        self.quiz_prompts = QuizPrompts()  # 新增

    def get_multiple_choice_prompt(self, word: str, difficulty: str) -> str:
        """取得選擇題生成 Prompt"""
        return self.quiz_prompts.get_multiple_choice_prompt(word, difficulty)
```

### 3. 更新 __init__.py

```python
from .quiz_prompts import QuizPrompts

__all__ = ['WordCardPrompts', 'DictationPrompts', 'QuizPrompts', 'PromptManager', 'prompt_manager']
```

## 設計原則

1. **分離關注點**：每個 Prompt 類別專注於一個功能領域
2. **統一介面**：透過 PromptManager 提供統一的存取介面
3. **易於測試**：所有 Prompt 生成邏輯都是靜態方法，易於單元測試
4. **可擴展性**：新增功能只需創建新類別並在管理器中註冊

## 現有 Prompt 類型

### WordCardPrompts
- `get_word_card_prompt()` - 生成 TOEIC 單字卡資訊

### DictationPrompts
- `get_subtitle_explanation_prompt()` - 生成字幕片段學習解說

### ListeningPrompts
- `get_part1_vision_prompt()` - Part 1 圖片描述選項生成
- `get_part2_generation_prompt()` - Part 2 問答生成
- `get_part3_generation_prompt()` - Part 3 對話題生成
- `get_part4_generation_prompt()` - Part 4 獨白題生成

### ReadingPrompts
- `get_sentence_completion_prompt()` - Part 5 句子填空
- `get_paragraph_completion_prompt()` - Part 6 段落填空
- `get_single_passage_prompt()` - Part 7 單篇閱讀
- `get_multiple_passage_prompt()` - Part 7 多篇閱讀

### ExplanationPrompts
- `get_explanation_prompt()` - 依題目/答案資料生成中文詳解

## 重要規範

- **JSON-only 輸出**：出題 Prompts 要求模型只回傳單一 JSON 物件，不要附加說明文字或多段 JSON。
- **模板說明**：Prompt 中的 Template 只提供欄位鍵結構，避免提供固定語意範例。
- **Gemini schema**：若使用 Gemini，可搭配 `toeic_response_schemas.py` 的 schema 進一步提高 JSON 穩定性。

## 特殊標記

以下標記用於識別自訂 Prompt，不會被系統替換：
- `【英文字幕學習解說】`
- `【英文字幕解說】`
- `【字幕片段解說】`
- `【自訂解說】`

可在 `PromptManager.is_custom_prompt()` 中新增更多標記。
