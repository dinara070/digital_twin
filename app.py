"""
================================================================================
DIGITAL TWIN v2.0 — Streamlit Web Application
Реальний LLM (Anthropic API), TF-IDF/семантичні embeddings, SQLite-персистентність,
багато профілів, аналітика.
================================================================================
"""

import streamlit as st
import sys
import os
import json
import hashlib
import uuid
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from digital_twin_core import (
    Orchestrator, PersonalityConfig, SecurityLevel,
    BiometricProfile, LegacyProtocol, TwinDatabase,
    PERSONALITY_PRESETS,
    emotion_distribution, memory_source_breakdown,
    conversation_activity_by_day, top_words,
    response_mode_breakdown, summary_stats,
    emotion_valence_timeline, activity_by_hour,
    message_length_stats, pinned_memories,
)


class _AnalyticsNamespace:
    """Тонка обгортка, щоб зберегти виклики виду analytics.summary_stats(...) в UI-коді."""
    emotion_distribution = staticmethod(emotion_distribution)
    memory_source_breakdown = staticmethod(memory_source_breakdown)
    conversation_activity_by_day = staticmethod(conversation_activity_by_day)
    top_words = staticmethod(top_words)
    response_mode_breakdown = staticmethod(response_mode_breakdown)
    summary_stats = staticmethod(summary_stats)
    emotion_valence_timeline = staticmethod(emotion_valence_timeline)
    activity_by_hour = staticmethod(activity_by_hour)
    message_length_stats = staticmethod(message_length_stats)
    pinned_memories = staticmethod(pinned_memories)


analytics = _AnalyticsNamespace()

DB_PATH = os.environ.get("DIGITAL_TWIN_DB", "digital_twin.db")

