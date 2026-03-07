import asyncio
import logging
from collections import defaultdict
from typing import List, Dict

from aiogram import Router, types, Bot
from aiogram.types import InputMediaPhoto
from aiogram.utils.chat_action import ChatActionSender

from llm import (
    generate_reply,          
    fallback_response,
    SYSTEM_PROMPT,                 
)
from services.evidence_service import find_evidence


logger = logging.getLogger(__name__)

router = Router(name="messages")

# Хранилище истории диалогов
history: Dict[int, List[Dict[str, str]]] = defaultdict(list)

is_generating: Dict[int, bool] = {}

MAX_HISTORY_MESSAGES = 40
MAX_APPROX_TOKENS = 30000


def trim_history(user_history: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Обрезает историю, если она слишком длинная"""
    if len(user_history) > MAX_HISTORY_MESSAGES:
        user_history = user_history[-MAX_HISTORY_MESSAGES:]

    
    total_chars = sum(len(msg["content"]) for msg in user_history)
    if total_chars > MAX_APPROX_TOKENS * 4:
        while total_chars > MAX_APPROX_TOKENS * 4 and len(user_history) > 2:
            removed = user_history.pop(0)
            total_chars -= len(removed["content"])

    return user_history

async def send_evidence(message: types.Message, category: str, user_text: str) -> bool:
    """
    Ищет фото до/после и отправляет альбомами.
    Возвращает True если фото нашлись и были отправлены.
    """
    cases = find_evidence(category or user_text)
    if not cases:
        return False

    for case in cases:
        media = [InputMediaPhoto(media=url) for url in case["images"]]
        media[0].caption = f"📸 {case['patient_case']}"
        try:
            await message.answer_media_group(media=media)
        except Exception as e:
            logger.error(f"Ошибка отправки фото для '{case['patient_case']}': {e}")

    return True


@router.message()
async def handle_message(message: types.Message, bot: Bot):
    user_id = message.from_user.id if message.from_user is not None else 0
    user_text = (message.text or "").strip()

    if not user_text:
        await message.reply("Пока понимаю только текст 😅")
        return

    if is_generating.get(user_id, False):
        await message.reply("Подожди, я еще дописываю предыдущий ответ... ✍️")
        return

    # начали генерировать ответ
    is_generating[user_id] = True

    try:
        history[user_id].append({"role": "user", "content": user_text})
        history[user_id] = trim_history(history[user_id])

        messages_for_llm =[
            {"role": "system", "content": SYSTEM_PROMPT},
            *history[user_id],
        ]

        async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
            llm_result = await generate_reply(messages_for_llm)

        bot_reply = llm_result["response"]
        history[user_id].append({"role": "assistant", "content": bot_reply})

        # Отправляем текстовый ответ
        if len(bot_reply) > 4000:
            for chunk in [bot_reply[i:i+4000] for i in range(0, len(bot_reply), 4000)]:
                await message.answer(chunk, parse_mode="Markdown")
                await asyncio.sleep(0.2)
        else:
            await message.answer(bot_reply, parse_mode="Markdown")

        # Если LLM решила что нужны фото — отправляем альбомы
        if llm_result.get("wants_evidence"):
            found = await send_evidence(
                message,
                category=llm_result.get("evidence_category", ""),
                user_text=user_text,
            )
            if not found:
                await message.answer("По этой процедуре фото пока не добавлены, но вы можете увидеть примеры работ на консультации или на сайте клиники 🌸")

    except Exception as e:
        logger.exception(f"Непредвиденная ошибка при обработке сообщения от {user_id}")
        await message.answer(fallback_response()["response"])
        
    finally:
        is_generating[user_id] = False