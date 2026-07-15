"""
================================================================================
DIGITAL TWIN — Streamlit Web Application
================================================================================
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from digital_twin import (
    Orchestrator, PersonalityConfig, SecurityLevel,
    BiometricProfile, LegacyProtocol,
    VectorDatabase, MemoryImporter, ContinuousLearning,
    VoiceCloning, Avatar3D, BodyLanguage,
    WebInterface, TelegramBot, VRInterface,
    EmotionalState, CognitiveEngine,
    EncryptionManager
)

import json
import hashlib
import time
from datetime import datetime
from typing import Dict, List, Optional

# ============================================================================
# STREAMLIT PAGE CONFIG
# ============================================================================
st.set_page_config(
    page_title="Digital Twin",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CSS STYLING
# ============================================================================
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        text-align: center;
        color: #666;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 12px 18px;
        border-radius: 18px 18px 4px 18px;
        margin: 8px 0 8px auto;
        max-width: 75%;
        word-wrap: break-word;
    }
    .twin-message {
        background: #ffffff;
        border: 1px solid #e0e0e0;
        color: #333;
        padding: 12px 18px;
        border-radius: 18px 18px 18px 4px;
        margin: 8px auto 8px 0;
        max-width: 75%;
        word-wrap: break-word;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    .emotion-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        margin-left: 8px;
    }
    .emotion-happy { background: #d4edda; color: #155724; }
    .emotion-sad { background: #f8d7da; color: #721c24; }
    .emotion-angry { background: #fff3cd; color: #856404; }
    .emotion-anxious { background: #e2e3f3; color: #383d7a; }
    .emotion-thoughtful { background: #d1ecf1; color: #0c5460; }
    .emotion-neutral { background: #e9ecef; color: #495057; }
    .stat-card {
        background: white;
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        text-align: center;
    }
    .stat-number {
        font-size: 2rem;
        font-weight: 700;
        color: #667eea;
    }
    .stat-label {
        color: #666;
        font-size: 0.9rem;
    }
    .memory-item {
        background: white;
        border-left: 4px solid #667eea;
        padding: 10px 15px;
        margin: 8px 0;
        border-radius: 0 8px 8px 0;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    }
    .memory-source {
        font-size: 0.75rem;
        color: #667eea;
        font-weight: 600;
    }
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
        "personality_configured": False,
        "memories_imported": False,
        "current_tab": "chat",
        "demo_mode": False,
        "voice_samples": 0,
        "last_activity": datetime.now().isoformat()
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ============================================================================
# HELPERS
# ============================================================================
def get_emotion_class(emotion: str) -> str:
    mapping = {
        "happy": "emotion-happy",
        "sad": "emotion-sad",
        "angry": "emotion-angry",
        "anxious": "emotion-anxious",
        "thoughtful": "emotion-thoughtful",
        "neutral": "emotion-neutral"
    }
    return mapping.get(emotion, "emotion-neutral")


def get_emotion_emoji(emotion: str) -> str:
    mapping = {
        "happy": "😊",
        "sad": "😢",
        "angry": "😠",
        "anxious": "😰",
        "excited": "🤩",
        "nostalgic": "🥹",
        "thoughtful": "🤔",
        "neutral": "😐"
    }
    return mapping.get(emotion, "😐")


def create_demo_twin() -> Orchestrator:
    twin = Orchestrator()

    personality = PersonalityConfig(
        vocabulary_style="casual",
        favorite_phrases=["Знаєш...", "Як на мене,", "Цікава думка", "Точно!"],
        speech_formality=0.3,
        humor_level=0.7,
        political_stance="liberal",
        religious_views="agnostic",
        work_ethic="balanced",
        family_values="very_important",
        stress_reaction="analytical",
        joy_expression="enthusiastic",
        criticism_response="accepting",
        common_words=["так", "звичайно", "цікаво", "взагалі", "типу", "короче"],
        slang_terms=["короче", "типу", "насправді", "просто"]
    )
    twin.initialize_personality(personality)

    bio_profile = BiometricProfile(
        voice_hash=hashlib.sha256(b"demo_voice_sample").hexdigest()
    )
    twin.access_control.register_biometrics(bio_profile)
    twin.authenticate("password", "demo")

    diary_entries = [
        {"date": "2024-01-15", "content": "Сьогодні був чудовий день. Зустрівся з друзями в кафе. Говорили про подорожі до Карпат."},
        {"date": "2024-02-20", "content": "Завершив важливий проєкт на роботі. Дуже задоволений результатом. Команда молодці!"},
        {"date": "2024-03-10", "content": "Святкували день народження бабусі. Вся родина зібралася. Такі моменти безцінні."},
        {"date": "2024-05-01", "content": "Поїхали в Карпати! Гори, свіже повітря, друзі — ідеальний відпочинок."}
    ]
    twin.import_memories("diary", diary_entries)

    messages = [
        {"from": "Олена", "content": "Привіт! Як твої справи? Давно не бачилися."},
        {"from": "Андрій", "content": "Давай зустрінемося на вихідних, поговоримо про стартап."},
        {"from": "Мама", "content": "Не забудь приїхати на вихідні, приготую твої улюблені пиріжки."}
    ]
    twin.import_memories("messages", messages)

    calendar_events = [
        {"date": "2024-04-01", "title": "Презентація проєкту", "description": "Важлива презентація перед інвесторами"},
        {"date": "2024-04-15", "title": "Похід у гори", "description": "З друзями в Карпати на вихідні"},
        {"date": "2024-06-20", "title": "День народження", "description": "Святкування з родиною"}
    ]
    twin.import_memories("calendar", calendar_events)

    twin.legacy.configure("archive", beneficiaries=["family@example.com"])

    for i in range(12):
        twin.voice.add_training_sample(f"sample_{i}".encode(), f"Текст зразка {i}")

    return twin


# ============================================================================
# SIDEBAR
# ============================================================================
with st.sidebar:
    st.markdown("## 🔐 Авторизація")

    if not st.session_state.authenticated:
        auth_method = st.radio("Спосіб входу:", ["Демо-режим", "Пароль"], index=0)

        if auth_method == "Демо-режим":
            if st.button("🚀 Запустити демо", use_container_width=True):
                st.session_state.twin = create_demo_twin()
                st.session_state.authenticated = True
                st.session_state.demo_mode = True
                st.rerun()
        else:
            password = st.text_input("Пароль:", type="password")
            if st.button("🔓 Увійти", use_container_width=True):
                if password:
                    twin = Orchestrator()
                    bio = BiometricProfile(voice_hash=hashlib.sha256(b"user_voice").hexdigest())
                    twin.access_control.register_biometrics(bio)
                    if twin.authenticate("password", password):
                        st.session_state.twin = twin
                        st.session_state.authenticated = True
                        st.rerun()
                    else:
                        st.error("Невірний пароль")
                else:
                    st.warning("Введіть пароль")
    else:
        st.success("✅ Авторизовано")
        if st.session_state.demo_mode:
            st.info("🎮 Демо-режим")

        if st.button("🚪 Вийти", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.twin = None
            st.session_state.chat_history = []
            st.rerun()

    st.markdown("---")
    st.markdown("## 📍 Навігація")

    tab = st.radio(
        "Оберіть розділ:",
        ["💬 Чат", "🧠 Пам'ять", "⚙️ Особистість", "🔒 Безпека", "📊 Статистика"],
        index=0
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

        Це інтерактивний цифровий двійник з повною підтримкою:

        - **🧠 Когнітивна модель** — мислить як ви
        - **💾 База спогадів** — пам'ятає ваше життя
        - **🎭 Емоційний інтелект** — реагує на настрій
        - **🔒 Безпека** — шифрування та контроль доступу
        - **📜 Протокол спадщини** — керування долею даних

        **Оберіть демо-режим у боковому меню, щоб спробувати!**
        """)

        st.markdown("---")
        feat_col1, feat_col2, feat_col3 = st.columns(3)
        with feat_col1:
            st.markdown("<div class='stat-card'><div class='stat-number'>🗣️</div><div class='stat-label'>Голосове клонування</div></div>", unsafe_allow_html=True)
        with feat_col2:
            st.markdown("<div class='stat-card'><div class='stat-number'>🧬</div><div class='stat-label'>3D-Аватар</div></div>", unsafe_allow_html=True)
        with feat_col3:
            st.markdown("<div class='stat-card'><div class='stat-number'>🔐</div><div class='stat-label'>Шифрування</div></div>", unsafe_allow_html=True)

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
            st.metric("Голос", "✅ Навчено" if status["voice_status"]["trained"] else "⏳ Навчання")

        st.markdown("---")

        # Чат
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    st.markdown("<div style='display: flex; justify-content: flex-end;'><div class='user-message'>" + msg["content"] + "</div></div>", unsafe_allow_html=True)
                else:
                    emotion_class = get_emotion_class(msg.get("emotion", "neutral"))
                    emotion_emoji = get_emotion_emoji(msg.get("emotion", "neutral"))
                    badge_html = "<span class='emotion-badge " + emotion_class + "'>" + emotion_emoji + " " + msg.get("emotion", "neutral") + "</span>"
                    st.markdown("<div style='display: flex; justify-content: flex-start; align-items: center;'><div class='twin-message'>" + msg["content"] + badge_html + "</div></div>", unsafe_allow_html=True)

        st.markdown("---")
        with st.form("chat_form", clear_on_submit=True):
            cols = st.columns([6, 1])
            with cols[0]:
                user_input = st.text_input("Ваше повідомлення:", placeholder="Напишіть щось...", label_visibility="collapsed")
            with cols[1]:
                submitted = st.form_submit_button("📤", use_container_width=True)

        if submitted and user_input:
            st.session_state.chat_history.append({
                "role": "user",
                "content": user_input,
                "timestamp": datetime.now().isoformat()
            })

            with st.spinner("Двійник думає..."):
                result = twin.process_message(user_input)

            st.session_state.chat_history.append({
                "role": "twin",
                "content": result.get("text", "..."),
                "emotion": result.get("emotion", "neutral"),
                "gesture": result.get("gesture", ""),
                "timestamp": datetime.now().isoformat()
            })

            st.rerun()

        st.markdown("---")
        st.markdown("**Швидкі теми:**")
        quick_cols = st.columns(5)
        quick_topics = [
            "Розкажи про Карпати",
            "Як ти ставишся до сім'ї?",
            "Порада щодо роботи",
            "Пригадай щось цікаве",
            "Як пройшов твій день?"
        ]
        for i, topic in enumerate(quick_topics):
            with quick_cols[i]:
                if st.button(topic, key=f"quick_{i}", use_container_width=True):
                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": topic,
                        "timestamp": datetime.now().isoformat()
                    })
                    result = twin.process_message(topic)
                    st.session_state.chat_history.append({
                        "role": "twin",
                        "content": result.get("text", "..."),
                        "emotion": result.get("emotion", "neutral"),
                        "timestamp": datetime.now().isoformat()
                    })
                    st.rerun()

    # ========================================
    # TAB: MEMORY
    # ========================================
    elif st.session_state.current_tab == "🧠 Пам'ять":
        st.markdown("### 🧠 База знань та спогадів")

        tabs = st.tabs(["📚 Перегляд", "➕ Імпорт", "🔍 Пошук"])

        with tabs[0]:
            memories = twin.vector_db.get_all_memories()
            if memories:
                st.success("Знайдено " + str(len(memories)) + " спогадів")
                for mem in memories:
                    source = mem.get("metadata", {}).get("source", "невідомо")
                    source_icons = {
                        "diary": "📔", "messages": "💬", "calendar": "📅",
                        "social_media": "📱", "books": "📖", "photos": "📷"
                    }
                    icon = source_icons.get(source, "📝")
                    mem_html = "<div class='memory-item'><div class='memory-source'>" + icon + " " + source.upper() + "</div><div>" + mem["text"][:200]
                    if len(mem["text"]) > 200:
                        mem_html += "..."
                    mem_html += "</div></div>"
                    st.markdown(mem_html, unsafe_allow_html=True)
            else:
                st.info("Спогадів ще немає. Імпортуйте дані у вкладці 'Імпорт'.")

        with tabs[1]:
            st.markdown("#### Імпорт спогадів")

            import_type = st.selectbox(
                "Джерело даних:",
                ["Щоденник", "Повідомлення", "Календар", "Соцмережі", "Книги"]
            )

            source_map = {
                "Щоденник": "diary",
                "Повідомлення": "messages",
                "Календар": "calendar",
                "Соцмережі": "social_media",
                "Книги": "books"
            }

            data_input = st.text_area(
                "Вставте дані (JSON формат):",
                height=200,
                placeholder='[\n  {"date": "2024-01-01", "content": "Текст запису"}\n]'
            )

            if st.button("📥 Імпортувати", use_container_width=True):
                try:
                    data = json.loads(data_input) if data_input else []
                    if isinstance(data, list):
                        twin.import_memories(source_map[import_type], data)
                        st.success("✅ Імпортовано " + str(len(data)) + " записів!")
                        st.rerun()
                    else:
                        st.error("Дані мають бути масивом (списком)")
                except json.JSONDecodeError:
                    st.error("❌ Невірний JSON формат")
                except Exception as e:
                    st.error("❌ Помилка: " + str(e))

            st.markdown("---")
            st.markdown("**Швидкий імпорт демо-даних:**")
            demo_cols = st.columns(3)
            with demo_cols[0]:
                if st.button("📔 Додати щоденник", use_container_width=True):
                    twin.import_memories("diary", [
                        {"date": "2024-06-01", "content": "Чудовий день на морі. Сонце, пляж, відпочинок."}
                    ])
                    st.success("Додано!")
                    st.rerun()
            with demo_cols[1]:
                if st.button("💬 Додати повідомлення", use_container_width=True):
                    twin.import_memories("messages", [
                        {"from": "Друг", "content": "Привіт! Коли зустрінемося?"}
                    ])
                    st.success("Додано!")
                    st.rerun()
            with demo_cols[2]:
                if st.button("📅 Додати подію", use_container_width=True):
                    twin.import_memories("calendar", [
                        {"date": "2024-07-20", "title": "Відпустка", "description": "Поїздка на море"}
                    ])
                    st.success("Додано!")
                    st.rerun()

        with tabs[2]:
            st.markdown("#### Пошук по спогадах")
            search_query = st.text_input("Запит:", placeholder="Наприклад: 'Карпати', 'робота', 'сім'я'")
            if search_query:
                results = twin.vector_db.search(search_query, top_k=5)
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

    # ========================================
    # TAB: PERSONALITY
    # ========================================
    elif st.session_state.current_tab == "⚙️ Особистість":
        st.markdown("### ⚙️ Налаштування особистості")

        with st.form("personality_form"):
            st.markdown("#### 🎭 Мовні характеристики")

            col1, col2 = st.columns(2)
            with col1:
                vocab_style = st.selectbox(
                    "Стиль мовлення:",
                    ["formal", "casual", "slang", "poetic"],
                    index=1
                )
                formality = st.slider("Рівень формальності:", 0.0, 1.0, 0.3)
                humor = st.slider("Почуття гумору:", 0.0, 1.0, 0.7)
            with col2:
                fav_phrases = st.text_area(
                    "Улюблені фрази (через кому):",
                    value="Знаєш..., Як на мене, Цікава думка"
                )
                common_words = st.text_area(
                    "Часто вживані слова:",
                    value="так, звичайно, цікаво, взагалі"
                )

            st.markdown("#### 🏛️ Цінності та переконання")

            col3, col4 = st.columns(2)
            with col3:
                political = st.selectbox("Політичні погляди:", ["conservative", "liberal", "neutral"], index=1)
                religious = st.selectbox("Релігійні погляди:", ["religious", "agnostic", "atheist"], index=1)
            with col4:
                work_ethic = st.selectbox("Ставлення до роботи:", ["dedicated", "balanced", "relaxed"], index=1)
                family = st.selectbox("Сімейні цінності:", ["very_important", "important", "moderate"], index=0)

            st.markdown("#### 💭 Емоційні патерни")

            col5, col6, col7 = st.columns(3)
            with col5:
                stress = st.selectbox("Реакція на стрес:", ["analytical", "emotional", "avoidant"], index=0)
            with col6:
                joy = st.selectbox("Вираження радості:", ["enthusiastic", "calm", "reserved"], index=0)
            with col7:
                criticism = st.selectbox("Реакція на критику:", ["defensive", "accepting", "dismissive"], index=1)

            submitted = st.form_submit_button("💾 Зберегти особистість", use_container_width=True)

        if submitted:
            personality = PersonalityConfig(
                vocabulary_style=vocab_style,
                favorite_phrases=[p.strip() for p in fav_phrases.split(",") if p.strip()],
                speech_formality=formality,
                humor_level=humor,
                political_stance=political,
                religious_views=religious,
                work_ethic=work_ethic,
                family_values=family,
                stress_reaction=stress,
                joy_expression=joy,
                criticism_response=criticism,
                common_words=[w.strip() for w in common_words.split(",") if w.strip()],
                slang_terms=[]
            )
            twin.initialize_personality(personality)
            st.session_state.personality_configured = True
            st.success("✅ Особистість оновлено!")
            st.balloons()

        if twin.cognitive_engine:
            st.markdown("---")
            st.markdown("#### 👁️ Попередній перегляд")
            preview = twin.cognitive_engine.personality.to_prompt_context()
            st.code(preview, language="text")

    # ========================================
    # TAB: SECURITY
    # ========================================
    elif st.session_state.current_tab == "🔒 Безпека":
        st.markdown("### 🔒 Безпека та контроль")

        sec_tabs = st.tabs(["🔐 Доступ", "🛡️ Шифрування", "📜 Спадщина", "📤 Експорт"])

        with sec_tabs[0]:
            st.markdown("#### Поточний статус безпеки")
            status = twin.get_status()

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Авторизовано", "Так" if status["security"]["authenticated"] else "Ні")
            with col2:
                st.metric("Користувач", status["security"].get("user", "невідомо"))

            st.markdown("---")
            st.markdown("#### Рівні доступу")

            access_data = {
                "Власник": ["✅ Читання", "✅ Запис", "✅ Видалення", "✅ Налаштування", "✅ Розмова"],
                "Родина": ["✅ Читання", "❌ Запис", "❌ Видалення", "❌ Налаштування", "✅ Розмова"],
                "Гість": ["❌ Читання", "❌ Запис", "❌ Видалення", "❌ Налаштування", "✅ Розмова"]
            }

            for role, perms in access_data.items():
                with st.expander("👤 " + role):
                    st.write(" | ".join(perms))

        with sec_tabs[1]:
            st.markdown("#### 🔐 Шифрування даних")

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

        with sec_tabs[2]:
            st.markdown("#### 📜 Протокол спадщини")

            st.info("""
            **Що станеться з вашим двійником у разі вашої відсутності?**

            Оберіть режим та налаштуйте умови активації.
            """)

            legacy_mode = st.selectbox(
                "Режим спадщини:",
                list(LegacyProtocol.INHERITANCE_MODES.keys()),
                format_func=lambda x: x + " — " + LegacyProtocol.INHERITANCE_MODES[x]
            )

            beneficiaries = st.text_area(
                "Бенефіціари (email через кому):",
                value="family@example.com"
            )

            st.markdown("#### ⏱️ Умови активації")

            inactivity_days = st.slider(
                "Активувати після днів неактивності:",
                min_value=30, max_value=365, value=90
            )

            if st.button("💾 Зберегти протокол", use_container_width=True):
                twin.legacy.configure(
                    legacy_mode,
                    beneficiaries=[b.strip() for b in beneficiaries.split(",") if b.strip()]
                )

                def inactivity_trigger(state):
                    last = state.get("last_interaction")
                    if last:
                        last_dt = datetime.fromisoformat(last)
                        return (datetime.now() - last_dt).days > inactivity_days
                    return False

                twin.legacy.add_trigger(inactivity_trigger)
                st.success("✅ Протокол налаштовано: " + LegacyProtocol.INHERITANCE_MODES[legacy_mode])

            st.markdown("---")
            st.markdown("**Поточний режим:** `" + twin.legacy.mode + "`")
            st.markdown("**Активний:** `" + ("Так" if twin.legacy.is_active else "Ні") + "`")

        with sec_tabs[3]:
            st.markdown("#### 📤 Експорт даних")

            export_level = st.selectbox(
                "Рівень доступу для експорту:",
                [SecurityLevel.PUBLIC, SecurityLevel.FAMILY, SecurityLevel.PRIVATE, SecurityLevel.CRITICAL],
                format_func=lambda x: x.value.upper()
            )

            if st.button("📥 Експортувати", use_container_width=True):
                try:
                    data = twin.export_data(export_level)
                    json_data = json.dumps(data, indent=2, ensure_ascii=False, default=str)

                    st.download_button(
                        label="⬇️ Завантажити JSON",
                        data=json_data,
                        file_name="digital_twin_export_" + datetime.now().strftime('%Y%m%d_%H%M%S') + ".json",
                        mime="application/json"
                    )

                    st.success("✅ Експортовано " + str(len(data.get('memories', []))) + " спогадів")

                    with st.expander("Переглянути дані"):
                        st.json(data)

                except Exception as e:
                    st.error("❌ Помилка: " + str(e))

    # ========================================
    # TAB: STATISTICS
    # ========================================
    elif st.session_state.current_tab == "📊 Статистика":
        st.markdown("### 📊 Статистика системи")

        status = twin.get_status()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown("<div class='stat-card'><div class='stat-number'>" + str(status["memories_count"]) + "</div><div class='stat-label'>Спогадів у базі</div></div>", unsafe_allow_html=True)
        with col2:
            st.markdown("<div class='stat-card'><div class='stat-number'>" + str(status["state"]["total_interactions"]) + "</div><div class='stat-label'>Взаємодій</div></div>", unsafe_allow_html=True)
        with col3:
            st.markdown("<div class='stat-card'><div class='stat-number'>" + str(status["voice_status"]["samples"]) + "</div><div class='stat-label'>Зразків голосу</div></div>", unsafe_allow_html=True)
        with col4:
            st.markdown("<div class='stat-card'><div class='stat-number'>" + str(len(st.session_state.chat_history) // 2) + "</div><div class='stat-label'>Повідомлень у чаті</div></div>", unsafe_allow_html=True)

        st.markdown("---")

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("#### 📈 Системна інформація")

            info_data = {
                "Статус": status["state"]["status"],
                "Остання взаємодія": status["state"]["last_interaction"] or "Немає",
                "Аватар завантажено": "Так" if status["avatar_loaded"] else "Ні",
                "Особистість налаштовано": "Так" if status["personality_configured"] else "Ні",
                "Голос навчено": "Так" if status["voice_status"]["trained"] else "Ні",
                "Режим спадщини": twin.legacy.mode,
                "Демо-режим": "Так" if st.session_state.demo_mode else "Ні"
            }

            for key, value in info_data.items():
                st.markdown("**" + key + ":** `" + value + "`")

        with col_right:
            st.markdown("#### 🧠 Історія емоцій")

            if twin.cognitive_engine and twin.cognitive_engine.emotional_state.emotion_history:
                emotions = twin.cognitive_engine.emotional_state.emotion_history

                emotion_counts = {}
                for e in emotions:
                    emotion_counts[e["emotion"]] = emotion_counts.get(e["emotion"], 0) + 1

                for emotion, count in sorted(emotion_counts.items(), key=lambda x: -x[1]):
                    emoji = get_emotion_emoji(emotion)
                    st.markdown(emoji + " **" + emotion + "**: " + str(count) + " разів")
            else:
                st.info("Ще немає емоційної історії. Поговоріть з двійником!")

        st.markdown("---")

        st.markdown("#### 💬 Історія розмов")
        if st.session_state.chat_history:
            for msg in st.session_state.chat_history[-10:]:
                role_icon = "👤" if msg["role"] == "user" else "🧬"
                st.markdown(role_icon + " **" + msg['role'].upper() + "**: " + msg['content'][:100])
        else:
            st.info("Історія чату порожня")


# ============================================================================
# FOOTER
# ============================================================================
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #999; font-size: 0.8rem;'>"
    "🧬 Digital Twin v1.0 | Створено з ❤️ на Python + Streamlit"
    "</div>",
    unsafe_allow_html=True
)
