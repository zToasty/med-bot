import gspread
import logging

logger = logging.getLogger(__name__)

gc = gspread.service_account(filename="creds.json")
sheet = gc.open_by_key("1bkjK8AvrmkdVkmk6P2fLmwAypddPxYKdMWDHdb5rVF8").sheet1



def get_available_slots() -> list[str]:
    records = sheet.get_all_records()
    return [str(r["slot"]) for r in records if r["status"] == "свободно"]


def book_appointment(name: str, phone: str, service: str, slot: str, user_id: int) -> bool:
    try:
        cell = sheet.find(slot)
        if not cell:
            return False

        row = cell.row

        sheet.update_cell(row, 2, name)
        sheet.update_cell(row, 3, phone)
        sheet.update_cell(row, 4, service)
        sheet.update_cell(row, 5, "занято")
        sheet.update_cell(row, 6, user_id)

        return True

    except Exception as e:
        logger.error(f"ошибка записи: {e}")
        return False
    


