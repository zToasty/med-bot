import json
import chromadb
from chromadb.utils import embedding_functions
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = str(PROJECT_ROOT / "chroma_db")
DATA_DIR = str(PROJECT_ROOT / "data")

ollama_ef = embedding_functions.OllamaEmbeddingFunction(
    url="http://localhost:11434/api/embeddings",
    model_name="nomic-embed-text"
)

client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_or_create_collection(
    name="med_bot_knowledge",
    embedding_function=ollama_ef
)

def chunk_text(text, max_len=600):
    """Режет текст на куски не более max_len, не разрывая слова."""
    if not text: return []
    res = []
    while len(text) > max_len:
        split_idx = text.rfind(' ', 0, max_len)
        if split_idx == -1: split_idx = max_len
        res.append(text[:split_idx].strip())
        text = text[split_idx:].strip()
    res.append(text)
    return [r for r in res if r]

def load_knowledge_base():
    if collection.count() > 0:
        logger.info(f"✅ RAG: База уже содержит {collection.count()} записей.")
        return

    logger.info("⏳ RAG: Начинаем загрузку...")
    docs_to_add = []

    # --- 1. ЦЕНЫ ---
    p_path = os.path.join(DATA_DIR, "prices.json")
    if os.path.exists(p_path):
        with open(p_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for cat, svcs in data.items():
                for s in svcs:
                    # Добавляем больше ключевых слов для эмбеддингов
                    txt = (f"Прайс-лист клиники Ованесовой. "
                           f"Услуга: {s['service']}. "
                           f"Цена: {s['price']}. "
                           f"Сколько стоит {s['service']}: {s['price']}. "
                           f"Стоимость процедуры в категории {cat}: {s['price']}.")
                    docs_to_add.append(txt)

    # --- 2. КОНТАКТЫ ---
    c_path = os.path.join(DATA_DIR, "contacts.json")
    if os.path.exists(c_path):
        with open(c_path, "r", encoding="utf-8") as f:
            c = json.load(f).get("clinic_contacts", {})
            txt = f"Адрес: {c.get('address')}. Тел: {c.get('phones')}. Проезд: {c.get('how_to_get_there')}"
            docs_to_add.append(txt)

    # --- 3. БАЗА ЗНАНИЙ (С ЖЕСТКОЙ НАРЕЗКОЙ) ---
    k_path = os.path.join(DATA_DIR, "knowledge.json")
    if os.path.exists(k_path):
        with open(k_path, "r", encoding="utf-8") as f:
            kb = json.load(f)
            if isinstance(kb, dict): kb = [kb]
            for page in kb:
                # FAQ
                for faq in page.get("faq", []):
                    full_faq = f"Вопрос: {faq['question']} Ответ: {faq['answer']}"
                    docs_to_add.extend(chunk_text(full_faq))
                # Описания
                for title, content in page.get("structured_info", {}).items():
                    header = f"Тема: {title}. "
                    # Режем контент на мелкие части
                    chunks = chunk_text(content, max_len=500)
                    for ch in chunks:
                        docs_to_add.append(header + ch)

    # --- ЗАГРУЗКА ПО ОДНОМУ ---
    logger.info(f"🚀 Загружаем {len(docs_to_add)} фрагментов...")
    added_count = 0
    for i, doc in enumerate(docs_to_add):
        try:
            collection.add(
                documents=[doc],
                ids=[f"id_{i}_{added_count}"],
                metadatas=[{"len": len(doc)}]
            )
            added_count += 1
            if added_count % 50 == 0:
                logger.info(f"Прогресс: {added_count}/{len(docs_to_add)}")
        except Exception as e:
            logger.error(f"❌ Пропущен кусок (слишком длинный или ошибка): {e}")

    logger.info(f"✅ Итого загружено: {added_count} фрагментов.")

def search_context(query: str, n_results: int = 5) -> str:
    try:
        # Ключевые слова, сигнализирующие о поиске цен
        price_keywords = ["цена", "стоит", "стоимость", "прайс", "руб", "сколько"]
        is_price_query = any(word in query.lower() for word in price_keywords)

        if is_price_query:
            # Если спрашивают про цену, запрашиваем больше результатов (например, 10),
            # чтобы короткие строчки цен точно пробились через длинные тексты
            results = collection.query(
                query_texts=[query],
                n_results=10 
            )
        else:
            results = collection.query(
                query_texts=[query],
                n_results=n_results
            )

        if results and results["documents"]:
            # Фильтруем дубликаты, если они вдруг проскочили
            unique_docs = list(dict.fromkeys(results["documents"][0]))
            return "\n\n---\n\n".join(unique_docs)
        return ""
    except Exception as e:
        logger.error(f"Ошибка поиска RAG: {e}")
        return ""