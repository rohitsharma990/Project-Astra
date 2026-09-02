from dataclasses import dataclass
import os
from pathlib import Path

from ..config import OLLAMA_BASE_URL, AI_MODEL, AI_TIMEOUT

dotenv_path = Path(__file__).resolve().parents[2] / ".env"
if dotenv_path.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path, override=True)
    except ImportError:
        try:
            with dotenv_path.open("r", encoding="utf-8") as env_file:
                for raw_line in env_file:
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if not key:
                        continue
                    if ((value.startswith('"') and value.endswith('"')) or
                            (value.startswith("'") and value.endswith("'"))):
                        value = value[1:-1]
                    os.environ[key] = value
        except OSError:
            pass


@dataclass(frozen=True)
class AIConfig:
    provider: str = os.getenv("AI_PROVIDER", "ollama")
    model: str = AI_MODEL
    api_url: str = os.getenv("AI_API_URL", f"{OLLAMA_BASE_URL}/api/chat")
    api_key: str = os.getenv("AI_API_KEY", "")
    timeout: float = AI_TIMEOUT


config = AIConfig()
