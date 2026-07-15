"""
================================================================================
DIGITAL TWIN — Повна реалізація цифрового двійника на Python
================================================================================
Архітектура:
  1. Візуальна та звукова ідентичність (аватар, голос, міміка)
  2. Когнітивна модель та особистість (LLM, цінності, емоції)
  3. База знань та пам'ять (RAG, векторна БД, continuous learning)
  4. Технічна інфраструктура (оркестратор, інтерфейс)
  5. Безпека, етика та контроль (аутентифікація, шифрування, спадщина)
================================================================================
"""

import os
import json
import hashlib
import secrets
import asyncio
import base64
import sqlite3
import pickle
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple, Any, Callable
from enum import Enum
from pathlib import Path
import threading
import queue
import time
import re

# ============================================================================
# МОДУЛЬ 1: БЕЗПЕКА, ЕТИКА ТА КОНТРОЛЬ
# ============================================================================

class SecurityLevel(Enum):
    """Рівні безпеки доступу до даних двійника."""
    PUBLIC = "public"           # Загальнодоступна інформація
    FAMILY = "family"           # Доступно родичам
    PRIVATE = "private"         # Особисті дані
    CRITICAL = "critical"       # Найчутливіші дані (фінанси, паролі)


@dataclass
class BiometricProfile:
    """Біометричний профіль власника для автентифікації."""
    voice_hash: str = ""
    face_embedding: List[float] = field(default_factory=list)
    fingerprint_hash: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def verify_voice(self, voice_sample: bytes) -> bool:
        """Перевірка голосу за хешем."""
        sample_hash = hashlib.sha256(voice_sample).hexdigest()
        # У реальності тут був би ML-модуль розпізнавання
        return secrets.compare_digest(sample_hash, self.voice_hash)


class EncryptionManager:
    """Менеджер шифрування для захисту даних двійника."""

    def __init__(self, master_key: Optional[bytes] = None):
        self.master_key = master_key or secrets.token_bytes(32)
        self._key_cache: Dict[str, bytes] = {}

    def _derive_key(self, context: str) -> bytes:
        """Виведення ключа для конкретного контексту."""
        if context not in self._key_cache:
            derived = hashlib.pbkdf2_hmac(
                'sha256', self.master_key, context.encode(), 100000
            )
            self._key_cache[context] = derived
        return self._key_cache[context]

    def encrypt(self, data: str, context: str = "default") -> str:
        """Шифрування даних AES-подібним способом (XOR для демо)."""
        key = self._derive_key(context)
        data_bytes = data.encode('utf-8')
        encrypted = bytearray()
        for i, byte in enumerate(data_bytes):
            encrypted.append(byte ^ key[i % len(key)])
        return base64.b64encode(bytes(encrypted)).decode()

    def decrypt(self, encrypted_data: str, context: str = "default") -> str:
        """Розшифрування даних."""
        key = self._derive_key(context)
        data_bytes = base64.b64decode(encrypted_data.encode())
        decrypted = bytearray()
        for i, byte in enumerate(data_bytes):
            decrypted.append(byte ^ key[i % len(key)])
        return bytes(decrypted).decode('utf-8')


class AccessControl:
    """Система контролю доступу до двійника."""

    def __init__(self):
        self._authenticated_user: Optional[str] = None
        self._permissions: Dict[str, List[str]] = {
            "owner": ["read", "write", "delete", "configure", "talk"],
            "family": ["read", "talk"],
            "guest": ["talk"]
        }
        self._session_expiry: Optional[datetime] = None
        self._biometric_profile: Optional[BiometricProfile] = None

    def register_biometrics(self, profile: BiometricProfile):
        """Реєстрація біометричного профілю власника."""
        self._biometric_profile = profile

    def authenticate(self, method: str, credentials: Any) -> bool:
        """Аутентифікація користувача."""
        if method == "biometric" and self._biometric_profile:
            # Перевірка біометрії
            verified = self._biometric_profile.verify_voice(credentials)
            if verified:
                self._authenticated_user = "owner"
                self._session_expiry = datetime.now() + timedelta(hours=1)
            return verified
        elif method == "password":
            # Хешування пароля для порівняння
            password_hash = hashlib.sha256(credentials.encode()).hexdigest()
            # У реальності — перевірка з БД
            self._authenticated_user = "owner"
            self._session_expiry = datetime.now() + timedelta(hours=1)
            return True
        return False

    def check_permission(self, action: str) -> bool:
        """Перевірка дозволу на дію."""
        if not self._authenticated_user:
            return False
        if datetime.now() > self._session_expiry:
            self._authenticated_user = None
            return False
        return action in self._permissions.get(self._authenticated_user, [])

    def logout(self):
        """Вихід із системи."""
        self._authenticated_user = None
        self._session_expiry = None


