import json
import time
import random
import os

from dotenv import load_dotenv
from prices_parser import parse_prices_page
from page_parser import parse_page
from link_parser import parse_service_links

load_dotenv()
# ==========================================
# КОНФИГ
# ==========================================
PRICES_PAGE_URL = os.getenv("PRICES_PAGE_URL")

CATEGORY_PAGES = [
    url.strip()
    for url in os.getenv("CATEGORY_PAGES", "").split(",")
    if url.strip()
]

DATA_DIR = "data"


# ==========================================
# УТИЛИТЫ
# ==========================================
def save_json(data, filename):
    """Сохраняет данные в JSON-файл."""
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_prices(prices, filename):
    save_json(prices, filename)
    print(f"💾 Цены сохранены: {filename}")


def save_pages(data, filename):
    save_json(data, filename)
    print(f"📚 Сохранено страниц: {len(data)}")


# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":

    # 1. ПАРСИМ ЦЕНЫ
    try:
        prices = parse_prices_page(PRICES_PAGE_URL)
        if prices:
            save_prices(prices, filename=f"{DATA_DIR}/prices.json")
    except Exception as e:
        print(f"⚠️ Не удалось спарсить цены: {e}")

    # 2. СОБИРАЕМ ВСЕ ССЫЛКИ УСЛУГ
    all_links = set()

    for page in CATEGORY_PAGES:
        try:
            links = parse_service_links(page)
            all_links |= set(links)
        except Exception as e:
            print(f"⚠️ Не удалось собрать ссылки с {page}: {e}")

        time.sleep(random.uniform(1, 2))

    print(f"\n📦 Всего уникальных услуг: {len(all_links)}\n")

    # 3. ПАРСИМ КАЖДУЮ СТРАНИЦУ
    all_pages = []

    for url in all_links:
        try:
            data = parse_page(url)
            if data:
                all_pages.append(data)
        except Exception as e:
            print(f"⚠️ Не удалось спарсить страницу {url}: {e}")

        sleep_time = random.uniform(1.5, 3)
        print(f"😴 sleep {sleep_time:.2f}s\n")
        time.sleep(sleep_time)

    # 4. СОХРАНЯЕМ
    save_pages(all_pages, filename=f"{DATA_DIR}/knowledge.json")

    print("\n🎉 Парсинг завершён")