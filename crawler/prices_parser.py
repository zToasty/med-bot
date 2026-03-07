import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

USER_AGENT = "Mozilla/5.0"


def _get_text(elem, separator=" "):
    """Единый хелпер для извлечения текста из элемента."""
    return elem.get_text(separator=separator, strip=True)


@retry(
    retry=retry_if_exception_type(requests.exceptions.RequestException),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True
)
def _fetch(url):
    """Загружает страницу с retry при сетевых ошибках."""
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
    response.raise_for_status()
    return response


def parse_prices_page(url):
    """Парсит страницу со всеми ценами и возвращает структуру цен."""

    print(f"💰 Парсим цены: {url}")

    try:
        response = _fetch(url)
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка загрузки: {e}")
        return {}

    soup = BeautifulSoup(response.text, "html.parser")

    prices_data = {}

    for cat in soup.find_all("div", class_=lambda c: c and "loop-pricelist" in c):

        title_elem = cat.find("div", class_="item-title")
        if not title_elem:
            continue

        category = _get_text(title_elem)

        services = [
            {
                "service": _get_text(offer.find("span", class_="offer-title")),
                "price": " ".join(_get_text(offer.find("span", class_="offer-value")).split())
            }
            for offer in cat.find_all("li")
            if offer.find("span", class_="offer-title") and offer.find("span", class_="offer-value")
        ]

        if services:
            prices_data[category] = services

    print(f"✅ Найдено {len(prices_data)} категорий цен")

    return prices_data