"""Оркестратор — центральний модуль координації всіх компонентів двійника."""

import json
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .security import EncryptionManager, AccessControl, LegacyProtocol, SecurityLevel
from .memory import VectorDatabase, MemoryImporter, ContinuousLearning, build_default_embedder
from .personality_model import PersonalityConfig
from .llm import CognitiveEngine, LLMProvider
from .identity import VoiceCloning, Avatar3D, BodyLanguage
from .db import TwinDatabase


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
            self.db.create_profile(self.profile_id, self.profile_name)

    # ---- Особистість / LLM ----
    def initialize_personality(self, config: PersonalityConfig):
        self.personality = config
        self.cognitive_engine = CognitiveEngine(self.vector_db, config, llm_provider=self.llm_provider)
        self.state["status"] = "personality_loaded"
        if self.autosave:
            self.db.save_personality(self.profile_id, self._personality_to_dict(config))

    def configure_llm(self, api_key: str, model: str = "claude-sonnet-5"):
        self.llm_provider = LLMProvider(api_key=api_key, model=model)
        if self.cognitive_engine:
            self.cognitive_engine.llm_provider = self.llm_provider
        if self.autosave and self.db:
            encrypted = self.encryption.encrypt(api_key, context=f"llm_key:{self.profile_id}")
            self.db.save_encrypted_secret(self.profile_id, encrypted)

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
        return self.access_control.authenticate(method, credentials)

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
                self.db.append_conversation(
                    self.profile_id, user_input, last_turn["twin"],
                    current_emotion, last_turn.get("mode", "template"),
                )
                self.db.append_emotion(
                    self.profile_id, current_emotion,
                    self.cognitive_engine.emotional_state.emotion_intensity,
                    (self.cognitive_engine.emotional_state.emotion_history[-1].get("trigger", "")
                     if self.cognitive_engine.emotional_state.emotion_history else ""),
                )
                self.db.touch_profile(self.profile_id)

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
                self.db.bulk_save_memories(self.profile_id, new_records)

    def enable_continuous_learning(self, sources: List[str]):
        self.continuous_learning.start()

        def on_update(update: Dict):
            print(f"[Auto-Learn] Нові дані з {update['source']}: {update['content'][:50]}...")
            if self.autosave:
                records = self.vector_db.export_records()
                if records:
                    self.db.save_memory(
                        self.profile_id, records[-1]["id"], records[-1]["text"],
                        records[-1]["vector"], records[-1]["metadata"],
                    )

        self.continuous_learning.on_update(on_update)

    def delete_memory(self, memory_id: str):
        if not self.access_control.check_permission("delete"):
            raise PermissionError("Немає дозволу на видалення")
        self.vector_db.delete_memory(memory_id)
        if self.autosave:
            self.db.delete_memory(self.profile_id, memory_id)

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
                self.db.bulk_save_memories(self.profile_id, records)

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
            self.db.delete_profile(self.profile_id)

    # ---- Персистентність профілю ----
    def load_from_db(self):
        """Завантажує стан профілю з бази даних (якщо профіль уже існує)."""
        if not self.db:
            return False

        personality_data = self.db.load_personality(self.profile_id)
        if personality_data:
            self.personality = PersonalityConfig(**personality_data)
            self.cognitive_engine = CognitiveEngine(self.vector_db, self.personality, llm_provider=self.llm_provider)

        records = self.db.load_memories(self.profile_id)
        if records:
            self.vector_db.load_records(records)

        if self.cognitive_engine:
            self.cognitive_engine.conversation_history = self.db.load_conversation(self.profile_id)
            self.cognitive_engine.emotional_state.emotion_history = [
                {"emotion": e["emotion"], "intensity": e["intensity"], "trigger": e["trigger"], "timestamp": e["timestamp"]}
                for e in self.db.load_emotion_history(self.profile_id)
            ]
            if self.cognitive_engine.emotional_state.emotion_history:
                self.cognitive_engine.emotional_state.current_emotion = \
                    self.cognitive_engine.emotional_state.emotion_history[-1]["emotion"]

        legacy_data = self.db.load_legacy(self.profile_id)
        if legacy_data:
            self.legacy.configure(legacy_data["mode"], legacy_data["beneficiaries"], legacy_data["inactivity_days"])
            self.legacy.is_active = legacy_data["is_active"]

        encrypted_key = self.db.load_encrypted_secret(self.profile_id)
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
            self.db.save_legacy(
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
