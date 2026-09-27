import base64
import json
import os
import re
from datetime import datetime, timezone
from io import BytesIO

from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from providers.router import detect_task
from providers.models import get_providers
from providers.provider_manager import ProviderManager
from providers.fallback import FallbackEngine
from providers.task_planner import TaskPlanner
from app.search_service import FreeSearchService
from app.brain_orchestrator import BrainOrchestrator

try:
    from app.knowledge import knowledge_engine
except Exception:
    knowledge_engine = None

from app.memory import (
    init_database,
    create_conversation,
    get_conversation,
    list_conversations,
    delete_conversation,
    save_message,
    get_messages,
    build_context,
    generate_conversation_title,
)


# ==========================================
# ENV
# ==========================================

load_dotenv()
init_database()


# ==========================================
# AI SYSTEM
# ==========================================

provider_manager = ProviderManager()
fallback_engine = FallbackEngine(provider_manager=provider_manager)
task_planner = TaskPlanner()
free_search = FreeSearchService()
brain = BrainOrchestrator()


# ==========================================
# FASTAPI
# ==========================================

app = FastAPI(
    title="Silent AI API",
    version="7.0.0-brain-orchestrator",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,
)


# ==========================================
# RUNTIME CLOCK
# ==========================================

def runtime_clock() -> str:
    now_utc = datetime.now(timezone.utc)
    now_local = datetime.now().astimezone()
    return (
        "Silent AI runtime clock:\n"
        f"- UTC: {now_utc.isoformat()}\n"
        f"- Local backend time: {now_local.isoformat()}\n"
        f"- Current year: {now_local.year}\n"
        f"- Current month: {now_local.month}\n"
        f"- Current day: {now_local.day}\n\n"
        "استخدم هذه الساعة كمرجع عند تفسير today / yesterday / now / current / latest. "
        "لا تفترض أن السنة 2025 أو أي سنة أخرى."
    )


# ==========================================
# SYSTEM INSTRUCTIONS
# ==========================================

INSTRUCTIONS = """
أنت Silent AI — مساعد ذكاء اصطناعي احترافي قوي.

أهم هدف: افهم نية المستخدم أولًا ثم حل المشكلة، وليس مجرد الرد على آخر جملة.

قواعد أساسية:
1. أجب باللغة التي يستخدمها المستخدم، وبأسلوب طبيعي ومباشر.
2. استخدم سياق المحادثة السابقة لفهم: كمل، عدّل، اللي فوق، نفس الكود، نفس المشروع، إلخ.
3. لا تخترع معلومة. فرّق بين حقيقة مؤكدة، استنتاج، واحتمال.
4. إذا كانت المعلومة مرتبطة بالوقت الحالي أو إصدار برنامج أو سعر أو خبر أو حدث حديث، استخدم البحث المباشر عندما يكون متاحًا.
5. لا تعرض سلسلة التفكير الداخلية أو reasoning الخاص بك؛ اعرض فقط خطوات الحل المفيدة والنتيجة.
6. راجع إجابتك داخليًا قبل إرسالها: صحة الحساب، الوحدات، أسماء الدوال، أنواع البيانات، الافتراضات، والتناقضات.
7. إذا كان السؤال ناقصًا، اسأل سؤالًا واحدًا فقط عند الضرورة؛ وإلا استخدم افتراضًا معقولًا واذكره.

البرمجة:
- تعامل مع الطلب كمهندس برمجيات كبير.
- افهم المشروع والـstack قبل اقتراح الحل.
- لا تعطِ كودًا شكليًا؛ أعطِ كودًا قابلًا للتشغيل، متوافقًا مع السياق، واذكر مكان وضعه.
- عند إصلاح خطأ: حدد السبب الحقيقي، ثم الحل، ثم طريقة الاختبار.
- انتبه للـasync/await، types، imports، API contracts، edge cases، security، والأداء.

الرياضيات:
- اشرح الحل خطوة بخطوة لكن بصياغة بشرية سهلة القراءة.
- لا تغرق الإجابة في LaTeX أو الرموز. استخدم العربية الواضحة مثل: السرعة = المسافة ÷ الزمن، والقوة = الكتلة × التسارع.
- استخدم الرموز الرياضية البسيطة فقط عند الحاجة مثل × ÷ = ≈ ≤ ≥ و² و³.
- اكتب كل خطوة في سطر واضح، ثم ضع النتيجة النهائية في سطر مستقل.
- تحقق من الناتج بالتعويض أو بطريقة مستقلة عندما يكون ذلك ممكنًا، واذكر الوحدات.

الفيزياء:
- ابدأ بـ: المعطيات، المطلوب، القانون، التعويض، الحساب، النتيجة.
- لا تستخدم كتلًا طويلة من المعادلات الرمزية. حوّل القانون إلى جملة مفهومة ثم استخدم الرموز الضرورية فقط.
- مثال التنسيق المفضل: القوة = الكتلة × التسارع، ثم التعويض بالأرقام، ثم النتيجة مع الوحدة.
- تحقق من الوحدات ومنطق النتيجة قبل الإصدار.

المعلومات العامة والعلوم:
- قدّم شرحًا واضحًا لا مجرد تعريف سطحي.
- إذا كانت المعلومة قابلة للتغير، لا تعاملها كحقيقة ثابتة بدون تحقق.

الملفات والصور:
- افحص المحتوى المرفق فعليًا قبل الإجابة.
- إذا كان الملف طويلًا، استخرج الأجزاء المهمة بدل تجاهله.

الأسلوب:
- لا تبدأ بحشو مثل «بالتأكيد» أو «يسعدني».
- لا تكرر السؤال.

هوية Silent AI:
- أنت Silent AI، وليس شركة أو provider خارجيًا.
- إذا سأل المستخدم: مين عملك؟ مين طورك؟ مين مطورك؟ مين صاحبك؟ مين أنشأك؟ مين برمجك؟ من صنعك؟ أو أي صيغة مكافئة بالعربية أو الإنجليزية، أجب مباشرة باستخدام هوية Silent AI المعرّفة في إعداد SILENT_AI_IDENTITY، ولا تخترع اسم شخص.
- لا تقل إنك من OpenAI أو Google أو Anthropic أو Cohere أو أي شركة أخرى عند السؤال عن هوية Silent AI.
- إذا سأل المستخدم تحديدًا عن النموذج أو provider المستخدم في الطلب، ميّز بين هوية Silent AI وبين مزود النموذج ولا تخترع اسمًا.

- لا تجعل الإجابة قصيرة بشكل يضر الفهم ولا طويلة بلا فائدة.
- عند طلب كود كامل، أعطِ الملف كاملًا وليس patch ناقصًا.
"""


