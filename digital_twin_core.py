"""
================================================================================
DIGITAL TWIN — Консолідований однофайловий модуль (для надійного деплою)
Усі класи з пакету digital_twin/ зібрані в один файл, щоб уникнути
ModuleNotFoundError на Streamlit Cloud через відсутність підпапки в репо.
================================================================================
"""

import hashlib
import secrets
import base64
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable
from enum import Enum
import time
import math
from typing import List, Dict, Optional, Tuple
from abc import ABC, abstractmethod
import threading
from datetime import datetime
from typing import List, Dict
import os
from typing import List, Dict, Optional
from typing import Dict, List, Optional, Tuple
import json
import sqlite3
from contextlib import contextmanager
from typing import Dict, List, Optional, Any
import uuid
from typing import Any, Dict, List, Optional
from collections import Counter
from typing import Dict, List

# ============================================================================
# MODULE: SECURITY — Безпека, шифрування, контроль доступу та протокол спадщини.
# ============================================================================
class SecurityLevel(Enum):
    PUBLIC = "public"
    FAMILY = "family"
    PRIVATE = "private"
    CRITICAL = "critical"


@dataclass
class BiometricProfile:
    voice_hash: str = ""
    face_embedding: List[float] = field(default_factory=list)
    fingerprint_hash: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def verify_voice(self, voice_sample: bytes) -> bool:
        sample_hash = hashlib.sha256(voice_sample).hexdigest()
        return secrets.compare_digest(sample_hash, self.voice_hash)


class EncryptionManager:
    """Симетричне шифрування для секретів (API-ключі, чутливі спогади).

    Використовує XOR-потоковий шифр на базі ключа, виведеного через
    PBKDF2-HMAC-SHA256. Це навчальна/демо-реалізація — для продакшн
    використання замініть на `cryptography.fernet.Fernet` або AES-GCM.
    """

    def __init__(self, master_key: Optional[bytes] = None):
        self.master_key = master_key or secrets.token_bytes(32)
        self._key_cache: Dict[str, bytes] = {}

    def _derive_key(self, context: str) -> bytes:
        if context not in self._key_cache:
            self._key_cache[context] = hashlib.pbkdf2_hmac(
                "sha256", self.master_key, context.encode(), 100_000
            )
        return self._key_cache[context]

    def encrypt(self, data: str, context: str = "default") -> str:
        key = self._derive_key(context)
        data_bytes = data.encode("utf-8")
        encrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data_bytes))
        return base64.b64encode(encrypted).decode()

    def decrypt(self, encrypted_data: str, context: str = "default") -> str:
        key = self._derive_key(context)
        data_bytes = base64.b64decode(encrypted_data.encode())
        decrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data_bytes))
        return decrypted.decode("utf-8")

    def export_master_key(self) -> str:
        """Base64-подання майстер-ключа для збереження користувачем."""
        return base64.b64encode(self.master_key).decode()

    @classmethod
    def from_exported_key(cls, exported: str) -> "EncryptionManager":
        return cls(master_key=base64.b64decode(exported.encode()))


class AccessControl:
    def __init__(self):
        self._authenticated_user: Optional[str] = None
        self._authenticated_username: Optional[str] = None
        self._permissions: Dict[str, List[str]] = {
            "owner": ["read", "write", "delete", "configure", "talk"],
            "family": ["read", "talk"],
            "guest": ["talk"],
        }
        self._session_expiry: Optional[datetime] = None
        self._biometric_profile: Optional[BiometricProfile] = None
        self._password_hash: Optional[str] = None
        # Таблиця іменованих облікових записів для рольового входу
        # (username -> {"password_hash":.., "role":..}), окрім єдиного
        # "власницького" пароля вище (used для звичайного profile switch).
        self._users: Dict[str, Dict[str, str]] = {}

    def register_biometrics(self, profile: BiometricProfile):
        self._biometric_profile = profile

    def add_user(self, username: str, password: str, role: str):
        """Реєструє іменований обліковий запис для входу за роллю."""
        if role not in self._permissions:
            raise ValueError(f"Невідома роль: {role}")
        self._users[username] = {
            "password_hash": hashlib.sha256(password.encode()).hexdigest(),
            "role": role,
        }

    def login(self, username: str, password: str) -> Optional[str]:
        """Вхід за логіном+паролем із таблиці іменованих користувачів.
        Повертає роль при успіху, або None при невірних даних."""
        user = self._users.get(username)
        if not user:
            return None
        candidate_hash = hashlib.sha256(password.encode()).hexdigest()
        if not secrets.compare_digest(candidate_hash, user["password_hash"]):
            return None
        self._authenticated_user = user["role"]
        self._authenticated_username = username
        self._session_expiry = datetime.now() + timedelta(hours=1)
        return user["role"]

    def current_username(self) -> Optional[str]:
        return self._authenticated_username

    def list_users(self) -> List[Dict]:
        """Список зареєстрованих іменованих облікових записів (без паролів)."""
        return [{"username": u, "role": info["role"]} for u, info in self._users.items()]

    def set_password(self, password: str):
        self._password_hash = hashlib.sha256(password.encode()).hexdigest()

    def has_password(self) -> bool:
        return self._password_hash is not None

    def change_password(self, old_password: str, new_password: str) -> bool:
        """Зміна пароля. Якщо пароль ще не встановлено — стара перевірка не потрібна."""
        if self._password_hash is not None:
            old_hash = hashlib.sha256(old_password.encode()).hexdigest()
            if not secrets.compare_digest(old_hash, self._password_hash):
                return False
        self.set_password(new_password)
        return True

    def session_seconds_left(self) -> int:
        if not self._authenticated_user or not self._session_expiry:
            return 0
        return max(0, int((self._session_expiry - datetime.now()).total_seconds()))

    def authenticate(self, method: str, credentials: Any) -> bool:
        if method == "biometric" and self._biometric_profile:
            verified = self._biometric_profile.verify_voice(credentials)
            if verified:
                self._authenticated_user = "owner"
                self._session_expiry = datetime.now() + timedelta(hours=1)
            return verified
        elif method == "password":
            candidate_hash = hashlib.sha256(str(credentials).encode()).hexdigest()
            if self._password_hash is None or secrets.compare_digest(candidate_hash, self._password_hash):
                self._authenticated_user = "owner"
                self._session_expiry = datetime.now() + timedelta(hours=1)
                return True
            return False
        return False

    def check_permission(self, action: str) -> bool:
        if not self._authenticated_user:
            return False
        if self._session_expiry and datetime.now() > self._session_expiry:
            self._authenticated_user = None
            return False
        return action in self._permissions.get(self._authenticated_user, [])

    def logout(self):
        self._authenticated_user = None
        self._session_expiry = None


class LegacyProtocol:
    INHERITANCE_MODES = {
        "delete": "Автоматичне видалення всіх даних",
        "archive": "Архівація для родини (тільки спогади)",
        "active": "Залишити активним для родини",
        "public": "Публічний меморіал (обмежені дані)",
    }

    def __init__(self):
        self.mode: str = "archive"
        self.beneficiaries: List[str] = []
        self.trigger_conditions: List[Callable] = []
        self.activation_date: Optional[datetime] = None
        self.is_active: bool = False
        self.inactivity_days: int = 90

    def configure(self, mode: str, beneficiaries: List[str] = None, inactivity_days: int = 90):
        if mode not in self.INHERITANCE_MODES:
            raise ValueError(f"Невідомий режим: {mode}")
        self.mode = mode
        self.beneficiaries = beneficiaries or []
        self.inactivity_days = inactivity_days

    def add_trigger(self, condition: Callable):
        self.trigger_conditions.append(condition)

    def default_inactivity_trigger(self) -> Callable:
        def trigger(state: Dict) -> bool:
            last = state.get("last_interaction")
            if not last:
                return False
            last_dt = datetime.fromisoformat(last)
            return (datetime.now() - last_dt).days > self.inactivity_days
        return trigger

    def check_activation(self, twin_state: Dict) -> bool:
        for condition in self.trigger_conditions:
            if condition(twin_state):
                self.is_active = True
                self.activation_date = datetime.now()
                return True
        return False

    def execute(self, twin) -> Dict:
        if not self.is_active:
            return {"status": "inactive"}

        result = {"mode": self.mode, "timestamp": datetime.now().isoformat()}

        if self.mode == "delete":
            twin.purge_all_data()
            result["action"] = "all_data_deleted"
        elif self.mode == "archive":
            archive = twin.export_data(SecurityLevel.FAMILY)
            result["action"] = "archived_for_family"
            result["archive_size"] = len(archive.get("memories", []))
        elif self.mode == "active":
            result["action"] = "family_mode_activated"
        elif self.mode == "public":
            archive = twin.export_data(SecurityLevel.PUBLIC)
            result["action"] = "public_memorial_created"
            result["archive_size"] = len(archive.get("memories", []))

        return result

