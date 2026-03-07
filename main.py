import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from handlers import start_router, messages_router, stats_router

from services.rag_service import load_knowledge_base
from services.evidence_service import load_evidence


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)7s | %(name)-20s | %(message)s",
        datefmt="%H:%M:%S",
    )

    load_knowledge_base()
    load_evidence()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start_router)
    dp.include_router(stats_router)
    dp.include_router(messages_router)
    

    logging.info("Бот запускается...")

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())