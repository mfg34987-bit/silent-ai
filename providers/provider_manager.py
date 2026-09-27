import base64
import os
import time
from typing import Iterator

import requests
from dotenv import load_dotenv
from openai import OpenAI
from google import genai
from google.genai import types

load_dotenv()


def get_clean_api_key(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        return ""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value.strip()


def _free_only() -> bool:
    mode = os.getenv("SILENT_AI_MODE", "smart").strip().lower()
    if mode in {"smart", "max"}:
        return False
    return os.getenv("SILENT_AI_FREE_ONLY", "true").strip().lower() in {"1", "true", "yes", "on"}


def _live_search_enabled() -> bool:
    return os.getenv("SILENT_AI_LIVE_SEARCH", "true").strip().lower() in {"1", "true", "yes", "on"}


class ProviderManager:
    """Provider gateway with strict Free-Only routing and multimodal OpenRouter support."""

    FREE_ROUTER = "openrouter/free"
    MODELS_URL = "https://openrouter.ai/api/v1/models"
    FREE_CACHE_SECONDS = 600

    def __init__(self):
        self.free_only = _free_only()
        self.openai_api_key = get_clean_api_key("OPENAI_API_KEY")
        self.gemini_api_key = get_clean_api_key("GEMINI_API_KEY")
        self.groq_api_key = get_clean_api_key("GROQ_API_KEY")
        self.openrouter_api_key = get_clean_api_key("OPENROUTER_API_KEY")

        self.openai_client = OpenAI(api_key=self.openai_api_key) if self.openai_api_key else None
        self.gemini_client = genai.Client(api_key=self.gemini_api_key) if self.gemini_api_key else None
        self.groq_client = OpenAI(api_key=self.groq_api_key, base_url="https://api.groq.com/openai/v1") if self.groq_api_key else None
        self.openrouter_client = OpenAI(api_key=self.openrouter_api_key, base_url="https://openrouter.ai/api/v1") if self.openrouter_api_key else None

        self._free_models_cache: list[str] = []
        self._free_models_cache_at = 0.0
        self._free_multimodal_cache: list[str] = []
        self._free_multimodal_cache_at = 0.0

    def _looks_like_web_search(self, message: str) -> bool:
        text = (message or "").strip().lower()
        if not text:
            return False
        keywords = (
            "latest", "recent", "today", "now", "current", "news", "search", "look up", "price", "weather", "stock", "score", "trend", "update", "2026",
            "آخر", "أحدث", "اليوم", "دلوقتي", "حالي", "الآن", "أخبار", "أسعار", "سعر", "طقس", "نتيجة", "نتائج", "ترند", "ابحث", "دور على", "معلومات حديثة", "معلومات جديدة", "الجديد",
        )
        return any(k in text for k in keywords)

    def is_configured(self, provider: str) -> bool:
        provider = (provider or "").strip().lower()
        if provider == "openai":
            return self.openai_client is not None
        if provider == "gemini":
            return self.gemini_client is not None
        if provider == "groq":
            return self.groq_client is not None
        if provider == "openrouter":
            return self.openrouter_client is not None
        if provider == "ollama":
            return self._ollama_model() is not None
        return False

    def _ollama_model(self) -> str | None:
        """Return an explicitly configured Ollama model or the first installed model."""
        preferred = os.getenv("SILENT_AI_OLLAMA_MODEL", "").strip()
        try:
            response = requests.get("http://127.0.0.1:11434/api/tags", timeout=2.5)
            response.raise_for_status()
            models = response.json().get("models", [])
            names = [str(item.get("name") or "").strip() for item in models]
            names = [name for name in names if name]
            if preferred and preferred in names:
                return preferred
            if preferred and not names:
                return None
            return names[0] if names else None
        except Exception:
            return None

    def _resolve_ollama_model(self, model: str) -> str:
        if model and model != "__auto__":
            return model
        resolved = self._ollama_model()
        if not resolved:
            raise RuntimeError(
                "Ollama غير جاهز أو لا يوجد نموذج مثبت. شغّل: ollama list"
            )
        return resolved

    def _ensure_allowed(self, provider: str, model: str):
        if not self.free_only:
            return

        # Strict free mode:
        # - OpenRouter: only :free models / openrouter/free
        # - Ollama: local inference, no API charge
        if provider == "ollama":
            return

        if provider != "openrouter":
            raise RuntimeError("SILENT_AI_FREE_ONLY يمنع استخدام مزود غير مجاني.")

        if model != self.FREE_ROUTER and not model.endswith(":free"):
            raise RuntimeError("SILENT_AI_FREE_ONLY يمنع استخدام نموذج غير مجاني.")

    def _free_models(self, multimodal: bool = False) -> list[str]:
        if not self.openrouter_api_key:
            return []
        now = time.time()
        cache = self._free_multimodal_cache if multimodal else self._free_models_cache
        cache_at = self._free_multimodal_cache_at if multimodal else self._free_models_cache_at
        if cache and now - cache_at < self.FREE_CACHE_SECONDS:
            return list(cache)

        try:
            response = requests.get(
                self.MODELS_URL,
                headers={"Authorization": f"Bearer {self.openrouter_api_key}"},
                timeout=20,
            )
            response.raise_for_status()
            items = response.json().get("data", [])
            result = []
            for item in items:
                model_id = str(item.get("id") or "").strip()
                pricing = item.get("pricing") or {}
                prompt = str(pricing.get("prompt", ""))
                completion = str(pricing.get("completion", ""))
                architecture = item.get("architecture") or {}
                input_modalities = architecture.get("input_modalities") or []
                if multimodal and "image" not in input_modalities:
                    continue
                if not model_id or model_id == self.FREE_ROUTER:
                    continue
                if prompt == "0" and completion == "0":
                    result.append(model_id)
            if multimodal:
                self._free_multimodal_cache = result
                self._free_multimodal_cache_at = now
            else:
                self._free_models_cache = result
                self._free_models_cache_at = now
            return list(result)
        except Exception:
            return list(cache)

    @staticmethod
    def _attachment_parts(attachment: dict | None) -> list[dict]:
        if not attachment:
            return []
        data_url = str(attachment.get("data_url") or "")
        if not data_url:
            return []
        mime = str(attachment.get("type") or attachment.get("mime_type") or "application/octet-stream")
        return [
            {"type": "image_url", "image_url": {"url": data_url}}
        ] if mime.startswith("image/") else []

    def _openrouter_messages(self, message: str, instructions: str = "", attachment: dict | None = None):
        messages = []
        if instructions:
            messages.append({"role": "system", "content": instructions})
        content = [{"type": "text", "text": message}]
        content.extend(self._attachment_parts(attachment))
        messages.append({"role": "user", "content": content if len(content) > 1 else message})
        return messages

    def generate(self, provider: str, model: str, message: str, instructions: str = "", attachment: dict | None = None, web_search: bool = False) -> str:
        provider = (provider or "").strip().lower()
        if provider == "ollama":
            model = self._resolve_ollama_model(model)
        self._ensure_allowed(provider, model)
        if provider == "openrouter":
            return self._openrouter_free_generate(model, message, instructions, attachment, web_search)
        if provider == "gemini":
            return self._gemini_generate(model, message, instructions, attachment, web_search)
        if provider == "groq":
            return self._groq_generate(model, message, instructions, web_search)
        if provider == "openai":
            return self._openai_generate(model, message, instructions)
        if provider == "ollama":
            return self._ollama_generate(model, message, instructions)
        raise RuntimeError(f"Provider غير معروف: {provider}")

    def _openrouter_free_generate(self, model, message, instructions, attachment, web_search=False):
        if not self.openrouter_client:
            raise RuntimeError("OpenRouter API key غير موجود.")

        models = [model]
        if model != self.FREE_ROUTER:
            models.append(self.FREE_ROUTER)
        else:
            models += self._free_models(multimodal=bool(attachment))[:6]

        errors = []
        for candidate in models:
            try:
                kwargs = {
                    "model": candidate,
                    "messages": self._openrouter_messages(message, instructions, attachment),
                }

                # OpenRouter's server tool gives even free models live web access.
                # The model decides whether a search is needed.
                if web_search and _live_search_enabled():
                    kwargs["tools"] = [{
                        "type": "openrouter:web_search",
                        "parameters": {
                            "engine": "auto",
                            "max_results": 5,
                            "search_context_size": "medium",
                            "max_total_results": 10,
                        },
                    }]

                response = self.openrouter_client.chat.completions.create(**kwargs)
                if response.choices and getattr(response.choices[0].message, "content", None):
                    return response.choices[0].message.content.strip()
            except Exception as exc:
                errors.append(f"{candidate}: {exc}")

        raise RuntimeError("كل نماذج OpenRouter المجانية فشلت. " + " | ".join(errors[-4:]))

    def _openrouter_free_stream(self, model, message, instructions, attachment, web_search=False) -> Iterator[str]:
        if web_search and _live_search_enabled():
            yield self._openrouter_free_generate(model, message, instructions, attachment, web_search=True)
            return

        if not self.openrouter_client:
            raise RuntimeError("OpenRouter API key غير موجود.")
        models = [model]
        if model != self.FREE_ROUTER:
            models.append(self.FREE_ROUTER)
        else:
            models += self._free_models(multimodal=bool(attachment))[:6]
        errors = []
        for candidate in models:
            try:
                stream = self.openrouter_client.chat.completions.create(
                    model=candidate,
                    messages=self._openrouter_messages(message, instructions, attachment),
                    stream=True,
                )
                emitted = False
                for chunk in stream:
                    if not chunk.choices:
                        continue
                    content = getattr(chunk.choices[0].delta, "content", None)
                    if content:
                        emitted = True
                        yield content
                if emitted:
                    return
            except Exception as exc:
                errors.append(f"{candidate}: {exc}")
        raise RuntimeError("كل نماذج OpenRouter المجانية فشلت. " + " | ".join(errors[-4:]))

    def _openai_generate(self, model, message, instructions):
        if not self.openai_client:
            raise RuntimeError("OpenAI API key غير موجود.")
        response = self.openai_client.responses.create(model=model, instructions=instructions or None, input=message)
        text = getattr(response, "output_text", None)
        if not text:
            raise RuntimeError("OpenAI رجّع رد فارغ.")
        return text.strip()

    def _openai_stream(self, model, message, instructions) -> Iterator[str]:
        if not self.openai_client:
            raise RuntimeError("OpenAI API key غير موجود.")
        stream = self.openai_client.responses.create(model=model, instructions=instructions or None, input=message, stream=True)
        for event in stream:
            if getattr(event, "type", "") == "response.output_text.delta":
                delta = getattr(event, "delta", None)
                if delta:
                    yield delta

    def _gemini_config(self, instructions="", web_search=False):
        kwargs = {}
        if instructions:
            kwargs["system_instruction"] = instructions
        if web_search:
            kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]
        return types.GenerateContentConfig(**kwargs)

    def _gemini_generate(self, model, message, instructions="", attachment=None, web_search=False):
        if not self.gemini_client:
            raise RuntimeError("Gemini API key غير موجود.")
        contents = []
        if attachment:
            data_url = attachment.get("data_url") or ""
            if "," in data_url:
                raw = base64.b64decode(data_url.split(",", 1)[1])
                contents.append(types.Part.from_bytes(data=raw, mime_type=attachment.get("type", "application/octet-stream")))
        contents.append(message)
        response = self.gemini_client.models.generate_content(model=model, contents=contents, config=self._gemini_config(instructions, web_search))
        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("Gemini رجّع رد فارغ.")
        return text.strip()

    def _gemini_stream(self, model, message, instructions="", attachment=None, web_search=False) -> Iterator[dict]:
        if not self.gemini_client:
            raise RuntimeError("Gemini API key غير موجود.")
        contents = []
        if attachment:
            data_url = attachment.get("data_url") or ""
            if "," in data_url:
                raw = base64.b64decode(data_url.split(",", 1)[1])
                contents.append(types.Part.from_bytes(data=raw, mime_type=attachment.get("type", "application/octet-stream")))
        contents.append(message)
        stream = self.gemini_client.models.generate_content_stream(model=model, contents=contents, config=self._gemini_config(instructions, web_search))
        for chunk in stream:
            text = getattr(chunk, "text", None)
            if text:
                yield {"type": "delta", "text": text}

    def _groq_generate(self, model, message, instructions="", web_search=False):
        if not self.groq_client:
            raise RuntimeError("Groq API key غير موجود.")
        messages = []
        if instructions:
            messages.append({"role": "system", "content": instructions})
        messages.append({"role": "user", "content": message})
        kwargs = {"model": model, "messages": messages}
        if web_search:
            kwargs["tools"] = [{"type": "browser_search"}]
            kwargs["tool_choice"] = "required"
        response = self.groq_client.chat.completions.create(**kwargs)
        if not response.choices or not getattr(response.choices[0].message, "content", None):
            raise RuntimeError("Groq رجّع رد فارغ.")
        return response.choices[0].message.content.strip()

    def _groq_stream(self, model, message, instructions="", web_search=False) -> Iterator[str]:
        if web_search:
            yield self._groq_generate(model, message, instructions, True)
            return
        if not self.groq_client:
            raise RuntimeError("Groq API key غير موجود.")
        messages = []
        if instructions:
            messages.append({"role": "system", "content": instructions})
        messages.append({"role": "user", "content": message})
        stream = self.groq_client.chat.completions.create(model=model, messages=messages, stream=True)
        for chunk in stream:
            if chunk.choices:
                content = getattr(chunk.choices[0].delta, "content", None)
                if content:
                    yield content

    def _ollama_generate(self, model, message, instructions=""):
        prompt = f"{instructions}\n\nUser:\n{message}" if instructions else message
        response = requests.post("http://127.0.0.1:11434/api/generate", json={"model": model, "prompt": prompt, "stream": False}, timeout=120)
        response.raise_for_status()
        text = response.json().get("response", "")
        if not text:
            raise RuntimeError("Ollama رجّع رد فارغ.")
        return text.strip()

    def stream_generate(self, provider, model, message, instructions="", attachment=None, web_search=False) -> Iterator[dict]:
        provider = (provider or "").strip().lower()
        if provider == "ollama":
            model = self._resolve_ollama_model(model)
        self._ensure_allowed(provider, model)
        if provider == "openrouter":
            for text in self._openrouter_free_stream(model, message, instructions, attachment, web_search=web_search):
                yield {"type": "delta", "text": text}
            return
        if provider == "gemini":
            yield from self._gemini_stream(model, message, instructions, attachment, web_search)
            return
        if provider == "groq":
            for text in self._groq_stream(model, message, instructions, web_search or self._looks_like_web_search(message)):
                yield {"type": "delta", "text": text}
            return
        if provider == "openai":
            for text in self._openai_stream(model, message, instructions):
                yield {"type": "delta", "text": text}
            return
        if provider == "ollama":
            yield {"type": "delta", "text": self._ollama_generate(model, message, instructions)}
            return
        raise RuntimeError(f"Provider غير معروف: {provider}")

    def catalog(self) -> dict:
        """Return a safe model/provider catalog for the UI without exposing keys."""
        free_models = self._free_models(multimodal=False)[:24]
        return {
            "providers": [
                {
                    "id": "groq",
                    "name": "Groq",
                    "configured": self.is_configured("groq"),
                    "models": [
                        "openai/gpt-oss-120b",
                        "openai/gpt-oss-20b",
                        "llama-3.3-70b-versatile",
                    ],
                },
                {
                    "id": "gemini",
                    "name": "Google Gemini",
                    "configured": self.is_configured("gemini"),
                    "models": [
                        "gemini-3.8-flash",
                        "gemini-3.7-flash",
                        "gemini-3.6-flash",
                        "gemini-3.5-flash-lite",
                    ],
                },
                {
                    "id": "openrouter",
                    "name": "OpenRouter",
                    "configured": self.is_configured("openrouter"),
                    "models": ["openrouter/free", *free_models],
                    "model_count_note": "OpenRouter can expose a large catalog; this list shows the currently discovered free endpoints.",
                },
                {
                    "id": "openai",
                    "name": "OpenAI",
                    "configured": self.is_configured("openai"),
                    "models": [os.getenv("SILENT_AI_OPENAI_MODEL", "gpt-5.6")],
                },
                {
                    "id": "ollama",
                    "name": "Ollama Local",
                    "configured": self.is_configured("ollama"),
                    "models": self._ollama_models(),
                },
            ],
            "free_model_count": len(free_models),
        }

    def _ollama_models(self) -> list[str]:
        try:
            response = requests.get("http://127.0.0.1:11434/api/tags", timeout=2.5)
            response.raise_for_status()
            return [
                str(item.get("name") or "").strip()
                for item in response.json().get("models", [])
                if str(item.get("name") or "").strip()
            ]
        except Exception:
            return []

    def status(self) -> dict:
        return {
            "openai": self.is_configured("openai"),
            "gemini": self.is_configured("gemini"),
            "groq": self.is_configured("groq"),
            "openrouter": self.is_configured("openrouter"),
            "ollama": self.is_configured("ollama"),
            "ollama_model": self._ollama_model(),
            "free_only": self.free_only,
            "mode": os.getenv("SILENT_AI_MODE", "smart").strip().lower(),
            "allow_paid": os.getenv("SILENT_AI_ALLOW_PAID", "false").strip().lower() in {"1", "true", "yes", "on"},
            "free_engine": self.free_only and (
                self.is_configured("openrouter") or self.is_configured("ollama")
            ),
            "live_search": _live_search_enabled() and self.is_configured("openrouter"),
        }
