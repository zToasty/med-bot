import requests
from bs4 import BeautifulSoup


def parse_service_links(url):
    """
    Парсит страницу категории и возвращает список ссылок на услуги
    """

    print(f"🔎 Собираем ссылки: {url}")

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Ошибка загрузки {url}: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    links = set()

    products = soup.find_all("h3", class_="product-title")

    for product in products:

        a = product.find("a")

        if not a:
            continue

        href = a.get("href")

        if href:
            links.add(href.strip())

    links = list(links)

    print(f"✅ Найдено ссылок: {len(links)}")

    return links