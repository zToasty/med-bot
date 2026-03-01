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

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:8b-instruct-q8_0")
if not OLLAMA_MODEL:
    raise ValueError("OLLAMA_MODEL is empty! Check .env")

print(f"Loaded OLLAMA_MODEL: {OLLAMA_MODEL}")