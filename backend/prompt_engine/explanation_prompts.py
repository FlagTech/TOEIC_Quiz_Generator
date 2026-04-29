"""
Shared explanation prompts for TOEIC parts.
"""


class ExplanationPrompts:
    """Common explanation prompt builder for TOEIC Parts 2-7."""

    def get_explanation_prompt(self, part_label: str, answer: dict) -> str:
        """
        Build a single-question explanation prompt.

        Args:
            part_label: Part name (e.g., Part 3 簡短對話)
            answer: Answer payload with question/options/context

        Returns:
            Prompt text
        """
        passage_text = ""
        if answer.get("passages"):
            passages = "\n\n".join([
                f"[Passage {idx + 1}]\n{p}" for idx, p in enumerate(answer["passages"])
            ])
            passage_text = f"\n文章內容（多篇）：\n{passages}\n"
        elif answer.get("passage"):
            passage_text = f"\n文章內容：\n{answer['passage']}\n"

        transcript_text = ""
        if answer.get("transcript"):
            transcript_text = f"\n對話或獨白逐字稿：\n{answer['transcript']}\n"

        options_text = "\n".join([f"{opt['label']}. {opt['text']}" for opt in answer["options"]])

        return f"""你是一位專業的 TOEIC 教學老師。請針對{part_label}的題目提供詳細的中文解說。
{passage_text}{transcript_text}
題目: {answer['question_text']}
選項:
{options_text}

正確答案: {answer['correct_answer']}
使用者作答: {answer['user_answer']}

## 解說要求

請使用 **Markdown 格式** 提供清晰的解說，包含：

### 1. 正確答案原因
說明為什麼 **{answer['correct_answer']}** 是正確答案

### 2. 其他選項分析
逐一說明其他選項為什麼不正確

### 3. 關鍵線索
若有文章內容，請指出關鍵句子或詞彙（使用引用格式 `>` 標示）

### 4. 重點補充
補充相關文法或詞彙知識點（使用列表格式）

## 格式規範
- 使用 `##` / `###` 標題分段
- 使用 `-` 或 `1.` 列表
- 使用 `**粗體**` 強調重點詞彙
- 使用 `> 引用` 標示關鍵句子
- 使用繁體中文，清晰簡潔

**重要**: 直接輸出 Markdown 內容，不要用 JSON 或程式碼區塊包裝。
"""
