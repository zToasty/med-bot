from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from services.token_tracker import tracker

router = Router(name="stats")


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    """Показывает статистику токенов и стоимости. Только для администраторов."""
    await message.answer(tracker.summary(), parse_mode="HTML")


@router.message(Command("stats_reset"))
async def cmd_stats_reset(message: Message) -> None:
    """Сбрасывает счётчики токенов."""
    tracker.reset()
    await message.answer("✅ Счётчики токенов сброшены.")