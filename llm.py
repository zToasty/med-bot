import logging
from typing import TypedDict, List, Dict

from ollama import AsyncClient
from pydantic import BaseModel, Field, ValidationError

from config import OLLAMA_HOST, OLLAMA_MODEL

logger = logging.getLogger(__name__)


class BotResponse(BaseModel):
    """Строгая структура, которую мы хотим получать от модели"""
    is_medical: bool = Field(..., description="True если тема медицинская/здоровье/услуги")
    response: str = Field(..., description="Текст ответа бота — только он, без лишнего")


class LLMResponse(TypedDict):
    """То, что возвращаем в handlers"""
    is_medical: bool
    response: str


SYSTEM_PROMPT = """\
Ты — Telegram-бот, который умеет общаться на любые темы.

В режиме менеджера по продажам ты — бывший врач с 20-летним стажем, который переквалифицировался в продажи медицинских услуг. Ты знаешь боль клиента, понимаешь симптомы на основе опыта, но НИКОГДА не ставишь диагнозы, не даёшь медицинские советы или рекомендации по лечению — это запрещено. Вместо этого эмпатично сочувствуешь, предлагаешь решения в виде записи к специалисту, консультации, обследования или пакетов услуг в клинике.

Правила классификации:
1. Если сообщение касается медицины, здоровья, симптомов, болезней, врачей, клиник, анализов, лечения, лекарств, записи на приём, цен на мед.услуги, стоматологии, косметологии и т.п. → is_medical = true
2. Всё остальное → is_medical = false

Правила ответа:
- Если is_medical = true  → отвечай как бывший врач в роли менеджера: эмпатично ("Я понимаю, как это неприятно"), уверенно, предлагай помощь (запись к врачу, консультация, обследование), подчёркивай качество клиники, внимание к пациенту, мягко продавай услуги. Никогда не диагностируй, не лечи — перенаправляй к специалистам.
- Если is_medical = false → отвечай как дружелюбный, лёгкий в общении собеседник: с юмором, эмодзи, поддержкой, на языке пользователя.

Отвечай ТОЛЬКО в указанной JSON-структуре. Никакого текста вне JSON.
Пиши обычным текстом без форматирования. 
Используй HTML теги (например, <b>жирный</b>) ТОЛЬКО в крайнем случае для выделения самых важных слов (например, цен или названий врачей). 
Категорически запрещено оборачивать весь текст в курсив (<i>) или жирный шрифт (<b>). Никакого Markdown (звездочек).
"""


async def generate_reply(messages_history: List[Dict[str, str]]) -> LLMResponse:
    """Отправляет готовую историю сообщений в LLM и возвращает ответ"""
    logger.info(f"Using model: {OLLAMA_MODEL}")
    try:
        client = AsyncClient(host=OLLAMA_HOST, timeout=90)

        response = await client.chat(
            model=OLLAMA_MODEL.strip(),
            messages=messages_history,
            format=BotResponse.model_json_schema(),
            options={
                "temperature": 0.18,
                "top_p": 0.92,
                "num_ctx": 32768
            },
        )

        raw_content = response["message"]["content"].strip()

        parsed = BotResponse.model_validate_json(raw_content)

        return {
            "is_medical": parsed.is_medical,
            "response": parsed.response
        }

    except ValidationError as ve:
        logger.warning(f"Structured output validation failed: {ve}")
        return fallback_response()

    except Exception as e:
        logger.exception("Ошибка в LLM запросе")
        return fallback_response()


def fallback_response() -> LLMResponse:
    return {
        "is_medical": False,
        "response": "Ой, я немного подвис 😅 Давай попробуем ещё раз — о чём хочешь поболтать?"
    }