# ==========================================
# IDENTITY + KNOWLEDGE HELPERS
# ==========================================

SILENT_AI_IDENTITY = os.getenv(
    "SILENT_AI_IDENTITY",
    "أنا Silent AI. طوّرني محمد، وهو طالب بالصف الثاني بكالوريا، كمشروع ذكاء اصطناعي مستقل يجمع عدة نماذج ومزودات في منصة واحدة.",
).strip()


def is_identity_question(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    patterns = (
        "مين عملك", "مين اللي عملك", "مين طورك", "مين مطورك", "مين صاحبك",
        "مين انشأك", "مين أنشأك", "مين صممك", "مين برمجك", "مين المبرمج بتاعك",
        "من طورك", "من مطورك", "من انشأك", "من أنشأك", "من صنعك", "من عملك",
        "who made you", "who developed you", "who created you", "who built you",
        "who is your developer", "who created silent ai", "who made silent ai",
    )
    return any(pattern in normalized for pattern in patterns)


def enforce_silent_ai_identity(task: str, reply: str) -> str:
    if is_identity_question(task):
        return SILENT_AI_IDENTITY
    return (reply or "").strip()


def infer_user_style(text: str) -> str:
    """Lightweight style adaptation without storing sensitive profiling data."""
    value = str(text or "").strip().lower()
    if not value:
        return "أسلوب محايد وواضح."
    if any(x in value for x in ("ببساطة", "بسيط", "مش فاهم", "مش فاهمة", "اشرحلي", "يعني ايه", "يعني إيه")):
        return "المستخدم يفضّل شرحًا بسيطًا، تدريجيًا، مع مثال عملي، وتجنب المصطلحات المعقدة دون شرح."
    if any(x in value for x in ("باختصار", "مختصر", "سريع", "quick", "short")):
        return "المستخدم يفضّل إجابة قصيرة ومباشرة مع أهم النقاط فقط."
    if any(x in value for x in ("بالتفصيل", "بالتفصيل الممل", "شرح كامل", "deep", "عمق")):
        return "المستخدم يفضّل شرحًا عميقًا ومنظمًا، لكن بدون حشو أو كشف سلسلة التفكير الداخلية."
    if any(x in value for x in ("كود", "code", "برمج", "python", "javascript", "typescript")):
        return "المستخدم يفضّل تنفيذًا عمليًا وكودًا كاملًا قابلًا للتشغيل، مع خطوات اختبار واضحة."
    return "أسلوب محايد وواضح، واضبط مستوى التفصيل حسب صعوبة السؤال."


def clean_math_answer(text: str) -> str:
    """Make common LaTeX-heavy answers readable in plain chat text."""
    value = str(text or "")
    replacements = {
        "\\times": " × ",
        "\\cdot": " · ",
        "\\div": " ÷ ",
        "\\leq": " ≤ ",
        "\\le": " ≤ ",
        "\\geq": " ≥ ",
        "\\ge": " ≥ ",
        "\\neq": " ≠ ",
        "\\approx": " ≈ ",
        "\\rightarrow": " → ",
        "\\pi": "π",
        "\\Delta": "Δ",
        "\\theta": "θ",
        "\\alpha": "α",
        "\\beta": "β",
        "\\gamma": "γ",
        "\\lambda": "λ",
        "\\sqrt": "√",
        "\\%": "%",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = re.sub(r"\\text\{([^{}]*)\}", r"\1", value)
    value = re.sub(r"\\mathrm\{([^{}]*)\}", r"\1", value)
    value = value.replace("\\(", "").replace("\\)", "")
    value = value.replace("\\[", "").replace("\\]", "")
    value = value.replace("$$", "")
    value = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1) ÷ (\2)", value)
    value = re.sub(r"\^\{2\}", "²", value)
    value = re.sub(r"\^\{3\}", "³", value)
    value = re.sub(r"\s{3,}", "  ", value)
    return value.strip()


def prepare_final_answer(task: str, reply: str) -> str:
    value = clean_math_answer(reply)
    if is_identity_question(task):
        return SILENT_AI_IDENTITY
    return value


def knowledge_search(task: str) -> str:
    if knowledge_engine is None or not task.strip():
        return ""
    try:
        if hasattr(knowledge_engine, "build_context"):
            try:
                value = knowledge_engine.build_context(task, max_chars=14000)
            except TypeError:
                value = knowledge_engine.build_context(task)
            return str(value or "").strip()
        if hasattr(knowledge_engine, "search"):
            result = knowledge_engine.search(task)
            return str(result or "").strip()
    except Exception as error:
        print("Silent AI Knowledge Engine failed:", error)
    return ""


def knowledge_stats() -> dict:
    if knowledge_engine is None:
        return {"enabled": False}
    try:
        stats = knowledge_engine.stats() if hasattr(knowledge_engine, "stats") else {}
        if isinstance(stats, dict):
            return {"enabled": True, **stats}
        return {"enabled": True, "stats": stats}
    except Exception as error:
        return {"enabled": True, "error": str(error)}


# ==========================================
# SMART WEB SEARCH
# ==========================================

WEB_SEARCH_KEYWORDS = (
    # English
    "latest",
    "recent",
    "today",
    "tonight",
    "current",
    "now",
    "breaking",
    "news",
    "search",
    "look up",
    "find information",
    "what happened",
    "price",
    "weather",
    "stock",
    "score",
    "trend",
    "update",
    "updates",
    "this week",
    "this month",
    "2026",
    # Arabic
    "آخر",
    "أحدث",
    "اليوم",
    "دلوقتي",
    "حالي",
    "الآن",
    "اخبار",
    "أخبار",
    "أسعار",
    "سعر",
    "طقس",
    "نتيجة",
    "نتائج",
    "ترند",
    "تحديث",
    "تحديثات",
    "الأسبوع ده",
    "هذا الأسبوع",
    "الشهر ده",
    "هذا الشهر",
    "ابحث",
    "دور على",
    "هاتلي معلومات حديثة",
    "معلومات حديثة",
    "معلومات جديدة",
    "حصل ايه",
    "حصل إيه",
    "إيه الجديد",
    "ايه الجديد",
)


def should_web_search(task: str, task_type: str) -> bool:
    text = (task or "").strip().lower()
    if not text:
        return False
    live_enabled = os.getenv("SILENT_AI_LIVE_SEARCH", "true").strip().lower() in {"1", "true", "yes", "on"}
    if not live_enabled:
        return False
    if task_type == "research":
        return True
    return any(keyword.lower() in text for keyword in WEB_SEARCH_KEYWORDS)


def prioritize_provider_chain(providers: list[dict], preferred_provider: str | None = None, preferred_model: str | None = None) -> list[dict]:
    provider = str(preferred_provider or "").strip().lower()
    model = str(preferred_model or "").strip()
    if not provider or not model:
        return providers
    preferred = {"provider": provider, "model": model}
    rest = [item for item in providers if not (item.get("provider") == provider and item.get("model") == model)]
    return [preferred, *rest]


def research_provider_chain(task_type: str, attachment: dict | None):
    # Web search is handled by our free search layer. The model only receives
    # the collected results, so we do not invoke Gemini or paid OpenRouter
    # search tools here.
    if attachment:
        return get_providers("image") if provider_manager.free_only else get_providers(task_type)
    return get_providers("research")


def clean_source_list(sources: list[dict]) -> list[dict]:
    """Deduplicate and normalize grounding sources for the frontend."""
    result = []
    seen = set()

    for source in sources:
        if not isinstance(source, dict):
            continue

        url = str(source.get("url") or "").strip()
        title = str(source.get("title") or "").strip()

        if not url or url in seen:
            continue

        seen.add(url)
        result.append({
            "title": title or url,
            "url": url,
        })

    return result[:12]


# ==========================================
# HEALTH
# ==========================================

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "message": "Silent AI Backend is running",
        "version": "7.0.0-brain-orchestrator",
        "providers": provider_manager.status(),
        "memory": "sqlite",
        "streaming": True,
        "knowledge": knowledge_stats(),
        "runtime_clock": datetime.now().astimezone().isoformat(),
    }