# ============================================================================
# MODULE: MEMORY —  Пріоритет вибору embedding-бекенду (автоматичний fallback): 1. sentence-transformers (справжні семантичні embeddings, якщо встановлено і модель доступна для завантаження) 2. scikit-learn TF-IDF (статистичні embeddings на основі корпусу спогадів — не потребує завантаження моделей з інтернету) 3. Хеш-based fallback (детермінований, але без семантики — крайній випадок, коли ні sentence-transformers, ні scikit-learn не встановлені)
# ============================================================================
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

    def update_memory(self, memory_id: str, new_text: str) -> Optional[List[float]]:
        """Оновлює текст спогаду та перераховує його вектор. Повертає новий вектор."""
        if memory_id not in self.text_store:
            return None
        self.text_store[memory_id] = new_text
        new_vector = self.embedder.embed(new_text)
        self.vectors = [
            (mid, new_vector if mid == memory_id else vec, meta)
            for mid, vec, meta in self.vectors
        ]
        return new_vector

    def update_metadata(self, memory_id: str, patch: Dict) -> bool:
        """Часткове оновлення metadata (теги, pinned, security-рівень) без перерахунку вектора."""
        found = False
        new_vectors = []
        for mid, vec, meta in self.vectors:
            if mid == memory_id:
                meta = {**meta, **patch}
                found = True
            new_vectors.append((mid, vec, meta))
        self.vectors = new_vectors
        return found

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

# ============================================================================
# MODULE: PERSONALITY_MODEL — Особистість та емоційний стан цифрового двійника.
# ============================================================================
@dataclass
class PersonalityConfig:
    vocabulary_style: str = "neutral"
    favorite_phrases: List[str] = field(default_factory=list)
    speech_formality: float = 0.5
    humor_level: float = 0.5

    political_stance: str = "neutral"
    religious_views: str = "agnostic"
    work_ethic: str = "balanced"
    family_values: str = "important"

    stress_reaction: str = "analytical"
    joy_expression: str = "enthusiastic"
    criticism_response: str = "defensive"

    common_words: List[str] = field(default_factory=list)
    slang_terms: List[str] = field(default_factory=list)

    # Вільний текстовий опис — біографія, стиль, історія — додає контексту LLM
    bio: str = ""

    def to_prompt_context(self) -> str:
        return f"""Ти — цифровий двійник людини з такими характеристиками:
- Стиль мовлення: {self.vocabulary_style}
- Рівень формальності: {self.speech_formality * 100:.0f}%
- Почуття гумору: {self.humor_level * 100:.0f}%
- Політичні погляди: {self.political_stance}
- Релігійні погляди: {self.religious_views}
- Ставлення до роботи: {self.work_ethic}
- Сімейні цінності: {self.family_values}
- Реакція на стрес: {self.stress_reaction}
- Вираження радості: {self.joy_expression}
- Реакція на критику: {self.criticism_response}
- Улюблені фрази: {', '.join(self.favorite_phrases[:5]) if self.favorite_phrases else 'немає'}
- Часто вживані слова: {', '.join(self.common_words[:10]) if self.common_words else 'стандартні'}
{"- Біографія: " + self.bio if self.bio else ""}
"""

    def diff(self, other: "PersonalityConfig") -> Dict[str, Tuple[Any, Any]]:
        """Порівнює дві конфігурації особистості, повертає лише поля, що відрізняються."""
        from dataclasses import asdict
        a, b = asdict(self), asdict(other)
        return {k: (a[k], b[k]) for k in a if a[k] != b[k]}


# Готові пресети особистості — швидкий старт без ручного налаштування кожного повзунка.
PERSONALITY_PRESETS: Dict[str, Dict[str, Any]] = {
    "Аналітик": dict(
        vocabulary_style="formal", speech_formality=0.7, humor_level=0.2,
        work_ethic="dedicated", stress_reaction="analytical",
        joy_expression="calm", criticism_response="accepting",
        common_words=["логічно", "дані", "структура", "аналіз"], slang_terms=[],
    ),
    "Комунікатор": dict(
        vocabulary_style="casual", speech_formality=0.25, humor_level=0.75,
        work_ethic="balanced", stress_reaction="emotional",
        joy_expression="enthusiastic", criticism_response="accepting",
        common_words=["класно", "давай", "чесно кажучи"], slang_terms=["короче", "типу"],
    ),
    "Творча особистість": dict(
        vocabulary_style="poetic", speech_formality=0.35, humor_level=0.6,
        work_ethic="relaxed", stress_reaction="avoidant",
        joy_expression="enthusiastic", criticism_response="dismissive",
        common_words=["натхнення", "ідея", "образ"], slang_terms=[],
    ),
    "Лідер": dict(
        vocabulary_style="formal", speech_formality=0.6, humor_level=0.4,
        work_ethic="dedicated", stress_reaction="analytical",
        joy_expression="reserved", criticism_response="accepting",
        common_words=["мета", "команда", "результат", "відповідальність"], slang_terms=[],
    ),
}


class EmotionalState:
    EMOTIONS = ["neutral", "happy", "sad", "angry", "anxious", "excited", "nostalgic", "thoughtful"]

    def __init__(self):
        self.current_emotion: str = "neutral"
        self.emotion_intensity: float = 0.3
        self.emotion_history: List[Dict] = []
        self._lock = threading.Lock()

    def set_emotion(self, emotion: str, intensity: float = 0.5, trigger: str = ""):
        with self._lock:
            if emotion not in self.EMOTIONS:
                emotion = "neutral"
            self.current_emotion = emotion
            self.emotion_intensity = max(0, min(1, intensity))
            self.emotion_history.append({
                "emotion": emotion,
                "intensity": intensity,
                "trigger": trigger,
                "timestamp": datetime.now().isoformat(),
            })

    def react_to_input(self, text: str, personality: PersonalityConfig) -> str:
        text_lower = text.lower()

        positive_words = ["чудово", "відмінно", "радість", "успіх", "любов", "дякую", "клас"]
        negative_words = ["погано", "жах", "проблема", "криза", "смерть", "втрата", "зрада"]
        stress_words = ["терміново", "критично", "наказ", "штраф", "звільнення"]

        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        stress_count = sum(1 for w in stress_words if w in text_lower)

        if stress_count > 0:
            if personality.stress_reaction == "analytical":
                self.set_emotion("thoughtful", 0.6, "stress_detected")
            elif personality.stress_reaction == "emotional":
                self.set_emotion("anxious", 0.7, "stress_detected")
            else:
                self.set_emotion("neutral", 0.4, "stress_detected")
        elif pos_count > neg_count:
            intensity = 0.7 if personality.joy_expression == "enthusiastic" else 0.4
            self.set_emotion("happy", intensity, "positive_input")
        elif neg_count > pos_count:
            self.set_emotion("sad", 0.5, "negative_input")
        else:
            # Немає явного сигналу — все одно фіксуємо стан в історії,
            # щоб аналітика й персистентність мали запис для кожного ходу розмови.
            self.set_emotion("neutral", 0.3, "no_signal")

        return self.current_emotion

    def get_emotional_prefix(self) -> str:
        prefixes = {
            "happy": "[з радістю] ",
            "sad": "[з сумом] ",
            "angry": "[з обуренням] ",
            "anxious": "[з хвилюванням] ",
            "excited": "[з ентузіазмом] ",
            "nostalgic": "[з ностальгією] ",
            "thoughtful": "[задумавшись] ",
            "neutral": "",
        }
        return prefixes.get(self.current_emotion, "")

# ============================================================================
# MODULE: LLM — з fallback на шаблонний генератор, якщо API-ключ не налаштовано або стався збій.
# ============================================================================
DEFAULT_MODEL = "claude-sonnet-5"


