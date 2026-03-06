import requests
from bs4 import BeautifulSoup
import json
import os
import time
import random

def parse_prices_page(url):
    """Парсит страницу со всеми ценами и возвращает структуру цен."""
    
    print(f"💰 Парсим цены: {url}")

    headers = {
        'User-Agent': 'Mozilla/5.0'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        return {}

    soup = BeautifulSoup(response.text, "html.parser")

    prices_data = {}

    categories = soup.find_all('div', class_=lambda c: c and 'loop-pricelist' in c)

    for cat in categories:

        title_elem = cat.find('div', class_='item-title')
        if not title_elem:
            continue

        category = title_elem.get_text(strip=True)

        services = []

        for offer in cat.find_all('li'):

            service_elem = offer.find('span', class_='offer-title')
            price_elem = offer.find('span', class_='offer-value')

            if not service_elem or not price_elem:
                continue

            services.append({
                "service": service_elem.get_text(strip=True),
                "price": " ".join(price_elem.get_text(strip=True).split())
            })

        if services:
            prices_data[category] = services

    print(f"✅ Найдено {len(prices_data)} категорий цен")

    return prices_data

def save_prices(prices, filename="prices.json"):

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)

    print(f"💾 Цены сохранены: {filename}")