@app.get("/models")
async def get_models_catalog():
    return {"status": "ok", "catalog": provider_manager.catalog()}


@app.get("/knowledge/stats")
async def get_knowledge_stats():
    return {"status": "ok", "knowledge": knowledge_stats()}


@app.get("/brain/status")
async def get_brain_status():
    return {"status": "ok", "brain": brain.status()}




# ==========================================
# CONVERSATIONS
# ==========================================

@app.post("/conversations")
async def create_new_conversation():
    conversation_id = create_conversation()
    conversation = get_conversation(conversation_id)
    return {"status": "ok", "conversation": conversation}


@app.get("/conversations")
async def get_all_conversations():
    return {"status": "ok", "conversations": list_conversations()}


@app.get("/conversations/{conversation_id}")
async def get_conversation_data(conversation_id: str):
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="المحادثة غير موجودة")

    messages = get_messages(conversation_id=conversation_id, limit=100)
    return {
        "status": "ok",
        "conversation": conversation,
        "messages": messages,
    }


@app.delete("/conversations/{conversation_id}")
async def remove_conversation(conversation_id: str):
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="المحادثة غير موجودة")

    delete_conversation(conversation_id)
    return {"status": "ok", "message": "تم حذف المحادثة"}


# ==========================================
# REQUEST HELPERS
# ==========================================