class LegacyProtocol:
    """Протокол спадщини — керування долею двійника після смерті власника."""

    INHERITANCE_MODES = {
        "delete": "Автоматичне видалення всіх даних",
        "archive": "Архівація для родини (тільки спогади)",
        "active": "Залишити активним для родини",
        "public": "Публічний меморіал (обмежені дані)"
    }

    def __init__(self):
        self.mode: str = "archive"
        self.beneficiaries: List[str] = []
        self.trigger_conditions: List[Callable] = []
        self.activation_date: Optional[datetime] = None
        self.is_active: bool = False

    def configure(self, mode: str, beneficiaries: List[str] = None):
        """Налаштування протоколу спадщини."""
        if mode not in self.INHERITANCE_MODES:
            raise ValueError(f"Невідомий режим: {mode}")
        self.mode = mode
        self.beneficiaries = beneficiaries or []

    def add_trigger(self, condition: Callable):
        """Додавання умови активації (наприклад, відсутність активності 90 днів)."""
        self.trigger_conditions.append(condition)

    def check_activation(self, twin_state: Dict) -> bool:
        """Перевірка, чи час активувати протокол."""
        for condition in self.trigger_conditions:
            if condition(twin_state):
                self.is_active = True
                self.activation_date = datetime.now()
                return True
        return False

    def execute(self, twin) -> Dict:
        """Виконання протоколу спадщини."""
        if not self.is_active:
            return {"status": "inactive"}

        result = {"mode": self.mode, "timestamp": datetime.now().isoformat()}

        if self.mode == "delete":
            twin.purge_all_data()
            result["action"] = "all_data_deleted"
        elif self.mode == "archive":
            archive = twin.export_memories(security_level=SecurityLevel.FAMILY)
            result["action"] = "archived_for_family"
            result["archive_size"] = len(archive)
        elif self.mode == "active":
            twin.restrict_to_family_mode(self.beneficiaries)
            result["action"] = "family_mode_activated"

        return result


# ============================================================================
# МОДУЛЬ 2: БАЗА ЗНАНЬ ТА ПАМ'ЯТЬ (RAG)
# ============================================================================

class VectorDatabase:
    """Векторна база даних для RAG (Retrieval-Augmented Generation)."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.vectors: List[Tuple[str, List[float], Dict]] = []  # (id, vector, metadata)
        self.text_store: Dict[str, str] = {}  # Зберігання оригінальних текстів

    def _simple_embedding(self, text: str) -> List[float]:
        """Спрощене векторне представлення тексту (для демо).
        У реальності — використовувати sentence-transformers."""
        # Хеш-основане векторне кодування
        hash_val = hashlib.md5(text.encode()).hexdigest()
        vec = []
        for i in range(self.dimension):
            seed = int(hash_val[i % 32], 16) + i
            vec.append((seed % 100) / 100.0)
        # Нормалізація
        norm = sum(x**2 for x in vec) ** 0.5
        return [x / norm for x in vec] if norm > 0 else vec

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """Обчислення косинусної схожості."""
        dot = sum(a * b for a, b in zip(v1, v2))
        return dot  # Вже нормалізовані

    def add_memory(self, text: str, metadata: Dict = None) -> str:
        """Додавання спогаду у векторну БД."""
        memory_id = hashlib.sha256(f"{text}{time.time()}".encode()).hexdigest()[:16]
        vector = self._simple_embedding(text)
        self.vectors.append((memory_id, vector, metadata or {}))
        self.text_store[memory_id] = text
        return memory_id

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Пошук релевантних спогадів."""
        query_vec = self._simple_embedding(query)
        similarities = []

        for mem_id, vec, meta in self.vectors:
            sim = self._cosine_similarity(query_vec, vec)
            similarities.append((sim, mem_id, meta))

        similarities.sort(reverse=True)
        results = []
        for sim, mem_id, meta in similarities[:top_k]:
            results.append({
                "id": mem_id,
                "text": self.text_store.get(mem_id, ""),
                "similarity": sim,
                "metadata": meta
            })
        return results

    def get_all_memories(self) -> List[Dict]:
        """Отримання всіх спогадів."""
        return [
            {"id": mid, "text": self.text_store.get(mid, ""), "metadata": meta}
            for mid, _, meta in self.vectors
        ]


class MemoryImporter:
    """Імпортер даних з різних джерел для бази знань."""

    SUPPORTED_SOURCES = ["diary", "social_media", "messages", "books", "photos", "calendar", "email"]

    def __init__(self, vector_db: VectorDatabase):
        self.vector_db = vector_db
        self.import_stats: Dict[str, int] = {source: 0 for source in self.SUPPORTED_SOURCES}

    def import_diary(self, entries: List[Dict]):
        """Імпорт щоденникових записів."""
        for entry in entries:
            text = f"Щоденник [{entry.get('date', 'невідомо')}]: {entry.get('content', '')}"
            self.vector_db.add_memory(text, {"source": "diary", "date": entry.get("date")})
            self.import_stats["diary"] += 1

    def import_social_media(self, posts: List[Dict]):
        """Імпорт постів з соцмереж."""
        for post in posts:
            text = f"Соцмережа [{post.get('platform', '')}]: {post.get('content', '')}"
            self.vector_db.add_memory(text, {"source": "social_media", "platform": post.get("platform")})
            self.import_stats["social_media"] += 1

    def import_messages(self, messages: List[Dict]):
        """Імпорт листування."""
        for msg in messages:
            text = f"Повідомлення від {msg.get('from', 'невідомо')}: {msg.get('content', '')}"
            self.vector_db.add_memory(text, {"source": "messages", "contact": msg.get("from")})
            self.import_stats["messages"] += 1

    def import_calendar(self, events: List[Dict]):
        """Імпорт подій календаря."""
        for event in events:
            text = f"Календар [{event.get('date', '')}]: {event.get('title', '')} — {event.get('description', '')}"
            self.vector_db.add_memory(text, {"source": "calendar", "date": event.get("date")})
            self.import_stats["calendar"] += 1

    def get_stats(self) -> Dict:
        """Статистика імпорту."""
        return self.import_stats.copy()


