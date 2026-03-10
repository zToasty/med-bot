from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from services.history_service import clear_history

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id if message.from_user is not None else 0

    # Очищаем историю общения при команде /start
    clear_history(user_id)

    await message.answer(
        "Привет! 👋\n\n"
        "Я бот, который может просто поболтать или помочь с медицинскими услугами (но без диагнозов!).\n"
        "Пиши что угодно 😄"
    )