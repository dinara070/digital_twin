"""SQLite-персистентність: багатопрофільне зберігання даних двійника
між сесіями (спогади, особистість, історія розмов/емоцій, спадщина).
"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any

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