class ContinuousLearning:
    """Модуль безперервного навчання — оновлення бази знань у реальному часі."""

    def __init__(self, vector_db: VectorDatabase):
        self.vector_db = vector_db
        self.update_queue: queue.Queue = queue.Queue()
        self.is_running: bool = False
        self._worker_thread: Optional[threading.Thread] = None
        self.update_callbacks: List[Callable] = []

    def start(self):
        """Запуск фонового потоку оновлення."""
        self.is_running = True
        self._worker_thread = threading.Thread(target=self._process_updates, daemon=True)
        self._worker_thread.start()

    def stop(self):
        """Зупинка фонового потоку."""
        self.is_running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=2)

    def _process_updates(self):
        """Обробка черги оновлень."""
        while self.is_running:
            try:
                update = self.update_queue.get(timeout=1)
                self._integrate_update(update)
            except queue.Empty:
                continue

    def _integrate_update(self, update: Dict):
        """Інтеграція нових даних у базу знань."""
        source = update.get("source")
        content = update.get("content")

        if source and content:
            self.vector_db.add_memory(content, {
                "source": source,
                "timestamp": datetime.now().isoformat(),
                "auto_imported": True
            })
            for callback in self.update_callbacks:
                callback(update)

    def add_update(self, source: str, content: str):
        """Додавання нового оновлення в чергу."""
        self.update_queue.put({"source": source, "content": content})

    def on_update(self, callback: Callable):
        """Реєстрація callback для сповіщень про оновлення."""
        self.update_callbacks.append(callback)


# ============================================================================
# МОДУЛЬ 3: КОГНІТИВНА МОДЕЛЬ ТА ОСОБИСТІСТЬ
# ============================================================================

@dataclass
class PersonalityConfig:
    """Конфігурація особистості цифрового двійника."""

    # Мовні характеристики
    vocabulary_style: str = "neutral"  # formal, casual, slang, poetic
    favorite_phrases: List[str] = field(default_factory=list)
    speech_formality: float = 0.5  # 0-1
    humor_level: float = 0.5  # 0-1

    # Цінності та переконання
    political_stance: str = "neutral"
    religious_views: str = "agnostic"
    work_ethic: str = "balanced"
    family_values: str = "important"

    # Емоційні патерни
    stress_reaction: str = "analytical"  # analytical, emotional, avoidant
    joy_expression: str = "enthusiastic"  # enthusiastic, calm, reserved
    criticism_response: str = "defensive"  # defensive, accepting, dismissive

    # Словниковий запас
    common_words: List[str] = field(default_factory=list)
    slang_terms: List[str] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        """Формування контексту для LLM."""
        return f"""Ти — цифровий двійник людини з такими характеристиками:
- Стиль мовлення: {self.vocabulary_style}
- Рівень формальності: {self.speech_formality * 100:.0f}%
- Почуття гумору: {self.humor_level * 100:.0f}%
- Реакція на стрес: {self.stress_reaction}
- Вираження радості: {self.joy_expression}
- Реакція на критику: {self.criticism_response}
- Улюблені фрази: {', '.join(self.favorite_phrases[:5]) if self.favorite_phrases else 'немає'}
- Часто вживані слова: {', '.join(self.common_words[:10]) if self.common_words else 'стандартні'}
"""


class EmotionalState:
    """Модуль емоційного інтелекту двійника."""

    EMOTIONS = ["neutral", "happy", "sad", "angry", "anxious", "excited", "nostalgic", "thoughtful"]

    def __init__(self):
        self.current_emotion: str = "neutral"
        self.emotion_intensity: float = 0.3  # 0-1
        self.emotion_history: List[Dict] = []
        self._lock = threading.Lock()

    def set_emotion(self, emotion: str, intensity: float = 0.5, trigger: str = ""):
        """Встановлення емоційного стану."""
        with self._lock:
            if emotion not in self.EMOTIONS:
                emotion = "neutral"
            self.current_emotion = emotion
            self.emotion_intensity = max(0, min(1, intensity))
            self.emotion_history.append({
                "emotion": emotion,
                "intensity": intensity,
                "trigger": trigger,
                "timestamp": datetime.now().isoformat()
            })

    def react_to_input(self, text: str, personality: PersonalityConfig) -> str:
        """Формування емоційної реакції на вхідний текст."""
        text_lower = text.lower()

        # Аналіз тональності (спрощений)
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
        elif pos_count > neg_count:
            if personality.joy_expression == "enthusiastic":
                self.set_emotion("happy", 0.7, "positive_input")
            else:
                self.set_emotion("happy", 0.4, "positive_input")
        elif neg_count > pos_count:
            self.set_emotion("sad", 0.5, "negative_input")

        return self.current_emotion

    def get_emotional_prefix(self) -> str:
        """Отримання емоційного префікса для відповіді."""
        prefixes = {
            "happy": "[з радістю] ",
            "sad": "[з сумом] ",
            "angry": "[з обуренням] ",
            "anxious": "[з хвилюванням] ",
            "excited": "[з ентузіазмом] ",
            "nostalgic": "[з ностальгією] ",
            "thoughtful": "[задумавшись] ",
            "neutral": ""
        }
        return prefixes.get(self.current_emotion, "")


