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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from digital_twin import (
    Orchestrator, PersonalityConfig, SecurityLevel,
    BiometricProfile, LegacyProtocol, TwinDatabase, analytics,
)

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

        auth_method = st.radio("Спосіб входу:", ["Демо-режим", "Існуючий профіль", "Новий профіль"], index=0)

        if auth_method == "Демо-режим":
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

        st.markdown("---")

        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    st.markdown("<div style='display: flex; justify-content: flex-end;'><div class='user-message'>" + msg["content"] + "</div></div>", unsafe_allow_html=True)
                else:
                    emotion_class = get_emotion_class(msg.get("emotion", "neutral"))
                    emotion_emoji = get_emotion_emoji(msg.get("emotion", "neutral"))
                    badge_html = "<span class='emotion-badge " + emotion_class + "'>" + emotion_emoji + " " + msg.get("emotion", "neutral") + "</span>"
                    mode_html = ""
                    if msg.get("mode"):
                        mode_html = "<span class='mode-badge'>" + ("🤖 LLM" if msg["mode"] == "llm" else "📋 шаблон") + "</span>"
                    st.markdown("<div style='display: flex; justify-content: flex-start; align-items: center;'><div class='twin-message'>" + msg["content"] + badge_html + mode_html + "</div></div>", unsafe_allow_html=True)

        st.markdown("---")
        with st.form("chat_form", clear_on_submit=True):
            cols = st.columns([6, 1])
            with cols[0]:
                user_input = st.text_input("Ваше повідомлення:", placeholder="Напишіть щось...", label_visibility="collapsed")
            with cols[1]:
                submitted = st.form_submit_button("📤", use_container_width=True)

        if submitted and user_input:
            st.session_state.chat_history.append({"role": "user", "content": user_input, "timestamp": datetime.now().isoformat()})
            with st.spinner("Двійник думає..."):
                result = twin.process_message(user_input)
            if "error" in result:
                st.error(result["error"])
            else:
                st.session_state.chat_history.append({
                    "role": "twin", "content": result.get("text", "..."),
                    "emotion": result.get("emotion", "neutral"), "mode": result.get("mode"),
                    "timestamp": datetime.now().isoformat(),
                })
                if result.get("llm_error"):
                    st.caption(f"⚠️ LLM недоступний, використано шаблон: {result['llm_error']}")
            st.rerun()

        st.markdown("---")
        st.markdown("**Швидкі теми:**")
        quick_cols = st.columns(5)
        quick_topics = ["Розкажи про Карпати", "Як ти ставишся до сім'ї?", "Порада щодо роботи",
                         "Пригадай щось цікаве", "Як пройшов твій день?"]
        for i, topic in enumerate(quick_topics):
            with quick_cols[i]:
                if st.button(topic, key=f"quick_{i}", use_container_width=True):
                    st.session_state.chat_history.append({"role": "user", "content": topic, "timestamp": datetime.now().isoformat()})
                    result = twin.process_message(topic)
                    st.session_state.chat_history.append({
                        "role": "twin", "content": result.get("text", "..."),
                        "emotion": result.get("emotion", "neutral"), "mode": result.get("mode"),
                        "timestamp": datetime.now().isoformat(),
                    })
                    st.rerun()

    # ========================================
    # TAB: MEMORY
    # ========================================
    elif st.session_state.current_tab == "🧠 Пам'ять":
        st.markdown("### 🧠 База знань та спогадів")
        st.caption(f"Embedding-бекенд: **{twin.vector_db.embedder.name}**")

        tabs = st.tabs(["📚 Перегляд", "➕ Імпорт", "🔍 Пошук", "📤 Повний експорт/імпорт"])

        with tabs[0]:
            memories = twin.vector_db.get_all_memories()
            if memories:
                st.success("Знайдено " + str(len(memories)) + " спогадів")
                for mem in memories:
                    source = mem.get("metadata", {}).get("source", "невідомо")
                    source_icons = {"diary": "📔", "messages": "💬", "calendar": "📅",
                                     "social_media": "📱", "books": "📖", "photos": "📷", "email": "✉️"}
                    icon = source_icons.get(source, "📝")
                    col_a, col_b = st.columns([9, 1])
                    with col_a:
                        mem_html = "<div class='memory-item'><div class='memory-source'>" + icon + " " + source.upper() + "</div><div>" + mem["text"][:200]
                        if len(mem["text"]) > 200:
                            mem_html += "..."
                        mem_html += "</div></div>"
                        st.markdown(mem_html, unsafe_allow_html=True)
                    with col_b:
                        if st.button("🗑️", key="del_" + mem["id"]):
                            twin.delete_memory(mem["id"])
                            st.rerun()
            else:
                st.info("Спогадів ще немає. Імпортуйте дані у вкладці 'Імпорт'.")

        with tabs[1]:
            st.markdown("#### Імпорт спогадів")
            import_type = st.selectbox("Джерело даних:", ["Щоденник", "Повідомлення", "Календар", "Соцмережі", "Книги", "Email"])
            source_map = {"Щоденник": "diary", "Повідомлення": "messages", "Календар": "calendar",
                          "Соцмережі": "social_media", "Книги": "books", "Email": "email"}
            data_input = st.text_area("Вставте дані (JSON формат):", height=200,
                                       placeholder='[\n  {"date": "2024-01-01", "content": "Текст запису"}\n]')
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

        with tabs[3]:
            st.markdown("#### Повний експорт / імпорт стану двійника")
            st.caption("Включає особистість, спогади, історію розмов та емоцій, налаштування спадщини.")
            level = st.selectbox("Рівень для експорту:", [SecurityLevel.PUBLIC, SecurityLevel.FAMILY,
                                                            SecurityLevel.PRIVATE, SecurityLevel.CRITICAL],
                                  format_func=lambda x: x.value.upper())
            if st.button("📥 Завантажити повний стан (JSON)"):
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

        with st.form("personality_form"):
            st.markdown("#### 🎭 Мовні характеристики")
            col1, col2 = st.columns(2)
            with col1:
                vocab_style = st.selectbox("Стиль мовлення:", ["formal", "casual", "slang", "poetic"], index=1)
                formality = st.slider("Рівень формальності:", 0.0, 1.0, 0.3)
                humor = st.slider("Почуття гумору:", 0.0, 1.0, 0.7)
            with col2:
                fav_phrases = st.text_area("Улюблені фрази (через кому):", value="Знаєш..., Як на мене, Цікава думка")
                common_words = st.text_area("Часто вживані слова:", value="так, звичайно, цікаво, взагалі")

            bio = st.text_area("Біографія / контекст для LLM:",
                                placeholder="Коротка розповідь про себе — професія, звички, історія...",
                                value=twin.personality.bio if twin.personality else "")

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
                speech_formality=formality, humor_level=humor,
                political_stance=political, religious_views=religious,
                work_ethic=work_ethic, family_values=family,
                stress_reaction=stress, joy_expression=joy, criticism_response=criticism,
                common_words=[w.strip() for w in common_words.split(",") if w.strip()],
                slang_terms=[], bio=bio,
            )
            twin.initialize_personality(personality)
            st.success("✅ Особистість оновлено!")
            st.balloons()

        if twin.cognitive_engine:
            st.markdown("---")
            st.markdown("#### 👁️ Попередній перегляд промпту для LLM")
            st.code(twin.cognitive_engine.personality.to_prompt_context(), language="text")

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
                "Гість": ["❌ Читання", "❌ Запис", "❌ Видалення", "❌ Налаштування", "✅ Розмова"],
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

        with sec_tabs[3]:
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
        st.markdown("#### 💬 Історія розмов (останні 10)")
        if conversation:
            for turn in conversation[-10:]:
                mode_icon = "🤖" if turn.get("mode") == "llm" else "📋"
                st.markdown(f"👤 **USER**: {turn['user'][:100]}")
                st.markdown(f"{mode_icon} **TWIN**: {turn['twin'][:100]}")
        else:
            st.info("Історія чату порожня")


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
