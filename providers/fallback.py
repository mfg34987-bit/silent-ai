import time


class FallbackEngine:
    def __init__(self, provider_manager):
        self.provider_manager = provider_manager
        self.free_only = bool(getattr(provider_manager, "free_only", False))

    @staticmethod
    def _retryable(error: Exception) -> bool:
        text = str(error).lower()
        markers = (
            "429", "rate limit", "quota", "temporarily", "timeout", "timed out",
            "503", "502", "504", "unavailable", "overloaded", "try again",
            "capacity", "connection", "reset",
        )
        return any(marker in text for marker in markers)

    def generate(self, providers, message, instructions="", attachment=None):
        errors = []
        for config in providers or []:
            provider = str(config.get("provider") or "").strip().lower()
            model = str(config.get("model") or "").strip()

            if self.free_only:
                # Strict free mode allows OpenRouter :free models and local Ollama.
                allowed = (
                    provider == "ollama"
                    or (provider == "openrouter" and (model == "openrouter/free" or model.endswith(":free")))
                )
                if not allowed:
                    continue

            if not self.provider_manager.is_configured(provider):
                continue

            attempts = 2
            for attempt in range(attempts):
                try:
                    reply = self.provider_manager.generate(
                        provider=provider,
                        model=model,
                        message=message,
                        instructions=instructions,
                        attachment=attachment,
                        web_search=False,
                    )
                    if reply and reply.strip():
                        return {
                            "status": "ok",
                            "provider": provider,
                            "model": model,
                            "reply": reply.strip(),
                            "errors": errors,
                        }
                    raise RuntimeError("Provider رجّع رد فارغ.")
                except Exception as error:
                    errors.append({"provider": provider, "model": model, "error": str(error)})
                    if attempt == 0 and self._retryable(error):
                        time.sleep(0.35)
                        continue
                    break

        raise RuntimeError(f"All providers failed: {errors}")