class LLMProvider:
    """Тонка обгортка над Anthropic Messages API (з підтримкою стрімінгу).

    Ключ береться з параметра, або зі змінної середовища ANTHROPIC_API_KEY.
    Якщо пакет `anthropic` не встановлено або ключ відсутній — provider
    вважається недоступним (`is_available() == False`), і CognitiveEngine
    автоматично перейде на розширений шаблонний режим.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        self.model = model
        self._client = None
        self._error: Optional[str] = None

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            self._error = "ANTHROPIC_API_KEY не заданий"
            return

        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=key)
        except ImportError:
            self._error = "Пакет 'anthropic' не встановлено (pip install anthropic)"
        except Exception as e:  # noqa
            self._error = f"Помилка ініціалізації клієнта: {e}"

    def is_available(self) -> bool:
        return self._client is not None

    def error(self) -> Optional[str]:
        return self._error

    def complete(self, system_prompt: str, messages: List[Dict], max_tokens: int = 500) -> str:
        """messages: [{"role": "user"|"assistant", "content": "..."}]"""
        if not self._client:
            raise RuntimeError(self._error or "LLM провайдер недоступний")

        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        )
        parts = [block.text for block in response.content if getattr(block, "type", "") == "text"]
        return "".join(parts).strip()

    def stream_complete(self, system_prompt: str, messages: List[Dict], max_tokens: int = 500):
        """Генератор текстових шматків у реальному часі (для live-виводу в чаті)."""
        if not self._client:
            raise RuntimeError(self._error or "LLM провайдер недоступний")

        with self._client.messages.stream(
            model=self.model, max_tokens=max_tokens, system=system_prompt, messages=messages,
        ) as stream:
            for chunk in stream.text_stream:
                yield chunk

    def classify_emotion(self, text: str) -> str:
        """Легка LLM-класифікація емоційного тону тексту (опційно)."""
        if not self._client:
            return "neutral"
        allowed = ", ".join(EmotionalState.EMOTIONS)
        try:
            result = self.complete(
                system_prompt=(
                    f"Класифікуй емоційний тон повідомлення одним словом зі списку: "
                    f"{allowed}. Відповідай ЛИШЕ цим словом, без пояснень."
                ),
                messages=[{"role": "user", "content": text}],
                max_tokens=10,
            )
            word = result.strip().lower()
            return word if word in EmotionalState.EMOTIONS else "neutral"
        except Exception:
            return "neutral"


class CognitiveEngine:
    """Генерація відповідей на основі особистості, пам'яті та (опційно) LLM.

    Двигун здатен вести розмову самостійно навіть без LLM: розширений
    шаблонний режим розпізнає широкий спектр тем (привітання, почуття,
    робота, цінності, спогади, довільні питання) і формує змістовну
    відповідь на основі bio та конфігурації особистості, а не лише
    короткого канону фраз.
    """

    def __init__(
        self,
        vector_db: VectorDatabase,
        personality: PersonalityConfig,
        llm_provider: Optional[LLMProvider] = None,
    ):
        self.vector_db = vector_db
        self.personality = personality
        self.llm_provider = llm_provider
        self.emotional_state = EmotionalState()
        self.conversation_history: List[Dict] = []

    def _retrieve_context(self, query: str, top_k: int = 5) -> List[Dict]:
        memories = self.vector_db.search(query, top_k=top_k)
        return [m for m in memories if m["similarity"] > 0.12]

    def _apply_personality(self, response: str) -> str:
        if self.personality.favorite_phrases and secrets.randbelow(100) < 25:
            phrase = secrets.choice(self.personality.favorite_phrases)
            response = f"{phrase} {response}"

        if self.personality.speech_formality > 0.7:
            response = response.replace("ти", "Ви").replace("тебе", "Вас")
        elif self.personality.speech_formality < 0.3:
            response = response.replace("Ви", "ти").replace("Вас", "тебе")

        if self.personality.slang_terms and self.personality.speech_formality < 0.4:
            if secrets.randbelow(100) < 20:
                response += f" {secrets.choice(self.personality.slang_terms)}"

        return response

    # ---- Розширений автономний шаблонний режим (без LLM) ----
    _TOPIC_KEYWORDS = {
        "greeting": ["привіт", "здоров", "hi", "hello", "добрий день", "доброго дня", "вітаю"],
        "farewell": ["бувай", "до зустрічі", "па-па", "прощавай", "на все добре", "бай"],
        "gratitude": ["дякую", "дяки", "спасибі", "вдячн"],
        "how_are_you": ["як справи", "як ти", "як твої", "як життя", "як почуваєш"],
        "work": ["робот", "кар'єра", "проєкт", "проект", "продукт", "стартап", "менеджмент"],
        "study": ["навчання", "вчиш", "вчишся", "матем", "алгоритм", "фізик", "наук", "програмув"],
        "family": ["сім", "родин", "батьк", "мама", "тато"],
        "stress": ["стрес", "хвилю", "паніку", "критичн", "терміново", "важко", "втомл"],
        "sport": ["спорт", "трену", "біга", "фітнес", "плаван"],
        "values": ["цінност", "принцип", "важлив", "сенс життя", "успіх"],
        "memory": ["пам'ятаєш", "пригадай", "розкажи про", "нагадай"],
        "opinion": ["думаєш", "думка", "вважаєш", "як ти ставишся", "твоя позиція"],
    }

    def _classify_topic(self, text: str) -> str:
        t = text.lower()
        for topic, keywords in self._TOPIC_KEYWORDS.items():
            if any(k in t for k in keywords):
                return topic
        return "general"

    def _maybe_follow_up(self) -> str:
        """Іноді додає запитання-продовження, щоб розмова тривала природно."""
        if secrets.randbelow(100) < 35:
            options = [
                " А як у тебе з цим?",
                " До речі, а ти як на це дивишся?",
                " Розкажи, а як у тебе справи з цим?",
                " Цікаво, що ти думаєш із цього приводу?",
            ]
            return secrets.choice(options)
        return ""

    def _generate_template_response(self, user_input: str, context: List[Dict]) -> str:
        topic = self._classify_topic(user_input)
        bio = self.personality.bio.strip()

        if topic == "greeting":
            base = secrets.choice([
                "Привіт! Радий(-а) тебе бачити.",
                "О, привіт! Як справи?",
                "Здоров був! Чим можу допомогти?",
            ])
            return base

        if topic == "farewell":
            return secrets.choice(["Бувай! До зустрічі.", "На все добре, до наступного разу!", "Па-па!"])

        if topic == "gratitude":
            return secrets.choice(["Завжди будь ласка!", "Немає за що, звертайся ще.", "Радий(-а) допомогти!"])

        if topic == "how_are_you":
            mood = {
                "analytical": "спокійно й зібрано, як завжди намагаюся тримати рівновагу",
                "emotional": "по-різному, залежно від дня, але стараюся не губити настрій",
                "avoidant": "нормально, головне — не заглиблюватись у зайве",
            }.get(self.personality.stress_reaction, "непогано")
            return f"Все {mood}. А в тебе як справи?"

        if topic == "stress":
            reaction = {
                "analytical": "стараюся зберігати спокій, розкласти ситуацію на частини й діяти системно",
                "emotional": "спершу відчуваю хвилювання, але намагаюся швидко взяти себе в руки",
                "avoidant": "намагаюся дистанціюватися й повернутися до питання, коли стане спокійніше",
            }.get(self.personality.stress_reaction, "намагаюся діяти виважено")
            return f"У стресових ситуаціях я {reaction}." + self._maybe_follow_up()

        if topic == "work" and bio:
            return (
                f"Робота і проєкти — це те, чим я живу. {bio.split('.')[0]}." + self._maybe_follow_up()
            )

        if topic == "study" and bio:
            sentences = [s.strip() for s in bio.split(".") if s.strip()]
            relevant = next((s for s in sentences if any(w in s.lower() for w in ["математ", "алгоритм", "фізик", "наук"])), sentences[0] if sentences else "")
            return (f"{relevant}." if relevant else "Навчання — важлива частина мого життя.") + self._maybe_follow_up()

        if topic == "sport":
            return "Регулярно займаюся спортом — це частина мого режиму відновлення та концентрації." + self._maybe_follow_up()

        if topic == "values" and bio:
            sentences = [s.strip() for s in bio.split(".") if s.strip()]
            relevant = next((s for s in sentences if any(w in s.lower() for w in ["цінност", "цілеспрям", "відповідальн", "вплив"])), None)
            if relevant:
                return f"{relevant}." + self._maybe_follow_up()

        if topic == "family":
            return (
                "Сім'я — це найголовніше в житті."
                if self.personality.family_values == "very_important"
                else "Сім'я важлива, але кожен сам визначає, яку роль вона відіграє."
            ) + self._maybe_follow_up()

        if (topic in ("memory", "opinion") or context) and context:
            top = context[0]["text"]
            if len(context) > 1:
                combined = " ".join(m["text"] for m in context[:2])
                return f"Пригадую: {combined}" + self._maybe_follow_up()
            return f"Це нагадує мені: {top}" + self._maybe_follow_up()

        # Загальний випадок — відповідаємо, спираючись на bio та цінності,
        # а не заглушкою "не знаю", щоб діалог відчувався живим і самостійним.
        opinion = self._generate_opinion(user_input)
        return f"Як на мене, {opinion}." + self._maybe_follow_up()

    def _generate_opinion(self, topic: str) -> str:
        t = topic.lower()
        if "робот" in t or "кар'єра" in t:
            return {
                "dedicated": "робота — це важлива частина життя, і до неї треба ставитися серйозно",
                "balanced": "важливо збалансувати роботу та особисте життя",
            }.get(self.personality.work_ethic, "головне — не перетворювати роботу на єдиний сенс життя")
        if "сім" in t or "родин" in t:
            return "сім'я — це найголовніше в житті" if self.personality.family_values == "very_important" \
                else "сім'я важлива, але кожен сам визначає її роль"
        if self.personality.bio:
            return self.personality.bio.split(".")[0].strip().lower()
        return "тут важливо подумати з різних боків і знайти баланс"

    # ---- LLM-режим ----
    def _build_system_prompt(self, context: List[Dict]) -> str:
        system_prompt = self.personality.to_prompt_context()
        if context:
            memory_block = "\n".join(f"- {m['text']}" for m in context)
            system_prompt += (
                f"\n\nРелевантні спогади з пам'яті, використовуй їх природно, "
                f"якщо це доречно (не цитуй дослівно як список):\n{memory_block}\n"
            )
        system_prompt += (
            "\nВідповідай від першої особи, природно і самостійно веди розмову — "
            "як реальна людина зі своїм характером, а не як асистент. Можеш відповідати "
            "на будь-які питання, спираючись на свої загальні знання, а не лише на спогади. "
            "Час від часу став зустрічні запитання, щоб діалог розвивався природно. "
            "Тримай відповіді стислими (1-5 речень), якщо тема сама не вимагає більшого. "
            "Не згадуй, що ти є AI-моделлю чи цифровим двійником — просто відповідай як людина."
        )
        return system_prompt

    def _build_messages(self, user_input: str, history_len: int = 12) -> List[Dict]:
        history = self.conversation_history[-history_len:]
        messages = []
        for turn in history:
            messages.append({"role": "user", "content": turn["user"]})
            messages.append({"role": "assistant", "content": turn["twin"]})
        messages.append({"role": "user", "content": user_input})
        return messages

    def _finalize_turn(self, user_input: str, response_text: str, mode: str, llm_error: Optional[str]):
        self.conversation_history.append({
            "user": user_input,
            "twin": response_text,
            "emotion": self.emotional_state.current_emotion,
            "timestamp": datetime.now().isoformat(),
            "mode": mode,
            "llm_error": llm_error,
        })

    def generate_response(self, user_input: str) -> str:
        """Одноразова (нестрімінгова) генерація — для Telegram/VR/API інтерфейсів."""
        return "".join(self.generate_response_stream(user_input))

    def generate_response_stream(self, user_input: str):
        """Генератор шматків тексту — для живого виводу в чаті (Streamlit st.write_stream).

        Для LLM-режиму текст надходить у реальному часі від Anthropic API.
        Для шаблонного режиму текст віддається одним шматком (генерація миттєва).
        Побічні ефекти (історія розмови, емоційний стан) застосовуються так само
        в обох режимах — виклик вважається завершеним, коли генератор вичерпано.
        """
        context = self._retrieve_context(user_input)

        if self.llm_provider and self.llm_provider.is_available():
            try:
                system_prompt = self._build_system_prompt(context)
                messages = self._build_messages(user_input)

                chunks: List[str] = []
                for chunk in self.llm_provider.stream_complete(system_prompt, messages):
                    chunks.append(chunk)
                    yield chunk
                response_text = "".join(chunks).strip()

                emotion = self.llm_provider.classify_emotion(user_input)
                self.emotional_state.set_emotion(emotion, 0.5, "llm_classified")
                self._finalize_turn(user_input, response_text, "llm", None)
                return
            except Exception as e:  # graceful degrade до шаблонів
                llm_error = str(e)
                self.emotional_state.react_to_input(user_input, self.personality)
                response_text = self._apply_personality(self._generate_template_response(user_input, context))
                yield response_text
                self._finalize_turn(user_input, response_text, "template", llm_error)
                return

        self.emotional_state.react_to_input(user_input, self.personality)
        response_text = self._apply_personality(self._generate_template_response(user_input, context))
        yield response_text
        self._finalize_turn(user_input, response_text, "template", None)


# ============================================================================
# MODULE: IDENTITY — Візуальна та звукова ідентичність двійника (голос, 3D-аватар, мова тіла).
# ============================================================================
class VoiceCloning:
    """Інтерфейс для інтеграції з провайдером клонування голосу (напр. ElevenLabs)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.voice_profile: Optional[Dict] = None
        self.sample_count: int = 0
        self.is_trained: bool = False

    def add_training_sample(self, audio_data: bytes, transcript: str) -> bool:
        self.sample_count += 1
        if self.sample_count >= 10:
            self.is_trained = True
        return True

    def synthesize_speech(self, text: str, emotion: str = "neutral") -> bytes:
        if not self.is_trained:
            raise RuntimeError("Голос ще не навчено. Потрібно мінімум 10 зразків.")
        return f"[SYNTHESIZED_VOICE: {text[:50]}... emotion={emotion}]".encode()

    def get_status(self) -> Dict:
        return {
            "trained": self.is_trained,
            "samples": self.sample_count,
            "ready": self.sample_count >= 10,
        }


