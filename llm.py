import logging
from typing import TypedDict, List, Dict, cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam 

from pydantic import BaseModel, Field

from config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

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

В режиме менеджера по продажам ты - бывший врач с 20-летним стажем, который переквалифицировался в продажи медицинских услуг. 
Ты эмпатично сочувствуешь, предлагаешь решения (запись к специалисту, обследования), но НИКОГДА не ставишь диагнозы и не лечишь.

Правила классификации:
1. Медицина, здоровье, симптомы, врачи, клиники, цены на услуги → is_medical = true
2. Всё остальное → is_medical = false

Правила ответа:
- is_medical = true: Отвечай как эксперт-менеджер. Мягко продавай услуги клиники.
- is_medical = false: Отвечай как дружелюбный собеседник с юмором.

ВАЖНО:
- Пиши обычным текстом.
- Используй HTML (<b>жирный</b>, <i>курсив</i>) ТОЛЬКО для выделения ключевых моментов (цены, названия).
- Не используй Markdown (звездочки **).
"""


async def generate_reply(messages_history: List[Dict[str, str]]) -> LLMResponse:
    """Отправляет в OpenAI и возвращает ответ"""
    try:
        openai_messages = cast(List[ChatCompletionMessageParam], messages_history)


        completion = await client.beta.chat.completions.parse(
            model=OPENAI_MODEL,
            messages=openai_messages,
            response_format=BotResponse, 
            temperature=0.3,
        )

        parsed_data = completion.choices[0].message.parsed
        
        if not parsed_data:
            logger.error("OpenAI вернул пустой parsed object")
            return fallback_response()

        return {
            "is_medical": parsed_data.is_medical,
            "response": parsed_data.response
        }

    except Exception as e:
        logger.exception("Ошибка при запросе к OpenAI API")
        return fallback_response()


def fallback_response() -> LLMResponse:
    return {
        "is_medical": False,
        "response": "Ой, я немного подвис 😅 Давай попробуем ещё раз — о чём хочешь поболтать?"
    }