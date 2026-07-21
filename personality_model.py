"""Особистість та емоційний стан цифрового двійника."""

import threading
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict


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
