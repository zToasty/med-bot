import logging
import json
from typing import TypedDict, List, Dict, cast
from pathlib import Path

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam 
from pydantic import BaseModel, Field

from config import OPENAI_API_KEY, OPENAI_MODEL
from services.rag_service import search_context
from services.token_tracker import tracker



logger = logging.getLogger(__name__)
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# --- ЗАГРУЖАЕМ ЦЕНЫ И КОНТАКТЫ В ПАМЯТЬ РАЗ И НАВСЕГДА ---
PROJECT_ROOT = Path(__file__).resolve().parent
with open(PROJECT_ROOT / "data" / "prices.json", "r", encoding="utf-8") as f:
    PRICES_DATA = json.load(f)
with open(PROJECT_ROOT / "data" / "contacts.json", "r", encoding="utf-8") as f:
    CONTACTS_DATA = json.load(f)

# Форматируем прайс-лист в компактную строку для GPT
formatted_prices = ""
for cat, services in PRICES_DATA.items():
    formatted_prices += f"\nКатегория {cat}:\n"
    for s in services:
        formatted_prices += f"- {s['service']}: {s['price']}\n"

class BotResponse(BaseModel):
    is_medical: bool = Field(..., description="True если тема медицинская/услуги")
    response: str = Field(..., description="Текст ответа Елены")

class LLMResponse(TypedDict):
    is_medical: bool
    response: str

_RAG_TRIGGER_KEYWORDS = {
    "как", "почему", "зачем", "что такое", "расскажи", "объясни",
    "операция", "процедура", "реабилитация", "восстановление", "лечение",
    "противопоказания", "побочные", "эффект", "помогает", "болит", "боль",
}

# Системный промпт с ЖЕСТКИМИ знаниями
SYSTEM_PROMPT = f"""\
Ты — Елена, 35 лет, экспертный менеджер клиники доктора Ольги Ованесовой.
Стиль: теплый, заботливый, разговорный. Используй эмодзи 🌸, ✨.

ТВОИ ЗНАНИЯ О ЦЕНАХ (ИСПОЛЬЗУЙ ИХ ВСЕГДА):
{formatted_prices}

ТВОИ КОНТАКТЫ:
{json.dumps(CONTACTS_DATA, ensure_ascii=False)}

ПРАВИЛА:
1. Если спрашивают цену — бери её из списка выше. Если услуги нет в списке — предлагай консультацию.
2. Если спрашивают про медицину/реабилитацию — используй блок "ДОПОЛНИТЕЛЬНЫЙ КОНТЕКСТ" если он есть.
3. Телефон для записи: +7 (916) 555-76-66.
"""

def _needs_rag(text: str) -> bool:
    """Определяет, нужен ли RAG для этого вопроса.
    RAG нужен только для сложных медицинских/информационных вопросов,
    но НЕ для вопросов о ценах — они уже вшиты в системный промпт.
    """
    text_lower = text.lower()
    # Не используем RAG для ценовых запросов — они уже в промпте
    price_keywords = {"цена", "стоит", "стоимость", "прайс", "сколько", "руб"}
    if any(w in text_lower for w in price_keywords):
        return False
    # Используем RAG для медицинских/информационных вопросов
    return any(w in text_lower for w in _RAG_TRIGGER_KEYWORDS)

async def generate_reply(messages_history: List[Dict[str, str]]) -> LLMResponse:
    try:
        last_user_msg = next(
            (m["content"] for m in reversed(messages_history) if m["role"] == "user"),
            ""
        )

        # ✅ RAG только для сложных вопросов, не для цен
        final_system_msg = SYSTEM_PROMPT
        if last_user_msg and _needs_rag(last_user_msg):
            found_context = search_context(last_user_msg, n_results=3)
            if found_context:  # ✅ Добавляем блок только если RAG что-то нашёл
                final_system_msg += f"\n\n=== ДОПОЛНИТЕЛЬНЫЙ КОНТЕКСТ ДЛЯ СПРАВКИ ===\n{found_context}"

        openai_messages = [{"role": "system", "content": final_system_msg}]
        for msg in messages_history:
            if msg["role"] != "system":
                openai_messages.append(msg)

        completion = await client.beta.chat.completions.parse(
            model=OPENAI_MODEL,
            messages=cast(List[ChatCompletionMessageParam], openai_messages),
            response_format=BotResponse,
            temperature=0.2,  # Минимум фантазии!
        )

        parsed_data = completion.choices[0].message.parsed
        usage = completion.usage
        if usage:
            tracker.add_chat(
                model=OPENAI_MODEL,
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
            )
            
        return {"is_medical": parsed_data.is_medical, "response": parsed_data.response}

    except Exception as e:
        logger.exception("Ошибка в LLM")
        return {
            "is_medical": False,
            "response": "Ой, я немного запуталась 🙈 Спросите еще раз, пожалуйста!"
        }

def fallback_response() -> LLMResponse:
    return {
        "is_medical": False,
        "response": "Ой, что-то я запуталась в бумагах 😅 Повторите, пожалуйста, ваш вопрос!"
    }