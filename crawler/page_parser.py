import requests
from bs4 import BeautifulSoup


def parse_page(url):
    """Парсит страницу услуги (без цен)."""

    print(f"⏳ Парсим страницу: {url}")

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Ошибка загрузки {url}: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    # название страницы
    h1_tag = soup.find("h1")
    category_name = h1_tag.get_text(strip=True) if h1_tag else url.strip("/").split("/")[-1]

    page_data = {
        "url": url,
        "category_name": category_name,
        "faq": [],
        "reviews": [],
        "structured_info": {},
        "evidence": []
    }

    # ==========================================
    # FAQ
    # ==========================================
    faq_section = soup.find("div", id="section-faq")

    if faq_section:
        for item in faq_section.find_all("div", class_=lambda c: c and "loop-post" in c):

            q_elem = item.find("div", class_="collapse-title")
            a_elem = item.find("div", class_="collapse-content")

            if q_elem and a_elem:
                page_data["faq"].append({
                    "question": q_elem.get_text(strip=True),
                    "answer": a_elem.get_text(separator=" ", strip=True)
                })

    # ==========================================
    # ТЕКСТ
    # ==========================================
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
        current_heading = tab_title_elem.get_text(strip=True) if tab_title_elem else "Общая информация"

        if current_heading not in info_dict:
            info_dict[current_heading] = []

        for element in tab.find_all(["h2", "h3", "p", "ul", "ol"]):

            text = element.get_text(separator=" ", strip=True)

            if not text:
                continue

            if element.name in ["h2", "h3"]:

                current_heading = text

                if current_heading not in info_dict:
                    info_dict[current_heading] = []

            elif element.name == "p":

                if len(text) > 10:
                    info_dict[current_heading].append(text)

            elif element.name in ["ul", "ol"]:

                for li in element.find_all("li"):

                    li_text = li.get_text(separator=" ", strip=True)

                    if len(li_text) > 5:
                        info_dict[current_heading].append(f"- {li_text}")

    for heading, texts in info_dict.items():
        if texts:
            page_data["structured_info"][heading] = "\n".join(texts)

    # ==========================================
    # ОТЗЫВЫ
    # ==========================================
    reviews_section = soup.find("div", class_="list-posts list-reviews")

    if reviews_section:

        reviews = reviews_section.find_all("div", class_="loop-review")

        for review in reviews:

            title_elem = review.find("div", class_="item-title")
            author_elem = review.find("div", class_="item-author")
            text_elem = review.find("div", class_="item-description")

            title = title_elem.get_text(strip=True) if title_elem else ""
            author = author_elem.get_text(strip=True) if author_elem else "Аноним"
            text = text_elem.get_text(separator=" ", strip=True) if text_elem else ""

            if text and len(text) > 10:
                page_data["reviews"].append({
                    "service": title,
                    "author": author,
                    "text": text
                })

    # ==========================================
    # ФОТО (КЕЙСЫ)
    # ==========================================
    galleries = soup.find_all("div", class_="gallery")

    for gallery in galleries:

        patient_meta = gallery.find("div", class_="item-meta")

        patient_name = (
            patient_meta.get_text(separator=" ", strip=True)
            .replace("Пациент:", "")
            .strip()
            if patient_meta
            else "Пример работы"
        )

        unique_images = set()

        for slide in gallery.find_all("li", class_="slide"):

            img_url = slide.get("data-url")

            if img_url:
                unique_images.add(img_url)

        if unique_images:
            page_data["evidence"].append({
                "patient_case": patient_name,
                "images": list(unique_images)
            })

    print(
        f"✅ {category_name}: FAQ({len(page_data['faq'])}), "
        f"Отзывы({len(page_data['reviews'])}), "
        f"Фото({len(page_data['evidence'])})"
    )

    return page_data