def decode_data_url(data_url: str) -> bytes:
    if not data_url or "," not in data_url:
        return b""
    try:
        return base64.b64decode(data_url.split(",", 1)[1])
    except Exception:
        return b""


def extract_binary_text(item: dict) -> str:
    """Best-effort extraction for common documents without making uploads fail."""
    name = str(item.get("name") or "")
    lower = name.lower()
    raw = decode_data_url(str(item.get("data_url") or ""))
    if not raw:
        return ""

    if lower.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(raw))
            pages = []
            for page in reader.pages[:30]:
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(text)
            return "\n\n".join(pages)[:120_000]
        except Exception:
            return ""

    if lower.endswith(".docx"):
        try:
            from docx import Document
            document = Document(BytesIO(raw))
            parts = [p.text for p in document.paragraphs if p.text.strip()]
            for table in document.tables:
                for row in table.rows:
                    parts.append(" | ".join(cell.text.strip() for cell in row.cells))
            return "\n".join(parts)[:120_000]
        except Exception:
            return ""

    if lower.endswith(".xlsx"):
        try:
            from openpyxl import load_workbook
            workbook = load_workbook(BytesIO(raw), read_only=True, data_only=True)
            rows = []
            for sheet in workbook.worksheets[:10]:
                rows.append(f"[Sheet: {sheet.title}]")
                for row in sheet.iter_rows(max_row=300, values_only=True):
                    values = ["" if value is None else str(value) for value in row]
                    if any(values):
                        rows.append(" | ".join(values))
            return "\n".join(rows)[:120_000]
        except Exception:
            return ""

    return ""


def enrich_message_with_attachments(message: str, attachments: list[dict]) -> str:
    text = message or ""
    parts = []
    for item in attachments:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "ملف")
        inline = str(item.get("text_content") or "").strip()
        extracted = inline or extract_binary_text(item)
        if extracted:
            parts.append(f"\n\n--- محتوى الملف: {name} ---\n{extracted}")
        else:
            parts.append(f"\n\n--- ملف مرفق: {name} ({item.get('type') or 'unknown'}) ---")
    return (text + "".join(parts))[:220_000]


def build_ai_request(task: str, context: str = "") -> str:
    if not context:
        return task

    return (
        "سياق المحادثة السابقة:\n\n"
        f"{context}\n\n"
        "--------------------------------\n\n"
        "الطلب الحالي:\n\n"
        f"{task}\n\n"
        "أجب عن الطلب الحالي مباشرة، واستخدم السياق فقط لفهم الاستمرارية."
    )


def validate_chat_data(data: dict):
    message = str(data.get("message") or "").strip()
    attachment = data.get("attachment")
    attachments = data.get("attachments") or []

    if not isinstance(attachments, list):
        attachments = []

    # Keep the first image as the model attachment.
    if not attachment:
        for item in attachments:
            if isinstance(item, dict) and str(item.get("type") or "").startswith("image/"):
                attachment = item
                break

    if not message and not attachment and not attachments:
        raise HTTPException(status_code=400, detail="الرسالة فارغة")

    if attachment:
        attachment_type = str(attachment.get("type") or "")
        if not attachment_type.startswith("image/"):
            attachment = None
        elif not attachment.get("data_url"):
            raise HTTPException(status_code=400, detail="بيانات الصورة غير موجودة.")

    # Text-like files are already extracted in the browser and included in
    # the message. Non-text files are still accepted as attachments so the
    # UI never rejects a valid upload just because the current provider
    # cannot parse that binary format.
    return message, attachment, attachments


