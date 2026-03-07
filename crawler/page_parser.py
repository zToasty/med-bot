import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

USER_AGENT = "Mozilla/5.0"

PRICE_SECTION_KEYWORDS = {"общая информация", "цены", "прайс", "стоимость"}


def _get_text(elem, separator=" "):
    """Единый хелпер для извлечения текста из элемента."""
    return elem.get_text(separator=separator, strip=True)


def _parse_faq(soup):
    """Извлекает FAQ со страницы."""
    faq = []
    faq_section = soup.find("div", id="section-faq")

    if not faq_section:
        return faq

    for item in faq_section.find_all("div", class_=lambda c: c and "loop-post" in c):
        q_elem = item.find("div", class_="collapse-title")
        a_elem = item.find("div", class_="collapse-content")

        if q_elem and a_elem:
            faq.append({
                "question": _get_text(q_elem),
                "answer": _get_text(a_elem)
            })

    return faq


def _parse_structured_info(soup):
    """Извлекает структурированный текстовый контент со страницы."""
    tab_contents = soup.find_all("div", class_=lambda c: c and "tab-content" in c)

    if not tab_contents:
        fallback = soup.find("div", class_="the_content") or soup.find("div", class_="entry-content")
        if fallback:
            tab_contents = [fallback]

    info_dict = {}

    for tab in tab_contents:

        for junk in tab.find_all(["script", "style"]):
            junk.decompose()

        tab_title_elem = tab.find("span", class_="title")
        current_heading = _get_text(tab_title_elem) if tab_title_elem else "Общая информация"

        if current_heading not in info_dict:
            info_dict[current_heading] = []

        for element in tab.find_all(["h2", "h3", "p", "ul", "ol"]):

            text = _get_text(element)

            if not text:
                continue

            if element.name in ["h2", "h3"]:
                current_heading = text
                if current_heading not in info_dict:
                    info_dict[current_heading] = []

            elif element.name == "p":
                if len(text) > 10 and text not in info_dict[current_heading]:
                    info_dict[current_heading].append(text)

            elif element.name in ["ul", "ol"]:
                for li in element.find_all("li"):
                    li_text = _get_text(li)
                    if len(li_text) > 5:
                        item = f"- {li_text}"
                        if item not in info_dict[current_heading]:
                            info_dict[current_heading].append(item)

    # Фильтрация: убираем прайс-секции и глобальные дубликаты
    seen_globally = set()
    structured_info = {}

    for heading in list(info_dict.keys()):

        if any(kw in heading.lower() for kw in PRICE_SECTION_KEYWORDS):
            continue

        unique_texts = [t for t in info_dict[heading] if t not in seen_globally]
        seen_globally.update(unique_texts)

        if unique_texts:
            structured_info[heading] = "\n".join(unique_texts)

    return structured_info


def _parse_reviews(soup):
    """Извлекает отзывы со страницы."""
    reviews = []
    reviews_section = soup.find("div", class_="list-posts list-reviews")

    if not reviews_section:
        return reviews

    for review in reviews_section.find_all("div", class_="loop-review"):

        title_elem = review.find("div", class_="item-title")
        author_elem = review.find("div", class_="item-author")
        text_elem = review.find("div", class_="item-description")

        text = _get_text(text_elem) if text_elem else ""

        if len(text) > 10:
            reviews.append({
                "service": _get_text(title_elem) if title_elem else "",
                "author": _get_text(author_elem) if author_elem else "Аноним",
                "text": text
            })

    return reviews


def _parse_evidence(soup):
    """Извлекает фото-кейсы (до/после) со страницы."""
    evidence = []

    for gallery in soup.find_all("div", class_="gallery"):

        patient_meta = gallery.find("div", class_="item-meta")
        patient_name = (
            _get_text(patient_meta).replace("Пациент:", "").strip()
            if patient_meta
            else "Пример работы"
        )

        unique_images = {
            slide.get("data-url")
            for slide in gallery.find_all("li", class_="slide")
            if slide.get("data-url")
        }

        if unique_images:
            evidence.append({
                "patient_case": patient_name,
                "images": list(unique_images)
            })

    return evidence


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


def parse_page(url):
    """Парсит страницу услуги (без цен)."""

    print(f"⏳ Парсим страницу: {url}")

    try:
        response = _fetch(url)
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка загрузки {url}: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    h1_tag = soup.find("h1")
    category_name = _get_text(h1_tag) if h1_tag else url.strip("/").split("/")[-1]

    page_data = {
        "url": url,
        "category_name": category_name,
        "faq": _parse_faq(soup),
        "reviews": _parse_reviews(soup),
        "structured_info": _parse_structured_info(soup),
        "evidence": _parse_evidence(soup)
    }

    print(
        f"✅ {category_name}: FAQ({len(page_data['faq'])}), "
        f"Отзывы({len(page_data['reviews'])}), "
        f"Фото({len(page_data['evidence'])})"
    )

    return page_data