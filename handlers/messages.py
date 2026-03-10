import asyncio
import logging
from collections import defaultdict
from typing import Dict

from aiogram import Router, types, Bot
from aiogram.types import InputMediaPhoto
from aiogram.utils.chat_action import ChatActionSender

from services.llm_service import generate_reply, fallback_response
from services.history_service import load_history, append_message
from config import ADMIN_CHAT_ID


logger = logging.getLogger(__name__)

router = Router(name="messages")

# Флаг «сейчас генерируем» — в памяти достаточно
is_generating: Dict[int, bool] = {}

# Показанные кейсы evidence — не критично терять при перезапуске
shown_evidence: Dict[int, list[str]] = defaultdict(list)


async def _send_evidence_photos(
    message: types.Message,
    cases: list[dict],
) -> list[str]:
    """Callback для отправки фото из tool executor."""
    shown = []
    for case in cases:
        media = [InputMediaPhoto(media=url) for url in case["images"]]
        media[0].caption = f"📸 {case['patient_case']}"
        try:
            await message.answer_media_group(media=media)
            shown.append(case["patient_case"])
        except Exception as e:
            logger.error(f"Ошибка отправки фото для '{case['patient_case']}': {e}")
    return shown


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

    is_generating[user_id] = True

    try:
        # Сохраняем сообщение пользователя в БД
        append_message(user_id, "user", user_text)

        # Загружаем историю из БД (уже обрезанную)
        messages_history = load_history(user_id)

        async def send_photos_fn(cases: list[dict]) -> list[str]:
            return await _send_evidence_photos(message, cases)

        async def notify_fn(text: str) -> None:
            if ADMIN_CHAT_ID:
                await bot.send_message(ADMIN_CHAT_ID, text)

        async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id, interval=4.0):
            bot_reply = await generate_reply(
                messages_history=messages_history,
                send_photos_fn=send_photos_fn,
                shown_evidence=shown_evidence[user_id],
                user_id=user_id,
                notify_fn=notify_fn,
            )

        # Сохраняем ответ бота в БД
        append_message(user_id, "assistant", bot_reply)

        if len(bot_reply) > 4000:
            for chunk in [bot_reply[i:i+4000] for i in range(0, len(bot_reply), 4000)]:
                await message.answer(chunk, parse_mode="Markdown")
                await asyncio.sleep(0.2)
        else:
            await message.answer(bot_reply, parse_mode="Markdown")

    except Exception:
        logger.exception(f"Непредвиденная ошибка при обработке сообщения от {user_id}")
        await message.answer(fallback_response())

    finally:
        is_generating[user_id] = False