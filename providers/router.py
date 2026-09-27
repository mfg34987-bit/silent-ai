from typing import Literal


TaskType = Literal[
    "chat",
    "coding",
    "reasoning",
    "writing",
    "summarization",
    "translation",
    "research",
    "image",
]


def contains_any(
    text: str,
    keywords: list[str],
) -> bool:
    return any(
        keyword in text
        for keyword in keywords
    )


def detect_task(message: str) -> TaskType:
    text = message.lower().strip()

    # ==========================================
    # IMAGE
    # ==========================================

    image_keywords = [
        "generate image",
        "generate an image",
        "create image",
        "create an image",
        "draw",
        "picture",
        "photo",
        "image",
        "صورة",
        "اعمل صورة",
        "اعمل لي صورة",
        "ارسم",
        "توليد صورة",
        "أنشئ صورة",
        "انشئ صورة",
        "حلل الصورة",
        "حلللي الصورة",
    ]

    if contains_any(
        text,
        image_keywords,
    ):
        return "image"

    # ==========================================
    # CODING
    # ==========================================

    coding_keywords = [
        "python",
        "javascript",
        "typescript",
        "react",
        "next.js",
        "nextjs",
        "html",
        "css",
        "sql",
        "api",
        "backend",
        "frontend",
        "program",
        "programming",
        "code",
        "coding",
        "debug",
        "bug",
        "error",
        "function",
        "class",
        "database",
        "برمجة",
        "برمج",
        "كود",
        "بايثون",
        "جافاسكريبت",
        "تايب سكريبت",
        "ريأكت",
        "خطأ في الكود",
        "صلح الكود",
        "اكتب برنامج",
    ]

    if contains_any(
        text,
        coding_keywords,
    ):
        return "coding"

    # ==========================================
    # RESEARCH / WEB
    # ==========================================

    research_keywords = [
        "latest",
        "recent",
        "today",
        "tonight",
        "yesterday",
        "current",
        "currently",
        "now",
        "news",
        "search",
        "search the web",
        "search online",
        "look up",
        "look it up",
        "find information",
        "what happened",
        "price today",
        "stock price",
        "exchange rate",
        "weather",
        "آخر الأخبار",
        "اخر الاخبار",
        "أحدث الأخبار",
        "احدث الاخبار",
        "أحدث",
        "احدث",
        "اليوم",
        "دلوقتي",
        "دلوقتى",
        "حاليًا",
        "حاليا",
        "الآن",
        "الان",
        "مؤخرًا",
        "مؤخرا",
        "حديث",
        "جديد",
        "الجديد",
        "آخر",
        "اخر",
        "ابحث",
        "دور على",
        "دورلي",
        "دور لي",
        "ابحثلي",
        "ابحث لي",
        "على النت",
        "على الإنترنت",
        "علي النت",
        "من على النت",
        "هاتلي من النت",
        "هات لي من النت",
        "أخبار",
        "اخبار",
        "سعر اليوم",
        "النهاردة",
        "النهارده",
        "الاسبوع ده",
        "الأسبوع ده",
        "السنة دي",
        "السنه دي",
        "2026",
    ]

    if contains_any(
        text,
        research_keywords,
    ):
        return "research"

    # ==========================================
    # TRANSLATION
    # ==========================================

    translation_keywords = [
        "translate",
        "translation",
        "ترجم",
        "ترجمة",
        "حول إلى الإنجليزية",
        "حول للإنجليزية",
        "حول إلى العربية",
        "حول للعربية",
        "بالإنجليزية",
        "بالانجليزية",
        "باللغة الإنجليزية",
        "باللغة العربية",
    ]

    if contains_any(
        text,
        translation_keywords,
    ):
        return "translation"

    # ==========================================
    # SUMMARIZATION
    # ==========================================

    summarization_keywords = [
        "summarize",
        "summary",
        "shorten",
        "تلخيص",
        "لخص",
        "اختصر",
        "اختصار",
        "ملخص",
        "اعمل ملخص",
        "لخصلي",
        "لخص لي",
    ]

    if contains_any(
        text,
        summarization_keywords,
    ):
        return "summarization"

    # ==========================================
    # REASONING
    # ==========================================

    reasoning_keywords = [
        "solve",
        "calculate",
        "reason",
        "reasoning",
        "analyze",
        "analysis",
        "compare",
        "why",
        "how",
        "math",
        "problem",
        "حل",
        "احسب",
        "مسألة",
        "مساله",
        "حلل",
        "تحليل",
        "قارن",
        "مقارنة",
        "ليه",
        "لماذا",
        "ازاي",
        "إزاي",
        "كيف",
        "استنتج",
        "استنتاج",
    ]

    if contains_any(
        text,
        reasoning_keywords,
    ):
        return "reasoning"

    # ==========================================
    # WRITING
    # ==========================================

    writing_keywords = [
        "write",
        "rewrite",
        "email",
        "essay",
        "article",
        "story",
        "letter",
        "post",
        "caption",
        "اكتب",
        "اكتبلي",
        "اكتب لي",
        "إعادة صياغة",
        "اعادة صياغة",
        "إيميل",
        "ايميل",
        "مقال",
        "قصة",
        "رسالة",
        "بوست",
        "كابشن",
    ]

    if contains_any(
        text,
        writing_keywords,
    ):
        return "writing"

    return "chat"