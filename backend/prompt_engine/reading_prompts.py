"""
TOEIC 閱讀測驗生成 Prompts

提供 TOEIC Reading Test Part 5-7 的考題生成提示詞
Prompt 模板存放於專案根目錄 prompts/ 資料夾中的 .md 檔案
"""
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
_env = Environment(
    loader=FileSystemLoader(str(_PROMPTS_DIR)),
    keep_trailing_newline=True,
)


class ReadingPrompts:
    """TOEIC 閱讀測驗相關 Prompt 模板"""

    def get_part5_prompt(self, count: int, difficulty: str = "medium", topic_hint: str = None) -> str:
        difficulty_desc = {
            "easy": "Beginner level with common vocabulary and simple grammar",
            "medium": "Intermediate level with common TOEIC business contexts",
            "hard": "Advanced level with higher-level vocabulary and complex structures"
        }

        topic_instruction = ""
        if topic_hint:
            topic_instruction = (
                f"\nTopic focus: {topic_hint}\n"
                "(Use this context while still testing grammar, vocabulary, or usage.)\n"
            )

        return _env.get_template("part5_sentence.md").render(
            count=count,
            difficulty_desc=difficulty_desc.get(difficulty, difficulty_desc["medium"]),
            topic_instruction=topic_instruction,
        )

    def get_part6_prompt(
        self,
        count: int,
        difficulty: str = "medium",
        topic_hint: str = None,
        passage_style: str = None,
    ) -> str:
        difficulty_desc = {
            "easy": "Beginner level with common words and simple sentence patterns",
            "medium": "Intermediate level with common TOEIC business contexts",
            "hard": "Advanced level requiring contextual reasoning and higher-level vocabulary"
        }

        topic_instruction = ""
        if topic_hint:
            topic_instruction = (
                f"\nTopic focus: {topic_hint}\n"
                "(Write a business-related passage aligned with this topic.)\n"
            )

        style_instruction = ""
        if passage_style:
            style_instruction = (
                f"\nPassage style preference: {passage_style}\n"
                "(If the style conflicts with the topic, switch to a more reasonable style.)\n"
            )

        return _env.get_template("part6_paragraph.md").render(
            count=count,
            difficulty_desc=difficulty_desc.get(difficulty, difficulty_desc["medium"]),
            topic_instruction=topic_instruction,
            style_instruction=style_instruction,
        )

    def get_part7_single_prompt(
        self,
        count: int,
        difficulty: str = "medium",
        topic_hint: str = None,
        passage_style: str = None,
    ) -> str:
        difficulty_desc = {
            "easy": "Short, clear passage with direct questions",
            "medium": "Moderate length passage requiring context understanding",
            "hard": "Longer, more complex passage requiring deeper inference"
        }

        topic_instruction = ""
        if topic_hint:
            topic_instruction = (
                f"\nTopic focus: {topic_hint}\n"
                "(Write a business passage aligned with this topic.)\n"
            )

        style_instruction = ""
        if passage_style:
            style_instruction = (
                f"\nPassage style preference: {passage_style}\n"
                "(If the style conflicts with the topic, switch to a more reasonable style.)\n"
            )

        return _env.get_template("part7_single.md").render(
            count=count,
            difficulty_desc=difficulty_desc.get(difficulty, difficulty_desc["medium"]),
            topic_instruction=topic_instruction,
            style_instruction=style_instruction,
        )

    def get_part7_multiple_prompt(
        self,
        count: int,
        difficulty: str = "medium",
        topic_hint: str = None,
        passage_style: str = None,
    ) -> str:
        difficulty_desc = {
            "easy": "Two short passages with clear connections",
            "medium": "Two to three passages requiring information synthesis",
            "hard": "Three longer passages requiring deeper integration and inference"
        }

        passage_count = 2 if difficulty == "easy" else (3 if difficulty == "hard" else 2)

        topic_instruction = ""
        if topic_hint:
            topic_instruction = (
                f"\nTopic focus: {topic_hint}\n"
                f"(Write {passage_count} related business passages with clear logical links.)\n"
            )

        style_instruction = ""
        if passage_style:
            style_instruction = (
                f"\nPassage style preference: {passage_style}\n"
                "(If the style conflicts with the topic, switch to a more reasonable style.)\n"
            )

        return _env.get_template("part7_multiple.md").render(
            count=count,
            passage_count=passage_count,
            difficulty_desc=difficulty_desc.get(difficulty, difficulty_desc["medium"]),
            topic_instruction=topic_instruction,
            style_instruction=style_instruction,
        )