def prepare_conversation(message: str, conversation_id: str | None):
    if conversation_id:
        conversation = get_conversation(conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="المحادثة غير موجودة")
        return conversation_id, conversation

    title = generate_conversation_title(message or "تحليل صورة")
    new_id = create_conversation(title=title)
    return new_id, get_conversation(new_id)


def save_user_message(conversation_id: str, message: str, attachment: dict | None, attachments: list[dict] | None = None):
    saved_content = message
    attachment_names = [
        str(item.get("name") or "ملف")
        for item in (attachments or [])
        if isinstance(item, dict)
    ]
    if attachment_names:
        marker = "\n\n[المرفقات: " + ", ".join(attachment_names[:8]) + "]"
        saved_content = f"{saved_content}{marker}" if saved_content else marker.strip()
    elif attachment:
        saved_content = (
            f"{saved_content}\n\n[تم إرفاق صورة]"
            if saved_content
            else "[تم إرفاق صورة]"
        )

    save_message(
        conversation_id=conversation_id,
        role="user",
        content=saved_content,
    )


# ==========================================
# NON-STREAMING EXECUTION
# ==========================================

def expert_instructions(task_type: str, web_search: bool, attachment: dict | None = None, user_message: str = "") -> str:
    blocks = [INSTRUCTIONS]
    modes = {
        "coding": "أنت الآن في وضع هندسة البرمجيات: حلّل architecture، dependencies، edge cases، ثم قدّم تنفيذًا كاملًا واختبره ذهنيًا.",
        "reasoning": "أنت الآن في وضع الاستدلال العميق: فكك المشكلة إلى خطوات منطقية، تحقق من كل نتيجة، ولا تقفز إلى الاستنتاج.",
        "research": "أنت الآن في وضع البحث: استخدم المصادر الحديثة عند توفرها، قارن المعلومات المتعارضة، واذكر التاريخ/المصدر عند أهمية ذلك.",
        "image": "أنت الآن في وضع الرؤية: افحص الصورة فعليًا، اقرأ النص الظاهر، صف ما يمكن إثباته، ثم أجب عن المطلوب.",
        "summarization": "أنت الآن في وضع التلخيص: حافظ على المعنى والمصطلحات، واحذف التكرار فقط.",
        "translation": "أنت الآن في وضع الترجمة: حافظ على المعنى والنبرة والمصطلحات، ولا تضف معلومات.",
        "writing": "أنت الآن في وضع الكتابة: اهتم بالهدف والجمهور والنبرة والبنية.",
        "chat": "أنت الآن في وضع المساعد العام: افهم المقصود وقدم إجابة مفيدة وعميقة بالقدر المناسب.",
    }
    blocks.append(modes.get(task_type, modes["chat"]))
    blocks.append(f"أسلوب المستخدم المكتشف من الرسالة الحالية: {infer_user_style(user_message)}")
    blocks.append("في الإجابات التعليمية، اجعل العناوين قصيرة والخطوات مرئية، وفضّل اللغة الطبيعية على الاستعراض الرمزي.")
    if web_search:
        blocks.append("هذه الإجابة تعتمد على معلومات قد تكون متغيرة؛ استخدم أداة البحث المتاحة، ولا تعتمد على الذاكرة وحدها. إذا استخدمت نتائج بحث، ميّز بوضوح بين ما وجدته وما استنتجته.")
    if attachment:
        blocks.append("هناك مرفق. لا تتجاهله ولا تدّعي رؤيته إذا لم تتمكن من قراءته فعليًا.")
    return "\n\n".join(blocks)


def make_brain_generator(configs: list[dict], attachment: dict | None = None):
    """Rotate available providers between brain passes, with local fallback."""
    usable = [c for c in configs if provider_manager.is_configured(c.get("provider", ""))]
    if not usable:
        raise RuntimeError("لا يوجد مزود متاح حاليًا.")
    cursor = 0
    trace: list[dict] = []

    def generate(message: str, instructions: str) -> str:
        nonlocal cursor
        errors = []
        for offset in range(len(usable)):
            index = (cursor + offset) % len(usable)
            config = usable[index]
            try:
                reply = provider_manager.generate(
                    provider=config["provider"],
                    model=config["model"],
                    message=message,
                    instructions=instructions,
                    attachment=attachment,
                    web_search=False,
                )
                if reply and reply.strip():
                    trace.append({"provider": config["provider"], "model": config["model"]})
                    cursor = (index + 1) % len(usable)
                    return reply.strip()
            except Exception as error:
                errors.append(f"{config['provider']}/{config['model']}: {error}")
        raise RuntimeError("Brain provider rotation failed: " + " | ".join(errors[-4:]))

    return generate, trace


