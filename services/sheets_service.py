import gspread
import logging

from config import GOOGLE_SHEET_ID


logger = logging.getLogger(__name__)

gc = gspread.service_account(filename="creds.json")
sheet = gc.open_by_key(GOOGLE_SHEET_ID).sheet1


def get_available_slots() -> list[str]:
    """Возвращает список свободных слотов."""
    records = sheet.get_all_records()
    return [str(r["slot"]) for r in records if r["status"] == "свободно"]


def book_appointment(
    name: str, phone: str, service: str, slot: str, user_id: int
) -> dict:
    """
    Записывает пациента на консультацию.
    Возвращает dict: {"ok": True/False, "error": "описание ошибки"}
    """
    try:
        # 1. Проверяем существование слота в таблице
        cell = sheet.find(slot)
        if not cell:
            logger.warning(f"⚠️ Слот не найден в таблице: {slot}")
            return {"ok": False, "error": "slot_not_found"}

        row = cell.row

        # 2. Проверяем что слот свободен (столбец 5 = статус)
        status = sheet.cell(row, 5).value
        if status and status.strip().lower() != "свободно":
            logger.warning(f"⚠️ Попытка записи в занятый слот: {slot} (статус: {status})")
            return {"ok": False, "error": "slot_taken"}

        # 3. Записываем
        sheet.update_cell(row, 2, name)
        sheet.update_cell(row, 3, phone)
        sheet.update_cell(row, 4, service)
        sheet.update_cell(row, 5, "занято")
        sheet.update_cell(row, 6, user_id)

        return {"ok": True, "error": None}

    except Exception as e:
        logger.error(f"Ошибка записи: {e}")
        return {"ok": False, "error": "internal_error"}
