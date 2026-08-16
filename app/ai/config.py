from dataclasses import dataclass
import os
from pathlib import Path

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
    model: str = os.getenv("AI_MODEL", "qwen3:4b")
    api_url: str = os.getenv("AI_API_URL", "http://localhost:11434/api/chat")
    api_key: str = os.getenv("AI_API_KEY", "")
    timeout: int = int(os.getenv("AI_TIMEOUT", "30"))


config = AIConfig()
