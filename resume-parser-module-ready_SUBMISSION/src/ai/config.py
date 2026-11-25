import os
from typing import List

try:
    from dotenv import load_dotenv
    _env_path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"))
    if os.path.exists(_env_path):
        load_dotenv(_env_path, override=True)
    else:
        load_dotenv(override=True)
except Exception:
    pass


def parse_port(val, default: int = 3001) -> int:
    """Matches JavaScript Number(process.env.PORT) || 3001 semantics.
    Invalid strings, '0', '0.0', whitespace, and empty strings evaluate to default (3001).
    """
    try:
        if val is None:
            return default
        s = str(val).strip()
        if not s:
            return default
        num = float(s)
        if num == 0 or num != num or num < 0:  # 0, NaN, or negative
            return default
        return int(num)
    except (ValueError, TypeError, OverflowError):
        return default


class _Config:
    def __init__(self):
        self.port = parse_port(os.environ.get("PORT"))

        self.nodeEnv = os.environ.get("NODE_ENV") or "development"
        self.node_env = self.nodeEnv

        self.geminiApiKey = (os.environ.get("GEMINI_API_KEY") or "").strip()
        self.gemini_api_key = self.geminiApiKey

        self.geminiModel = (
            os.environ.get("GEMINI_MODEL")
            or os.environ.get("GEMINI_RESUME_MODEL")
            or "gemini-3.1-flash-lite"
        ).strip()
        self.gemini_model = self.geminiModel

        raw_fallbacks = os.environ.get("GEMINI_FALLBACK_MODELS") or "gemini-3.1-flash-lite,gemini-3.8-flash,gemini-3.5-flash"
        self.geminiFallbackModels = [m.strip() for m in raw_fallbacks.split(",") if m.strip()]
        self.gemini_fallback_models = self.geminiFallbackModels

        self.corsOrigin = os.environ.get("CORS_ORIGIN") or "*"
        self.cors_origin = self.corsOrigin

        self.maxFileSizeMb = 10
        self.max_file_size_mb = 10
        self.maxBulkFiles = 5
        self.max_bulk_files = 5

    def __setattr__(self, name: str, value):
        super().__setattr__(name, value)
        # Keep camelCase and snake_case synchronized
        if name == "geminiApiKey":
            super().__setattr__("gemini_api_key", value)
        elif name == "gemini_api_key":
            super().__setattr__("geminiApiKey", value)
        elif name == "geminiModel":
            super().__setattr__("gemini_model", value)
        elif name == "gemini_model":
            super().__setattr__("geminiModel", value)
        elif name == "geminiFallbackModels":
            super().__setattr__("gemini_fallback_models", value)
        elif name == "gemini_fallback_models":
            super().__setattr__("geminiFallbackModels", value)


config = _Config()


def get_ai_model_label() -> str:
    primary = config.geminiModel
    fallbacks = [m for m in config.geminiFallbackModels if m != primary]
    if fallbacks:
        return f"{primary} (+ {', '.join(fallbacks)})"
    return primary


getAiModelLabel = get_ai_model_label