def execute_task(
    task: str,
    task_type: str,
    context: str = "",
    attachment: dict | None = None,
    preferred_provider: str | None = None,
    preferred_model: str | None = None,
) -> dict:
    final_task = build_ai_request(task, context)
    web_search = should_web_search(task, task_type)
    active_instructions = expert_instructions(task_type, web_search, attachment, task)
    active_instructions = f"{active_instructions}\n\n{runtime_clock()}"

    local_knowledge = knowledge_search(task)
    if local_knowledge:
        final_task += (
            f"\n\n=== قاعدة المعرفة المحلية ===\n{local_knowledge}\n=== نهاية قاعدة المعرفة ===\n"
            "استخدم قاعدة المعرفة المحلية عندما تكون مرتبطة بالسؤال، ولا تنسب إليها معلومة غير موجودة فيها."
        )

    search_sources = []
    if web_search and not attachment:
        search_bundle = free_search.search(task)
        search_sources = search_bundle.get("sources", [])
        search_context = search_bundle.get("context", "")
        if search_context:
            final_task += (
                "\n\n=== نتائج البحث المجاني ===\n"
                f"{search_context}\n"
                "=== نهاية نتائج البحث ===\n"
                "استخدم نتائج البحث كمرجع للمعلومات الحديثة. لا تخترع مصدرًا غير موجود في النتائج."
            )

    providers = research_provider_chain(task_type, attachment) if web_search else get_providers(task_type)
    providers = prioritize_provider_chain(providers, preferred_provider, preferred_model)
    if not providers:
        raise RuntimeError("لا توجد نماذج متاحة لتنفيذ الطلب حاليًا.")

    errors = []

    def call_model(message: str, instructions: str, config: dict) -> str:
        return provider_manager.generate(
            provider=config["provider"],
            model=config["model"],
            message=message,
            instructions=instructions,
            attachment=attachment,
            web_search=False,
        )

    usable = [c for c in providers if provider_manager.is_configured(c["provider"])]
    if not usable:
        raise RuntimeError("لا يوجد مزود متاح حاليًا.")

    try:
        brain_generate, brain_trace = make_brain_generator(usable, attachment)
        result = brain.run(
            task=task,
            task_type=task_type,
            base_message=final_task,
            instructions=active_instructions,
            provider="multi-provider",
            generate=brain_generate,
        )
        reply = prepare_final_answer(task, result["reply"])
        if reply:
            chosen = brain_trace[-1] if brain_trace else usable[0]
            return {
                "status": "ok",
                "provider": chosen["provider"],
                "model": chosen["model"],
                "reply": reply,
                "web_search": web_search,
                "sources": clean_source_list(search_sources),
                "errors": errors,
                "brain": {**result["meta"], "provider_trace": brain_trace},
            }
    except Exception as error:
        errors.append({"provider": "multi-provider", "model": "adaptive", "error": str(error)})

    # Final lightweight fallback if the verified brain path cannot complete.
    for config in usable:
        try:
            reply = provider_manager.generate(
                provider=config["provider"],
                model=config["model"],
                message=final_task,
                instructions=active_instructions,
                attachment=attachment,
                web_search=False,
            )
            if reply and reply.strip():
                return {
                    "status": "ok",
                    "provider": config["provider"],
                    "model": config["model"],
                    "reply": prepare_final_answer(task, reply),
                    "web_search": web_search,
                    "sources": clean_source_list(search_sources),
                    "errors": errors,
                    "brain": {"mode": "lightweight-fallback", "verified": False},
                }
        except Exception as error:
            errors.append({"provider": config["provider"], "model": config["model"], "error": str(error)})

    raise RuntimeError(f"All providers failed: {errors}")


# ==========================================
# CHAT
# ==========================================

@app.post("/chat")
async def chat(data: dict):
    message, attachment, attachments = validate_chat_data(data)
    message = enrich_message_with_attachments(message, attachments)
    conversation_id, _conversation = prepare_conversation(
        message,
        data.get("conversation_id"),
    )

    previous_context = build_context(
        conversation_id=conversation_id,
        limit=20,
    )

    save_user_message(
        conversation_id=conversation_id,
        message=message,
        attachment=attachment,
        attachments=attachments,
    )

    task_type = detect_task(message or "حلل الصورة المرفقة")
    if attachment or attachments:
        task_type = "image"

    try:
        result = execute_task(
            task=message or "حلل الصورة المرفقة.",
            task_type=task_type,
            context=previous_context,
            attachment=attachment,
            preferred_provider=data.get("provider"),
            preferred_model=data.get("model"),
        )

        final_reply = prepare_final_answer(message, result["reply"])
        save_message(
            conversation_id=conversation_id,
            role="assistant",
            content=final_reply,
        )

        conversation = get_conversation(conversation_id)

        return {
            "status": "ok",
            "conversation_id": conversation_id,
            "conversation": conversation,
            "task": task_type,
            "steps": 1,
            "provider": result["provider"],
            "model": result["model"],
            "reply": final_reply,
        }

    except Exception as error:
        print("Silent AI error:", error)
        raise HTTPException(status_code=500, detail=str(error))


