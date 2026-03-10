"""
Определения инструментов (tools) и executor для OpenAI Tool Calling.
"""

import asyncio
import logging
from typing import Callable, Awaitable

from .rag_service import search_context
from .evidence_service import find_evidence
from .sheets_service import get_available_slots, book_appointment

logger = logging.getLogger(__name__)

# Тип для callback-функции отправки фото
SendPhotosFn = Callable[[list[dict]], Awaitable[list[str]]]

# ============================================================
# TOOL DEFINITIONS
# ============================================================
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": (
                "Поиск по базе знаний клиники. Используй для медицинских вопросов, "
                "информации о процедурах, реабилитации, противопоказаниях и отзывах."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос на русском языке",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_evidence",
            "description": (
                "Поиск фотографий до/после операций. Используй когда пользователь "
                "просит показать примеры работ, результаты или фото до/после."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": (
                            "Категория операции, например: блефаропластика, "
                            "СМАС подтяжка лица, ринопластика, маммопластика"
                        ),
                    }
                },
                "required": ["category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_slots",
            "description": "Получить список свободных слотов для записи на консультацию",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Записать пациента на консультацию в выбранный слот",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Имя пациента"},
                    "phone": {"type": "string", "description": "Номер телефона"},
                    "service": {"type": "string", "description": "Услуга"},
                    "slot": {"type": "string", "description": "Слот, например '2026-03-10 14:00'"},
                },
                "required": ["name", "phone", "service", "slot"],
            },
        },
    },
]


NotifyFn = Callable[[str], Awaitable[None]]

# ============================================================
# TOOL EXECUTOR
# ============================================================
async def execute_tool(
    tool_name: str,
    tool_args: dict,
    send_photos_fn: SendPhotosFn | None,
    shown_evidence: list[str],
    user_id: int = 0,
    notify_fn: NotifyFn | None = None,
) -> str:
    """Выполняет tool call и возвращает результат как строку."""

    if tool_name == "search_knowledge_base":
        query = tool_args.get("query", "")
        result = search_context(query, n_results=5)
        if result:
            return result
        return "По этому запросу ничего не найдено в базе знаний."

    if tool_name == "search_evidence":
        category = tool_args.get("category", "")
        cases = find_evidence(category, exclude_cases=shown_evidence)

        if not cases:
            return "Фото по этой категории не найдены."

        # Отправляем фото в чат через callback
        if send_photos_fn:
            newly_shown = await send_photos_fn(cases)
            shown_evidence.extend(newly_shown)

        descriptions = []
        for case in cases:
            descriptions.append(
                f"- {case['patient_case']} ({len(case['images'])} фото)"
            )
        return "Отправлены фото следующих случаев:\n" + "\n".join(descriptions)
    
    if tool_name == "get_available_slots":
        slots = await asyncio.to_thread(get_available_slots)
        if slots:
            return "Свободные слоты:\n" + "\n".join(slots)
        return "Свободных слотов нет, предложи связаться по телефону."

    if tool_name == "book_appointment":
        slot = tool_args.get("slot", "")
        phone = tool_args.get("phone", "")

        # Валидация номера телефона
        from .validation import validate_phone
        if not validate_phone(phone):
            logger.warning(f"⚠️ Некорректный номер телефона от LLM: {phone}")
            return (
                f"Некорректный формат телефона: '{phone}'. "
                "Пожалуйста, попроси пользователя ввести номер корректно (10-11 цифр)."
            )

        # Очистка номера перед сохранением (если валиден)
        import re
        clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
        if len(clean_phone) == 10:
            clean_phone = '7' + clean_phone
        elif clean_phone.startswith('8'):
            clean_phone = '7' + clean_phone[1:]
        elif clean_phone.startswith('+'):
            clean_phone = clean_phone[1:]

        # Превентивная проверка: слот должен быть в списке свободных
        available = await asyncio.to_thread(get_available_slots)
        if slot not in available:
            logger.warning(f"⚠️ Попытка записи в недоступный слот: {slot}")
            if available:
                return (
                    f"Слот '{slot}' недоступен для записи. "
                    f"Свободные слоты:\n" + "\n".join(available)
                )
            return (
                f"Слот '{slot}' недоступен, и свободных слотов сейчас нет. "
                "Предложи связаться по телефону."
            )

        result = await asyncio.to_thread(
            book_appointment,
            name=tool_args["name"],
            phone=clean_phone,
            service=tool_args["service"],
            slot=slot,
            user_id=user_id,
        )

        if result["ok"]:
            if notify_fn:
                await notify_fn(
                    f"📅 Новая запись!\n"
                    f"Имя: {tool_args['name']}\n"
                    f"Телефон: {tool_args['phone']}\n"
                    f"Услуга: {tool_args['service']}\n"
                    f"Слот: {slot}"
                )
            return f"Запись подтверждена: {tool_args['name']} на {slot}"

        # Обработка ошибок
        error = result.get("error", "unknown")
        if error == "slot_not_found":
            return f"Слот '{slot}' не найден в расписании. Покажи актуальные свободные слоты."
        if error == "slot_taken":
            return f"Слот '{slot}' уже занят. Покажи актуальные свободные слоты."
        return "Не удалось записать из-за технической ошибки. Предложи связаться по телефону."

    return f"Неизвестный инструмент: {tool_name}"
