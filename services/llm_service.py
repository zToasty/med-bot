import logging
import json
from typing import List, Dict, Callable, Awaitable
from pathlib import Path

from openai import AsyncOpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL
from .token_tracker import tracker
from .tools import TOOLS, execute_tool, SendPhotosFn


logger = logging.getLogger(__name__)
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# --- ЗАГРУЖАЕМ ЦЕНЫ И КОНТАКТЫ В ПАМЯТЬ РАЗ И НАВСЕГДА ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
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

# ============================================================
# SYSTEM PROMPT
# ============================================================
SYSTEM_PROMPT = f"""\
Ты — Елена, 35 лет, экспертный менеджер клиники доктора Ольги Ованесовой.
Стиль: теплый, заботливый, разговорный. Используй эмодзи 🌸, ✨.

ТВОИ ЗНАНИЯ О ЦЕНАХ (ИСПОЛЬЗУЙ ИХ ВСЕГДА):
{formatted_prices}

ТВОИ КОНТАКТЫ:
{json.dumps(CONTACTS_DATA, ensure_ascii=False)}

ПРАВИЛА:
1. Если спрашивают цену — бери её из списка выше. Если услуги нет в списке — предлагай консультацию.
2. Для медицинских/информационных вопросов, отзывов или реабилитации — \
ОБЯЗАТЕЛЬНО используй инструмент search_knowledge_base чтобы найти точную информацию.
3. Телефон для записи: +7 (916) 555-76-66.
4. Если просят фото до/после, примеры работ или результаты операций — \
используй инструмент search_evidence чтобы найти и отправить фото.
5. Если спрашивают отзывы — ищи их через search_knowledge_base. \
Никогда не выдумывай отзывы. Если ничего не нашлось — скажи что уточнишь и предложи консультацию.
6. Не вызывай инструменты для простых приветствий, благодарностей или вопросов о ценах — \
эта информация у тебя уже есть.
7. Если пользователь хочет записаться — сначала вызови get_available_slots чтобы показать свободные слоты, потом попроси имя, телефон и услугу.
8. Когда у тебя есть имя, телефон, услуга и выбранный слот — вызови book_appointment для подтверждения записи.

СТРОЖАЙШЕ ЗАПРЕЩЕНО:
- Предлагать, намекать или соглашаться на любые скидки, акции, промокоды, бонусы, специальные предложения.
- Менять, округлять, занижать или завышать цены из прайса выше.
- Называй ТОЛЬКО точные цены из списка. Если клиент просит скидку — вежливо откажи и предложи записаться на консультацию для обсуждения деталей.
- Записывать пациента в слот, который НЕ был возвращён инструментом get_available_slots. ВСЕГДА сначала проверяй свободные слоты.
"""


# ============================================================
# GENERATE REPLY (TOOL CALLING LOOP)
# ============================================================
MAX_TOOL_ROUNDS = 5


async def generate_reply(
    messages_history: List[Dict[str, str]],
    send_photos_fn: SendPhotosFn | None = None,
    shown_evidence: list[str] | None = None,
    user_id: int = 0,
    notify_fn: Callable[[str], Awaitable[None]] | None = None,
) -> str:
    """
    Генерирует ответ с поддержкой tool calling.
    Возвращает финальный текстовый ответ (str).
    """
    if shown_evidence is None:
        shown_evidence = []

    try:
        # Собираем messages для OpenAI
        openai_messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        for msg in messages_history:
            if msg["role"] != "system":
                openai_messages.append(msg)

        # Tool calling loop
        for _ in range(MAX_TOOL_ROUNDS):
            completion = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=openai_messages,
                tools=TOOLS,
                temperature=0.2,
            )

            choice = completion.choices[0]

            # Трекинг токенов
            usage = completion.usage
            if usage:
                tracker.add_chat(
                    model=OPENAI_MODEL,
                    input_tokens=usage.prompt_tokens,
                    output_tokens=usage.completion_tokens,
                )

            # Если нет tool_calls — финальный ответ
            if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
                return choice.message.content or fallback_response()

            # Добавляем assistant message с tool_calls
            openai_messages.append(choice.message.model_dump())

            # Выполняем каждый tool call
            for tool_call in choice.message.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)

                logger.info(f"🔧 Tool call: {fn_name}({fn_args})")

                result = await execute_tool(
                    fn_name, fn_args, send_photos_fn, shown_evidence, user_id, notify_fn
                )

                openai_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

        # Если вышли по лимиту раундов
        logger.warning("⚠️ Достигнут лимит раундов tool calling")
        return fallback_response()

    except Exception:
        logger.exception("Ошибка в LLM")
        return fallback_response()


def fallback_response() -> str:
    return "Ой, я немного запуталась 🙈 Спросите еще раз, пожалуйста!"