st.set_page_config(page_title="Digital Twin", page_icon="🧬", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: 700;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        text-align: center; margin-bottom: 0.5rem; }
    .sub-header { text-align: center; color: #666; font-size: 1.1rem; margin-bottom: 2rem; }
    .user-message { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;
        padding: 12px 18px; border-radius: 18px 18px 4px 18px; margin: 8px 0 8px auto;
        max-width: 75%; word-wrap: break-word; }
    .twin-message { background: #ffffff; border: 1px solid #e0e0e0; color: #333;
        padding: 12px 18px; border-radius: 18px 18px 18px 4px; margin: 8px auto 8px 0;
        max-width: 75%; word-wrap: break-word; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
    .emotion-badge { display: inline-block; padding: 2px 10px; border-radius: 12px;
        font-size: 0.75rem; margin-left: 8px; }
    .emotion-happy { background: #d4edda; color: #155724; }
    .emotion-sad { background: #f8d7da; color: #721c24; }
    .emotion-angry { background: #fff3cd; color: #856404; }
    .emotion-anxious { background: #e2e3f3; color: #383d7a; }
    .emotion-thoughtful { background: #d1ecf1; color: #0c5460; }
    .emotion-neutral { background: #e9ecef; color: #495057; }
    .mode-badge { display: inline-block; padding: 1px 8px; border-radius: 10px;
        font-size: 0.68rem; margin-left: 6px; background: #eef0ff; color: #4b3fa1; }
    .stat-card { background: white; border-radius: 12px; padding: 1rem;
        box-shadow: 0 2px 12px rgba(0,0,0,0.08); text-align: center; }
    .stat-number { font-size: 2rem; font-weight: 700; color: #667eea; }
    .stat-label { color: #666; font-size: 0.9rem; }
    .memory-item { background: white; border-left: 4px solid #667eea; padding: 10px 15px;
        margin: 8px 0; border-radius: 0 8px 8px 0; box-shadow: 0 1px 4px rgba(0,0,0,0.05); }
    .memory-source { font-size: 0.75rem; color: #667eea; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# SESSION STATE
# ============================================================================
def init_session_state():
    defaults = {
        "twin": None,
        "authenticated": False,
        "chat_history": [],
        "current_tab": "chat",
        "demo_mode": False,
        "pending_regenerate": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


@st.cache_resource
def get_db() -> TwinDatabase:
    return TwinDatabase(DB_PATH)


db = get_db()


# ============================================================================
# HELPERS
# ============================================================================
def get_emotion_class(emotion: str) -> str:
    mapping = {"happy": "emotion-happy", "sad": "emotion-sad", "angry": "emotion-angry",
               "anxious": "emotion-anxious", "thoughtful": "emotion-thoughtful", "neutral": "emotion-neutral"}
    return mapping.get(emotion, "emotion-neutral")


def get_emotion_emoji(emotion: str) -> str:
    mapping = {"happy": "😊", "sad": "😢", "angry": "😠", "anxious": "😰",
               "excited": "🤩", "nostalgic": "🥹", "thoughtful": "🤔", "neutral": "😐"}
    return mapping.get(emotion, "😐")


from contextlib import contextmanager


@contextmanager
def permission_guarded():
    """Перехоплює PermissionError від дій, недоступних для поточної ролі
    (напр. «гість» чи «родина» намагається редагувати/видаляти дані),
    і показує зрозуміле повідомлення замість падіння всього застосунку."""
    try:
        yield
    except PermissionError as e:
        current = st.session_state.twin.current_username() if st.session_state.twin else None
        role_note = f" (поточний користувач: {current})" if current else ""
        st.error(f"⛔ {e}{role_note}")


def create_demo_twin(profile_id: str = None) -> Orchestrator:
    twin = Orchestrator(
        profile_id=profile_id or "demo-" + str(uuid.uuid4())[:8],
        profile_name="Демо-двійник",
        db=db,
        embedder_preference="tfidf",
    )

    personality = PersonalityConfig(
        vocabulary_style="casual",
        favorite_phrases=["Знаєш...", "Як на мене,", "Цікава думка", "Точно!"],
        speech_formality=0.3, humor_level=0.7,
        political_stance="liberal", religious_views="agnostic",
        work_ethic="balanced", family_values="very_important",
        stress_reaction="analytical", joy_expression="enthusiastic", criticism_response="accepting",
        common_words=["так", "звичайно", "цікаво", "взагалі", "типу", "короче"],
        slang_terms=["короче", "типу", "насправді", "просто"],
        bio="Тестовий демо-профіль для ознайомлення з можливостями Digital Twin.",
    )
    twin.initialize_personality(personality)

    bio_profile = BiometricProfile(voice_hash=hashlib.sha256(b"demo_voice_sample").hexdigest())
    twin.access_control.register_biometrics(bio_profile)
    twin.access_control.set_password("demo")
    twin.authenticate("password", "demo")

    twin.import_memories("diary", [
        {"date": "2024-01-15", "content": "Сьогодні був чудовий день. Зустрівся з друзями в кафе. Говорили про подорожі до Карпат."},
        {"date": "2024-02-20", "content": "Завершив важливий проєкт на роботі. Дуже задоволений результатом. Команда молодці!"},
        {"date": "2024-03-10", "content": "Святкували день народження бабусі. Вся родина зібралася. Такі моменти безцінні."},
        {"date": "2024-05-01", "content": "Поїхали в Карпати! Гори, свіже повітря, друзі — ідеальний відпочинок."},
    ])
    twin.import_memories("messages", [
        {"from": "Олена", "content": "Привіт! Як твої справи? Давно не бачилися."},
        {"from": "Андрій", "content": "Давай зустрінемося на вихідних, поговоримо про стартап."},
        {"from": "Мама", "content": "Не забудь приїхати на вихідні, приготую твої улюблені пиріжки."},
    ])
    twin.import_memories("calendar", [
        {"date": "2024-04-01", "title": "Презентація проєкту", "description": "Важлива презентація перед інвесторами"},
        {"date": "2024-04-15", "title": "Похід у гори", "description": "З друзями в Карпати на вихідні"},
        {"date": "2024-06-20", "title": "День народження", "description": "Святкування з родиною"},
    ])

    twin.legacy.configure("archive", beneficiaries=["family@example.com"])
    twin.save_legacy_config()

    for i in range(12):
        twin.voice.add_training_sample(f"sample_{i}".encode(), f"Текст зразка {i}")

    return twin


def create_owner_twin(profile_id: str = None) -> Orchestrator:
    """Профіль, побудований на реальних відповідях власника на анкету
    (професійний блок + короткі відповіді на питання 1-3, 4, 13-15)."""
    twin = Orchestrator(
        profile_id=profile_id or "owner-" + str(uuid.uuid4())[:8],
        profile_name="Мій професійний профіль",
        db=db,
        embedder_preference="tfidf",
    )

    bio = (
        "Моя професійна експертиза зосереджена на фундаментальній математиці "
        "(лінійна алгебра, математичний аналіз, теорія функцій), фізиці, "
        "алгоритмічному програмуванні, а також креативному письмі та професійних "
        "комунікаціях. У роботі я фокусуюся на оптимізації та структуруванні процесів, "
        "щоб ефективно поєднувати інтенсивне навчання, викладання точних наук та "
        "генерацію ідей для стартап-змагань. Моя кар'єрна амбіція — розвиватися в "
        "продакт-менеджменті та створювати соціально значущі технологічні проєкти, "
        "зокрема ті, що допомагають долати розрив між поколіннями за допомогою "
        "інновацій. Я можу годинами обговорювати складні алгоритмічні задачі (рівня "
        "Project Euler), математичні концепції та технологічні рішення для конкурсів. "
        "Мої фундаментальні цінності — цілеспрямованість, системний інтелектуальний "
        "розвиток, соціальна відповідальність та прагнення створювати продукти з "
        "реальним суспільним впливом. У спілкуванні, прийнятті рішень і в стресових "
        "ситуаціях я завжди стараюся залишатися спокійною. Найбільш продуктивна я "
        "з 8:00 до 20:00, регулярно займаюся спортом."
    )

    personality = PersonalityConfig(
        vocabulary_style="formal",
        favorite_phrases=[],
        speech_formality=0.6,
        humor_level=0.4,
        political_stance="neutral",
        religious_views="agnostic",
        work_ethic="dedicated",
        family_values="important",
        stress_reaction="analytical",   # питання 1-3: завжди стараюсь бути спокійною
        joy_expression="calm",
        criticism_response="accepting",
        common_words=["оптимізація", "структура", "алгоритм", "продукт", "вплив", "фокус"],
        slang_terms=[],
        bio=bio,
    )
    twin.initialize_personality(personality)

    bio_profile = BiometricProfile(voice_hash=hashlib.sha256(b"owner_voice_sample").hexdigest())
    twin.access_control.register_biometrics(bio_profile)
    twin.access_control.set_password("")
    twin.authenticate("password", "")

    # Спогади-нотатки, побудовані прямо з відповідей анкети — щоб RAG міг їх
    # використовувати у відповідях (пошук за темами "робота", "стрес", "спорт" тощо).
    twin.import_memories("diary", [
        {"date": "2026-07-21", "content":
            "Професійна експертиза: фундаментальна математика (лінійна алгебра, "
            "математичний аналіз, теорія функцій), фізика, алгоритмічне програмування, "
            "креативне письмо та професійні комунікації."},
        {"date": "2026-07-21", "content":
            "Організація роботи: фокус на оптимізацію та структурування процесів, щоб "
            "поєднувати інтенсивне навчання, викладання точних наук та генерацію ідей "
            "для стартап-змагань."},
        {"date": "2026-07-21", "content":
            "Кар'єрні амбіції: розвиток у продакт-менеджменті, створення соціально "
            "значущих технологічних проєктів, зокрема тих, що допомагають долати "
            "розрив між поколіннями за допомогою інновацій."},
        {"date": "2026-07-21", "content":
            "Інформаційне поле: можу годинами обговорювати складні алгоритмічні задачі "
            "(рівня Project Euler), математичні концепції та технологічні рішення для "
            "конкурсів."},
        {"date": "2026-07-21", "content":
            "Життєві цінності: цілеспрямованість, системний інтелектуальний розвиток, "
            "соціальна відповідальність, прагнення створювати продукти з реальним "
            "суспільним впливом."},
        {"date": "2026-07-21", "content":
            "Стиль, прийняття рішень і реакція на стрес: завжди стараюся залишатися "
            "спокійною, навіть коли плани руйнуються або ситуація критична."},
        {"date": "2026-07-21", "content":
            "Продуктивність, сон і відновлення: найбільш сфокусована з 8:00 до 20:00; "
            "регулярно займаюся спортом як частиною режиму відновлення."},
    ])

    return twin


def load_profile(profile_id: str, name: str) -> Orchestrator:
    twin = Orchestrator(profile_id=profile_id, profile_name=name, db=db, embedder_preference="tfidf")
    twin.access_control.set_password("")  # profile switch без пароля (демо-модель довіри в UI-шарі)
    twin.authenticate("password", "")
    twin.load_from_db()
    if not twin.cognitive_engine:
        twin.initialize_personality(PersonalityConfig())
    return twin


# ============================================================================
# SIDEBAR
# ============================================================================
with st.sidebar:
    st.markdown("## 🔐 Профіль")

    if not st.session_state.authenticated:
        existing_profiles = db.list_profiles()

        auth_method = st.radio("Спосіб входу:", ["Мій профіль (анкета)", "Демо-режим", "Існуючий профіль", "Новий профіль"], index=0)

        if auth_method == "Мій профіль (анкета)":
            st.caption("Профіль, побудований на ваших відповідях: професійний блок, "
                       "цінності, продуктивність і реакція на стрес.")
            if st.button("👩‍💻 Завантажити мій профіль", use_container_width=True):
                st.session_state.twin = create_owner_twin()
                st.session_state.authenticated = True
                st.session_state.demo_mode = False
                st.rerun()

        elif auth_method == "Демо-режим":
            if st.button("🚀 Запустити демо", use_container_width=True):
                st.session_state.twin = create_demo_twin()
                st.session_state.authenticated = True
                st.session_state.demo_mode = True
                st.rerun()

        elif auth_method == "Існуючий профіль":
            if existing_profiles:
                options = {f"{p['name']} ({p['id']})": p["id"] for p in existing_profiles}
                choice = st.selectbox("Оберіть профіль:", list(options.keys()))
                if st.button("🔓 Завантажити", use_container_width=True):
                    pid = options[choice]
                    name = choice.split(" (")[0]
                    st.session_state.twin = load_profile(pid, name)
                    st.session_state.authenticated = True
                    st.session_state.chat_history = [
                        {"role": ("user" if False else "twin"), "content": t["twin"],
                         "emotion": t["emotion"], "timestamp": t["timestamp"]}
                        for t in []
                    ]
                    # відновити chat_history з БД у форматі UI
                    convo = db.load_conversation(pid)
                    hist = []
                    for turn in convo:
                        hist.append({"role": "user", "content": turn["user"], "timestamp": turn["timestamp"]})
                        hist.append({"role": "twin", "content": turn["twin"], "emotion": turn["emotion"],
                                     "timestamp": turn["timestamp"]})
                    st.session_state.chat_history = hist
                    st.rerun()
            else:
                st.info("Ще немає збережених профілів.")

        else:  # Новий профіль
            new_name = st.text_input("Ім'я профілю:", value="Мій двійник")
            if st.button("✨ Створити профіль", use_container_width=True):
                pid = str(uuid.uuid4())[:12]
                twin = Orchestrator(profile_id=pid, profile_name=new_name, db=db, embedder_preference="tfidf")
                twin.access_control.set_password("")
                twin.authenticate("password", "")
                twin.initialize_personality(PersonalityConfig())
                st.session_state.twin = twin
                st.session_state.authenticated = True
                st.session_state.chat_history = []
                st.rerun()
    else:
        twin = st.session_state.twin
        st.success(f"✅ {twin.profile_name}")
        if st.session_state.demo_mode:
            st.info("🎮 Демо-режим")

        if st.button("🔄 Змінити профіль", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.twin = None
            st.session_state.chat_history = []
            st.rerun()

        st.markdown("---")
        st.markdown("### 🤖 LLM (Anthropic API)")
        llm_status = twin.llm_status()
        if llm_status["available"]:
            st.success(f"Підключено: {llm_status['model']}")
        elif llm_status["configured"]:
            st.error(f"Помилка: {llm_status['error']}")
        else:
            st.warning("Не налаштовано — відповіді генеруються шаблонами")

        with st.expander("⚙️ Налаштувати LLM"):
            api_key_input = st.text_input("Anthropic API-ключ:", type="password",
                                           help="Зберігається зашифрованим локально в SQLite")
            model_input = st.selectbox("Модель:", ["claude-sonnet-5", "claude-opus-4-8", "claude-haiku-4-5-20251001"])
            if st.button("💾 Зберегти ключ", use_container_width=True):
                if api_key_input:
                    twin.configure_llm(api_key_input, model_input)
                    st.success("Ключ збережено (зашифровано)")
                    st.rerun()
                else:
                    st.warning("Введіть ключ")

        st.markdown("---")
        role_labels = {"owner": "👑 Власник", "family": "👨‍👩‍👧 Родина", "guest": "🚶 Гість"}
        current_role = twin.get_status()["security"].get("user")
        if twin.current_username():
            st.caption(f"🔑 Увійшли як **{twin.current_username()}** — {role_labels.get(current_role, current_role)}")
        else:
            st.caption("🔑 Ролі доступу (Власник / Родина / Гість) — розділ 🔒 Безпека → 🔐 Доступ")

    st.markdown("---")
    st.markdown("## 📍 Навігація")
    tab = st.radio(
        "Оберіть розділ:",
        ["💬 Чат", "🧠 Пам'ять", "⚙️ Особистість", "🔒 Безпека", "📊 Аналітика"],
        index=0,
    )
    st.session_state.current_tab = tab


# ============================================================================
# MAIN CONTENT
# ============================================================================
st.markdown('<div class="main-header">🧬 Digital Twin</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Ваш цифровий двійник — завжди поруч</div>', unsafe_allow_html=True)

if not st.session_state.authenticated:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.info("""
        ### 👋 Ласкаво просимо!

        Це інтерактивний цифровий двійник з підтримкою:

        - **🤖 Реальний LLM** — підключіть Anthropic API для живих відповідей
        - **🧠 Семантична пам'ять** — TF-IDF / sentence-transformers embeddings
        - **💾 Персистентність** — профілі зберігаються між сесіями (SQLite)
        - **📊 Аналітика** — динаміка емоцій, джерела спогадів, активність
        - **🔒 Безпека** — шифрування, контроль доступу, протокол спадщини

        **Оберіть спосіб входу у боковому меню, щоб почати!**
        """)
        feat_col1, feat_col2, feat_col3 = st.columns(3)
        with feat_col1:
            st.markdown("<div class='stat-card'><div class='stat-number'>🤖</div><div class='stat-label'>Anthropic LLM</div></div>", unsafe_allow_html=True)
        with feat_col2:
            st.markdown("<div class='stat-card'><div class='stat-number'>💾</div><div class='stat-label'>SQLite-профілі</div></div>", unsafe_allow_html=True)
        with feat_col3:
            st.markdown("<div class='stat-card'><div class='stat-number'>📊</div><div class='stat-label'>Аналітика</div></div>", unsafe_allow_html=True)

else:
    twin = st.session_state.twin

    # ========================================
    # TAB: CHAT
    # ========================================
    if st.session_state.current_tab == "💬 Чат":
        st.markdown("### 💬 Спілкування з двійником")

        status = twin.get_status()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Спогадів", status["memories_count"])
        with col2:
            st.metric("Взаємодій", status["state"]["total_interactions"])
        with col3:
            emotion = twin.cognitive_engine.emotional_state.current_emotion if twin.cognitive_engine else "neutral"
            st.metric("Емоція", get_emotion_emoji(emotion) + " " + emotion)
        with col4:
            llm_label = "🤖 LLM" if status["llm"]["available"] else "📋 Шаблони"
            st.metric("Режим відповідей", llm_label)

        ctrl_col1, ctrl_col2, ctrl_col3 = st.columns(3)
        with ctrl_col1:
            if st.button("🗑️ Очистити історію", use_container_width=True, disabled=not st.session_state.chat_history):
                twin.clear_conversation()
                st.session_state.chat_history = []
                st.rerun()
        with ctrl_col2:
            can_regenerate = len(st.session_state.chat_history) >= 2
            if st.button("🔄 Перегенерувати останню", use_container_width=True, disabled=not can_regenerate):
                st.session_state.chat_history = st.session_state.chat_history[:-2]
                last_user_msg = twin.pop_last_turn()
                if last_user_msg:
                    st.session_state.pending_regenerate = last_user_msg
                st.rerun()
        with ctrl_col3:
            transcript = "\n\n".join(
                f"{'Ви' if m['role'] == 'user' else 'Двійник'}: {m['content']}"
                for m in st.session_state.chat_history
            )
            st.download_button("⬇️ Експортувати чат", data=transcript or "Історія порожня",
                                file_name=f"chat_{twin.profile_id}.txt", mime="text/plain",
                                use_container_width=True, disabled=not st.session_state.chat_history)

        st.markdown("---")

        chat_search = st.text_input("🔍 Пошук у чаті:", placeholder="Введіть слово, щоб знайти в історії...", key="chat_search")

        def render_twin_message(content: str, emotion: str = "neutral", mode: Optional[str] = None, msg_key: str = ""):
            emoji = get_emotion_emoji(emotion)
            mode_label = "🤖 LLM" if mode == "llm" else ("📋 шаблон" if mode else "")
            st.markdown(content)
            caption = f"{emoji} {emotion}"
            if mode_label:
                caption += f" · {mode_label}"
            cap_col, btn_col = st.columns([5, 1])
            with cap_col:
                st.caption(caption)
            with btn_col:
                if msg_key and st.button("💾", key="pin_" + msg_key, help="Зберегти цю репліку як спогад"):
                    with permission_guarded():
                        twin.save_text_as_memory(content, source="chat")
                        st.toast("Збережено як спогад!")

        # Історія розмови (з опційним фільтром пошуку)
        visible_history = st.session_state.chat_history
        if chat_search:
            q = chat_search.lower()
            visible_history = [m for m in st.session_state.chat_history if q in m["content"].lower()]
            st.caption(f"Знайдено {len(visible_history)} повідомлень із «{chat_search}»")

        for idx, msg in enumerate(visible_history):
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(msg["content"])
            else:
                with st.chat_message("assistant", avatar="🧬"):
                    render_twin_message(msg["content"], msg.get("emotion", "neutral"), msg.get("mode"), msg_key=f"hist_{idx}")

        def send_message(text: str):
            """Надсилає повідомлення двійнику з живим (стрімінговим) виводом відповіді."""
            st.session_state.chat_history.append({"role": "user", "content": text, "timestamp": datetime.now().isoformat()})
            with st.chat_message("user"):
                st.markdown(text)
            with st.chat_message("assistant", avatar="🧬"):
                full_text = st.write_stream(twin.process_message_stream(text))
                last_turn = twin.cognitive_engine.conversation_history[-1] if twin.cognitive_engine else {}
                emotion = last_turn.get("emotion", "neutral")
                mode = last_turn.get("mode")
                emoji = get_emotion_emoji(emotion)
                mode_label = "🤖 LLM" if mode == "llm" else ("📋 шаблон" if mode else "")
                caption = f"{emoji} {emotion}"
                if mode_label:
                    caption += f" · {mode_label}"
                st.caption(caption)
                if last_turn.get("llm_error"):
                    st.caption(f"⚠️ LLM недоступний, використано шаблон: {last_turn['llm_error']}")
            st.session_state.chat_history.append({
                "role": "twin", "content": full_text,
                "emotion": emotion, "mode": mode,
                "timestamp": datetime.now().isoformat(),
            })

        st.markdown("**Швидкі теми:**")
        quick_cols = st.columns(5)
        quick_topics = ["Розкажи про Карпати", "Як ти ставишся до сім'ї?", "Порада щодо роботи",
                         "Пригадай щось цікаве", "Як пройшов твій день?"]
        for i, topic in enumerate(quick_topics):
            with quick_cols[i]:
                if st.button(topic, key=f"quick_{i}", use_container_width=True):
                    send_message(topic)
                    st.rerun()

        if st.session_state.pending_regenerate:
            pending_text = st.session_state.pending_regenerate
            st.session_state.pending_regenerate = None
            send_message(pending_text)
            st.rerun()

        user_input = st.chat_input("Напишіть щось своєму двійнику...")
        if user_input:
            send_message(user_input)
            st.rerun()

    # ========================================
    # TAB: MEMORY
    # ========================================
    elif st.session_state.current_tab == "🧠 Пам'ять":
        st.markdown("### 🧠 База знань та спогадів")
        st.caption(f"Embedding-бекенд: **{twin.vector_db.embedder.name}**")

        tabs = st.tabs(["📚 Перегляд", "⭐ Закріплені", "➕ Імпорт", "🔍 Пошук", "📤 Повний експорт/імпорт"])

        with tabs[0]:
            memories = twin.vector_db.get_all_memories()
            source_icons = {"diary": "📔", "messages": "💬", "calendar": "📅",
                             "social_media": "📱", "books": "📖", "photos": "📷", "email": "✉️", "chat": "💬"}
            if memories:
                total_words = sum(len(m["text"].split()) for m in memories)
                stat_c1, stat_c2, stat_c3 = st.columns(3)
                with stat_c1:
                    st.metric("Усього спогадів", len(memories))
                with stat_c2:
                    st.metric("Слів у пам'яті", total_words)
                with stat_c3:
                    st.metric("Закріплено", len(analytics.pinned_memories(memories)))

                all_sources = sorted({m.get("metadata", {}).get("source", "невідомо") for m in memories})
                selected_sources = st.multiselect("Фільтр за джерелом:", all_sources, default=all_sources)
                filtered = [m for m in memories if m.get("metadata", {}).get("source", "невідомо") in selected_sources]

                st.success(f"Показано {len(filtered)} з {len(memories)} спогадів")
                security_options = [s.value for s in SecurityLevel]
                for mem in filtered:
                    source = mem.get("metadata", {}).get("source", "невідомо")
                    icon = source_icons.get(source, "📝")
                    pin_mark = "⭐ " if mem.get("metadata", {}).get("pinned") else ""
                    with st.expander(f"{pin_mark}{icon} {source.upper()} — {mem['text'][:60]}{'...' if len(mem['text']) > 60 else ''}"):
                        edit_key = "edit_text_" + mem["id"]
                        new_text = st.text_area("Текст спогаду:", value=mem["text"], key=edit_key, height=80)

                        tags_key = "tags_" + mem["id"]
                        current_tags = ", ".join(mem.get("metadata", {}).get("tags", []))
                        new_tags = st.text_input("Теги (через кому):", value=current_tags, key=tags_key)

                        sec_key = "sec_" + mem["id"]
                        current_sec = mem.get("metadata", {}).get("security", "public")
                        new_sec = st.selectbox("Рівень безпеки:", security_options,
                                                index=security_options.index(current_sec) if current_sec in security_options else 0,
                                                key=sec_key)

                        col_pin, col_save, col_del = st.columns(3)
                        with col_pin:
                            pin_label = "📌 Відкріпити" if mem.get("metadata", {}).get("pinned") else "⭐ Закріпити"
                            if st.button(pin_label, key="pin_mem_" + mem["id"], use_container_width=True):
                                with permission_guarded():
                                    twin.toggle_memory_pin(mem["id"])
                                    st.rerun()
                        with col_save:
                            if st.button("💾 Зберегти зміни", key="save_" + mem["id"], use_container_width=True):
                                with permission_guarded():
                                    if new_text != mem["text"]:
                                        twin.update_memory(mem["id"], new_text)
                                    tag_list = [t.strip() for t in new_tags.split(",") if t.strip()]
                                    twin.update_memory_metadata(mem["id"], {"tags": tag_list, "security": new_sec})
                                    st.success("Оновлено!")
                                    st.rerun()
                        with col_del:
                            if st.button("🗑️ Видалити", key="del_" + mem["id"], use_container_width=True):
                                with permission_guarded():
                                    twin.delete_memory(mem["id"])
                                    st.rerun()
            else:
                st.info("Спогадів ще немає. Імпортуйте дані у вкладці 'Імпорт'.")

        with tabs[1]:
            st.markdown("#### ⭐ Закріплені спогади")
            st.caption("Найважливіші спогади, позначені зіркою — швидкий доступ без фільтрів.")
            pinned = analytics.pinned_memories(twin.vector_db.get_all_memories())
            if pinned:
                for mem in pinned:
                    source = mem.get("metadata", {}).get("source", "невідомо")
                    icon = source_icons.get(source, "📝")
                    st.markdown(f"**{icon} {source.upper()}**")
                    st.markdown(mem["text"])
                    if mem.get("metadata", {}).get("tags"):
                        st.caption("Теги: " + ", ".join(mem["metadata"]["tags"]))
                    if st.button("📌 Відкріпити", key="unpin_" + mem["id"]):
                        with permission_guarded():
                            twin.toggle_memory_pin(mem["id"])
                            st.rerun()
                    st.markdown("---")
            else:
                st.info("Ще немає закріплених спогадів — натисніть ⭐ біля будь-якого запису у вкладці «Перегляд».")

        with tabs[2]:
            st.markdown("#### Імпорт спогадів")
            import_type = st.selectbox("Джерело даних:", ["Щоденник", "Повідомлення", "Календар", "Соцмережі", "Книги", "Email"])
            source_map = {"Щоденник": "diary", "Повідомлення": "messages", "Календар": "calendar",
                          "Соцмережі": "social_media", "Книги": "books", "Email": "email"}

            import_mode = st.radio("Спосіб імпорту:", ["Вставити JSON", "Завантажити файл"], horizontal=True)
            data_input = None
            if import_mode == "Вставити JSON":
                data_input = st.text_area("Вставте дані (JSON формат):", height=200,
                                           placeholder='[\n  {"date": "2024-01-01", "content": "Текст запису"}\n]')
            else:
                uploaded_json = st.file_uploader("Оберіть .json файл зі списком записів:", type=["json"], key="mem_upload")
                if uploaded_json:
                    data_input = uploaded_json.read().decode("utf-8")

            if st.button("📥 Імпортувати", use_container_width=True):
                try:
                    data = json.loads(data_input) if data_input else []
                    if isinstance(data, list) and data:
                        twin.import_memories(source_map[import_type], data)
                        st.success("✅ Імпортовано " + str(len(data)) + " записів!")
                        st.rerun()
                    else:
                        st.error("Дані мають бути непорожнім масивом (списком)")
                except json.JSONDecodeError:
                    st.error("❌ Невірний JSON формат")
                except Exception as e:
                    st.error("❌ Помилка: " + str(e))

        with tabs[3]:
            st.markdown("#### Пошук по спогадах")
            search_query = st.text_input("Запит:", placeholder="Наприклад: 'Карпати', 'робота', 'сім'я'")
            top_k = st.slider("Кількість результатів:", 1, 15, 5)
            if search_query:
                results = twin.vector_db.search(search_query, top_k=top_k)
                if results:
                    st.success("Знайдено " + str(len(results)) + " результатів")
                    for r in results:
                        sim_percent = r["similarity"] * 100
                        res_html = "<div class='memory-item'><div style='display: flex; justify-content: space-between;'><span class='memory-source'>📄 Спогад</span><span style='color: #667eea; font-weight: 600;'>Схожість: " + f"{sim_percent:.1f}" + "%</span></div><div>" + r["text"][:250]
                        if len(r["text"]) > 250:
                            res_html += "..."
                        res_html += "</div></div>"
                        st.markdown(res_html, unsafe_allow_html=True)
                else:
                    st.warning("Нічого не знайдено")

        with tabs[4]:
            st.markdown("#### Повний експорт / імпорт стану двійника")
            st.caption("Включає особистість, спогади, історію розмов та емоцій, налаштування спадщини.")
            level = st.selectbox("Рівень для експорту:", [SecurityLevel.PUBLIC, SecurityLevel.FAMILY,
                                                            SecurityLevel.PRIVATE, SecurityLevel.CRITICAL],
                                  format_func=lambda x: x.value.upper())
            if st.button("📥 Завантажити повний стан (JSON)"):
                with permission_guarded():
                    data = twin.export_data(level)
                    st.download_button("⬇️ Зберегти файл", data=json.dumps(data, indent=2, ensure_ascii=False, default=str),
                                        file_name=f"twin_state_{twin.profile_id}.json", mime="application/json")

            uploaded = st.file_uploader("Імпортувати стан з JSON:", type=["json"])
            if uploaded and st.button("📤 Застосувати імпорт"):
                try:
                    payload = json.loads(uploaded.read().decode("utf-8"))
                    twin.import_full_state(payload)
                    st.success("Стан успішно імпортовано!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Помилка імпорту: {e}")

    # ========================================
    # TAB: PERSONALITY
    # ========================================
    elif st.session_state.current_tab == "⚙️ Особистість":
        st.markdown("### ⚙️ Налаштування особистості")

        p = twin.personality

        st.markdown("#### ⚡ Швидкі архетипи")
        st.caption("Одним кліком застосовує готовий набір рис мовлення та поведінки (bio та улюблені фрази залишаються без змін).")
        preset_cols = st.columns(len(PERSONALITY_PRESETS))
        preset_icons = {"Аналітик": "🧮", "Комунікатор": "🗣️", "Творча особистість": "🎨", "Лідер": "🚀"}
        for col, name in zip(preset_cols, PERSONALITY_PRESETS.keys()):
            with col:
                if st.button(f"{preset_icons.get(name, '⚡')} {name}", use_container_width=True, key="quickpreset_" + name):
                    twin.apply_builtin_preset(name)
                    st.success(f"Застосовано архетип «{name}»")
                    st.rerun()

        st.markdown("---")
        st.markdown("#### 💼 Збережені пресети")
        preset_col1, preset_col2 = st.columns([2, 1])
        with preset_col1:
            presets = twin.list_personality_presets()
            if presets:
                preset_options = {f"{pr['name']} ({pr['created_at'][:10]})": pr["id"] for pr in presets}
                chosen = st.selectbox("Збережені пресети:", list(preset_options.keys()))
                col_apply, col_delete = st.columns(2)
                with col_apply:
                    if st.button("📂 Застосувати пресет", use_container_width=True):
                        twin.apply_personality_preset(preset_options[chosen])
                        st.success("Пресет застосовано!")
                        st.rerun()
                with col_delete:
                    if st.button("🗑️ Видалити пресет", use_container_width=True):
                        twin.delete_personality_preset(preset_options[chosen])
                        st.rerun()
            else:
                st.caption("Ще немає збережених пресетів — налаштуйте особистість нижче і збережіть як пресет.")
        with preset_col2:
            new_preset_name = st.text_input("Назва нового пресету:", placeholder="напр. «Робочий режим»")
            if st.button("💾 Зберегти поточну як пресет", use_container_width=True, disabled=not new_preset_name):
                twin.save_personality_preset(new_preset_name)
                st.success(f"Збережено пресет «{new_preset_name}»")
                st.rerun()

        if st.button("🎲 Згенерувати випадкову особистість (для тестування)"):
            import random
            random_personality = PersonalityConfig(
                vocabulary_style=random.choice(["formal", "casual", "slang", "poetic"]),
                favorite_phrases=random.sample(["Знаєш...", "Чесно кажучи,", "Уяви собі,", "Насправді"], 2),
                speech_formality=round(random.uniform(0, 1), 2),
                humor_level=round(random.uniform(0, 1), 2),
                political_stance=random.choice(["conservative", "liberal", "neutral"]),
                religious_views=random.choice(["religious", "agnostic", "atheist"]),
                work_ethic=random.choice(["dedicated", "balanced", "relaxed"]),
                family_values=random.choice(["very_important", "important", "moderate"]),
                stress_reaction=random.choice(["analytical", "emotional", "avoidant"]),
                joy_expression=random.choice(["enthusiastic", "calm", "reserved"]),
                criticism_response=random.choice(["defensive", "accepting", "dismissive"]),
                common_words=random.sample(["цікаво", "звичайно", "мабуть", "справді", "взагалі"], 3),
                bio=p.bio,
            )
            twin.initialize_personality(random_personality)
            st.rerun()

        st.markdown("---")
        with st.form("personality_form"):
            st.markdown("#### 🎭 Мовні характеристики")
            vocab_options = ["formal", "casual", "slang", "poetic"]
            political_options = ["conservative", "liberal", "neutral"]
            religious_options = ["religious", "agnostic", "atheist"]
            work_options = ["dedicated", "balanced", "relaxed"]
            family_options = ["very_important", "important", "moderate"]
            stress_options = ["analytical", "emotional", "avoidant"]
            joy_options = ["enthusiastic", "calm", "reserved"]
            criticism_options = ["defensive", "accepting", "dismissive"]

            col1, col2 = st.columns(2)
            with col1:
                vocab_style = st.selectbox("Стиль мовлення:", vocab_options,
                                            index=vocab_options.index(p.vocabulary_style) if p.vocabulary_style in vocab_options else 1)
                formality = st.slider("Рівень формальності:", 0.0, 1.0, p.speech_formality)
                humor = st.slider("Почуття гумору:", 0.0, 1.0, p.humor_level)
            with col2:
                fav_phrases = st.text_area("Улюблені фрази (через кому):", value=", ".join(p.favorite_phrases))
                common_words = st.text_area("Часто вживані слова:", value=", ".join(p.common_words))

            bio = st.text_area("Біографія / контекст для LLM:",
                                placeholder="Коротка розповідь про себе — професія, звички, історія...",
                                value=p.bio, height=120)

            st.markdown("#### 🏛️ Цінності та переконання")
            col3, col4 = st.columns(2)
            with col3:
                political = st.selectbox("Політичні погляди:", political_options,
                                          index=political_options.index(p.political_stance) if p.political_stance in political_options else 2)
                religious = st.selectbox("Релігійні погляди:", religious_options,
                                          index=religious_options.index(p.religious_views) if p.religious_views in religious_options else 1)
            with col4:
                work_ethic = st.selectbox("Ставлення до роботи:", work_options,
                                           index=work_options.index(p.work_ethic) if p.work_ethic in work_options else 1)
                family = st.selectbox("Сімейні цінності:", family_options,
                                       index=family_options.index(p.family_values) if p.family_values in family_options else 1)

            st.markdown("#### 💭 Емоційні патерни")
            col5, col6, col7 = st.columns(3)
            with col5:
                stress = st.selectbox("Реакція на стрес:", stress_options,
                                       index=stress_options.index(p.stress_reaction) if p.stress_reaction in stress_options else 0)
            with col6:
                joy = st.selectbox("Вираження радості:", joy_options,
                                    index=joy_options.index(p.joy_expression) if p.joy_expression in joy_options else 0)
            with col7:
                criticism = st.selectbox("Реакція на критику:", criticism_options,
                                          index=criticism_options.index(p.criticism_response) if p.criticism_response in criticism_options else 1)

            submitted = st.form_submit_button("💾 Зберегти особистість", use_container_width=True)

        if submitted:
            personality = PersonalityConfig(
                vocabulary_style=vocab_style,
                favorite_phrases=[ph.strip() for ph in fav_phrases.split(",") if ph.strip()],
                speech_formality=formality, humor_level=humor,
                political_stance=political, religious_views=religious,
                work_ethic=work_ethic, family_values=family,
                stress_reaction=stress, joy_expression=joy, criticism_response=criticism,
                common_words=[w.strip() for w in common_words.split(",") if w.strip()],
                slang_terms=p.slang_terms, bio=bio,
            )
            twin.initialize_personality(personality)
            st.success("✅ Особистість оновлено!")
            st.balloons()
            st.rerun()

        if twin.cognitive_engine:
            st.markdown("---")
            st.markdown("#### 👁️ Попередній перегляд промпту для LLM")
            st.code(twin.cognitive_engine.personality.to_prompt_context(), language="text")

    # ========================================
    # TAB: SECURITY
    # ========================================
    elif st.session_state.current_tab == "🔒 Безпека":
        st.markdown("### 🔒 Безпека та контроль")
        sec_tabs = st.tabs(["🔐 Доступ", "🔑 Пароль", "🛡️ Шифрування", "📜 Спадщина", "📋 Аудит", "📤 Експорт і бекап"])

        with sec_tabs[0]:
            st.markdown("#### Поточний статус безпеки")
            status = twin.get_status()
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Авторизовано", "Так" if status["security"]["authenticated"] else "Ні")
            with col2:
                current_user_label = twin.current_username() or status["security"].get("user", "невідомо")
                st.metric("Користувач", current_user_label)
            with col3:
                seconds_left = twin.access_control.session_seconds_left()
                st.metric("Сесія спливає через", f"{seconds_left // 60} хв" if seconds_left else "—")

            st.markdown("---")
            st.markdown("#### 🔑 Вхід під роллю (Власник / Родина / Гість)")
            st.caption("Перевірте, як виглядає доступ до двійника з точки зору різних ролей — "
                       "власника, члена родини чи гостя.")

            registered_users = twin.list_users()
            if not registered_users:
                st.info("Тестові облікові записи ще не створені для цього профілю.")
                if st.button("⚙️ Створити тестові облікові записи", use_container_width=True):
                    twin.setup_demo_accounts()
                    st.success("Створено 3 тестові облікові записи!")
                    st.rerun()
            else:
                login_col1, login_col2 = st.columns(2)
                with login_col1:
                    role_username = st.text_input("Логін користувача:", key="role_login_username",
                                                    placeholder="Введіть логін...")
                with login_col2:
                    show_pwd = st.checkbox("👁 Показати пароль", key="role_login_show_pwd")
                    role_password = st.text_input("Пароль:", key="role_login_password",
                                                    type="default" if show_pwd else "password",
                                                    placeholder="Введіть пароль...")

                if st.button("▶️ Увійти під роллю", use_container_width=True, type="primary"):
                    role = twin.login_as(role_username, role_password)
                    if role:
                        role_labels = {"owner": "👑 Власник", "family": "👨‍👩‍👧 Родина", "guest": "🚶 Гість"}
                        st.success(f"Успішний вхід як «{role_username}» — роль: {role_labels.get(role, role)}")
                        st.rerun()
                    else:
                        st.error("Невірний логін або пароль")

                with st.expander("ℹ️ Тестові облікові записи (для демо)"):
                    demo_rows = "\n".join(
                        f"| `{u}` | `{p}` | {label} |" for u, p, _r, label in twin.DEMO_ACCOUNTS
                    )
                    st.markdown(
                        "| Логін | Пароль | Роль |\n|---|---|---|\n" + demo_rows
                    )
                    st.caption("Система розмежування доступу за ролями. Власник має повний доступ, "
                               "родина може читати й спілкуватися, гість — лише спілкуватися.")

            st.markdown("---")
            st.markdown("#### Рівні доступу")
            access_data = {
                "Власник": ["✅ Читання", "✅ Запис", "✅ Видалення", "✅ Налаштування", "✅ Розмова"],
                "Родина": ["✅ Читання", "❌ Запис", "❌ Видалення", "❌ Налаштування", "✅ Розмова"],
                "Гість": ["❌ Читання", "❌ Запис", "❌ Видалення", "❌ Налаштування", "✅ Розмова"],
            }
            for role, perms in access_data.items():
                with st.expander("👤 " + role):
                    st.write(" | ".join(perms))

        with sec_tabs[1]:
            st.markdown("#### 🔑 Зміна пароля")
            has_pwd = twin.access_control.has_password()
            st.caption("Пароль ще не встановлено — можна задати новий без підтвердження старого."
                       if not has_pwd else "Введіть поточний пароль, щоб встановити новий.")
            with st.form("change_password_form"):
                old_pwd = st.text_input("Поточний пароль:", type="password", disabled=not has_pwd)
                new_pwd = st.text_input("Новий пароль:", type="password")
                new_pwd_confirm = st.text_input("Повторіть новий пароль:", type="password")
                pwd_submitted = st.form_submit_button("💾 Змінити пароль", use_container_width=True)
            if pwd_submitted:
                if not new_pwd:
                    st.warning("Введіть новий пароль")
                elif new_pwd != new_pwd_confirm:
                    st.error("Паролі не збігаються")
                else:
                    ok = twin.change_password(new_pwd, old_pwd)
                    if ok:
                        st.success("✅ Пароль змінено")
                    else:
                        st.error("❌ Неправильний поточний пароль")

        with sec_tabs[2]:
            st.markdown("#### 🛡️ Шифрування даних")
            text_to_encrypt = st.text_area("Текст для шифрування:", placeholder="Введіть секретне повідомлення...")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔒 Зашифрувати", use_container_width=True):
                    if text_to_encrypt:
                        encrypted = twin.encryption.encrypt(text_to_encrypt, "demo")
                        st.session_state["last_encrypted"] = encrypted
                        st.success("Зашифровано!")
                        st.code(encrypted, language="text")
                    else:
                        st.warning("Введіть текст")
            with col2:
                if st.button("🔓 Розшифрувати", use_container_width=True):
                    if "last_encrypted" in st.session_state:
                        try:
                            decrypted = twin.encryption.decrypt(st.session_state["last_encrypted"], "demo")
                            st.success("Розшифровано!")
                            st.code(decrypted, language="text")
                        except Exception as e:
                            st.error("Помилка: " + str(e))
                    else:
                        st.warning("Спочатку зашифруйте щось")

        with sec_tabs[3]:
            st.markdown("#### 📜 Протокол спадщини")
            st.info("**Що станеться з вашим двійником у разі вашої відсутності?**")
            legacy_mode = st.selectbox("Режим спадщини:", list(LegacyProtocol.INHERITANCE_MODES.keys()),
                                        format_func=lambda x: x + " — " + LegacyProtocol.INHERITANCE_MODES[x])
            beneficiaries = st.text_area("Бенефіціари (email через кому):", value="family@example.com")
            inactivity_days = st.slider("Активувати після днів неактивності:", min_value=30, max_value=365, value=90)

            if st.button("💾 Зберегти протокол", use_container_width=True):
                twin.legacy.configure(legacy_mode, beneficiaries=[b.strip() for b in beneficiaries.split(",") if b.strip()],
                                       inactivity_days=inactivity_days)
                twin.legacy.add_trigger(twin.legacy.default_inactivity_trigger())
                twin.save_legacy_config()
                st.success("✅ Протокол налаштовано: " + LegacyProtocol.INHERITANCE_MODES[legacy_mode])

            st.markdown("---")
            st.markdown("**Поточний режим:** `" + twin.legacy.mode + "`")
            st.markdown("**Активний:** `" + ("Так" if twin.legacy.is_active else "Ні") + "`")

            st.markdown("---")
            st.markdown("#### 🧪 Симуляція активації")
            st.caption("Перевірте, що станеться, якщо умова активації (напр. неактивність) спрацює — без реального очікування.")
            if st.button("▶️ Симулювати активацію протоколу зараз"):
                with permission_guarded():
                    twin.legacy.is_active = True
                    result = twin.legacy.execute(twin)
                    st.json(result)
                    twin.legacy.is_active = False  # скидаємо симуляцію, щоб не впливати на реальний стан
                    twin.save_legacy_config()

        with sec_tabs[4]:
            st.markdown("#### 📋 Журнал дій (аудит)")
            st.caption("Останні дії з профілем: вхід, зміна пароля, редагування спогадів і особистості.")
            log = twin.access_log(limit=100)
            if log:
                for entry in log:
                    st.markdown(f"`{entry['timestamp'][:19]}` — **{entry['action']}**" +
                                (f" _{entry['detail']}_" if entry.get("detail") else ""))
            else:
                st.info("Журнал ще порожній.")

        with sec_tabs[5]:
            st.markdown("#### 📤 Експорт даних")
            export_level = st.selectbox("Рівень доступу для експорту:",
                                         [SecurityLevel.PUBLIC, SecurityLevel.FAMILY, SecurityLevel.PRIVATE, SecurityLevel.CRITICAL],
                                         format_func=lambda x: x.value.upper())
            if st.button("📥 Експортувати", use_container_width=True):
                try:
                    data = twin.export_data(export_level)
                    json_data = json.dumps(data, indent=2, ensure_ascii=False, default=str)
                    st.download_button(label="⬇️ Завантажити JSON", data=json_data,
                                        file_name="digital_twin_export_" + datetime.now().strftime('%Y%m%d_%H%M%S') + ".json",
                                        mime="application/json")
                    st.success("✅ Експортовано " + str(len(data.get('memories', []))) + " спогадів")
                    with st.expander("Переглянути дані"):
                        st.json(data)
                except Exception as e:
                    st.error("❌ Помилка: " + str(e))

            st.markdown("---")
            st.markdown("#### 💽 Повний бекап бази даних")
            st.caption("Завантажте всю SQLite-базу (усі профілі, спогади, розмови) як єдиний файл для резервного копіювання.")
            backup = twin.backup_bytes()
            if backup:
                st.download_button("⬇️ Завантажити .db бекап", data=backup,
                                    file_name="digital_twin_backup_" + datetime.now().strftime('%Y%m%d_%H%M%S') + ".db",
                                    mime="application/octet-stream")
            else:
                st.info("Бекап недоступний (персистентність вимкнена).")

    # ========================================
    # TAB: ANALYTICS
    # ========================================
    elif st.session_state.current_tab == "📊 Аналітика":
        st.markdown("### 📊 Аналітика двійника")

        status = twin.get_status()
        memories = twin.vector_db.get_all_memories()
        conversation = twin.cognitive_engine.conversation_history if twin.cognitive_engine else []
        emotions = twin.cognitive_engine.emotional_state.emotion_history if twin.cognitive_engine else []

        stats = analytics.summary_stats(status, memories, conversation, emotions)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown("<div class='stat-card'><div class='stat-number'>" + str(stats["memories_count"]) + "</div><div class='stat-label'>Спогадів</div></div>", unsafe_allow_html=True)
        with col2:
            st.markdown("<div class='stat-card'><div class='stat-number'>" + str(stats["interactions_count"]) + "</div><div class='stat-label'>Взаємодій</div></div>", unsafe_allow_html=True)
        with col3:
            st.markdown("<div class='stat-card'><div class='stat-number'>" + get_emotion_emoji(stats["dominant_emotion"]) + "</div><div class='stat-label'>Домінантна емоція</div></div>", unsafe_allow_html=True)
        with col4:
            st.markdown("<div class='stat-card'><div class='stat-number'>" + str(stats["llm_usage_pct"]) + "%</div><div class='stat-label'>Відповідей від LLM</div></div>", unsafe_allow_html=True)

        st.markdown("---")
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("#### 🧠 Розподіл емоцій")
            emo_dist = analytics.emotion_distribution(emotions)
            if emo_dist:
                st.bar_chart(emo_dist)
            else:
                st.info("Ще немає емоційної історії. Поговоріть з двійником!")

            st.markdown("#### 📔 Джерела спогадів")
            sources = analytics.memory_source_breakdown(memories)
            if sources:
                st.bar_chart(sources)
            else:
                st.info("Спогадів ще немає.")

        with col_right:
            st.markdown("#### 📈 Активність за днями")
            activity = analytics.conversation_activity_by_day(conversation)
            if activity:
                st.line_chart(activity)
            else:
                st.info("Ще немає історії розмов.")

            st.markdown("#### 🗣️ Найчастотніші слова у спогадах")
            words = analytics.top_words(memories)
            if words:
                st.bar_chart({w["word"]: w["count"] for w in words})
            else:
                st.info("Недостатньо тексту для аналізу.")

        st.markdown("---")
        st.markdown("#### 🤖 Режим генерації відповідей (LLM vs шаблони)")
        mode_dist = analytics.response_mode_breakdown(conversation)
        if mode_dist:
            st.bar_chart(mode_dist)
        else:
            st.info("Немає даних.")

        st.markdown("---")
        col_mood, col_hour = st.columns(2)

        with col_mood:
            st.markdown("#### 📉 Динаміка настрою в часі")
            st.caption("Числове значення настрою (від −1 негативний до +1 позитивний) за кожну репліку.")
            valence = analytics.emotion_valence_timeline(emotions)
            if valence:
                st.line_chart(valence)
            else:
                st.info("Ще немає даних для побудови динаміки настрою.")

        with col_hour:
            st.markdown("#### 🕐 Активність за годинами доби")
            hourly = analytics.activity_by_hour(conversation)
            if any(hourly.values()):
                st.bar_chart(hourly)
            else:
                st.info("Ще немає історії розмов для цієї діаграми.")

        st.markdown("---")
        st.markdown("#### ✍️ Довжина повідомлень")
        len_stats = analytics.message_length_stats(conversation)
        len_col1, len_col2 = st.columns(2)
        with len_col1:
            st.markdown("<div class='stat-card'><div class='stat-number'>" + str(len_stats["avg_user_words"]) + "</div><div class='stat-label'>Слів у повідомленні (Ви)</div></div>", unsafe_allow_html=True)
        with len_col2:
            st.markdown("<div class='stat-card'><div class='stat-number'>" + str(len_stats["avg_twin_words"]) + "</div><div class='stat-label'>Слів у відповіді (Двійник)</div></div>", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("#### 💬 Історія розмов (останні 10)")
        if conversation:
            for turn in conversation[-10:]:
                mode_icon = "🤖" if turn.get("mode") == "llm" else "📋"
                st.markdown(f"👤 **USER**: {turn['user'][:100]}")
                st.markdown(f"{mode_icon} **TWIN**: {turn['twin'][:100]}")
        else:
            st.info("Історія чату порожня")

        st.markdown("---")
        st.markdown("#### 📄 Звіт")
        report_lines = [
            f"# Аналітичний звіт — {twin.profile_name}",
            f"Дата формування: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Загальна статистика",
            f"- Спогадів: {stats['memories_count']}",
            f"- Взаємодій: {stats['interactions_count']}",
            f"- Домінантна емоція: {stats['dominant_emotion']}",
            f"- Відповідей від LLM: {stats['llm_usage_pct']}%",
            f"- Середня довжина повідомлення (Ви): {len_stats['avg_user_words']} слів",
            f"- Середня довжина відповіді (Двійник): {len_stats['avg_twin_words']} слів",
            "",
            "## Розподіл емоцій",
            *([f"- {e}: {c}" for e, c in emo_dist.items()] if emo_dist else ["Немає даних"]),
            "",
            "## Джерела спогадів",
            *([f"- {s}: {c}" for s, c in sources.items()] if sources else ["Немає даних"]),
            "",
            "## Найчастотніші слова",
            *([f"- {w['word']}: {w['count']}" for w in words] if words else ["Немає даних"]),
        ]
        report_md = "\n".join(report_lines)
        st.download_button("⬇️ Завантажити звіт (Markdown)", data=report_md,
                            file_name=f"analytics_report_{twin.profile_id}_{datetime.now().strftime('%Y%m%d')}.md",
                            mime="text/markdown")


# ============================================================================
# FOOTER
# ============================================================================
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #999; font-size: 0.8rem;'>"
    "🧬 Digital Twin v2.0 | Anthropic LLM + SQLite + TF-IDF | Створено з ❤️ на Python + Streamlit"
    "</div>",
    unsafe_allow_html=True,
)
