"""
TOEIC 聽力測驗 Prompts

提供 TOEIC Listening Test Part 1-4 的題目生成和解說 prompts
Prompt 模板存放於專案根目錄 prompts/ 資料夾中的 .md 檔案
"""
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
_env = Environment(
    loader=FileSystemLoader(str(_PROMPTS_DIR)),
    keep_trailing_newline=True,
)

# ========== TOEIC 13 大主題細分情境（聽力專用）==========

# Part 2 適用情境：簡短問答（基於 TOEIC 13 大主題）
PART2_TOPICS = [
    # 1. 研究、產品研發
    "Ask about R&D progress", "Confirm test results", "Discuss product specifications", "Request lab access",
    "Ask about technical documents", "Confirm research meeting time",

    # 2. 商務/非正式午餐、宴會、招待會、餐廳訂位
    "Book a business lunch", "Confirm banquet headcount", "Ask about restaurant location", "Change a reservation time",
    "Ask about menu options", "Confirm meal budget",

    # 3. 電影、劇場、音樂、藝術、展覽、博物館、媒體
    "Ask about exhibition hours", "Book a guided tour", "Purchase event tickets", "Confirm show times",
    "Ask about parking information", "Ask about member discounts",

    # 4. 銀行業務、投資、稅務、會計、帳單
    "Ask about account balance", "Confirm transfer time", "Ask about loan rates", "Payment due date",
    "Confirm invoice details", "Ask about tax documents",

    # 5. 契約、談判、併購、行銷、銷售、保證、商業企劃、會議、勞動關係
    "Confirm meeting room booking", "Ask about contract terms", "Discuss sales targets", "Arrange a client visit",
    "Confirm proposal deadline", "Ask about warranty period",

    # 6. 醫療保險、看醫生、牙醫、診所、醫院
    "Schedule a medical appointment", "Confirm insurance coverage", "Ask about medication use", "Change an appointment date",
    "Ask about test results", "Confirm clinic location",

    # 7. 建築、規格、購買租賃、電力瓦斯服務
    "Ask about rent pricing", "Confirm maintenance time", "Report equipment issues", "Ask about utility fees",
    "Confirm construction progress", "Ask about contract duration",

    # 8. 工廠管理、生產線、品管
    "Ask about production status", "Confirm quality inspection", "Report equipment failure", "Check inventory levels",
    "Confirm shipment time", "Discuss process improvements",

    # 9. 董事會、委員會、信件、備忘錄、電話、傳真、電子郵件、辦公室器材與家俱、辦公室流程
    "Ask about document location", "Confirm meeting agenda", "Request equipment repair", "Ask about copier use",
    "Confirm memo contents", "Ask about office supplies",

    # 10. 招考、雇用、退休、薪資、升遷、應徵與廣告、津貼、獎勵
    "Ask about interview time", "Confirm resume receipt", "Ask about salary and benefits", "Confirm start date",
    "Ask about promotion opportunities", "Confirm bonus payout",

    # 11. 購物、訂購物資、送貨、發票
    "Ask about product price", "Confirm order status", "Ask about delivery time", "Request a return or exchange",
    "Ask about invoice issuance", "Confirm payment method",

    # 12. 電子、科技、電腦、實驗室與相關器材、技術規格
    "Ask about software licensing", "Report system issues", "Confirm specification requirements", "Ask for tech support",
    "Confirm equipment purchase", "Ask about upgrade timing",

    # 13. 火車、飛機、計程車、巴士、船隻、渡輪、票務、時刻表、車站、機場廣播、租車、飯店、預定、脫班與取消
    "Ask about flight times", "Confirm hotel booking", "Ask about transportation options", "Change travel dates",
    "Ask about rental car fees", "Confirm itinerary details"
]
# Part 3 適用情境：簡短對話（基於 TOEIC 13 大主題）
PART3_TOPICS = [
    # 1. 研究、產品研發
    "Discuss new product test results", "Schedule an R&D meeting", "Review experiment data", "Solve a technical issue",
    "Plan product improvements", "Discuss a patent application",

    # 2. 商務/非正式午餐、宴會、招待會、餐廳訂位
    "Book a business lunch venue", "Plan a banquet menu", "Coordinate client hospitality", "Handle a reservation change",
    "Discuss banquet budget", "Arrange catering service",

    # 3. 電影、劇場、音樂、藝術、展覽、博物館、媒體
    "Plan an art exhibition", "Arrange media interviews", "Coordinate performance schedules", "Discuss booth setup",
    "Plan a tour route", "Handle ticket sales issues",

    # 4. 銀行業務、投資、稅務、會計、帳單
    "Discuss investment strategy", "Resolve accounting issues", "Consult loan terms", "Review financial statements",
    "Plan tax filings", "Handle billing disputes",

    # 5. 契約、談判、併購、行銷、銷售、保證、商業企劃、會議、勞動關係
    "Negotiate contract terms", "Discuss marketing strategy", "Review sales performance", "Plan a business proposal",
    "Schedule a client meeting", "Discuss labor relations",

    # 6. 醫療保險、看醫生、牙醫、診所、醫院
    "Schedule a medical checkup", "Ask about insurance claims", "Discuss a treatment plan", "Reschedule an appointment",
    "Consult health insurance", "Confirm appointment time",

    # 7. 建築、規格、購買租賃、電力瓦斯服務
    "Discuss office renovation", "Negotiate lease terms", "Report facility issues", "Discuss utility maintenance",
    "Plan a construction project", "Handle property management",

    # 8. 工廠管理、生產線、品管
    "Discuss production scheduling", "Review quality issues", "Coordinate equipment repairs", "Plan process optimization",
    "Discuss inventory management", "Handle supply chain issues",

    # 9. 董事會、委員會、信件、備忘錄、電話、傳真、電子郵件、辦公室器材與家俱、辦公室流程
    "Discuss board meeting agenda", "Handle office equipment issues", "Coordinate document filing", "Improve admin workflow",
    "Schedule committee meeting", "Resolve mail system issues",

    # 10. 招考、雇用、退休、薪資、升遷、應徵與廣告、津貼、獎勵
    "Discuss hiring needs", "Plan interview process", "Negotiate compensation", "Discuss employee training",
    "Review promotion decisions", "Plan performance bonuses",

    # 11. 購物、訂購物資、送貨、發票
    "Handle order problems", "Discuss supplier contracts", "Coordinate delivery times", "Process returns",
    "Verify invoice details", "Plan procurement",

    # 12. 電子、科技、電腦、實驗室與相關器材、技術規格
    "Discuss system upgrades", "Handle technical support", "Plan IT equipment purchases", "Coordinate software installation",
    "Discuss network issues", "Plan technical training",

    # 13. 火車、飛機、計程車、巴士、船隻、渡輪、票務、時刻表、車站、機場廣播、租車、飯店、預定、脫班與取消
    "Arrange business travel", "Handle flight changes", "Coordinate hotel bookings", "Discuss transportation pickup",
    "Handle itinerary cancellations", "Plan group travel"
]
# Part 4 適用情境：簡短獨白（基於 TOEIC 13 大主題）
PART4_TOPICS = [
    # 1. 研究、產品研發
    "New product launch speech", "Research findings report", "Technical seminar talk", "Product testing overview",

    # 2. 商務/非正式午餐、宴會、招待會、餐廳訂位
    "Banquet welcome speech", "Meal schedule announcement", "Restaurant service introduction", "Business dinner notice",

    # 3. 電影、劇場、音樂、藝術、展覽、博物館、媒體
    "Exhibition tour introduction", "Museum visit guidelines", "Concert program briefing", "Media press statement",

    # 4. 銀行業務、投資、稅務、會計、帳單
    "Financial planning seminar", "Investment briefing", "Tax filing reminder", "Bank service introduction",

    # 5. 契約、談判、併購、行銷、銷售、保證、商業企劃、會議、勞動關係
    "Sales review meeting", "Marketing strategy briefing", "Business plan presentation", "Sales training talk",

    # 6. 醫療保險、看醫生、牙醫、診所、醫院
    "Health seminar", "Insurance coverage briefing", "Clinic service overview", "Health check reminder",

    # 7. 建築、規格、購買租賃、電力瓦斯服務
    "Construction project briefing", "Property management notice", "Facility maintenance announcement", "Utility service update",

    # 8. 工廠管理、生產線、品管
    "Production process overview", "Quality management training", "Factory safety briefing", "Process improvement report",

    # 9. 董事會、委員會、信件、備忘錄、電話、傳真、電子郵件、辦公室器材與家俱、辦公室流程
    "Board report", "Company policy announcement", "Office rules briefing", "Administrative process overview",

    # 10. 招考、雇用、退休、薪資、升遷、應徵與廣告、津貼、獎勵
    "New employee orientation", "Recruiting event introduction", "Benefits overview", "Performance evaluation standards",

    # 11. 購物、訂購物資、送貨、發票
    "Promotional announcement", "Product sale promotion", "Shopping guidelines", "Membership benefits overview",

    # 12. 電子、科技、電腦、實驗室與相關器材、技術規格
    "Product technical briefing", "Software update notice", "IT maintenance announcement", "Tech product launch",

    # 13. 火車、飛機、計程車、巴士、船隻、渡輪、票務、時刻表、車站、機場廣播、租車、飯店、預定、脫班與取消
    "Airport boarding announcement", "Flight delay notice", "Hotel check-in guidance", "Travel itinerary briefing",
    "Train delay announcement", "Car rental service overview"
]
class ListeningPrompts:
    """TOEIC 聽力測驗相關 Prompt 模板"""

    # ========== Part 1 Prompts ==========

    def get_part1_vision_prompt(self, difficulty: str = "medium") -> str:
        difficulty_hints = {
            "easy": "Options are clearly different and easy to distinguish",
            "medium": "Options are somewhat similar and require careful listening",
            "hard": "Options are very similar with subtle differences"
        }

        return _env.get_template("part1_vision.md").render(
            difficulty=difficulty,
            difficulty_hint=difficulty_hints.get(difficulty, ""),
        )

    # ========== Part 2 Prompts ==========

    def get_part2_generation_prompt(self, difficulty: str = "medium", topic_hint: str = None) -> str:
        difficulty_hints = {
            "easy": "Simple, direct questions with straightforward responses",
            "medium": "Slightly complex questions that require inference",
            "hard": "Complex or indirect questions with nuanced responses"
        }

        topic_instruction = ""
        if topic_hint:
            topic_instruction = f"\nTopic focus: {topic_hint}\n(Design the Q&A to match this topic and keep the question and response aligned.)\n"

        return _env.get_template("part2_qa.md").render(
            difficulty=difficulty,
            difficulty_hint=difficulty_hints.get(difficulty, ""),
            topic_instruction=topic_instruction,
            topic_context=" and keep it related to the topic above" if topic_hint else "",
        )

    # ========== Part 3 Prompts ==========

    def get_part3_generation_prompt(
        self,
        scenario: str,
        difficulty: str = "medium",
        topic_hint: str = None
    ) -> str:
        difficulty_hints = {
            "easy": "Straightforward dialogue with obvious answers",
            "medium": "Moderately complex dialogue that requires inference",
            "hard": "Complex dialogue requiring synthesis of multiple details"
        }

        # 優先使用 topic_hint，否則使用 scenario
        actual_scenario = topic_hint if topic_hint else scenario

        return _env.get_template("part3_conversation.md").render(
            actual_scenario=actual_scenario,
            difficulty=difficulty,
            difficulty_hint=difficulty_hints.get(difficulty, ""),
        )

    # ========== Part 4 Prompts ==========

    def get_part4_generation_prompt(
        self,
        talk_topic: str,
        difficulty: str = "medium",
        topic_hint: str = None
    ) -> str:
        difficulty_hints = {
            "easy": "Simple monologue with obvious answers",
            "medium": "Moderately complex monologue requiring inference",
            "hard": "Complex monologue requiring synthesis of details"
        }

        # 優先使用 topic_hint，否則使用 talk_topic
        actual_topic = topic_hint if topic_hint else talk_topic

        return _env.get_template("part4_talk.md").render(
            actual_topic=actual_topic,
            difficulty=difficulty,
            difficulty_hint=difficulty_hints.get(difficulty, ""),
        )


