from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from handlers.messages import history

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id if message.from_user is not None else 0

    # Очищаем историю общения при команде /start
    if user_id in history:
        history[user_id].clear()

    await message.answer(
        "Привет! 👋\n\n"
        "Я бот, который может просто поболтать или помочь с медицинскими услугами (но без диагнозов!).\n"
        "Пиши что угодно 😄"
    )