# ==========================================
# STREAMING HELPERS
# ==========================================

def sse(event: str, payload: dict) -> str:
    return (
        f"event: {event}\n"
        f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    )


def iter_provider_events(
    provider: str,
    model: str,
    message: str,
    instructions: str,
    attachment: dict | None = None,
    web_search: bool = False,
):
    """Yield normalized streaming events from ProviderManager."""
    yield from provider_manager.stream_generate(
        provider=provider,
        model=model,
        message=message,
        instructions=instructions,
        attachment=attachment,
        web_search=web_search,
    )


def streaming_provider_chain(
    task_type: str,
    attachment: dict | None,
    web_search: bool,
    preferred_provider: str | None = None,
    preferred_model: str | None = None,
):
    if web_search:
        return prioritize_provider_chain(research_provider_chain(task_type, attachment), preferred_provider, preferred_model)

    if attachment:
        # In strict free mode, image analysis must stay on the free OpenRouter path.
        if provider_manager.free_only:
            return prioritize_provider_chain(get_providers("image"), preferred_provider, preferred_model)
        return prioritize_provider_chain([{
            "provider": "gemini", "model": "gemini-3.8-flash",
        }], preferred_provider, preferred_model)

    return prioritize_provider_chain(get_providers(task_type), preferred_provider, preferred_model)


# ==========================================
# CHAT STREAM
# ==========================================