class CognitiveEngine:
    """Когнітивний двигун — генерація відповідей на основі особистості та пам'яті."""

    def __init__(self, vector_db: VectorDatabase, personality: PersonalityConfig):
        self.vector_db = vector_db
        self.personality = personality
        self.emotional_state = EmotionalState()
        self.conversation_history: List[Dict] = []
        self._response_templates = self._load_templates()

    def _load_templates(self) -> Dict:
        """Завантаження шаблонів відповідей."""
        return {
            "greeting": [
                "Привіт! Радий тебе бачити.",
                "О, привіт! Як справи?",
                "Здоров був! Чим можу допомогти?"
            ],
            "memory_recall": [
                "О, це нагадує мені про... {memory}",
                "Знаєш, якось було схоже... {memory}",
                "Це мені нагадує: {memory}"
            ],
            "unknown": [
                "Чесно кажучи, не пам'ятаю такого.",
                "Мабуть, це було до мого часу, або я просто забув.",
                "Не можу пригадати, але звучить цікаво."
            ],
            "opinion": [
                "Як на мене, {opinion}",
                "Моя думка така: {opinion}",
                "Я б сказав, що {opinion}"
            ]
        }

    def _retrieve_context(self, query: str) -> str:
        """Отримання релевантного контексту з пам'яті."""
        memories = self.vector_db.search(query, top_k=3)
        if not memories or memories[0]["similarity"] < 0.5:
            return ""

        context_parts = []
        for mem in memories:
            context_parts.append(f"- {mem['text']}")

        return "\n".join(context_parts)

    def _apply_personality(self, response: str) -> str:
        """Застосування особистісних характеристик до відповіді."""
        # Додавання улюблених фраз
        if self.personality.favorite_phrases and secrets.randbelow(100) < 30:
            phrase = secrets.choice(self.personality.favorite_phrases)
            response = f"{phrase} {response}"

        # Застосування формальності
        if self.personality.speech_formality > 0.7:
            response = response.replace("ти", "Ви").replace("тебе", "Вас")
        elif self.personality.speech_formality < 0.3:
            response = response.replace("Ви", "ти").replace("Вас", "тебе")

        # Додавання сленгу
        if self.personality.slang_terms and self.personality.speech_formality < 0.4:
            if secrets.randbelow(100) < 20:
                slang = secrets.choice(self.personality.slang_terms)
                response += f" {slang}"

        return response

    def generate_response(self, user_input: str) -> str:
        """Генерація відповіді на вхідне повідомлення."""
        # Визначення емоційної реакції
        self.emotional_state.react_to_input(user_input, self.personality)

        # Отримання контексту з пам'яті
        context = self._retrieve_context(user_input)

        # Базова генерація відповіді
        if any(g in user_input.lower() for g in ["привіт", "здоров", "hi", "hello"]):
            response = secrets.choice(self._response_templates["greeting"])
        elif context:
            memory_text = context.split("\n")[0].replace("- ", "")
            template = secrets.choice(self._response_templates["memory_recall"])
            response = template.format(memory=memory_text)
        else:
            # Генерація на основі особистості
            opinion = self._generate_opinion(user_input)
            template = secrets.choice(self._response_templates["opinion"])
            response = template.format(opinion=opinion)

        # Застосування особистості та емоцій
        response = self._apply_personality(response)
        emotional_prefix = self.emotional_state.get_emotional_prefix()
        response = emotional_prefix + response

        # Збереження в історію
        self.conversation_history.append({
            "user": user_input,
            "twin": response,
            "emotion": self.emotional_state.current_emotion,
            "timestamp": datetime.now().isoformat()
        })

        return response

    def _generate_opinion(self, topic: str) -> str:
        """Генерація думки на основі цінностей."""
        # Спрощена логіка на основі цінностей
        if "робота" in topic.lower() or "кар'єра" in topic.lower():
            if self.personality.work_ethic == "dedicated":
                return "робота — це важлива частина життя, і до неї треба ставитися серйозно"
            elif self.personality.work_ethic == "balanced":
                return "важливо збалансувати роботу та особисте життя"
            else:
                return "головне — не перетворювати роботу на єдиний сенс життя"

        if "сім" in topic.lower() or "родин" in topic.lower():
            if self.personality.family_values == "important":
                return "сім'я — це найголовніше в житті"
            else:
                return "сім'я важлива, але кожен сам визначає її роль"

        return "тут важливо подумати з різних боків і знайти баланс"


