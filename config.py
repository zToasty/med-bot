from pathlib import Path
from dotenv import load_dotenv
from typing import cast

import os


env_path = Path(__file__).parent / ".env"

load_dotenv(dotenv_path=env_path, override=True)

BASE_DIR = Path(__file__).parent

BOT_TOKEN = cast(str, os.getenv("BOT_TOKEN"))
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in .env")

OPENAI_API_KEY = cast(str, os.getenv("OPENAI_API_KEY"))
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is missing! Check .env")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

print(f"[DEBUG] Loaded OpenAI Model: {OPENAI_MODEL}")