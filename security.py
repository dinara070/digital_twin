"""Безпека, шифрування, контроль доступу та протокол спадщини."""

import hashlib
import secrets
import base64
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable
from enum import Enum


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
        self._permissions: Dict[str, List[str]] = {
            "owner": ["read", "write", "delete", "configure", "talk"],
            "family": ["read", "talk"],
            "guest": ["talk"],
        }
        self._session_expiry: Optional[datetime] = None
        self._biometric_profile: Optional[BiometricProfile] = None
        self._password_hash: Optional[str] = None

    def register_biometrics(self, profile: BiometricProfile):
        self._biometric_profile = profile

    def set_password(self, password: str):
        self._password_hash = hashlib.sha256(password.encode()).hexdigest()

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
