"""Аналітика: обчислення статистики для дашборду (без прив'язки до UI)."""

from collections import Counter
from datetime import datetime
from typing import Dict, List


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
