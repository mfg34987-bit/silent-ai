from __future__ import annotations

import os
import re
from typing import Callable


class BrainOrchestrator:
    """Silent AI Brain V10: adaptive verification without exposing chain-of-thought."""

    HARD_TASKS = {"coding", "reasoning", "research", "image"}
    VERIFY_HINTS = (
        "حل", "احسب", "برهن", "اثبت", "راجع", "صحح", "حلل", "قارن",
        "اشرح بالتفصيل", "مسألة", "رياضيات", "رياضيات", "فيزياء", "قانون",
        "debug", "fix", "implement", "refactor", "prove", "calculate",
        "analyze", "compare", "research", "architecture", "design", "build",
        "optimize", "derive", "math", "physics",
    )

    def __init__(self) -> None:
        self.max_chars = int(os.getenv("SILENT_AI_BRAIN_MAX_CHARS", "24000"))
        self.enabled = os.getenv("SILENT_AI_BRAIN_VERIFY", "true").strip().lower() in {
            "1", "true", "yes", "on"
        }

    @staticmethod
    def _clean(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    def should_verify(self, task_type: str, task: str) -> bool:
        if not self.enabled:
            return False
        text = self._clean(task).lower()
        if not text:
            return False
        if task_type in self.HARD_TASKS:
            return True
        return len(text) >= 180 or any(x in text for x in self.VERIFY_HINTS)

    def depth(self, task_type: str, task: str) -> str:
        text = self._clean(task).lower()
        if task_type in {"coding", "reasoning", "research", "image"}:
            return "deep"
        if any(x in text for x in ("فيزياء", "رياضيات", "مسألة", "احسب", "برهن", "derive", "physics", "math")):
            return "deep"
        if len(text) >= 700:
            return "deep"
        if any(x in text for x in self.VERIFY_HINTS):
            return "verified"
        return "quick"

    def _expert_prompt(self, task: str, draft: str, task_type: str) -> str:
        focus = {
            "coding": "افحص architecture وAPIs وimports وtypes وasync وsecurity وedge cases وقابلية التشغيل.",
            "reasoning": "افحص المنطق والافتراضات والحسابات والنتيجة، وابحث عن القفزات غير المبررة.",
            "research": "افحص التواريخ والمصادر وما تدعمه الأدلة وما هو استنتاج، ولا تخترع مصدرًا.",
            "image": "افحص أن كل استنتاج متعلق بالمرفق مدعوم بما يمكن رؤيته أو قراءته فعلًا.",
        }.get(task_type, "افحص الدقة والاكتمال والافتراضات والملاءمة للطلب.")
        if task_type in {"reasoning", "chat"} and any(x in task.lower() for x in ("رياضيات", "فيزياء", "مسألة", "احسب")):
            focus += " في المسألة التعليمية: تحقق من القانون، التعويض، الحساب، الإشارة، والوحدة، ثم اجعل العرض بسيطًا وغير مزدحم بالرموز."
        return f"""
أنت Expert Agent مستقل داخل Silent AI.

المهمة الأصلية:
{task}

المسودة الحالية:
{draft[:self.max_chars]}

{focus}

أخرج تقرير تحقق عمليًا ومختصرًا:
- ما الذي يمكن اعتماده
- أي خطأ مؤكد
- أي افتراض يحتاج توضيحًا
- الإصلاح المطلوب
- النتيجة التي يجب اعتمادها

لا تكتب للمستخدم ولا تكشف سلسلة التفكير الداخلية.
""".strip()

    def _critic_prompt(self, task: str, draft: str, expert: str, task_type: str) -> str:
        return f"""
أنت Quality Gate داخل Silent AI.

نوع المهمة: {task_type}
الطلب: {task}
المسودة: {draft[:self.max_chars]}
التحقق: {expert[:12000]}

راجع فقط:
1. مطابقة الطلب.
2. صحة الحقائق وعدم اختراع معلومات.
3. البرمجة: API/import/type/async/security/edge cases.
4. الرياضيات والفيزياء: القانون، الحساب، الإشارة، والوحدات.
5. البحث: الحداثة والمصادر والتمييز بين الحقيقة والاستنتاج.
6. وضوح الإجابة وعدم إغراقها بالرموز.

أخرج إصلاحات قصيرة فقط. لا تكتب الإجابة النهائية ولا تكشف التفكير الداخلي.
""".strip()

    def _final_prompt(self, task: str, draft: str, expert: str, critique: str, task_type: str) -> str:
        return f"""
أنت Silent AI في مرحلة الإصدار النهائي.

نوع المهمة: {task_type}
الطلب الأصلي:
{task}

المسودة:
{draft[:self.max_chars]}

التحقق المستقل:
{expert[:12000]}

Quality Gate:
{critique[:10000]}

أصدر أفضل إجابة نهائية الآن.

قواعد الإصدار:
- أصلح الأخطاء الحقيقية فقط.
- لا تضف حشوًا.
- لا تخترع مصادر أو أرقامًا أو APIs.
- لا تذكر Brain أو الوكلاء أو المراجعة الداخلية.
- لا تعرض سلسلة التفكير الداخلية.
- في الرياضيات والفيزياء استخدم تنسيقًا واضحًا: المعطيات → المطلوب → القانون → التعويض → الحساب → النتيجة، مع أقل قدر ممكن من LaTeX.
- استخدم الرموز البسيطة عند الحاجة فقط: × ÷ = ≈ ≤ ≥ ² ³.
""".strip()

    def run(
        self,
        task: str,
        task_type: str,
        base_message: str,
        instructions: str,
        provider: str,
        generate: Callable[[str, str], str],
    ) -> dict:
        task = str(task or "").strip()
        if not task:
            raise RuntimeError("Brain task was empty")

        draft = str(generate(base_message, instructions) or "").strip()
        if not draft:
            raise RuntimeError("Brain draft was empty")

        if not self.should_verify(task_type, task):
            return {
                "reply": draft,
                "meta": {
                    "version": "10.0",
                    "mode": "quick",
                    "verified": False,
                    "depth": "quick",
                    "provider": provider,
                    "passes": 1,
                },
            }

        depth = self.depth(task_type, task)
        expert = str(generate(
            self._expert_prompt(task, draft, task_type),
            instructions + "\n\nأنت Expert Agent للتحقق فقط.",
        ) or "").strip()

        if not expert:
            return {
                "reply": draft,
                "meta": {
                    "version": "10.0",
                    "mode": "draft-fallback",
                    "verified": False,
                    "depth": depth,
                    "provider": provider,
                    "passes": 1,
                },
            }

        critique = str(generate(
            self._critic_prompt(task, draft, expert, task_type),
            instructions + "\n\nأنت Quality Gate. أخرج إصلاحات فقط.",
        ) or "").strip()

        final = str(generate(
            self._final_prompt(task, draft, expert, critique, task_type),
            instructions,
        ) or "").strip() or draft

        return {
            "reply": final[:self.max_chars],
            "meta": {
                "version": "10.0",
                "mode": "adaptive-draft-expert-quality-final",
                "verified": True,
                "depth": depth,
                "provider": provider,
                "passes": 4,
                "capabilities": [
                    "adaptive-routing",
                    "multi-provider-verification",
                    "expert-check",
                    "quality-gate",
                    "math-physics-check",
                    "context-aware-finalization",
                ],
            },
        }

    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "version": "10.0",
            "architecture": "adaptive multi-provider agent: draft -> expert -> quality-gate -> final",
            "hard_tasks": sorted(self.HARD_TASKS),
            "capabilities": [
                "adaptive-depth",
                "multi-provider-verification",
                "expert-verification",
                "quality-gate",
                "math-physics-check",
                "context-aware-final-answer",
            ],
            "passes": {"simple": 1, "complex": 4},
        }
