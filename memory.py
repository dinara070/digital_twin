"""База знань та пам'ять (RAG) з реальними embedding-моделями.

Пріоритет вибору embedding-бекенду (автоматичний fallback):
  1. sentence-transformers (справжні семантичні embeddings, якщо встановлено
     і модель доступна для завантаження)
  2. scikit-learn TF-IDF (статистичні embeddings на основі корпусу спогадів —
     не потребує завантаження моделей з інтернету)
  3. Хеш-based fallback (детермінований, але без семантики — крайній випадок,
     коли ні sentence-transformers, ні scikit-learn не встановлені)
"""

import hashlib
import time
import math
from typing import List, Dict, Optional, Tuple
from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    name: str = "base"

    @abstractmethod
    def fit(self, corpus: List[str]) -> None:
        """(Пере)навчання/калібрування на повному корпусі текстів."""

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Повертає вектор для одного тексту."""

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        ...


class SentenceTransformerEmbedder(BaseEmbedder):
    """Справжні семантичні embeddings через sentence-transformers."""

    name = "sentence-transformers"

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer  # noqa: местный import
        self.model = SentenceTransformer(model_name)

    def fit(self, corpus: List[str]) -> None:
        pass  # претренована модель, донавчання не потрібне

    def embed(self, text: str) -> List[float]:
        return self.model.encode([text], normalize_embeddings=True)[0].tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return self.model.encode(texts, normalize_embeddings=True).tolist()


class TFIDFEmbedder(BaseEmbedder):
    """TF-IDF вектори на основі scikit-learn.

    Реальний, статистично обґрунтований embedding без потреби завантажувати
    ваги моделі з інтернету. Векторизатор перенавчається на всьому корпусі
    спогадів кожного разу, коли додається суттєва кількість нового тексту,
    щоб словник залишався актуальним.
    """

    name = "tfidf"

    def __init__(self, max_features: int = 4096):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self._vectorizer_cls = TfidfVectorizer
        self.max_features = max_features
        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=(1, 2),
            analyzer="word",
            token_pattern=r"(?u)\b\w\w+\b",
        )
        self._fitted = False
        self._corpus: List[str] = []

    def fit(self, corpus: List[str]) -> None:
        self._corpus = list(corpus) if corpus else ["порожньо"]
        self.vectorizer.fit(self._corpus)
        self._fitted = True

    def embed(self, text: str) -> List[float]:
        if not self._fitted:
            self.fit([text])
        vec = self.vectorizer.transform([text]).toarray()[0]
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if not self._fitted:
            self.fit(texts)
        mat = self.vectorizer.transform(texts).toarray()
        out = []
        for row in mat:
            norm = math.sqrt(sum(x * x for x in row)) or 1.0
            out.append([x / norm for x in row])
        return out


class HashEmbedder(BaseEmbedder):
    """Останній fallback: детермінований псевдо-embedding без залежностей."""

    name = "hash"

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def fit(self, corpus: List[str]) -> None:
        pass

    def embed(self, text: str) -> List[float]:
        hash_val = hashlib.md5(text.encode()).hexdigest()
        vec = [((int(hash_val[i % 32], 16) + i) % 100) / 100.0 for i in range(self.dimension)]
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]


def build_default_embedder(prefer: Optional[str] = None) -> BaseEmbedder:
    """Обирає найкращий доступний embedder із graceful fallback."""
    order = [prefer] if prefer else []
    order += ["sentence-transformers", "tfidf", "hash"]

    for choice in order:
        try:
            if choice == "sentence-transformers":
                return SentenceTransformerEmbedder()
            if choice == "tfidf":
                return TFIDFEmbedder()
            if choice == "hash":
                return HashEmbedder()
        except Exception:
            continue
    return HashEmbedder()


class VectorDatabase:
    """Векторна база даних для RAG з підключним embedding-бекендом."""

    def __init__(self, embedder: Optional[BaseEmbedder] = None):
        self.embedder = embedder or build_default_embedder()
        self.vectors: List[Tuple[str, List[float], Dict]] = []  # (id, vector, metadata)
        self.text_store: Dict[str, str] = {}
        self._needs_refit = False
        self._refit_threshold = 5  # для TF-IDF: перенавчати кожні N нових текстів
        self._since_refit = 0

    @staticmethod
    def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
        n = min(len(v1), len(v2))
        return sum(v1[i] * v2[i] for i in range(n))

    def _maybe_refit(self):
        """Для TF-IDF потрібне періодичне перенавчання словника на корпусі."""
        if self.embedder.name != "tfidf":
            return
        self._since_refit += 1
        if self._since_refit >= self._refit_threshold or not self.embedder._fitted:
            texts = list(self.text_store.values())
            if texts:
                self.embedder.fit(texts)
                # перерахувати всі вектори з новим словником
                ids = [mid for mid, _, _ in self.vectors]
                new_vecs = self.embedder.embed_batch([self.text_store[i] for i in ids])
                self.vectors = [
                    (mid, new_vecs[idx], meta)
                    for idx, (mid, _, meta) in enumerate(self.vectors)
                ]
            self._since_refit = 0

    def add_memory(self, text: str, metadata: Dict = None) -> str:
        memory_id = hashlib.sha256(f"{text}{time.time()}".encode()).hexdigest()[:16]
        self.text_store[memory_id] = text
        vector = self.embedder.embed(text)
        self.vectors.append((memory_id, vector, metadata or {}))
        self._maybe_refit()
        return memory_id

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        if not self.vectors:
            return []
        query_vec = self.embedder.embed(query)
        scored = []
        for mem_id, vec, meta in self.vectors:
            sim = self._cosine_similarity(query_vec, vec)
            scored.append((sim, mem_id, meta))
        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for sim, mem_id, meta in scored[:top_k]:
            results.append({
                "id": mem_id,
                "text": self.text_store.get(mem_id, ""),
                "similarity": float(sim),
                "metadata": meta,
            })
        return results

    def get_all_memories(self) -> List[Dict]:
        return [
            {"id": mid, "text": self.text_store.get(mid, ""), "metadata": meta}
            for mid, _, meta in self.vectors
        ]

    def delete_memory(self, memory_id: str) -> bool:
        before = len(self.vectors)
        self.vectors = [v for v in self.vectors if v[0] != memory_id]
        self.text_store.pop(memory_id, None)
        return len(self.vectors) < before

    # ---- Персистентність (серіалізація без ваг моделі) ----
    def export_records(self) -> List[Dict]:
        return [
            {"id": mid, "text": self.text_store[mid], "vector": vec, "metadata": meta}
            for mid, vec, meta in self.vectors
        ]

    def load_records(self, records: List[Dict]):
        self.vectors = []
        self.text_store = {}
        for r in records:
            self.text_store[r["id"]] = r["text"]
            self.vectors.append((r["id"], r["vector"], r.get("metadata", {})))
        if self.embedder.name == "tfidf" and self.text_store:
            self.embedder.fit(list(self.text_store.values()))


class MemoryImporter:
    SUPPORTED_SOURCES = ["diary", "social_media", "messages", "books", "photos", "calendar", "email"]

    def __init__(self, vector_db: VectorDatabase):
        self.vector_db = vector_db
        self.import_stats: Dict[str, int] = {s: 0 for s in self.SUPPORTED_SOURCES}

    def import_diary(self, entries: List[Dict]):
        for entry in entries:
            text = f"Щоденник [{entry.get('date', 'невідомо')}]: {entry.get('content', '')}"
            self.vector_db.add_memory(text, {"source": "diary", "date": entry.get("date")})
            self.import_stats["diary"] += 1

    def import_social_media(self, posts: List[Dict]):
        for post in posts:
            text = f"Соцмережа [{post.get('platform', '')}]: {post.get('content', '')}"
            self.vector_db.add_memory(text, {"source": "social_media", "platform": post.get("platform")})
            self.import_stats["social_media"] += 1

    def import_messages(self, messages: List[Dict]):
        for msg in messages:
            text = f"Повідомлення від {msg.get('from', 'невідомо')}: {msg.get('content', '')}"
            self.vector_db.add_memory(text, {"source": "messages", "contact": msg.get("from")})
            self.import_stats["messages"] += 1

    def import_calendar(self, events: List[Dict]):
        for event in events:
            text = f"Календар [{event.get('date', '')}]: {event.get('title', '')} — {event.get('description', '')}"
            self.vector_db.add_memory(text, {"source": "calendar", "date": event.get("date")})
            self.import_stats["calendar"] += 1

    def import_books(self, quotes: List[Dict]):
        for q in quotes:
            text = f"Книга [{q.get('title', '')}]: {q.get('excerpt', '')}"
            self.vector_db.add_memory(text, {"source": "books", "title": q.get("title")})
            self.import_stats["books"] += 1

    def import_email(self, emails: List[Dict]):
        for e in emails:
            text = f"Email від {e.get('from', '')}: {e.get('subject', '')} — {e.get('body', '')}"
            self.vector_db.add_memory(text, {"source": "email", "contact": e.get("from")})
            self.import_stats["email"] += 1

    def get_stats(self) -> Dict:
        return self.import_stats.copy()


class ContinuousLearning:
    """Модуль безперервного навчання — фонове оновлення бази знань."""

    def __init__(self, vector_db: VectorDatabase):
        import queue
        import threading
        self.vector_db = vector_db
        self.update_queue = queue.Queue()
        self.is_running = False
        self._worker_thread = None
        self._threading = threading
        self.update_callbacks = []

    def start(self):
        self.is_running = True
        self._worker_thread = self._threading.Thread(target=self._process_updates, daemon=True)
        self._worker_thread.start()

    def stop(self):
        self.is_running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=2)

    def _process_updates(self):
        import queue as _q
        while self.is_running:
            try:
                update = self.update_queue.get(timeout=1)
                self._integrate_update(update)
            except _q.Empty:
                continue

    def _integrate_update(self, update: Dict):
        from datetime import datetime
        source = update.get("source")
        content = update.get("content")
        if source and content:
            self.vector_db.add_memory(content, {
                "source": source,
                "timestamp": datetime.now().isoformat(),
                "auto_imported": True,
            })
            for callback in self.update_callbacks:
                callback(update)

    def add_update(self, source: str, content: str):
        self.update_queue.put({"source": source, "content": content})

    def on_update(self, callback):
        self.update_callbacks.append(callback)