# ============================================================================
# МОДУЛЬ 4: ВІЗУАЛЬНА ТА ЗВУКОВА ІДЕНТИЧНІСТЬ
# ============================================================================

class VoiceCloning:
    """Модуль клонування голосу (інтерфейс для інтеграції з ElevenLabs)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.voice_profile: Optional[Dict] = None
        self.sample_count: int = 0
        self.is_trained: bool = False

    def add_training_sample(self, audio_data: bytes, transcript: str) -> bool:
        """Додавання навчального зразка голосу."""
        # У реальності — відправка на API ElevenLabs
        self.sample_count += 1
        if self.sample_count >= 10:  # Мінімум 10 зразків
            self.is_trained = True
        return True

    def synthesize_speech(self, text: str, emotion: str = "neutral") -> bytes:
        """Синтез мовлення з клонованим голосом."""
        if not self.is_trained:
            raise RuntimeError("Голос ще не навчено. Потрібно мінімум 10 зразків.")

        # У реальності — виклик API ElevenLabs
        # Тут повертаємо заглушку
        return f"[SYNTHESIZED_VOICE: {text[:50]}... emotion={emotion}]".encode()

    def get_status(self) -> Dict:
        """Статус навчання голосу."""
        return {
            "trained": self.is_trained,
            "samples": self.sample_count,
            "ready": self.sample_count >= 10
        }


class Avatar3D:
    """3D-аватар (інтерфейс для інтеграції з Unreal Engine MetaHuman)."""

    def __init__(self):
        self.model_path: Optional[str] = None
        self.face_scan_data: Optional[Dict] = None
        self.body_scan_data: Optional[Dict] = None
        self.expressions: Dict[str, Dict] = {}
        self.is_loaded: bool = False

    def load_from_scan(self, face_scan: Dict, body_scan: Dict):
        """Завантаження аватара з 3D-сканування."""
        self.face_scan_data = face_scan
        self.body_scan_data = body_scan
        self.is_loaded = True

    def set_expression(self, emotion: str, intensity: float = 0.5):
        """Встановлення виразу обличчя."""
        self.expressions[emotion] = {
            "intensity": intensity,
            "active": True,
            "timestamp": datetime.now().isoformat()
        }

    def animate_lips(self, phonemes: List[str], duration: float):
        """Анімація губ (lip-sync)."""
        # У реальності — відправка команд до Unreal Engine
        return {
            "phonemes": phonemes,
            "duration": duration,
            "status": "animating"
        }

    def render_frame(self) -> Dict:
        """Рендеринг кадру аватара."""
        if not self.is_loaded:
            return {"status": "not_loaded"}

        return {
            "status": "rendered",
            "expressions": self.expressions,
            "timestamp": datetime.now().isoformat()
        }


class BodyLanguage:
    """Модуль мови тіла та міміки."""

    def __init__(self):
        self.gestures: Dict[str, Dict] = {}
        self.blink_rate: float = 0.15  # разів на секунду
        self.micro_expressions: List[str] = []

    def capture_gesture(self, name: str, joint_positions: List[Tuple[float, float, float]]):
        """Захоплення жесту з трекінгу."""
        self.gestures[name] = {
            "joints": joint_positions,
            "captured_at": datetime.now().isoformat()
        }

    def get_gesture_for_emotion(self, emotion: str) -> Optional[str]:
        """Отримання типового жесту для емоції."""
        gesture_map = {
            "happy": "open_arms",
            "sad": "head_down",
            "thoughtful": "chin_touch",
            "angry": "fist_clench",
            "neutral": "relaxed_posture"
        }
        return gesture_map.get(emotion, "relaxed_posture")

    def generate_blink(self) -> Dict:
        """Генерація кліпання очима."""
        return {
            "action": "blink",
            "duration": 0.15,
            "timestamp": datetime.now().isoformat()
        }


# ============================================================================
# МОДУЛЬ 5: ТЕХНІЧНА ІНФРАСТРУКТУРА (ОРКЕСТРАТОР)
# ============================================================================

class Orchestrator:
    """Оркестратор — центральний модуль координації всіх компонентів."""

    def __init__(self):
        # Ініціалізація компонентів
        self.encryption = EncryptionManager()
        self.access_control = AccessControl()
        self.legacy = LegacyProtocol()

        self.vector_db = VectorDatabase()
        self.memory_importer = MemoryImporter(self.vector_db)
        self.continuous_learning = ContinuousLearning(self.vector_db)

        self.personality = PersonalityConfig()
        self.cognitive_engine: Optional[CognitiveEngine] = None

        self.voice = VoiceCloning()
        self.avatar = Avatar3D()
        self.body_language = BodyLanguage()

        self.state: Dict = {
            "status": "initialized",
            "last_interaction": None,
            "total_interactions": 0,
            "active_sessions": 0
        }
        self._lock = threading.RLock()

    def initialize_personality(self, config: PersonalityConfig):
        """Ініціалізація особистості двійника."""
        self.personality = config
        self.cognitive_engine = CognitiveEngine(self.vector_db, config)
        self.state["status"] = "personality_loaded"

    def authenticate(self, method: str, credentials: Any) -> bool:
        """Аутентифікація користувача."""
        return self.access_control.authenticate(method, credentials)

    def process_message(self, user_input: str, user_id: str = "default") -> Dict:
        """Обробка повідомлення користувача."""
        with self._lock:
            # Перевірка доступу
            if not self.access_control.check_permission("talk"):
                return {"error": "Доступ заборонено. Авторизуйтесь."}

            # Оновлення стану
            self.state["last_interaction"] = datetime.now().isoformat()
            self.state["total_interactions"] += 1

            # Когнітивна обробка
            if not self.cognitive_engine:
                return {"error": "Особистість не ініціалізована"}

            response_text = self.cognitive_engine.generate_response(user_input)
            current_emotion = self.cognitive_engine.emotional_state.current_emotion

            # Візуальна складова
            self.avatar.set_expression(current_emotion)
            gesture = self.body_language.get_gesture_for_emotion(current_emotion)

            # Звукова складова
            voice_data = None
            if self.voice.is_trained:
                try:
                    voice_data = self.voice.synthesize_speech(response_text, current_emotion)
                except RuntimeError:
                    pass

            # Перевірка протоколу спадщини
            self.legacy.check_activation(self.state)

            return {
                "text": response_text,
                "emotion": current_emotion,
                "gesture": gesture,
                "voice": voice_data,
                "timestamp": datetime.now().isoformat(),
                "session_stats": {
                    "total_interactions": self.state["total_interactions"]
                }
            }

    def import_memories(self, source_type: str, data: List[Dict]):
        """Імпорт спогадів з зовнішніх джерел."""
        if not self.access_control.check_permission("write"):
            raise PermissionError("Немає дозволу на запис")

        importer_method = getattr(self.memory_importer, f"import_{source_type}", None)
        if importer_method:
            importer_method(data)
        else:
            # Загальний імпорт
            for item in data:
                text = json.dumps(item)
                self.vector_db.add_memory(text, {"source": source_type})

    def enable_continuous_learning(self, sources: List[str]):
        """Увімкнення безперервного навчання."""
        self.continuous_learning.start()

        def on_update(update: Dict):
            print(f"[Auto-Learn] Нові дані з {update['source']}: {update['content'][:50]}...")

        self.continuous_learning.on_update(on_update)

    def export_data(self, security_level: SecurityLevel) -> Dict:
        """Експорт даних двійника."""
        if not self.access_control.check_permission("read"):
            raise PermissionError("Немає дозволу на читання")

        memories = self.vector_db.get_all_memories()

        # Фільтрація за рівнем безпеки
        filtered_memories = [
            m for m in memories
            if self._check_security_level(m, security_level)
        ]

        return {
            "personality": asdict(self.personality),
            "memories": filtered_memories,
            "conversation_history": self.cognitive_engine.conversation_history if self.cognitive_engine else [],
            "emotional_history": self.cognitive_engine.emotional_state.emotion_history if self.cognitive_engine else [],
            "export_timestamp": datetime.now().isoformat()
        }

    def _check_security_level(self, memory: Dict, level: SecurityLevel) -> bool:
        """Перевірка рівня безпеки спогаду."""
        meta = memory.get("metadata", {})
        mem_level = meta.get("security", "public")

        level_order = {
            SecurityLevel.PUBLIC: 0,
            SecurityLevel.FAMILY: 1,
            SecurityLevel.PRIVATE: 2,
            SecurityLevel.CRITICAL: 3
        }

        return level_order.get(level, 0) >= level_order.get(SecurityLevel(mem_level), 0)

    def purge_all_data(self):
        """Повне видалення всіх даних (для протоколу спадщини)."""
        if not self.access_control.check_permission("delete"):
            raise PermissionError("Немає дозволу на видалення")

        self.vector_db = VectorDatabase()
        self.cognitive_engine = None
        self.state = {"status": "purged", "timestamp": datetime.now().isoformat()}

    def get_status(self) -> Dict:
        """Отримання статусу системи."""
        return {
            "state": self.state,
            "memories_count": len(self.vector_db.vectors),
            "voice_status": self.voice.get_status(),
            "avatar_loaded": self.avatar.is_loaded,
            "personality_configured": self.cognitive_engine is not None,
            "security": {
                "authenticated": self.access_control._authenticated_user is not None,
                "user": self.access_control._authenticated_user
            }
        }


# ============================================================================
# МОДУЛЬ 6: ІНТЕРФЕЙСИ ВЗАЄМОДІЇ
# ============================================================================

class WebInterface:
    """Веб-інтерфейс для взаємодії з двійником."""

    def __init__(self, orchestrator: Orchestrator):
        self.orchestrator = orchestrator
        self.routes: Dict[str, Callable] = {
            "/": self._handle_root,
            "/chat": self._handle_chat,
            "/status": self._handle_status,
            "/auth": self._handle_auth,
            "/import": self._handle_import,
            "/export": self._handle_export,
            "/configure": self._handle_configure
        }

    def _handle_root(self, request: Dict) -> Dict:
        """Головна сторінка."""
        return {
            "status": "Digital Twin API",
            "version": "1.0.0",
            "endpoints": list(self.routes.keys())
        }

    def _handle_chat(self, request: Dict) -> Dict:
        """Обробка чат-повідомлення."""
        message = request.get("message", "")
        if not message:
            return {"error": "Повідомлення не може бути порожнім"}

        result = self.orchestrator.process_message(message)
        return result

    def _handle_status(self, request: Dict) -> Dict:
        """Статус системи."""
        return self.orchestrator.get_status()

    def _handle_auth(self, request: Dict) -> Dict:
        """Аутентифікація."""
        method = request.get("method", "password")
        credentials = request.get("credentials", "")
        success = self.orchestrator.authenticate(method, credentials)
        return {"authenticated": success}

    def _handle_import(self, request: Dict) -> Dict:
        """Імпорт даних."""
        source = request.get("source", "")
        data = request.get("data", [])
        try:
            self.orchestrator.import_memories(source, data)
            return {"status": "imported", "source": source, "count": len(data)}
        except Exception as e:
            return {"error": str(e)}

    def _handle_export(self, request: Dict) -> Dict:
        """Експорт даних."""
        level = request.get("level", "public")
        try:
            data = self.orchestrator.export_data(SecurityLevel(level))
            return {"data": data}
        except Exception as e:
            return {"error": str(e)}

    def _handle_configure(self, request: Dict) -> Dict:
        """Налаштування особистості."""
        config_data = request.get("personality", {})
        config = PersonalityConfig(**config_data)
        self.orchestrator.initialize_personality(config)
        return {"status": "personality_configured"}

    def handle_request(self, path: str, request: Dict) -> Dict:
        """Обробка HTTP-подібного запиту."""
        handler = self.routes.get(path, lambda r: {"error": "Not found"})
        return handler(request)


class TelegramBot:
    """Telegram-бот інтерфейс."""

    def __init__(self, orchestrator: Orchestrator, bot_token: str = ""):
        self.orchestrator = orchestrator
        self.bot_token = bot_token
        self.authorized_users: set = set()

    def process_update(self, update: Dict) -> Dict:
        """Обробка оновлення від Telegram."""
        message = update.get("message", {})
        text = message.get("text", "")
        user_id = message.get("from", {}).get("id", "")

        if text.startswith("/start"):
            return {"text": "Привіт! Я твій цифровий двійник. Авторизуйся командою /auth"}

        elif text.startswith("/auth"):
            password = text.split(maxsplit=1)[1] if len(text.split()) > 1 else ""
            success = self.orchestrator.authenticate("password", password)
            if success:
                self.authorized_users.add(user_id)
            return {"text": "Авторизовано!" if success else "Невірний пароль"}

        elif user_id not in self.authorized_users:
            return {"text": "Спочатку авторизуйся: /auth <пароль>"}

        elif text.startswith("/status"):
            status = self.orchestrator.get_status()
            return {"text": json.dumps(status, indent=2, ensure_ascii=False)}

        else:
            result = self.orchestrator.process_message(text)
            return {"text": result.get("text", "...")}


class VRInterface:
    """VR-інтерфейс для віртуальної реальності."""

    def __init__(self, orchestrator: Orchestrator):
        self.orchestrator = orchestrator
        self.session_active: bool = False
        self.headset_position: Tuple[float, float, float] = (0, 0, 0)

    def start_session(self) -> Dict:
        """Початок VR-сесії."""
        self.session_active = True
        return {
            "status": "vr_session_started",
            "avatar": self.orchestrator.avatar.render_frame(),
            "instructions": "Подивіться на аватара, щоб почати розмову"
        }

    def process_voice_input(self, audio_data: bytes) -> Dict:
        """Обробка голосового вводу в VR."""
        # Розпізнавання мовлення (у реальності — Whisper API)
        recognized_text = "[розпізнаний текст з голосу]"

        result = self.orchestrator.process_message(recognized_text)

        # Оновлення аватара
        self.orchestrator.avatar.set_expression(result.get("emotion", "neutral"))

        return {
            "recognized_text": recognized_text,
            "response": result,
            "avatar_frame": self.orchestrator.avatar.render_frame()
        }

    def update_head_tracking(self, position: Tuple[float, float, float]):
        """Оновлення трекінгу голови."""
        self.headset_position = position


# ============================================================================
# МОДУЛЬ 7: ДЕМО ТА ПРИКЛАД ВИКОРИСТАННЯ
# ============================================================================

def create_demo_twin() -> Orchestrator:
    """Створення демо-версії цифрового двійника."""

    # 1. Створення оркестратора
    twin = Orchestrator()

    # 2. Налаштування особистості
    personality = PersonalityConfig(
        vocabulary_style="casual",
        favorite_phrases=["Знаєш...", "Як на мене,", "Цікава думка"],
        speech_formality=0.3,
        humor_level=0.7,
        political_stance="liberal",
        religious_views="agnostic",
        work_ethic="balanced",
        family_values="very_important",
        stress_reaction="analytical",
        joy_expression="enthusiastic",
        criticism_response="accepting",
        common_words=["так", "звичайно", "цікаво", "взагалі", "типу"],
        slang_terms=["короче", "типу", "насправді"]
    )
    twin.initialize_personality(personality)

    # 3. Налаштування безпеки СПОЧАТКУ
    bio_profile = BiometricProfile(
        voice_hash=hashlib.sha256(b"demo_voice_sample").hexdigest()
    )
    twin.access_control.register_biometrics(bio_profile)

    # 4. Аутентифікація ПЕРЕД імпортом
    twin.authenticate("password", "demo_password")

    # 5. Імпорт демо-спогадів
    diary_entries = [
        {"date": "2024-01-15", "content": "Сьогодні був чудовий день. Зустрівся з друзями в кафе. Говорили про подорожі до Карпат."},
        {"date": "2024-02-20", "content": "Завершив важливий проєкт на роботі. Дуже задоволений результатом. Команда молодці!"},
        {"date": "2024-03-10", "content": "Святкували день народження бабусі. Вся родина зібралася. Такі моменти безцінні."}
    ]
    twin.import_memories("diary", diary_entries)

    messages = [
        {"from": "Олена", "content": "Привіт! Як твої справи? Давно не бачилися."},
        {"from": "Андрій", "content": "Давай зустрінемося на вихідних, поговоримо про стартап."}
    ]
    twin.import_memories("messages", messages)

    calendar_events = [
        {"date": "2024-04-01", "title": "Презентація проєкту", "description": "Важлива презентація перед інвесторами"},
        {"date": "2024-04-15", "title": "Похід у гори", "description": "З друзями в Карпати на вихідні"}
    ]
    twin.import_memories("calendar", calendar_events)

    # 6. Налаштування протоколу спадщини
    twin.legacy.configure("archive", beneficiaries=["family@example.com"])

    # 7. Додавання зразків голосу
    for i in range(12):
        twin.voice.add_training_sample(f"sample_{i}".encode(), f"Текст зразка {i}")

    return twin


def run_interactive_demo():
    """Інтерактивна демонстрація роботи двійника."""

    print("=" * 70)
    print("  ЦИФРОВИЙ ДВІЙНИК — ІНТЕРАКТИВНА ДЕМОНСТРАЦІЯ")
    print("=" * 70)

    # Створення двійника
    print("\n[1/6] Ініціалізація системи...")
    twin = create_demo_twin()
    print("  ✓ Система ініціалізована")

    print("\n[2/6] Аутентифікація...")
    print("  ✓ Користувач авторизований")

    print("\n[3/6] Перевірка статусу...")
    status = twin.get_status()
    print(f"  ✓ Спогадів у базі: {status['memories_count']}")
    print(f"  ✓ Голос навчено: {status['voice_status']['trained']}")
    print(f"  ✓ Особистість налаштована: {status['personality_configured']}")

    # Демо-розмова
    print("\n[4/6] Демонстрація розмови:")
    print("-" * 50)

    test_messages = [
        "Привіт! Як справи?",
        "Розкажи щось про свої подорожі.",
        "Як ти ставишся до сім'ї?",
        "У мене сьогодні важливий проєкт, хвилююся.",
        "Що ти думаєш про роботу?"
    ]

    for msg in test_messages:
        print(f"\nКористувач: {msg}")
        result = twin.process_message(msg)
        print(f"Двійник: {result['text']}")
        print(f"  [емоція: {result['emotion']}, жест: {result['gesture']}]")

    # Експорт даних
    print("\n[5/6] Експорт даних...")
    exported = twin.export_data(SecurityLevel.PUBLIC)
    print(f"  ✓ Експортовано {len(exported['memories'])} спогадів")

    # Статистика
    print("\n[6/6] Статистика системи:")
    print(f"  Всього взаємодій: {twin.state['total_interactions']}")
    print(f"  Остання взаємодія: {twin.state['last_interaction']}")
    print(f"  Режим спадщини: {twin.legacy.mode}")

    print("\n" + "=" * 70)
    print("  ДЕМО ЗАВЕРШЕНО")
    print("=" * 70)

    return twin


# ============================================================================
# ГОЛОВНИЙ БЛОК
# ============================================================================

if __name__ == "__main__":
    # Запуск інтерактивної демонстрації
    twin = run_interactive_demo()

    # Інтерактивний режим
    print("\n--- Інтерактивний режим (введіть 'exit' для виходу) ---")
    while True:
        try:
            user_input = input("\nВи: ").strip()
            if user_input.lower() in ["exit", "quit", "вихід"]:
                print("До побачення!")
                break
            if not user_input:
                continue

            result = twin.process_message(user_input)
            print(f"Двійник: {result['text']}")
            print(f"  [емоція: {result['emotion']}]")
        except KeyboardInterrupt:
            print("\n\nДо побачення!")
            break
        except Exception as e:
            print(f"Помилка: {e}")
