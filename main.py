import asyncio
import logging
import signal
import sqlite3

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from handlers import start_router, messages_router, stats_router

from services.rag_service import load_knowledge_base
from services.evidence_service import load_evidence
from services.history_service import init_db

from datetime import datetime
from config import BASE_DIR, BOT_TOKEN, DB_PATH


# Оставляем глобальное соединение, чтобы иметь возможность корректно его закрывать (db.close())
db = sqlite3.connect(DB_PATH, check_same_thread=False)


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


async def shutdown(bot: Bot):
    """Корректное завершение работы (graceful shutdown)."""
    logging.info("Выполняется graceful shutdown...")
    
    # Закрываем соединение с клиентом/сессией бота
    await bot.session.close()

    # Закрытие соединения с SQLite
    if db:
        db.close()
        logging.info("Соединение с базой данных (SQLite) закрыто.")

    # Закрытие логгера
    logging.info("Завершение системы логирования.")
    logging.shutdown()


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

    # Ивенты жизненного цикла
    stop_event = asyncio.Event()

    def signal_handler():
        logging.info("Получен сигнал завершения (SIGINT/SIGTERM)...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    logging.info("Бот запускается...")

    # Запускаем polling в фоне (отключаем встроенную обработку сигналов aiogram, чтобы управлять самостоятельно)
    polling_task = asyncio.create_task(
        dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), handle_signals=False)
    )

    # Ждем сигнала от ОС
    await stop_event.wait()

    logging.info("Завершение работы (остановка polling_task)...")
    await dp.stop_polling()
    
    try:
        await polling_task
    except Exception as e:
        logging.error(f"Ошибка при ожидании завершения polling: {e}")

    # Вызываем shutdown
    await shutdown(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Резервный перехват на случай, если event loop прерван до установки обработчиков
        pass