@app.post("/chat/stream")
async def chat_stream(data: dict):
    message, attachment, attachments = validate_chat_data(data)
    message = enrich_message_with_attachments(message, attachments)
    conversation_id, _conversation = prepare_conversation(
        message,
        data.get("conversation_id"),
    )

    previous_context = build_context(
        conversation_id=conversation_id,
        limit=20,
    )

    save_user_message(
        conversation_id=conversation_id,
        message=message,
        attachment=attachment,
        attachments=attachments,
    )

    task_type = detect_task(message or "حلل الصورة المرفقة")
    if attachment or attachments:
        task_type = "image"

    final_task = build_ai_request(
        message or "حلل الصورة المرفقة.",
        previous_context,
    )

    web_search = should_web_search(message, task_type)
    active_instructions = expert_instructions(task_type, web_search, attachment, message)
    active_instructions = f"{active_instructions}\n\n{runtime_clock()}"

    local_knowledge = knowledge_search(message)
    if local_knowledge:
        final_task = (
            f"{final_task}\n\n=== قاعدة المعرفة المحلية ===\n{local_knowledge}\n=== نهاية قاعدة المعرفة ===\n"
            "استخدم قاعدة المعرفة المحلية عندما تكون مرتبطة بالسؤال، ولا تنسب إليها معلومة غير موجودة فيها."
        )

    search_sources = []
    if web_search and not attachment:
        try:
            search_bundle = free_search.search(message)
            search_sources = search_bundle.get("sources", [])
            search_context = search_bundle.get("context", "")
            if search_context:
                final_task = (
                    f"{final_task}\n\n"
                    "=== نتائج البحث المجاني ===\n"
                    f"{search_context}\n"
                    "=== نهاية نتائج البحث ===\n"
                    "استخدم نتائج البحث كمرجع للمعلومات الحديثة. لا تخترع مصدرًا غير موجود في النتائج."
                )
        except Exception as error:
            print("Silent AI Free Search failed:", error)
            search_sources = []

    providers = streaming_provider_chain(
        task_type=task_type,
        attachment=attachment,
        preferred_provider=data.get("provider"),
        preferred_model=data.get("model"),
        # Search is already handled locally; this flag only describes the
        # request in the API events and must not trigger provider-side search.
        web_search=False,
    )

    # For difficult tasks, build a verified final answer before opening the SSE stream.
    # Simple chat stays truly streaming and uses the normal provider stream.
    brain_prepared_reply = None
    brain_prepared_meta = None
    if not is_identity_question(message) and brain.should_verify(task_type, message):
        try:
            usable = [c for c in providers if provider_manager.is_configured(c["provider"])]
            brain_generate, brain_trace = make_brain_generator(usable, attachment)
            result = brain.run(
                task=message,
                task_type=task_type,
                base_message=final_task,
                instructions=active_instructions,
                provider="multi-provider",
                generate=brain_generate,
            )
            brain_prepared_reply = prepare_final_answer(message, result["reply"])
            brain_prepared_meta = {**result["meta"], "provider_trace": brain_trace}
        except Exception as error:
            print("Silent AI Brain preflight failed:", error)

    if not providers:
        raise HTTPException(
            status_code=500,
            detail=f"لا توجد providers متاحة للمهمة: {task_type}",
        )

    def event_stream():
        accumulated = ""
        selected_provider = None

        if is_identity_question(message):
            accumulated = SILENT_AI_IDENTITY
            yield sse("meta", {"status": "started", "conversation_id": conversation_id, "task": "identity", "provider": "silent-ai", "model": "identity", "web_search": False})
            yield sse("delta", {"text": SILENT_AI_IDENTITY})
            save_message(conversation_id=conversation_id, role="assistant", content=accumulated)
            yield sse("done", {"status": "ok", "conversation_id": conversation_id, "task": "identity", "provider": "silent-ai", "model": "identity", "web_search": False, "sources": []})
            return
        selected_model = None
        sources = clean_source_list(search_sources)
        errors = []

        if brain_prepared_reply:
            selected_provider = "brain-orchestrator"
            selected_model = "verified"
            yield sse("meta", {
                "status": "started",
                "conversation_id": conversation_id,
                "task": task_type,
                "provider": "brain-orchestrator",
                "model": "verified",
                "web_search": web_search,
                "brain": brain_prepared_meta or {},
            })
            yield sse("delta", {"text": brain_prepared_reply})
            save_message(conversation_id=conversation_id, role="assistant", content=brain_prepared_reply)
            yield sse("done", {
                "status": "ok", "conversation_id": conversation_id, "task": task_type,
                "provider": selected_provider, "model": selected_model,
                "web_search": web_search, "sources": sources,
                "brain": brain_prepared_meta or {},
            })
            return

        try:
            for config in providers:
                provider = config["provider"]
                model = config["model"]

                if not provider_manager.is_configured(provider):
                    errors.append({
                        "provider": provider,
                        "model": model,
                        "error": "غير متصل",
                    })
                    continue

                print(
                    f"Silent AI Stream → trying {provider}/{model} "
                    f"web_search={web_search}"
                )

                try:
                    stream = iter_provider_events(
                        provider=provider,
                        model=model,
                        message=final_task,
                        instructions=active_instructions,
                        attachment=attachment,
                        web_search=False,
                    )

                    local_text = ""
                    sent_meta = False

                    for item in stream:
                        if not isinstance(item, dict):
                            continue

                        event_type = item.get("type")

                        if event_type == "sources":
                            incoming = item.get("sources") or []
                            sources = clean_source_list(
                                sources + incoming
                            )
                            yield sse(
                                "sources",
                                {
                                    "sources": sources,
                                },
                            )
                            continue

                        if event_type != "delta":
                            continue

                        chunk = str(item.get("text") or "")
                        if not chunk:
                            continue

                        if not sent_meta:
                            selected_provider = provider
                            selected_model = model
                            sent_meta = True
                            yield sse(
                                "meta",
                                {
                                    "status": "started",
                                    "conversation_id": conversation_id,
                                    "task": task_type,
                                    "provider": provider,
                                    "model": model,
                                    "web_search": web_search,
                                },
                            )

                        local_text += chunk
                        accumulated += chunk
                        yield sse("delta", {"text": chunk})

                    if local_text:
                        selected_provider = provider
                        selected_model = model
                        print(
                            f"Silent AI Stream → success "
                            f"{provider}/{model} web_search={web_search}"
                        )
                        break

                    raise RuntimeError("Provider رجّع Stream بدون نص")

                except Exception as error:
                    error_message = str(error)
                    print(
                        f"Silent AI Stream → failed "
                        f"{provider}/{model}: {error_message}"
                    )
                    errors.append({
                        "provider": provider,
                        "model": model,
                        "error": error_message,
                    })

                    # Never mix a second provider into a partially streamed answer.
                    if accumulated:
                        yield sse(
                            "error",
                            {
                                "error": "انقطع التوليد بعد بدء الرد.",
                                "provider": provider,
                            },
                        )
                        break

                    continue

            if not accumulated:
                if web_search:
                    user_error = "تعذر تنفيذ البحث المجاني أو معالجة نتائجه حاليًا."
                else:
                    user_error = "تعذر تنفيذ الطلب حاليًا."

                yield sse(
                    "error",
                    {
                        "error": user_error,
                        "web_search": web_search,
                        "details": errors,
                    },
                )
                return

            save_message(
                conversation_id=conversation_id,
                role="assistant",
                content=accumulated,
            )

            yield sse(
                "done",
                {
                    "status": "ok",
                    "conversation_id": conversation_id,
                    "task": task_type,
                    "provider": selected_provider,
                    "model": selected_model,
                    "web_search": web_search,
                    "sources": clean_source_list(sources),
                },
            )

        except GeneratorExit:
            if accumulated:
                save_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=accumulated,
                )
            raise
        except Exception as error:
            print("Silent AI stream fatal error:", error)
            if accumulated:
                save_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=accumulated,
                )
            yield sse("error", {"error": str(error)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": data.get("_cors_origin", "http://localhost:3000"),
            "Access-Control-Allow-Credentials": "true",
        },
    )

