import json
import time
import random

from prices_parser import parse_prices_page, save_prices
from page_parser import parse_page
from link_parser import parse_service_links


# ==========================================
# СТРАНИЦА ЦЕН
# ==========================================
PRICES_PAGE_URL = "https://med-plastic.ru/pricelists/"


# ==========================================
# СТРАНИЦЫ КАТЕГОРИЙ (ГДЕ ЛЕЖАТ ССЫЛКИ)
# ==========================================
CATEGORY_PAGES = [
    "https://med-plastic.ru/category/liczo/",
    # "https://med-plastic.ru/category/grud/",
    # "https://med-plastic.ru/category/telo/"
]


def save_pages(data, filename="knowledge.json"):

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"📚 Сохранено страниц: {len(data)}")


if __name__ == "__main__":

    # ==========================================
    # 1 ПАРСИМ ЦЕНЫ
    # ==========================================
    prices = parse_prices_page(PRICES_PAGE_URL)

    if prices:
        save_prices(prices, filename='data/prices.json')

    # ==========================================
    # 2 СОБИРАЕМ ВСЕ ССЫЛКИ УСЛУГ
    # ==========================================
    all_links = set()

    for page in CATEGORY_PAGES:

        links = parse_service_links(page)

        for link in links:
            all_links.add(link)

        time.sleep(random.uniform(1, 2))

    all_links = list(all_links)

    print(f"\n📦 Всего уникальных услуг: {len(all_links)}\n")

    # ==========================================
    # 3 ПАРСИМ КАЖДУЮ СТРАНИЦУ
    # ==========================================
    all_pages = []

    for url in all_links:

        data = parse_page(url)

        if data:
            all_pages.append(data)

        sleep_time = random.uniform(1.5, 3)

        print(f"😴 sleep {sleep_time:.2f}s\n")

        time.sleep(sleep_time)

    # ==========================================
    # 4 СОХРАНЯЕМ
    # ==========================================
    save_pages(all_pages, filename='data/knowledge.json')

    print("\n🎉 Парсинг завершён")