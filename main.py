import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage


from handlers import start_router, messages_router, stats_router

from services.rag_service import load_knowledge_base
from services.evidence_service import load_evidence
from services.history_service import init_db


from datetime import datetime
from config import BASE_DIR, BOT_TOKEN


def setup_logging():
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = log_dir / f"bot_{timestamp}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)7s | %(name)-20s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    logging.info(f"Логирование настроено. Файл логов: {log_file}")


async def main():
    setup_logging()

    load_knowledge_base()
    load_evidence()
    init_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start_router)
    dp.include_router(stats_router)
    dp.include_router(messages_router)

    logging.info("Бот запускается...")

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
