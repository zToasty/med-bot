"""
Сервис для поиска фото до/после по категории операции.
Загружает evidence из knowledge.json один раз при старте.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Структура: [{"category": "SMAS подтяжка лица", "patient_case": "Пациент 65...", "images": [...]}]
_evidence_index: list[dict] = []


def load_evidence():
    """Загружает все evidence из knowledge.json в память."""
    global _evidence_index
    _evidence_index = []

    k_path = PROJECT_ROOT / "data" / "knowledge.json"
    if not k_path.exists():
        logger.warning("knowledge.json не найден, evidence недоступны.")
        return

    with open(k_path, "r", encoding="utf-8") as f:
        kb = json.load(f)

    if isinstance(kb, dict):
        kb = [kb]

    for page in kb:
        category = page.get("category_name", "")
        for case in page.get("evidence", []):
            images = case.get("images", [])
            if images:
                _evidence_index.append({
                    "category": category,
                    "patient_case": case.get("patient_case", ""),
                    "images": images,
                })

    logger.info(f"✅ Evidence: загружено {len(_evidence_index)} случаев из {len(kb)} категорий.")


def find_evidence(query: str, max_cases: int = 3) -> list[dict]:
    """
    Ищет релевантные случаи по ключевым словам из запроса.
    Возвращает список случаев, каждый с первыми 2 фото.
    """
    if not _evidence_index:
        return []

    query_lower = query.lower()

    # Синонимы для улучшения поиска
    SYNONYMS: dict[str, list[str]] = {
        "блефаропластика": ["блефаро", "веки", "веко", "глаза"],
        "смас": ["smas", "подтяжка лица", "фейслифтинг", "лифтинг лица"],
        "ринопластика": ["нос", "ринопласт"],
        "маммопластика": ["грудь", "грудь", "маммо"],
        "липосакция": ["жир", "липо"],
        "подтяжка шеи": ["шея", "платизма"],
    }

    # Расширяем запрос синонимами
    search_terms = [query_lower]
    for key, synonyms in SYNONYMS.items():
        if key in query_lower or any(s in query_lower for s in synonyms):
            search_terms.extend([key] + synonyms)

    # Ищем совпадения по категории и названию случая
    matched = []
    for case in _evidence_index:
        category_lower = case["category"].lower()
        case_lower = case["patient_case"].lower()

        if any(term in category_lower or term in case_lower for term in search_terms):
            matched.append(case)

    if not matched:
        return []

    # Берём max_cases случаев, у каждого — первые 2 фото
    result = []
    for case in matched[:max_cases]:
        result.append({
            "category": case["category"],
            "patient_case": case["patient_case"],
            "images": case["images"][:2],  # только до и после
        })

    return result