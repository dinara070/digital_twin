"""Інтерфейси взаємодії: Web API, Telegram-бот, VR."""

import json
from typing import Callable, Dict

from .orchestrator import Orchestrator
from .security import SecurityLevel


class WebInterface:
    def __init__(self, orchestrator: Orchestrator):
        self.orchestrator = orchestrator
        self.routes: Dict[str, Callable] = {
            "/": self._handle_root,
            "/chat": self._handle_chat,
            "/status": self._handle_status,
            "/auth": self._handle_auth,
            "/import": self._handle_import,
            "/export": self._handle_export,
            "/configure": self._handle_configure,
            "/configure_llm": self._handle_configure_llm,
        }

    def _handle_root(self, request: Dict) -> Dict:
        return {"status": "Digital Twin API", "version": "2.0.0", "endpoints": list(self.routes.keys())}

    def _handle_chat(self, request: Dict) -> Dict:
        message = request.get("message", "")
        if not message:
            return {"error": "Повідомлення не може бути порожнім"}
        return self.orchestrator.process_message(message)

    def _handle_status(self, request: Dict) -> Dict:
        return self.orchestrator.get_status()

    def _handle_auth(self, request: Dict) -> Dict:
        method = request.get("method", "password")
        credentials = request.get("credentials", "")
        return {"authenticated": self.orchestrator.authenticate(method, credentials)}

    def _handle_import(self, request: Dict) -> Dict:
        source = request.get("source", "")
        data = request.get("data", [])
        try:
            self.orchestrator.import_memories(source, data)
            return {"status": "imported", "source": source, "count": len(data)}
        except Exception as e:
            return {"error": str(e)}

    def _handle_export(self, request: Dict) -> Dict:
        level = request.get("level", "public")
        try:
            return {"data": self.orchestrator.export_data(SecurityLevel(level))}
        except Exception as e:
            return {"error": str(e)}

    def _handle_configure(self, request: Dict) -> Dict:
        from .personality_model import PersonalityConfig
        config = PersonalityConfig(**request.get("personality", {}))
        self.orchestrator.initialize_personality(config)
        return {"status": "personality_configured"}

    def _handle_configure_llm(self, request: Dict) -> Dict:
        api_key = request.get("api_key", "")
        model = request.get("model", "claude-sonnet-5")
        if not api_key:
            return {"error": "api_key обов'язковий"}
        self.orchestrator.configure_llm(api_key, model)
        return {"status": "llm_configured", "llm": self.orchestrator.llm_status()}

    def handle_request(self, path: str, request: Dict) -> Dict:
        handler = self.routes.get(path, lambda r: {"error": "Not found"})
        return handler(request)


class TelegramBot:
    def __init__(self, orchestrator: Orchestrator, bot_token: str = ""):
        self.orchestrator = orchestrator
        self.bot_token = bot_token
        self.authorized_users: set = set()

    def process_update(self, update: Dict) -> Dict:
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
            return {"text": json.dumps(self.orchestrator.get_status(), indent=2, ensure_ascii=False)}
        else:
            result = self.orchestrator.process_message(text)
            return {"text": result.get("text", "...")}


class VRInterface:
    def __init__(self, orchestrator: Orchestrator):
        self.orchestrator = orchestrator
        self.session_active: bool = False
        self.headset_position = (0.0, 0.0, 0.0)

    def start_session(self) -> Dict:
        self.session_active = True
        return {
            "status": "vr_session_started",
            "avatar": self.orchestrator.avatar.render_frame(),
            "instructions": "Подивіться на аватара, щоб почати розмову",
        }

    def process_voice_input(self, audio_data: bytes) -> Dict:
        recognized_text = "[розпізнаний текст з голосу]"
        result = self.orchestrator.process_message(recognized_text)
        self.orchestrator.avatar.set_expression(result.get("emotion", "neutral"))
        return {
            "recognized_text": recognized_text,
            "response": result,
            "avatar_frame": self.orchestrator.avatar.render_frame(),
        }

    def update_head_tracking(self, position):
        self.headset_position = position
