"""Когнітивний двигун: реальна генерація відповідей через Anthropic API,
з fallback на шаблонний генератор, якщо API-ключ не налаштовано або стався збій.
"""

import os
import secrets
from typing import List, Dict, Optional

from .memory import VectorDatabase
from .personality_model import PersonalityConfig, EmotionalState

DEFAULT_MODEL = "claude-sonnet-5"


class LLMProvider:
    """Тонка обгортка над Anthropic Messages API.

    Ключ береться з параметра, або зі змінної середовища ANTHROPIC_API_KEY.
    Якщо пакет `anthropic` не встановлено або ключ відсутній — provider
    вважається недоступним (`is_available() == False`), і CognitiveEngine
    автоматично перейде на шаблонний режим.
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

    def complete(self, system_prompt: str, messages: List[Dict], max_tokens: int = 400) -> str:
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
    """Генерація відповідей на основі особистості, пам'яті та (опційно) LLM."""

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
        self._response_templates = self._load_templates()

    def _load_templates(self) -> Dict:
        return {
            "greeting": [
                "Привіт! Радий тебе бачити.",
                "О, привіт! Як справи?",
                "Здоров був! Чим можу допомогти?",
            ],
            "memory_recall": [
                "О, це нагадує мені про... {memory}",
                "Знаєш, якось було схоже... {memory}",
                "Це мені нагадує: {memory}",
            ],
            "unknown": [
                "Чесно кажучи, не пам'ятаю такого.",
                "Мабуть, це було до мого часу, або я просто забув.",
                "Не можу пригадати, але звучить цікаво.",
            ],
            "opinion": [
                "Як на мене, {opinion}",
                "Моя думка така: {opinion}",
                "Я б сказав, що {opinion}",
            ],
        }

    def _retrieve_context(self, query: str, top_k: int = 3) -> List[Dict]:
        memories = self.vector_db.search(query, top_k=top_k)
        return [m for m in memories if m["similarity"] > 0.15]

    def _apply_personality(self, response: str) -> str:
        if self.personality.favorite_phrases and secrets.randbelow(100) < 30:
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

    # ---- Шаблонний (offline) режим ----
    def _generate_template_response(self, user_input: str, context: List[Dict]) -> str:
        if any(g in user_input.lower() for g in ["привіт", "здоров", "hi", "hello"]):
            return secrets.choice(self._response_templates["greeting"])
        if context:
            memory_text = context[0]["text"]
            template = secrets.choice(self._response_templates["memory_recall"])
            return template.format(memory=memory_text)

        opinion = self._generate_opinion(user_input)
        template = secrets.choice(self._response_templates["opinion"])
        return template.format(opinion=opinion)

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
        return "тут важливо подумати з різних боків і знайти баланс"

    # ---- LLM-режим ----
    def _generate_llm_response(self, user_input: str, context: List[Dict]) -> str:
        system_prompt = self.personality.to_prompt_context()
        if context:
            memory_block = "\n".join(f"- {m['text']}" for m in context)
            system_prompt += (
                f"\n\nРелевантні спогади з пам'яті, використовуй їх природно, "
                f"якщо це доречно (не цитуй дослівно як список):\n{memory_block}\n"
            )
        system_prompt += (
            "\nВідповідай від першої особи, коротко (1-4 речення), у своєму стилі. "
            "Не згадуй, що ти є AI-моделлю чи цифровим двійником — просто відповідай як людина."
        )

        history = self.conversation_history[-6:]
        messages = []
        for turn in history:
            messages.append({"role": "user", "content": turn["user"]})
            messages.append({"role": "assistant", "content": turn["twin"]})
        messages.append({"role": "user", "content": user_input})

        return self.llm_provider.complete(system_prompt, messages)

    def generate_response(self, user_input: str) -> str:
        context = self._retrieve_context(user_input)

        llm_error = None
        if self.llm_provider and self.llm_provider.is_available():
            try:
                response = self._generate_llm_response(user_input, context)
                emotion = self.llm_provider.classify_emotion(user_input)
                self.emotional_state.set_emotion(emotion, 0.5, "llm_classified")
            except Exception as e:  # graceful degrade
                llm_error = str(e)
                self.emotional_state.react_to_input(user_input, self.personality)
                response = self._generate_template_response(user_input, context)
                response = self._apply_personality(response)
        else:
            self.emotional_state.react_to_input(user_input, self.personality)
            response = self._generate_template_response(user_input, context)
            response = self._apply_personality(response)

        emotional_prefix = self.emotional_state.get_emotional_prefix()
        final_response = emotional_prefix + response

        from datetime import datetime
        self.conversation_history.append({
            "user": user_input,
            "twin": response,
            "emotion": self.emotional_state.current_emotion,
            "timestamp": datetime.now().isoformat(),
            "mode": "llm" if (self.llm_provider and self.llm_provider.is_available() and not llm_error) else "template",
            "llm_error": llm_error,
        })

        return final_response
