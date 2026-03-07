import json
import chromadb
from chromadb.utils import embedding_functions
import os
import logging
from pathlib import Path

from config import OPENAI_API_KEY
from services.token_tracker import tracker


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = str(PROJECT_ROOT / "chroma_db")
DATA_DIR = str(PROJECT_ROOT / "data")

openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=OPENAI_API_KEY,
    model_name="text-embedding-3-small"
)

client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_or_create_collection(
    name="med_bot_knowledge",
    embedding_function=openai_ef
)

BATCH_SIZE = 50

def chunk_text(text, max_len=600) -> list[str]:
    """Режет текст на куски не более max_len, не разрывая слова."""
    if not text:
        return []
    res = []
    while len(text) > max_len:
        split_idx = text.rfind(' ', 0, max_len)
        if split_idx == -1:
            split_idx = max_len
        res.append(text[:split_idx].strip())
        text = text[split_idx:].strip()
    if text:
        res.append(text)
    return res


def _flush_batch(docs: list, ids: list, metas: list) -> int:
    """Загружает один батч в ChromaDB, возвращает кол-во добавленных."""
    if not docs:
        return 0
    try:
        collection.add(documents=docs, ids=ids, metadatas=metas)
        return len(docs)
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке батча: {e}")
        # Попытка загрузить по одному, чтобы не потерять весь батч
        added = 0
        for doc, doc_id, meta in zip(docs, ids, metas):
            try:
                collection.add(documents=[doc], ids=[doc_id], metadatas=[meta])
                added += 1
            except Exception as inner_e:
                logger.error(f"  ↳ Пропущен документ {doc_id}: {inner_e}")
        return added


def load_knowledge_base(force_reload: bool = False):
    """
    Загружает базу знаний в ChromaDB.
    force_reload=True — очищает коллекцию и загружает заново.
    """
    if not force_reload and collection.count() > 0:
        logger.info(f"✅ RAG: База уже содержит {collection.count()} записей.")
        return

    if force_reload:
        logger.info("🔄 RAG: Принудительная перезагрузка, очищаем коллекцию...")
        # Удаляем все документы
        existing = collection.get()
        if existing["ids"]:
            collection.delete(ids=existing["ids"])

    logger.info("⏳ RAG: Начинаем загрузку...")

    docs_to_add: list[str] = []

    # --- 1. ЦЕНЫ ---
    p_path = os.path.join(DATA_DIR, "prices.json")
    if os.path.exists(p_path):
        with open(p_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for cat, svcs in data.items():
            for s in svcs:
                txt = (
                    f"Прайс-лист клиники Ованесовой. "
                    f"Услуга: {s['service']}. "
                    f"Цена: {s['price']}. "
                    f"Сколько стоит {s['service']}: {s['price']}. "
                    f"Стоимость процедуры в категории {cat}: {s['price']}."
                )
                docs_to_add.append(txt)
        logger.info(f"  📋 Цены: загружено {len(docs_to_add)} позиций")

    # --- 2. КОНТАКТЫ ---
    c_path = os.path.join(DATA_DIR, "contacts.json")
    if os.path.exists(c_path):
        with open(c_path, "r", encoding="utf-8") as f:
            c = json.load(f).get("clinic_contacts", {})
        txt = (
            f"Контакты клиники Ованесовой. "
            f"Адрес: {c.get('address')}. "
            f"Телефон: {c.get('phones')}. "
            f"Как добраться: {c.get('how_to_get_there')}"
        )
        docs_to_add.append(txt)
        logger.info("  📞 Контакты: добавлены")

    # --- 3. БАЗА ЗНАНИЙ ---
    k_path = os.path.join(DATA_DIR, "knowledge.json")
    if os.path.exists(k_path):
        with open(k_path, "r", encoding="utf-8") as f:
            kb = json.load(f)
        if isinstance(kb, dict):
            kb = [kb]

        faq_count = 0
        info_count = 0

        for page in kb:
            # FAQ — храним вопрос и ответ вместе, не режем (смысловая единица)
            for faq in page.get("faq", []):
                full_faq = f"Вопрос: {faq['question']} Ответ: {faq['answer']}"
                # Режем только если FAQ реально огромный (> 800 символов)
                if len(full_faq) > 800:
                    docs_to_add.extend(chunk_text(full_faq, max_len=600))
                else:
                    docs_to_add.append(full_faq)
                faq_count += 1

            # Структурированная информация
            for title, content in page.get("structured_info", {}).items():
                header = f"Тема: {title}. "
                chunks = chunk_text(content, max_len=500)
                for ch in chunks:
                    docs_to_add.append(header + ch)
                    info_count += 1

        logger.info(f"  📚 FAQ: {faq_count} записей, инфо: {info_count} фрагментов")

    # --- БАТЧЕВАЯ ЗАГРУЗКА ---
    total = len(docs_to_add)
    logger.info(f"🚀 Загружаем {total} фрагментов батчами по {BATCH_SIZE}...")

    added_total = 0
    batch_docs, batch_ids, batch_metas = [], [], []

    for i, doc in enumerate(docs_to_add):
        batch_docs.append(doc)
        batch_ids.append(f"id_{i}")  # ✅ Простые уникальные ID
        batch_metas.append({"len": len(doc), "index": i})

        if len(batch_docs) >= BATCH_SIZE:
            added_total += _flush_batch(batch_docs, batch_ids, batch_metas)
            batch_docs, batch_ids, batch_metas = [], [], []
            logger.info(f"  Прогресс: {added_total}/{total}")

    # Остаток
    added_total += _flush_batch(batch_docs, batch_ids, batch_metas)

    logger.info(f"✅ Итого загружено: {added_total}/{total} фрагментов.")

_PRICE_KEYWORDS = {"цена", "стоит", "стоимость", "прайс", "руб", "сколько", "расценки", "тариф"}

def search_context(query: str, n_results: int = 5) -> str:
    """
    Ищет релевантный контекст в базе знаний.
    Для ценовых запросов автоматически расширяет выборку.
    """
    try:
        query_lower = query.lower()
        is_price_query = any(word in query_lower for word in _PRICE_KEYWORDS)

        # Для ценовых запросов берём больше результатов
        actual_n = 10 if is_price_query else n_results

        results = collection.query(
            query_texts=[query],
            n_results=min(actual_n, collection.count())  # ✅ Не запрашиваем больше, чем есть
        )

        estimated_tokens = max(1, len(query) // 4)
        tracker.add_embedding(model="text-embedding-3-small", input_tokens=estimated_tokens)

        if results and results["documents"] and results["documents"][0]:
            # Убираем дубликаты, сохраняя порядок по релевантности
            seen = set()
            unique_docs = []
            for doc in results["documents"][0]:
                if doc not in seen:
                    seen.add(doc)
                    unique_docs.append(doc)

            return "\n\n---\n\n".join(unique_docs)

        return ""

    except Exception as e:
        logger.error(f"Ошибка поиска RAG: {e}")
        return ""