class Avatar3D:
    """Інтерфейс для інтеграції з рушієм 3D-аватара (напр. Unreal MetaHuman)."""

    def __init__(self):
        self.model_path: Optional[str] = None
        self.face_scan_data: Optional[Dict] = None
        self.body_scan_data: Optional[Dict] = None
        self.expressions: Dict[str, Dict] = {}
        self.is_loaded: bool = False

    def load_from_scan(self, face_scan: Dict, body_scan: Dict):
        self.face_scan_data = face_scan
        self.body_scan_data = body_scan
        self.is_loaded = True

    def set_expression(self, emotion: str, intensity: float = 0.5):
        self.expressions[emotion] = {
            "intensity": intensity,
            "active": True,
            "timestamp": datetime.now().isoformat(),
        }

    def animate_lips(self, phonemes: List[str], duration: float):
        return {"phonemes": phonemes, "duration": duration, "status": "animating"}

    def render_frame(self) -> Dict:
        if not self.is_loaded:
            return {"status": "not_loaded"}
        return {
            "status": "rendered",
            "expressions": self.expressions,
            "timestamp": datetime.now().isoformat(),
        }


class BodyLanguage:
    def __init__(self):
        self.gestures: Dict[str, Dict] = {}
        self.blink_rate: float = 0.15
        self.micro_expressions: List[str] = []

    def capture_gesture(self, name: str, joint_positions: List[Tuple[float, float, float]]):
        self.gestures[name] = {"joints": joint_positions, "captured_at": datetime.now().isoformat()}

    def get_gesture_for_emotion(self, emotion: str) -> Optional[str]:
        gesture_map = {
            "happy": "open_arms",
            "sad": "head_down",
            "thoughtful": "chin_touch",
            "angry": "fist_clench",
            "anxious": "fidgeting",
            "excited": "hands_up",
            "nostalgic": "soft_smile",
            "neutral": "relaxed_posture",
        }
        return gesture_map.get(emotion, "relaxed_posture")

    def generate_blink(self) -> Dict:
        return {"action": "blink", "duration": 0.15, "timestamp": datetime.now().isoformat()}

