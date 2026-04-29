"""
TOEIC 考題主題分類常數

根據 TOEIC 官方 13 大主題類別，細分為具體的情境主題
每個主題都可以用於生成具有多樣性的考題
"""

# TOEIC 官方 13 大主題的細分情境列表
TOEIC_TOPICS = [
    # 1. 研究、產品研發
    "New product development project",
    "Market research survey",
    "Technical research report",
    "Product testing and evaluation",
    "R&D team meeting",
    "Innovation proposal review",

    # 2. 商務／非正式午餐、宴會、招待會、餐廳訂位
    "Business lunch arrangement",
    "Client appreciation banquet",
    "Year-end company party",
    "Welcome lunch for new employees",
    "Project completion celebration dinner",
    "Private dining room reservation",
    "Catering service booking",
    "Business dinner planning",

    # 3. 電影、劇場、音樂、藝術、展覽、博物館、媒體
    "Movie premiere event",
    "Theater ticketing",
    "Concert ticket reservation",
    "Art exhibition opening",
    "Museum tour booking",
    "Corporate arts sponsorship",
    "Media interview scheduling",
    "Cultural event sponsorship",
    "Performance promotion campaign",

    # 4. 銀行業務、投資、稅務、會計、帳單
    "Bank account opening request",
    "Commercial loan review",
    "Investment planning",
    "Stock trade notification",
    "Tax filing reminder",
    "Annual financial statements",
    "Accounting record processing",
    "Invoice issuance notice",
    "Bill payment deadline",
    "Credit card statement details",

    # 5. 契約、談判、併購、行銷、銷售、保證、商業企劃、會議、勞動關係
    "Contract signing negotiation",
    "Business negotiation meeting",
    "Company merger deal",
    "Marketing strategy meeting",
    "Sales target setting",
    "Product warranty terms",
    "Annual business plan",
    "Quarterly performance review",
    "Labor-management meeting",
    "Union negotiation notice",
    "Supplier contract renewal",

    # 6. 醫療保險、看醫生、牙醫、診所、醫院
    "Employee health insurance",
    "Medical benefits overview",
    "Health checkup notice",
    "Dental appointment booking",
    "Clinic hours",
    "Hospital admission procedure",
    "Insurance claim application",
    "Work injury compensation",

    # 7. 建築、規格、購買租賃、電力瓦斯服務
    "Office renovation project",
    "Building design specifications",
    "Commercial lease agreement",
    "Facility purchase plan",
    "Power system upgrade",
    "Gas pipeline inspection",
    "Utility maintenance notice",
    "Property management service",
    "Facility safety inspection",

    # 8. 工廠管理、生產線、品管
    "Production line expansion plan",
    "Factory equipment maintenance",
    "Quality control process",
    "Process improvement project",
    "Production efficiency boost",
    "Inventory management system",
    "Supply chain optimization",
    "Workplace safety standards",

    # 9. 董事會、委員會、信件、備忘錄、電話、傳真、電子郵件、辦公室器材與家俱、辦公室流程
    "Board meeting call",
    "Committee decision notice",
    "Formal business letter",
    "Internal memo",
    "Conference call scheduling",
    "Fax confirmation",
    "Email policy update",
    "Office equipment procurement",
    "Office furniture replacement",
    "Document filing process",
    "Administrative procedure update",

    # 10. 招考、雇用、退休、薪資、升遷、應徵與廣告、津貼、獎勵
    "Job posting announcement",
    "Interview process notice",
    "New employee onboarding",
    "Probation evaluation",
    "Retirement plan",
    "Salary adjustment notice",
    "Promotion criteria",
    "Performance bonus payout",
    "Employee allowance benefits",
    "Employee recognition award",
    "Internal job opening",

    # 11. 購物、訂購物資、送貨、發票
    "Office supplies purchase",
    "Materials order request",
    "Supplier quotation",
    "Delivery confirmation",
    "Invoice reconciliation",
    "Return and exchange handling",
    "Procurement contract signing",
    "Inventory restock notice",

    # 12. 電子、科技、電腦、實驗室與相關器材、技術規格
    "Computer equipment upgrade",
    "Software system update",
    "Technical specification review",
    "Laboratory instrument purchase",
    "IT infrastructure",
    "Network security policy",
    "Data backup plan",
    "Tech product launch",
    "Technical support service",

    # 13. 火車、飛機、計程車、巴士、船隻、渡輪、票務、時刻表、車站、機場廣播、租車、飯店、預定、脫班與取消
    "Business travel planning",
    "Flight ticket confirmation",
    "High-speed rail booking",
    "Airport pickup service",
    "Bus timetable",
    "Ferry schedule information",
    "Train delay notice",
    "Flight cancellation and refund",
    "Car rental reservation",
    "Hotel booking",
    "Conference venue booking",
    "Travel itinerary change",
    "Transportation allowance request",
]

# Part 6/7 文章格式選項（避免固定範例導致同質化）
PASSAGE_STYLES = [
    "business email",
    "web page",
    "memo",
    "advertisement",
    "job posting",
    "customer service letter",
    "messaging app",
    "event notice",
    "press release",
    "business report summary",
    "news report",
    "schedule",
    "invoice",
]

# 按照使用頻率排序，確保常見商務情境優先
def get_topic_for_question_type(question_type: str, index: int = 0) -> str:
    """
    根據題型和索引獲取主題

    Args:
        question_type: 題型 (sentence/paragraph/single_passage/multiple_passage)
        index: 索引（用於循環選擇不同主題）

    Returns:
        主題字串
    """
    # 使用模運算確保索引不會超出範圍，同時確保不同索引選到不同主題
    topic_index = index % len(TOEIC_TOPICS)
    return TOEIC_TOPICS[topic_index]

# 獲取指定數量的不重複主題
def get_diverse_topics(count: int) -> list[str]:
    """
    獲取指定數量的不重複主題

    Args:
        count: 需要的主題數量

    Returns:
        主題列表
    """
    import random

    # 如果需要的數量超過可用主題，則循環使用
    if count <= len(TOEIC_TOPICS):
        # 隨機打亂並取前 count 個
        shuffled = TOEIC_TOPICS.copy()
        random.shuffle(shuffled)
        return shuffled[:count]
    else:
        # 需要循環使用主題
        topics = []
        shuffled = TOEIC_TOPICS.copy()
        while len(topics) < count:
            random.shuffle(shuffled)
            topics.extend(shuffled)
        return topics[:count]


def get_diverse_passage_styles(count: int) -> list[str]:
    """
    獲取指定數量的文章格式

    Args:
        count: 需要的格式數量

    Returns:
        格式列表
    """
    import random

    if count <= len(PASSAGE_STYLES):
        shuffled = PASSAGE_STYLES.copy()
        random.shuffle(shuffled)
        return shuffled[:count]

    styles = []
    shuffled = PASSAGE_STYLES.copy()
    while len(styles) < count:
        random.shuffle(shuffled)
        styles.extend(shuffled)
    return styles[:count]
