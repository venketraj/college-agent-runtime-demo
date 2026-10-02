"""Model providers: Claude API (online) with Ollama (local) fallback, both through Strands."""
import os
from dataclasses import dataclass
from pathlib import Path

import ollama
from strands.models.anthropic import AnthropicModel
from strands.models.ollama import OllamaModel

def load_env(path=Path(__file__).resolve().parent.parent / ".env"):
    """Minimal .env loader: KEY=value lines; real environment variables take precedence; blanks are skipped."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if sep and key and not key.startswith("#") and val and not os.environ.get(key):
            os.environ[key] = val


load_env()

DEFAULT_CLAUDE = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")
DEFAULT_OLLAMA = os.environ.get("OLLAMA_MODEL", "qwen3.5:9b")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
EMBED_MODEL = "nomic-embed-text"


@dataclass
class Settings:
    provider: str            # "auto" | "claude" | "ollama"
    claude_model: str
    ollama_model: str
    api_key: str | None


@dataclass
class Candidate:
    label: str               # shown in the UI, e.g. "Claude · claude-sonnet-5"
    kind: str                # "claude" | "ollama"
    build: callable          # () -> strands Model


def ollama_models() -> list[str]:
    """Installed chat models (embedding models filtered out); empty list if Ollama isn't running."""
    try:
        names = [m.model for m in ollama.Client(host=OLLAMA_HOST).list().models]
    except Exception:
        return []
    return [n for n in names if "embed" not in n]


def candidates(s: Settings) -> list[Candidate]:
    """Models to try in order. 'auto' = Claude first, then the local Ollama model."""
    claude = Candidate(
        f"Claude · {s.claude_model}", "claude",
        lambda: AnthropicModel(client_args={"api_key": s.api_key, "max_retries": 1, "timeout": 60},
                               model_id=s.claude_model, max_tokens=8192))
    local = Candidate(
        f"Ollama · {s.ollama_model}", "ollama",
        lambda: OllamaModel(OLLAMA_HOST, model_id=s.ollama_model, temperature=0.3, keep_alive="30m", max_tokens=4096,
                            additional_args={"think": False}))
    if s.provider == "claude":
        return [claude]
    if s.provider == "ollama":
        return [local]
    return ([claude] if s.api_key else []) + [local]
