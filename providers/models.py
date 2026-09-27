import os


def _env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


MODE = os.getenv("SILENT_AI_MODE", "smart").strip().lower()
ALLOW_PAID = _env_bool("SILENT_AI_ALLOW_PAID", False)

# Compatibility: the old FREE_ONLY flag is honored only when the new mode is
# explicitly set to "free". This lets the upgraded app escape the old
# OpenRouter-only lock without silently editing the user's .env file.
FREE_ONLY = MODE == "free" or (MODE not in {"smart", "max"} and _env_bool("SILENT_AI_FREE_ONLY", True))


# Current OpenRouter free endpoints change over time. openrouter/free is kept
# as a dynamic router, while these known-good current endpoints add diversity.
OPENROUTER_FREE = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "inclusionai/ling-3.0-flash:free",
    "thinkingmachines/inkling:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "openrouter/free",
]


SMART_CHAINS = {
    "chat": [
        {"provider": "groq", "model": "openai/gpt-oss-120b"},
        {"provider": "gemini", "model": "gemini-3.8-flash"},
        {"provider": "openrouter", "model": "nvidia/nemotron-3-ultra-550b-a55b:free"},
        {"provider": "openrouter", "model": "openrouter/free"},
        {"provider": "ollama", "model": "__auto__"},
    ],
    "coding": [
        {"provider": "groq", "model": "openai/gpt-oss-120b"},
        {"provider": "gemini", "model": "gemini-3.8-flash"},
        {"provider": "openrouter", "model": "nvidia/nemotron-3-ultra-550b-a55b:free"},
        {"provider": "openrouter", "model": "openrouter/free"},
        {"provider": "ollama", "model": "__auto__"},
    ],
    "reasoning": [
        {"provider": "gemini", "model": "gemini-3.8-flash"},
        {"provider": "groq", "model": "openai/gpt-oss-120b"},
        {"provider": "openrouter", "model": "nvidia/nemotron-3-ultra-550b-a55b:free"},
        {"provider": "openrouter", "model": "openrouter/free"},
        {"provider": "ollama", "model": "__auto__"},
    ],
    "writing": [
        {"provider": "gemini", "model": "gemini-3.8-flash"},
        {"provider": "groq", "model": "openai/gpt-oss-20b"},
        {"provider": "openrouter", "model": "inclusionai/ling-3.0-flash:free"},
        {"provider": "openrouter", "model": "openrouter/free"},
        {"provider": "ollama", "model": "__auto__"},
    ],
    "summarization": [
        {"provider": "groq", "model": "openai/gpt-oss-20b"},
        {"provider": "gemini", "model": "gemini-3.8-flash"},
        {"provider": "openrouter", "model": "openrouter/free"},
        {"provider": "ollama", "model": "__auto__"},
    ],
    "translation": [
        {"provider": "gemini", "model": "gemini-3.8-flash"},
        {"provider": "groq", "model": "openai/gpt-oss-20b"},
        {"provider": "openrouter", "model": "openrouter/free"},
        {"provider": "ollama", "model": "__auto__"},
    ],
    "research": [
        {"provider": "gemini", "model": "gemini-3.8-flash"},
        {"provider": "groq", "model": "openai/gpt-oss-120b"},
        {"provider": "openrouter", "model": "nvidia/nemotron-3-ultra-550b-a55b:free"},
        {"provider": "openrouter", "model": "openrouter/free"},
    ],
    "image": [
        {"provider": "gemini", "model": "gemini-3.8-flash"},
        {"provider": "openrouter", "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"},
        {"provider": "openrouter", "model": "openrouter/free"},
    ],
}


FREE_CHAINS = {
    task: [*([{"provider": "openrouter", "model": m} for m in models]), {"provider": "ollama", "model": "__auto__"}]
    for task, models in {
        "chat": OPENROUTER_FREE,
        "coding": OPENROUTER_FREE,
        "reasoning": OPENROUTER_FREE,
        "writing": OPENROUTER_FREE,
        "summarization": OPENROUTER_FREE,
        "translation": OPENROUTER_FREE,
        "research": OPENROUTER_FREE,
        "image": OPENROUTER_FREE[:4],
    }.items()
}


MAX_CHAINS = {
    task: chain + ([{"provider": "openai", "model": os.getenv("SILENT_AI_OPENAI_MODEL", "gpt-5.6")}] if ALLOW_PAID else [])
    for task, chain in SMART_CHAINS.items()
}


def get_providers(task_type: str) -> list[dict]:
    task_type = (task_type or "chat").strip().lower()
    if task_type not in SMART_CHAINS:
        task_type = "chat"

    if FREE_ONLY:
        return [dict(item) for item in FREE_CHAINS[task_type]]

    if MODE == "max":
        return [dict(item) for item in MAX_CHAINS[task_type]]

    return [dict(item) for item in SMART_CHAINS[task_type]]


def is_free_only() -> bool:
    return FREE_ONLY


def routing_status() -> dict:
    return {
        "mode": "free" if FREE_ONLY else MODE,
        "free_only": FREE_ONLY,
        "allow_paid": ALLOW_PAID,
        "architecture": "adaptive multi-provider brain",
        "provider_order": ["groq", "gemini", "openrouter", "ollama"] if not FREE_ONLY else ["openrouter", "ollama"],
    }