# ============================================================================
# MODULE: DB — між сесіями (спогади, особистість, історія розмов/емоцій, спадщина).
# ============================================================================
SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS personality (
    profile_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    text TEXT NOT NULL,
    vector TEXT NOT NULL,
    metadata TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_memories_profile ON memories(profile_id);

CREATE TABLE IF NOT EXISTS conversation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    user_msg TEXT NOT NULL,
    twin_msg TEXT NOT NULL,
    emotion TEXT,
    mode TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_conversation_profile ON conversation(profile_id);

CREATE TABLE IF NOT EXISTS emotion_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    emotion TEXT NOT NULL,
    intensity REAL NOT NULL,
    trigger_reason TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_emotion_profile ON emotion_history(profile_id);

CREATE TABLE IF NOT EXISTS legacy (
    profile_id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    beneficiaries TEXT NOT NULL,
    inactivity_days INTEGER NOT NULL,
    is_active INTEGER NOT NULL,
    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS secrets_store (
    profile_id TEXT PRIMARY KEY,
    encrypted_api_key TEXT,
    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS personality_presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    name TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_presets_profile ON personality_presets(profile_id);

CREATE TABLE IF NOT EXISTS access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_access_log_profile ON access_log(profile_id);
"""


class TwinDatabase:
    """Потокобезпечна обгортка над SQLite для збереження стану двійника."""

    def __init__(self, db_path: str = "digital_twin.db"):
        self.db_path = db_path
        self._lock = threading.RLock()
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ---- Профілі ----
    def create_profile(self, profile_id: str, name: str):
        with self._lock, self._connect() as conn:
            now = datetime.now().isoformat()
            conn.execute(
                "INSERT OR IGNORE INTO profiles (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (profile_id, name, now, now),
            )

    def touch_profile(self, profile_id: str):
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE profiles SET updated_at = ? WHERE id = ?",
                (datetime.now().isoformat(), profile_id),
            )

    def list_profiles(self) -> List[Dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, created_at, updated_at FROM profiles ORDER BY updated_at DESC"
            ).fetchall()
            return [
                {"id": r[0], "name": r[1], "created_at": r[2], "updated_at": r[3]}
                for r in rows
            ]

    def delete_profile(self, profile_id: str):
        with self._lock, self._connect() as conn:
            for table in ["memories", "conversation", "emotion_history", "legacy",
                          "secrets_store", "personality", "profiles"]:
                conn.execute(f"DELETE FROM {table} WHERE {'id' if table == 'profiles' else 'profile_id'} = ?", (profile_id,))

    # ---- Особистість ----
    def save_personality(self, profile_id: str, data: Dict):
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO personality (profile_id, data) VALUES (?, ?) "
                "ON CONFLICT(profile_id) DO UPDATE SET data = excluded.data",
                (profile_id, json.dumps(data, ensure_ascii=False)),
            )

    def load_personality(self, profile_id: str) -> Optional[Dict]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM personality WHERE profile_id = ?", (profile_id,)
            ).fetchone()
            return json.loads(row[0]) if row else None

    # ---- Спогади ----
    def save_memory(self, profile_id: str, memory_id: str, text: str, vector: List[float], metadata: Dict):
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO memories (id, profile_id, text, vector, metadata, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (memory_id, profile_id, text, json.dumps(vector), json.dumps(metadata, ensure_ascii=False),
                 datetime.now().isoformat()),
            )

    def bulk_save_memories(self, profile_id: str, records: List[Dict]):
        with self._lock, self._connect() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO memories (id, profile_id, text, vector, metadata, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (r["id"], profile_id, r["text"], json.dumps(r["vector"]),
                     json.dumps(r.get("metadata", {}), ensure_ascii=False), datetime.now().isoformat())
                    for r in records
                ],
            )

    def load_memories(self, profile_id: str) -> List[Dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT id, text, vector, metadata FROM memories WHERE profile_id = ?", (profile_id,)
            ).fetchall()
            return [
                {"id": r[0], "text": r[1], "vector": json.loads(r[2]), "metadata": json.loads(r[3])}
                for r in rows
            ]

    def delete_memory(self, profile_id: str, memory_id: str):
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM memories WHERE profile_id = ? AND id = ?", (profile_id, memory_id))

    # ---- Історія розмов ----
    def append_conversation(self, profile_id: str, user_msg: str, twin_msg: str, emotion: str, mode: str):
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO conversation (profile_id, user_msg, twin_msg, emotion, mode, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (profile_id, user_msg, twin_msg, emotion, mode, datetime.now().isoformat()),
            )

    def load_conversation(self, profile_id: str, limit: int = 200) -> List[Dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT user_msg, twin_msg, emotion, mode, timestamp FROM conversation "
                "WHERE profile_id = ? ORDER BY id ASC LIMIT ?",
                (profile_id, limit),
            ).fetchall()
            return [
                {"user": r[0], "twin": r[1], "emotion": r[2], "mode": r[3], "timestamp": r[4]}
                for r in rows
            ]

    # ---- Історія емоцій ----
    def append_emotion(self, profile_id: str, emotion: str, intensity: float, trigger: str):
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO emotion_history (profile_id, emotion, intensity, trigger_reason, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (profile_id, emotion, intensity, trigger, datetime.now().isoformat()),
            )

    def load_emotion_history(self, profile_id: str, limit: int = 500) -> List[Dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT emotion, intensity, trigger_reason, timestamp FROM emotion_history "
                "WHERE profile_id = ? ORDER BY id ASC LIMIT ?",
                (profile_id, limit),
            ).fetchall()
            return [
                {"emotion": r[0], "intensity": r[1], "trigger": r[2], "timestamp": r[3]}
                for r in rows
            ]

    # ---- Протокол спадщини ----
    def save_legacy(self, profile_id: str, mode: str, beneficiaries: List[str], inactivity_days: int, is_active: bool):
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO legacy (profile_id, mode, beneficiaries, inactivity_days, is_active) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(profile_id) DO UPDATE SET "
                "mode = excluded.mode, beneficiaries = excluded.beneficiaries, "
                "inactivity_days = excluded.inactivity_days, is_active = excluded.is_active",
                (profile_id, mode, json.dumps(beneficiaries), inactivity_days, int(is_active)),
            )

    def load_legacy(self, profile_id: str) -> Optional[Dict]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT mode, beneficiaries, inactivity_days, is_active FROM legacy WHERE profile_id = ?",
                (profile_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "mode": row[0], "beneficiaries": json.loads(row[1]),
                "inactivity_days": row[2], "is_active": bool(row[3]),
            }

    # ---- API-ключ (зашифрований) ----
    def save_encrypted_secret(self, profile_id: str, encrypted_api_key: str):
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO secrets_store (profile_id, encrypted_api_key) VALUES (?, ?) "
                "ON CONFLICT(profile_id) DO UPDATE SET encrypted_api_key = excluded.encrypted_api_key",
                (profile_id, encrypted_api_key),
            )

    def load_encrypted_secret(self, profile_id: str) -> Optional[str]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT encrypted_api_key FROM secrets_store WHERE profile_id = ?", (profile_id,)
            ).fetchone()
            return row[0] if row else None

    # ---- Пресети особистості ----
    def save_personality_preset(self, profile_id: str, name: str, data: Dict) -> int:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO personality_presets (profile_id, name, data, created_at) VALUES (?, ?, ?, ?)",
                (profile_id, name, json.dumps(data, ensure_ascii=False), datetime.now().isoformat()),
            )
            return cur.lastrowid

    def list_personality_presets(self, profile_id: str) -> List[Dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, created_at FROM personality_presets WHERE profile_id = ? ORDER BY created_at DESC",
                (profile_id,),
            ).fetchall()
            return [{"id": r[0], "name": r[1], "created_at": r[2]} for r in rows]

    def load_personality_preset(self, preset_id: int) -> Optional[Dict]:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT data FROM personality_presets WHERE id = ?", (preset_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def delete_personality_preset(self, preset_id: int):
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM personality_presets WHERE id = ?", (preset_id,))

    # ---- Журнал доступу / аудит ----
    def log_access(self, profile_id: str, action: str, detail: str = ""):
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO access_log (profile_id, action, detail, timestamp) VALUES (?, ?, ?, ?)",
                (profile_id, action, detail, datetime.now().isoformat()),
            )

    def load_access_log(self, profile_id: str, limit: int = 100) -> List[Dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT action, detail, timestamp FROM access_log WHERE profile_id = ? ORDER BY id DESC LIMIT ?",
                (profile_id, limit),
            ).fetchall()
            return [{"action": r[0], "detail": r[1], "timestamp": r[2]} for r in rows]

    # ---- Керування історією розмов ----
    def clear_conversation(self, profile_id: str):
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM conversation WHERE profile_id = ?", (profile_id,))
            conn.execute("DELETE FROM emotion_history WHERE profile_id = ?", (profile_id,))

    def delete_last_conversation_turn(self, profile_id: str):
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM conversation WHERE profile_id = ? ORDER BY id DESC LIMIT 1", (profile_id,)
            ).fetchone()
            if row:
                conn.execute("DELETE FROM conversation WHERE id = ?", (row[0],))
            row2 = conn.execute(
                "SELECT id FROM emotion_history WHERE profile_id = ? ORDER BY id DESC LIMIT 1", (profile_id,)
            ).fetchone()
            if row2:
                conn.execute("DELETE FROM emotion_history WHERE id = ?", (row2[0],))

    def update_memory_text(self, profile_id: str, memory_id: str, new_text: str, new_vector: List[float]):
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE memories SET text = ?, vector = ? WHERE profile_id = ? AND id = ?",
                (new_text, json.dumps(new_vector), profile_id, memory_id),
            )

    def raw_backup_bytes(self) -> bytes:
        """Повертає сирі байти файлу SQLite для резервного копіювання."""
        with self._lock:
            with open(self.db_path, "rb") as f:
                return f.read()

# ============================================================================
# MODULE: ORCHESTRATOR — Оркестратор — центральний модуль координації всіх компонентів двійника.
# ============================================================================
class Orchestrator:
    """Координує безпеку, пам'ять, когніцію, ідентичність та персистентність."""

    def __init__(
        self,
        profile_id: Optional[str] = None,
        profile_name: str = "Мій двійник",
        db: Optional[TwinDatabase] = None,
        embedder_preference: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        llm_model: Optional[str] = None,
        autosave: bool = True,
    ):
        self.profile_id = profile_id or str(uuid.uuid4())[:12]
        self.profile_name = profile_name
        self.db = db
        self.autosave = autosave and db is not None

        self.encryption = EncryptionManager()
        self.access_control = AccessControl()
        self.legacy = LegacyProtocol()

        self.vector_db = VectorDatabase(embedder=build_default_embedder(embedder_preference))
        self.memory_importer = MemoryImporter(self.vector_db)
        self.continuous_learning = ContinuousLearning(self.vector_db)

        self.personality = PersonalityConfig()
        self.llm_provider = LLMProvider(api_key=llm_api_key, model=llm_model or "claude-sonnet-5") \
            if llm_api_key else None
        self.cognitive_engine: Optional[CognitiveEngine] = None

        self.voice = VoiceCloning()
        self.avatar = Avatar3D()
        self.body_language = BodyLanguage()

        self.state: Dict = {
            "status": "initialized",
            "last_interaction": None,
            "total_interactions": 0,
            "active_sessions": 0,
        }
        self._lock = threading.RLock()

        if self.db:
            try:
                self.db.create_profile(self.profile_id, self.profile_name)
            except Exception:
                pass  # захист від неповної/несумісної схеми БД при частковому деплої

    def _log(self, action: str, detail: str = ""):
        """Захищений виклик аудит-логу: ніколи не кидає виняток, навіть якщо
        self.db застарілий/несумісний (напр. неповний деплой без методу
        log_access). Втрата запису в лог не повинна ламати основну функцію."""
        if not self.autosave or not self.db:
            return
        try:
            self.db.log_access(self.profile_id, action, detail)
        except Exception:
            pass

    def _db_call(self, method_name: str, *args, default=None, **kwargs):
        """Універсальний захищений виклик self.db.<method_name>(...).

        Якщо задеплоєна версія TwinDatabase застаріла/несумісна (не має
        потрібного методу) або сам виклик впаде з будь-якої іншої причини,
        повертає `default` замість падіння всього застосунку. Використовується
        на «гарячому шляху» вхід → завантаження профілю → чат, щоб розбіжність
        версій файлів під час деплою не блокувала роботу двійника повністю.
        """
        if not self.db:
            return default
        method = getattr(self.db, method_name, None)
        if method is None:
            return default
        try:
            return method(*args, **kwargs)
        except Exception:
            return default

    # ---- Особистість / LLM ----
    def initialize_personality(self, config: PersonalityConfig):
        # Зберігаємо історію розмови та емоційний стан поточного ядра (якщо є),
        # щоб зміна особистості/застосування пресету не стирала активний чат.
        old_history = self.cognitive_engine.conversation_history if self.cognitive_engine else []
        old_emotion_history = self.cognitive_engine.emotional_state.emotion_history if self.cognitive_engine else []
        old_current_emotion = self.cognitive_engine.emotional_state.current_emotion if self.cognitive_engine else "neutral"

        self.personality = config
        self.cognitive_engine = CognitiveEngine(self.vector_db, config, llm_provider=self.llm_provider)
        self.cognitive_engine.conversation_history = old_history
        self.cognitive_engine.emotional_state.emotion_history = old_emotion_history
        self.cognitive_engine.emotional_state.current_emotion = old_current_emotion

        self.state["status"] = "personality_loaded"
        if self.autosave:
            self._db_call("save_personality", self.profile_id, self._personality_to_dict(config))

    def configure_llm(self, api_key: str, model: str = "claude-sonnet-5"):
        self.llm_provider = LLMProvider(api_key=api_key, model=model)
        if self.cognitive_engine:
            self.cognitive_engine.llm_provider = self.llm_provider
        if self.autosave and self.db:
            encrypted = self.encryption.encrypt(api_key, context=f"llm_key:{self.profile_id}")
            self._db_call("save_encrypted_secret", self.profile_id, encrypted)
            self._log("configure_llm", model)

    def llm_status(self) -> Dict:
        if not self.llm_provider:
            return {"configured": False, "available": False, "error": "API-ключ не заданий"}
        return {
            "configured": True,
            "available": self.llm_provider.is_available(),
            "model": self.llm_provider.model,
            "error": self.llm_provider.error(),
        }

    @staticmethod
    def _personality_to_dict(config: PersonalityConfig) -> Dict:
        from dataclasses import asdict
        return asdict(config)

    # ---- Аутентифікація ----
    def authenticate(self, method: str, credentials: Any) -> bool:
        result = self.access_control.authenticate(method, credentials)
        if result and self.autosave:
            self._log("login", method)
        return result

    def change_password(self, new_password: str, old_password: str = "") -> bool:
        ok = self.access_control.change_password(old_password, new_password)
        if ok:
            self.access_control.authenticate("password", new_password)
            if self.autosave:
                self._log("change_password")
        return ok

    # ---- Рольовий вхід за іменованими обліковими записами ----
    DEMO_ACCOUNTS = [
        ("owner", "owner2026", "owner", "👑 Власник"),
        ("family", "family2026", "family", "👨‍👩‍👧 Родина"),
        ("guest", "guest2026", "guest", "🚶 Гість"),
    ]

    def add_user(self, username: str, password: str, role: str):
        """Реєструє іменований обліковий запис із заданою роллю доступу."""
        self.access_control.add_user(username, password, role)
        self._log("add_user", f"{username}:{role}")

    def login_as(self, username: str, password: str) -> Optional[str]:
        """Вхід за логіном+паролем. Повертає роль при успіху, або None."""
        role = self.access_control.login(username, password)
        if role:
            self._log("login_as", f"{username}:{role}")
        return role

    def list_users(self) -> List[Dict]:
        return self.access_control.list_users()

    def current_username(self) -> Optional[str]:
        return self.access_control.current_username()

    def setup_demo_accounts(self):
        """Створює 3 тестові облікові записи (Власник/Родина/Гість) для демонстрації
        розмежування доступу за ролями — за зразком тестових акаунтів диспетчерських систем."""
        for username, password, role, _label in self.DEMO_ACCOUNTS:
            self.add_user(username, password, role)
        self._log("setup_demo_accounts")

    # ---- Основний цикл спілкування ----
    def process_message(self, user_input: str, user_id: str = "default") -> Dict:
        with self._lock:
            if not self.access_control.check_permission("talk"):
                return {"error": "Доступ заборонено. Авторизуйтесь."}

            self.state["last_interaction"] = datetime.now().isoformat()
            self.state["total_interactions"] += 1

            if not self.cognitive_engine:
                return {"error": "Особистість не ініціалізована"}

            response_text = self.cognitive_engine.generate_response(user_input)
            current_emotion = self.cognitive_engine.emotional_state.current_emotion

            self.avatar.set_expression(current_emotion)
            gesture = self.body_language.get_gesture_for_emotion(current_emotion)

            voice_data = None
            if self.voice.is_trained:
                try:
                    voice_data = self.voice.synthesize_speech(response_text, current_emotion)
                except RuntimeError:
                    pass

            self.legacy.check_activation(self.state)

            last_turn = self.cognitive_engine.conversation_history[-1]
            if self.autosave:
                self._db_call(
                    "append_conversation", self.profile_id, user_input, last_turn["twin"],
                    current_emotion, last_turn.get("mode", "template"),
                )
                self._db_call(
                    "append_emotion", self.profile_id, current_emotion,
                    self.cognitive_engine.emotional_state.emotion_intensity,
                    (self.cognitive_engine.emotional_state.emotion_history[-1].get("trigger", "")
                     if self.cognitive_engine.emotional_state.emotion_history else ""),
                )
                self._db_call("touch_profile", self.profile_id)

            return {
                "text": response_text,
                "emotion": current_emotion,
                "gesture": gesture,
                "voice": voice_data,
                "mode": last_turn.get("mode", "template"),
                "llm_error": last_turn.get("llm_error"),
                "timestamp": datetime.now().isoformat(),
                "session_stats": {"total_interactions": self.state["total_interactions"]},
            }

    def process_message_stream(self, user_input: str, user_id: str = "default"):
        """Потокова версія process_message — для живого виводу тексту в чаті.

        Генерує шматки тексту одразу, як вони приходять від LLM (або миттєво
        для шаблонного режиму). Побічні ефекти (збереження в БД, оновлення
        аватара/емоцій) виконуються один раз, коли генератор повністю вичерпано —
        тобто після того, як увесь текст показано користувачу.
        """
        if not self.access_control.check_permission("talk"):
            yield "Доступ заборонено. Авторизуйтесь."
            return
        if not self.cognitive_engine:
            yield "Особистість не ініціалізована."
            return

        with self._lock:
            self.state["last_interaction"] = datetime.now().isoformat()
            self.state["total_interactions"] += 1

        for chunk in self.cognitive_engine.generate_response_stream(user_input):
            yield chunk

        with self._lock:
            current_emotion = self.cognitive_engine.emotional_state.current_emotion
            self.avatar.set_expression(current_emotion)
            self.body_language.get_gesture_for_emotion(current_emotion)
            self.legacy.check_activation(self.state)

            last_turn = self.cognitive_engine.conversation_history[-1]
            if self.autosave:
                self._db_call(
                    "append_conversation", self.profile_id, user_input, last_turn["twin"],
                    current_emotion, last_turn.get("mode", "template"),
                )
                self._db_call(
                    "append_emotion", self.profile_id, current_emotion,
                    self.cognitive_engine.emotional_state.emotion_intensity,
                    (self.cognitive_engine.emotional_state.emotion_history[-1].get("trigger", "")
                     if self.cognitive_engine.emotional_state.emotion_history else ""),
                )
                self._db_call("touch_profile", self.profile_id)

    # ---- Пам'ять ----
    def import_memories(self, source_type: str, data: List[Dict]):
        if not self.access_control.check_permission("write"):
            raise PermissionError("Немає дозволу на запис")

        before_ids = {mid for mid, _, _ in self.vector_db.vectors}
        importer_method = getattr(self.memory_importer, f"import_{source_type}", None)
        if importer_method:
            importer_method(data)
        else:
            for item in data:
                self.vector_db.add_memory(json.dumps(item, ensure_ascii=False), {"source": source_type})

        if self.autosave:
            new_records = [r for r in self.vector_db.export_records() if r["id"] not in before_ids]
            if new_records:
                self._db_call("bulk_save_memories", self.profile_id, new_records)

    def enable_continuous_learning(self, sources: List[str]):
        self.continuous_learning.start()

        def on_update(update: Dict):
            print(f"[Auto-Learn] Нові дані з {update['source']}: {update['content'][:50]}...")
            if self.autosave:
                records = self.vector_db.export_records()
                if records:
                    self._db_call(
                        "save_memory",
                        self.profile_id, records[-1]["id"], records[-1]["text"],
                        records[-1]["vector"], records[-1]["metadata"],
                    )

        self.continuous_learning.on_update(on_update)

    def delete_memory(self, memory_id: str):
        if not self.access_control.check_permission("delete"):
            raise PermissionError("Немає дозволу на видалення")
        self.vector_db.delete_memory(memory_id)
        if self.autosave:
            self._db_call("delete_memory", self.profile_id, memory_id)
            self._log("delete_memory", memory_id)

    def update_memory(self, memory_id: str, new_text: str):
        if not self.access_control.check_permission("write"):
            raise PermissionError("Немає дозволу на запис")
        new_vector = self.vector_db.update_memory(memory_id, new_text)
        if new_vector is not None and self.autosave:
            self._db_call("update_memory_text", self.profile_id, memory_id, new_text, new_vector)
            self._log("update_memory", memory_id)

    def update_memory_metadata(self, memory_id: str, patch: Dict) -> bool:
        """Часткове оновлення метаданих спогаду (pinned, tags, security-рівень тощо)."""
        if not self.access_control.check_permission("write"):
            raise PermissionError("Немає дозволу на запис")
        found = self.vector_db.update_metadata(memory_id, patch)
        if found and self.autosave:
            record = next((r for r in self.vector_db.export_records() if r["id"] == memory_id), None)
            if record:
                self._db_call("save_memory", self.profile_id, record["id"], record["text"], record["vector"], record["metadata"])
                self._log("update_memory_metadata", memory_id)
        return found

    def toggle_memory_pin(self, memory_id: str) -> bool:
        memories = self.vector_db.get_all_memories()
        mem = next((m for m in memories if m["id"] == memory_id), None)
        new_pinned = not mem.get("metadata", {}).get("pinned", False) if mem else True
        self.update_memory_metadata(memory_id, {"pinned": new_pinned})
        return new_pinned

    def apply_builtin_preset(self, preset_name: str) -> bool:
        """Застосовує один із вбудованих швидких пресетів (PERSONALITY_PRESETS)."""
        if preset_name not in PERSONALITY_PRESETS:
            return False
        current = self._personality_to_dict(self.personality)
        current.update(PERSONALITY_PRESETS[preset_name])
        self.initialize_personality(PersonalityConfig(**current))
        if self.autosave:
            self._log("apply_builtin_preset", preset_name)
        return True

    def save_text_as_memory(self, text: str, source: str = "chat") -> str:
        """Швидке збереження довільного тексту (напр. репліки з чату) як нового спогаду."""
        if not self.access_control.check_permission("write"):
            raise PermissionError("Немає дозволу на запис")
        memory_id = self.vector_db.add_memory(text, {"source": source})
        if self.autosave:
            record = next((r for r in self.vector_db.export_records() if r["id"] == memory_id), None)
            if record:
                self._db_call("save_memory", self.profile_id, record["id"], record["text"], record["vector"], record["metadata"])
                self._log("save_text_as_memory", memory_id)
        return memory_id

    # ---- Пресети особистості ----
    def save_personality_preset(self, name: str) -> Optional[int]:
        if not self.autosave:
            return None
        preset_id = self._db_call("save_personality_preset", self.profile_id, name, self._personality_to_dict(self.personality))
        self._log("save_preset", name)
        return preset_id

    def list_personality_presets(self) -> List[Dict]:
        return self._db_call("list_personality_presets", self.profile_id, default=[])

    def apply_personality_preset(self, preset_id: int) -> bool:
        if not self.db:
            return False
        data = self._db_call("load_personality_preset", preset_id)
        if not data:
            return False
        self.initialize_personality(PersonalityConfig(**data))
        self._log("apply_preset", str(preset_id))
        return True

    def delete_personality_preset(self, preset_id: int):
        if self.db:
            self._db_call("delete_personality_preset", preset_id)

    # ---- Керування історією розмов ----
    def clear_conversation(self):
        if self.cognitive_engine:
            self.cognitive_engine.conversation_history = []
            self.cognitive_engine.emotional_state.emotion_history = []
            self.cognitive_engine.emotional_state.current_emotion = "neutral"
        self.state["total_interactions"] = 0
        if self.autosave:
            self._db_call("clear_conversation", self.profile_id)
            self._log("clear_conversation")

    def pop_last_turn(self) -> Optional[str]:
        """Видаляє останній хід розмови (для регенерації) і повертає текст користувача."""
        if not self.cognitive_engine or not self.cognitive_engine.conversation_history:
            return None
        last = self.cognitive_engine.conversation_history.pop()
        if self.cognitive_engine.emotional_state.emotion_history:
            self.cognitive_engine.emotional_state.emotion_history.pop()
        self.state["total_interactions"] = max(0, self.state["total_interactions"] - 1)
        if self.autosave:
            self._db_call("delete_last_conversation_turn", self.profile_id)
        return last["user"]

    # ---- Аудит ----
    def access_log(self, limit: int = 100) -> List[Dict]:
        return self._db_call("load_access_log", self.profile_id, limit, default=[])

    # ---- Резервне копіювання ----
    def backup_bytes(self) -> Optional[bytes]:
        return self._db_call("raw_backup_bytes", default=None)

    # ---- Експорт / Імпорт ----
    def export_data(self, security_level: SecurityLevel) -> Dict:
        if not self.access_control.check_permission("read"):
            raise PermissionError("Немає дозволу на читання")

        memories = self.vector_db.get_all_memories()
        filtered = [m for m in memories if self._check_security_level(m, security_level)]

        return {
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "personality": self._personality_to_dict(self.personality),
            "memories": filtered,
            "conversation_history": self.cognitive_engine.conversation_history if self.cognitive_engine else [],
            "emotional_history": self.cognitive_engine.emotional_state.emotion_history if self.cognitive_engine else [],
            "legacy": {
                "mode": self.legacy.mode,
                "beneficiaries": self.legacy.beneficiaries,
                "inactivity_days": self.legacy.inactivity_days,
            },
            "export_timestamp": datetime.now().isoformat(),
        }

    def import_full_state(self, data: Dict):
        """Відновлення повного стану з JSON-експорту (наприклад, в новому профілі)."""
        if not self.access_control.check_permission("write"):
            raise PermissionError("Немає дозволу на запис")

        personality = PersonalityConfig(**data.get("personality", {}))
        self.initialize_personality(personality)

        for mem in data.get("memories", []):
            meta = mem.get("metadata", {})
            self.vector_db.add_memory(mem["text"], meta)

        legacy = data.get("legacy", {})
        if legacy:
            self.legacy.configure(
                legacy.get("mode", "archive"),
                legacy.get("beneficiaries", []),
                legacy.get("inactivity_days", 90),
            )

        if self.autosave:
            records = self.vector_db.export_records()
            if records:
                self._db_call("bulk_save_memories", self.profile_id, records)

    def _check_security_level(self, memory: Dict, level: SecurityLevel) -> bool:
        meta = memory.get("metadata", {})
        mem_level = meta.get("security", "public")
        level_order = {
            SecurityLevel.PUBLIC: 0, SecurityLevel.FAMILY: 1,
            SecurityLevel.PRIVATE: 2, SecurityLevel.CRITICAL: 3,
        }
        try:
            mem_level_enum = SecurityLevel(mem_level)
        except ValueError:
            mem_level_enum = SecurityLevel.PUBLIC
        return level_order.get(level, 0) >= level_order.get(mem_level_enum, 0)

    def purge_all_data(self):
        if not self.access_control.check_permission("delete"):
            raise PermissionError("Немає дозволу на видалення")
        self.vector_db = VectorDatabase(embedder=build_default_embedder())
        self.cognitive_engine = None
        self.state = {"status": "purged", "timestamp": datetime.now().isoformat()}
        if self.autosave:
            self._db_call("delete_profile", self.profile_id)

    # ---- Персистентність профілю ----
    def load_from_db(self):
        """Завантажує стан профілю з бази даних (якщо профіль уже існує).

        Кожен окремий читання обгорнуто в захищений виклик: якщо задеплоєна
        версія TwinDatabase застаріла й не має якогось методу (розсинхрон
        файлів під час деплою), профіль все одно завантажиться настільки
        повно, наскільки це можливо, замість падіння всього застосунку.
        """
        if not self.db:
            return False

        personality_data = self._db_call("load_personality", self.profile_id)
        if personality_data:
            self.personality = PersonalityConfig(**personality_data)
            self.cognitive_engine = CognitiveEngine(self.vector_db, self.personality, llm_provider=self.llm_provider)

        records = self._db_call("load_memories", self.profile_id, default=[])
        if records:
            self.vector_db.load_records(records)

        if self.cognitive_engine:
            self.cognitive_engine.conversation_history = self._db_call(
                "load_conversation", self.profile_id, default=[])
            raw_emotions = self._db_call("load_emotion_history", self.profile_id, default=[])
            self.cognitive_engine.emotional_state.emotion_history = [
                {"emotion": e["emotion"], "intensity": e["intensity"], "trigger": e["trigger"], "timestamp": e["timestamp"]}
                for e in raw_emotions
            ]
            if self.cognitive_engine.emotional_state.emotion_history:
                self.cognitive_engine.emotional_state.current_emotion = \
                    self.cognitive_engine.emotional_state.emotion_history[-1]["emotion"]

        legacy_data = self._db_call("load_legacy", self.profile_id)
        if legacy_data:
            self.legacy.configure(legacy_data["mode"], legacy_data["beneficiaries"], legacy_data["inactivity_days"])
            self.legacy.is_active = legacy_data["is_active"]

        encrypted_key = self._db_call("load_encrypted_secret", self.profile_id)
        if encrypted_key and not self.llm_provider:
            try:
                api_key = self.encryption.decrypt(encrypted_key, context=f"llm_key:{self.profile_id}")
                self.configure_llm(api_key)
            except Exception:
                pass  # неможливо розшифрувати (інший master key) — пропускаємо

        self.state["total_interactions"] = len(self.cognitive_engine.conversation_history) if self.cognitive_engine else 0
        return True

    def save_legacy_config(self):
        if self.autosave:
            self._db_call(
                "save_legacy",
                self.profile_id, self.legacy.mode, self.legacy.beneficiaries,
                self.legacy.inactivity_days, self.legacy.is_active,
            )

    def get_status(self) -> Dict:
        return {
            "state": self.state,
            "memories_count": len(self.vector_db.vectors),
            "embedder": self.vector_db.embedder.name,
            "voice_status": self.voice.get_status(),
            "avatar_loaded": self.avatar.is_loaded,
            "personality_configured": self.cognitive_engine is not None,
            "llm": self.llm_status(),
            "security": {
                "authenticated": self.access_control._authenticated_user is not None,
                "user": self.access_control._authenticated_user,
            },
        }

# ============================================================================
# MODULE: ANALYTICS — Аналітика: обчислення статистики для дашборду (без прив'язки до UI).
# ============================================================================
def emotion_distribution(emotion_history: List[Dict]) -> Dict[str, int]:
    return dict(Counter(e["emotion"] for e in emotion_history))


def emotion_timeline(emotion_history: List[Dict]) -> List[Dict]:
    """Повертає [{timestamp, emotion, intensity}] відсортовано за часом."""
    return sorted(emotion_history, key=lambda e: e["timestamp"])


def memory_source_breakdown(memories: List[Dict]) -> Dict[str, int]:
    return dict(Counter(m.get("metadata", {}).get("source", "невідомо") for m in memories))


def conversation_activity_by_day(conversation_history: List[Dict]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for turn in conversation_history:
        ts = turn.get("timestamp", "")
        day = ts[:10] if ts else "невідомо"
        counts[day] = counts.get(day, 0) + 1
    return dict(sorted(counts.items()))


def top_words(memories: List[Dict], top_n: int = 15, stopwords: set = None) -> List[Dict]:
    """Найчастотніші слова в спогадах (проста, без зовнішніх залежностей)."""
    default_stop = {
        "і", "в", "на", "з", "до", "як", "що", "це", "та", "не", "за",
        "я", "ти", "він", "вона", "ми", "ви", "вони", "але", "або",
        "джерело", "невідомо", "щоденник", "повідомлення", "календар",
    }
    stopwords = stopwords or default_stop
    counter: Counter = Counter()
    for m in memories:
        text = m.get("text", "").lower()
        for raw_word in text.replace(":", " ").replace(",", " ").replace(".", " ").split():
            word = "".join(ch for ch in raw_word if ch.isalpha())
            if len(word) > 2 and word not in stopwords:
                counter[word] += 1
    return [{"word": w, "count": c} for w, c in counter.most_common(top_n)]


def response_mode_breakdown(conversation_history: List[Dict]) -> Dict[str, int]:
    """Скільки відповідей згенеровано через LLM vs шаблони."""
    return dict(Counter(turn.get("mode", "template") for turn in conversation_history))


EMOTION_VALENCE = {
    "happy": 1.0, "excited": 1.0, "nostalgic": 0.3, "thoughtful": 0.0,
    "neutral": 0.0, "anxious": -0.5, "sad": -0.7, "angry": -1.0,
}


def emotion_valence_timeline(emotion_history: List[Dict]) -> Dict[str, float]:
    """{timestamp: valence} — числовий ряд для графіка динаміки настрою в часі."""
    timeline = sorted(emotion_history, key=lambda e: e["timestamp"])
    return {
        e["timestamp"][:19]: EMOTION_VALENCE.get(e["emotion"], 0.0) * e.get("intensity", 0.5)
        for e in timeline
    }


def activity_by_hour(conversation_history: List[Dict]) -> Dict[str, int]:
    """Розподіл кількості повідомлень за годиною доби (00-23)."""
    counts = {f"{h:02d}": 0 for h in range(24)}
    for turn in conversation_history:
        ts = turn.get("timestamp", "")
        if len(ts) >= 13 and "T" in ts:
            hour = ts.split("T")[1][:2]
            if hour in counts:
                counts[hour] += 1
    return counts


def message_length_stats(conversation_history: List[Dict]) -> Dict[str, float]:
    """Середня довжина повідомлень користувача та двійника (у словах)."""
    if not conversation_history:
        return {"avg_user_words": 0.0, "avg_twin_words": 0.0}
    user_lens = [len(t.get("user", "").split()) for t in conversation_history]
    twin_lens = [len(t.get("twin", "").split()) for t in conversation_history]
    return {
        "avg_user_words": round(sum(user_lens) / len(user_lens), 1),
        "avg_twin_words": round(sum(twin_lens) / len(twin_lens), 1),
    }


def pinned_memories(memories: List[Dict]) -> List[Dict]:
    return [m for m in memories if m.get("metadata", {}).get("pinned")]


def summary_stats(status: Dict, memories: List[Dict], conversation_history: List[Dict],
                   emotion_history: List[Dict]) -> Dict:
    return {
        "memories_count": len(memories),
        "interactions_count": len(conversation_history),
        "dominant_emotion": Counter(e["emotion"] for e in emotion_history).most_common(1)[0][0]
        if emotion_history else "neutral",
        "sources": memory_source_breakdown(memories),
        "llm_usage_pct": round(
            100 * sum(1 for t in conversation_history if t.get("mode") == "llm") / len(conversation_history), 1
        ) if conversation_history else 0.0,
    }
