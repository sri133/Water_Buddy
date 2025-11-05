# hp_partner_sqlite.py
import streamlit as st
import sqlite3
import os
import pycountry
import re
import pandas as pd
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
import google.generativeai as genai
import calendar
import plotly.graph_objects as go
import json

# -------------------------------
# Config & DB init
# -------------------------------
DB_PATH = "hp_partner.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    # users: username + password (simple local auth kept as your original)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)
    # profiles: personal settings
    cur.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            username TEXT PRIMARY KEY,
            profile_json TEXT,
            ai_water_goal REAL DEFAULT 2.5,
            FOREIGN KEY(username) REFERENCES users(username)
        )
    """)
    # water_profile: daily goal & frequency
    cur.execute("""
        CREATE TABLE IF NOT EXISTS water_profile (
            username TEXT PRIMARY KEY,
            daily_goal REAL DEFAULT 2.5,
            frequency TEXT DEFAULT '30 minutes',
            FOREIGN KEY(username) REFERENCES users(username)
        )
    """)
    # today_progress: persistent today's intake & log; resets when date changes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS today_progress (
            username TEXT PRIMARY KEY,
            date_iso TEXT,
            intake_l REAL DEFAULT 0,
            log_json TEXT DEFAULT '[]',
            FOREIGN KEY(username) REFERENCES users(username)
        )
    """)
    # streaks: store completed_dates as JSON array and current_streak int
    cur.execute("""
        CREATE TABLE IF NOT EXISTS streaks (
            username TEXT PRIMARY KEY,
            completed_json TEXT DEFAULT '[]',
            current_streak INTEGER DEFAULT 0,
            FOREIGN KEY(username) REFERENCES users(username)
        )
    """)
    conn.commit()
    conn.close()

init_db()

# -------------------------------
# DB helpers
# -------------------------------
def create_user(username, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO users(username,password) VALUES(?,?)", (username, password))
    # init other tables
    cur.execute("INSERT OR REPLACE INTO profiles(username, profile_json, ai_water_goal) VALUES(?,?,?)",
                (username, json.dumps({}), 2.5))
    cur.execute("INSERT OR REPLACE INTO water_profile(username, daily_goal, frequency) VALUES(?,?,?)",
                (username, 2.5, "30 minutes"))
    cur.execute("INSERT OR REPLACE INTO today_progress(username, date_iso, intake_l, log_json) VALUES(?,?,?,?)",
                (username, str(date.today()), 0.0, json.dumps([])))
    cur.execute("INSERT OR REPLACE INTO streaks(username, completed_json, current_streak) VALUES(?,?,?)",
                (username, json.dumps([]), 0))
    conn.commit()
    conn.close()

def check_user(username, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    row = cur.fetchone()
    conn.close()
    return row is not None

def load_profile(username):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT profile_json, ai_water_goal FROM profiles WHERE username=?", (username,))
    row = cur.fetchone()
    if row:
        profile = json.loads(row["profile_json"]) if row["profile_json"] else {}
        return profile, float(row["ai_water_goal"])
    conn.close()
    return {}, 2.5

def save_profile(username, profile_dict, ai_goal):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO profiles(username, profile_json, ai_water_goal) VALUES(?,?,?)",
                (username, json.dumps(profile_dict), float(ai_goal)))
    conn.commit()
    conn.close()

def load_water_profile(username):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT daily_goal, frequency FROM water_profile WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()
    if row:
        return float(row["daily_goal"]), row["frequency"]
    return 2.5, "30 minutes"

def save_water_profile(username, daily_goal, frequency):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO water_profile(username, daily_goal, frequency) VALUES(?,?,?)",
                (username, float(daily_goal), frequency))
    conn.commit()
    conn.close()

def load_today_progress(username):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT date_iso, intake_l, log_json FROM today_progress WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row["date_iso"], float(row["intake_l"]), json.loads(row["log_json"] or "[]")
    return str(date.today()), 0.0, []

def save_today_progress(username, date_iso, intake_l, log_list):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO today_progress(username, date_iso, intake_l, log_json) VALUES(?,?,?,?)",
                (username, date_iso, float(intake_l), json.dumps(log_list)))
    conn.commit()
    conn.close()

def load_streaks(username):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT completed_json, current_streak FROM streaks WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()
    if row:
        completed = json.loads(row["completed_json"] or "[]")
        return completed, int(row["current_streak"])
    return [], 0

def save_streaks(username, completed_list, current_streak):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO streaks(username, completed_json, current_streak) VALUES(?,?,?)",
                (username, json.dumps(completed_list), int(current_streak)))
    conn.commit()
    conn.close()

# -------------------------------
# ✅ Load API key (same as your app)
# -------------------------------
api_key = None
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    st.warning("No GOOGLE_API_KEY found — AI features will use fallback text.")
else:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("models/gemini-2.5-flash")
    except Exception:
        model = None

# -------------------------------
# Streamlit page config & session defaults
# -------------------------------
st.set_page_config(page_title="HP PARTNER", page_icon="💧", layout="centered")
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "page" not in st.session_state:
    st.session_state.page = "login"
if "username" not in st.session_state:
    st.session_state.username = ""
if "total_intake" not in st.session_state:
    st.session_state.total_intake = 0.0
if "water_intake_log" not in st.session_state:
    st.session_state.water_intake_log = []
if "show_chatbot" not in st.session_state:
    st.session_state.show_chatbot = False
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# countries
countries = [c.name for c in pycountry.countries]

def go_to_page(p):
    st.session_state.page = p
    st.experimental_rerun()

# -------------------------------
# LOGIN PAGE
# -------------------------------
if st.session_state.page == "login":
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 HP PARTNER</h1>", unsafe_allow_html=True)
    st.markdown("### Login or Sign Up to Continue")

    option = st.radio("Choose Option", ["Login", "Sign Up"])
    username = st.text_input("Enter Username")
    password = st.text_input("Enter Password", type="password")

    if st.button("Submit"):
        if option == "Sign Up":
            if not username or not password:
                st.error("Username and password cannot be empty.")
            else:
                # handle if username exists
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM users WHERE username=?", (username,))
                if cur.fetchone():
                    st.error("Username already exists.")
                    conn.close()
                else:
                    conn.close()
                    create_user(username, password)
                    st.success("Account created. Please login.")
        else:  # Login
            if check_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username

                # restore today's intake if same date, else reset only progress (not account)
                saved_date, intake_l, log_ml = load_today_progress(username)
                if saved_date == str(date.today()):
                    st.session_state.total_intake = float(intake_l)
                    st.session_state.water_intake_log = log_ml
                else:
                    # reset DB today_progress row for today
                    save_today_progress(username, str(date.today()), 0.0, [])
                    st.session_state.total_intake = 0.0
                    st.session_state.water_intake_log = []

                # load other state if needed (profile loaded on settings page)
                # decide next page
                profile, ai_goal = load_profile(username)
                if profile:
                    go_to_page("home")
                else:
                    go_to_page("settings")
            else:
                st.error("Invalid username/password.")

# -------------------------------
# SETTINGS PAGE
# -------------------------------
elif st.session_state.page == "settings":
    if not st.session_state.logged_in:
        go_to_page("login")

    username = st.session_state.username
    saved_profile, ai_goal = load_profile(username)
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 Personal Settings</h1>", unsafe_allow_html=True)

    name = st.text_input("Name", value=saved_profile.get("Name", username))
    age = st.text_input("Age", value=saved_profile.get("Age", ""))
    default_country = saved_profile.get("Country") or "India"
    try:
        default_index = countries.index(default_country)
    except ValueError:
        default_index = countries.index("India")
    country = st.selectbox("Country", countries, index=default_index)
    language = st.text_input("Language", value=saved_profile.get("Language", ""))
    st.write("---")

    height_unit = st.radio("Height Unit", ["cm", "feet"], horizontal=True)
    height_raw = saved_profile.get("Height", "0")
    try:
        height_default = float(str(height_raw).split()[0])
    except Exception:
        height_default = 0.0
    height = st.number_input(f"Height ({height_unit})", value=height_default)

    weight_unit = st.radio("Weight Unit", ["kg", "lbs"], horizontal=True)
    weight_raw = saved_profile.get("Weight", "0")
    try:
        weight_default = float(str(weight_raw).split()[0])
    except Exception:
        weight_default = 0.0
    weight = st.number_input(f"Weight ({weight_unit})", value=weight_default)

    def calculate_bmi(weight_val, height_val, weight_unit_val, height_unit_val):
        try:
            if height_unit_val == "feet":
                height_m = height_val * 0.3048
            else:
                height_m = height_val / 100.0
            if weight_unit_val == "lbs":
                weight_kg = weight_val * 0.453592
            else:
                weight_kg = weight_val
            return round(weight_kg / (height_m ** 2), 2) if height_m > 0 else 0
        except Exception:
            return 0

    bmi = calculate_bmi(weight, height, weight_unit, height_unit)
    st.write(f"**Your BMI is:** {bmi}")

    health_condition = st.radio("Health condition", ["Excellent", "Fair", "Poor"],
                               horizontal=True,
                               index=["Excellent", "Fair", "Poor"].index(saved_profile.get("Health Condition", "Excellent")))
    health_problems = st.text_area("Health problems", value=saved_profile.get("Health Problems", ""))

    st.write("---")
    new_profile = {
        "Name": name,
        "Age": age,
        "Country": country,
        "Language": language,
        "Height": f"{height} {height_unit}",
        "Weight": f"{weight} {weight_unit}",
        "BMI": bmi,
        "Health Condition": health_condition,
        "Health Problems": health_problems
    }

    if st.button("Save & Continue ➡️"):
        # Recompute AI suggestion if changed
        recalc_needed = new_profile != saved_profile
        suggested_water = None
        text_output = ""
        if recalc_needed:
            with st.spinner("Water Buddy is calculating your ideal water intake..."):
                prompt = f"""
                You are Water Buddy, a smart hydration assistant.
                Based on the following personal health information, suggest an ideal daily water intake goal in liters.
                Only return a single numeric value in liters (no text, no units).
                Age: {age}
                Height: {height} {height_unit}
                Weight: {weight} {weight_unit}
                BMI: {bmi}
                Health condition: {health_condition}
                Health problems: {health_problems if health_problems else 'None'}
                """
                try:
                    if model:
                        response = model.generate_content(prompt)
                        text_output = response.text.strip()
                        match = re.search(r"(\d+(\.\d+)?)", text_output)
                        if match:
                            suggested_water = float(match.group(1))
                    if suggested_water is None:
                        suggested_water = 2.5
                except Exception as e:
                    suggested_water = 2.5
                    text_output = f"Error: {e}"
        else:
            suggested_water = load_profile(username)[1]
            text_output = "Profile unchanged — using previous goal."

        # Save profile, water_profile defaults and ensure day row exists
        save_profile(username, new_profile, round(suggested_water, 2))
        save_water_profile(username, round(suggested_water, 2), load_water_profile(username)[1])
        # ensure today_progress exists and streak exists
        _d, _int, _log = load_today_progress(username)
        if _d != str(date.today()):
            save_today_progress(username, str(date.today()), 0.0, [])
        saved_streaks, saved_current = load_streaks(username)
        save_streaks(username, saved_streaks, saved_current)

        st.success(f"✅ Profile saved! Water Buddy suggests {suggested_water:.2f} L/day 💧")
        st.info(f"Water Buddy output: {text_output}")
        go_to_page("water_profile")

# -------------------------------
# WATER PROFILE PAGE (set daily goal / frequency)
# -------------------------------
elif st.session_state.page == "water_profile":
    if not st.session_state.logged_in:
        go_to_page("login")
    username = st.session_state.username
    daily_goal, frequency = load_water_profile(username)
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 Water Intake</h1>", unsafe_allow_html=True)
    st.success(f"Your ideal daily water intake is **{daily_goal} L/day** (saved).")

    daily_goal = st.slider("Set your daily water goal (L):", 0.5, 10.0, float(daily_goal), 0.1)
    freq_options = [f"{i} minutes" for i in range(5, 185, 5)]
    try:
        freq_index = freq_options.index(frequency)
    except ValueError:
        freq_index = freq_options.index("30 minutes")
    selected_freq = st.selectbox("🔔 Reminder Frequency:", freq_options, index=freq_index)

    if st.button("💾 Save & Continue ➡️"):
        save_water_profile(username, daily_goal, selected_freq)
        st.success("✅ Water profile saved successfully!")
        go_to_page("home")

# -------------------------------
# HOME PAGE
# -------------------------------
elif st.session_state.page == "home":
    if not st.session_state.logged_in:
        go_to_page("login")
    username = st.session_state.username

    daily_goal, _freq = load_water_profile(username)
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 HP PARTNER</h1>", unsafe_allow_html=True)

    # Ensure today's progress is loaded and consistent
    db_date, db_intake, db_log = load_today_progress(username)
    if db_date == str(date.today()):
        # restore if session_state empty or lower
        if st.session_state.total_intake == 0.0 and db_intake:
            st.session_state.total_intake = float(db_intake)
        if not st.session_state.water_intake_log and db_log:
            st.session_state.water_intake_log = db_log
    else:
        # reset DB row for the new date (this only happens once when date changes)
        save_today_progress(username, str(date.today()), 0.0, [])
        st.session_state.total_intake = 0.0
        st.session_state.water_intake_log = []

    fill_percent = min(st.session_state.total_intake / daily_goal, 1.0) if daily_goal > 0 else 0.0
    bottle_html = f"""
    <div style='width: 120px; height: 300px; border: 3px solid #1A73E8; border-radius: 20px; position: relative; margin: auto; 
    background: linear-gradient(to top, #1A73E8 {fill_percent*100}%, #E0E0E0 {fill_percent*100}%);'>
        <div style='position: absolute; bottom: 5px; width: 100%; text-align: center; color: #fff; font-weight: bold; font-size: 18px;'>
            {round(st.session_state.total_intake,2)}L / {daily_goal}L
        </div>
    </div>
    """
    st.markdown(bottle_html, unsafe_allow_html=True)
    st.write("---")

    water_input = st.text_input("Enter water amount (in ml):", key="water_input")

    if st.button("➕ Add Water"):
        value = re.sub("[^0-9.]", "", water_input).strip()
        if value:
            try:
                ml = float(value)
                liters = ml / 1000.0
                st.session_state.total_intake = round(st.session_state.total_intake + liters, 3)
                st.session_state.water_intake_log.append(f"{int(ml)} ml")
                st.success(f"✅ Added {int(ml)} ml of water!")

                # persist to DB (ensure today's row exists and matches today)
                saved_date, saved_int, saved_log = load_today_progress(username)
                if saved_date != str(date.today()):
                    saved_log = []
                saved_log = st.session_state.water_intake_log
                save_today_progress(username, str(date.today()), st.session_state.total_intake, saved_log)

                # update streaks if we crossed daily goal
                completed_dates, current_streak = load_streaks(username)
                today_iso = str(date.today())
                if st.session_state.total_intake >= daily_goal:
                    if today_iso not in completed_dates:
                        completed_dates.append(today_iso)
                        completed_dates = sorted(list(set(completed_dates)))
                        # recompute current streak by checking contiguous days back from today
                        completed_dates_dt = sorted([datetime.strptime(d, "%Y-%m-%d").date() for d in completed_dates])
                        streak = 0
                        cursor = date.today()
                        while cursor in completed_dates_dt:
                            streak += 1
                            cursor -= timedelta(days=1)
                        current_streak = streak
                        save_streaks(username, completed_dates, current_streak)

                # save progress and rerun to update UI
                st.experimental_rerun()
            except ValueError:
                st.error("Please enter a valid number like 700, 700ml, or 700 ml.")
        else:
            st.error("Please enter a valid number like 700, 700ml, or 700 ml.")

    if st.session_state.water_intake_log:
        st.write("### Today's Log:")
        for i, entry in enumerate(st.session_state.water_intake_log, 1):
            st.write(f"{i}. {entry}")

    st.write("---")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("👤 Personal Settings"):
            go_to_page("settings")
    with col2:
        if st.button("🚰 Water Intake"):
            go_to_page("water_profile")
    with col3:
        if st.button("📈 Report"):
            go_to_page("report")
    with col4:
        if st.button("🔥 Daily Streak"):
            go_to_page("daily_streak")
    with col5:
        if st.button("🚪 Logout"):
            # clear session_state but keep DB
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.total_intake = 0.0
            st.session_state.water_intake_log = []
            st.session_state.show_chatbot = False
            st.session_state.chat_history = []
            go_to_page("login")

    # Chatbot UI (kept simple)
    st.markdown("""
    <style>
    .chat-button { position: fixed; bottom: 25px; right: 25px; background-color: #1A73E8; border-radius: 50%; width: 60px; height: 60px; display: flex; align-items: center; justify-content: center; color: white; font-size: 28px; cursor: pointer; box-shadow: 0 4px 10px rgba(0,0,0,0.3); z-index: 999; }
    .chat-window { position: fixed; bottom: 100px; right: 25px; width: 350px; background: white; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); padding: 15px; z-index: 1000; overflow-y: auto; max-height: 400px; scrollbar-width: none; }
    .bot-message { text-align: left; color: #222; background: #F1F1F1; padding: 8px 10px; border-radius: 10px; margin: 5px 0; display: inline-block; }
    </style>
    """, unsafe_allow_html=True)

    chat_button_clicked = st.button("🤖", key="chat_button", help="Chat with Water Buddy")
    if chat_button_clicked:
        st.session_state.show_chatbot = not st.session_state.show_chatbot

    if st.session_state.show_chatbot:
        with st.container():
            st.markdown("<div class='chat-window'>", unsafe_allow_html=True)
            st.markdown("<div style='text-align:center; color:#1A73E8; font-weight:600; font-size:18px;'>💬 Water Buddy</div>", unsafe_allow_html=True)
            for entry in st.session_state.chat_history:
                if entry["sender"] == "bot":
                    st.markdown(f"<div class='bot-message'>🤖 {entry['text']}</div>", unsafe_allow_html=True)
            user_msg = st.text_input("Type your message...", key="chat_input")
            if st.button("Send", key="send_btn"):
                if user_msg.strip():
                    try:
                        if model:
                            prompt = f"You are Water Buddy, a friendly AI hydration assistant. Respond conversationally.\nUser: {user_msg}"
                            response = model.generate_content(prompt)
                            reply = response.text.strip()
                        else:
                            reply = "⚠️ Chatbot not configured currently."
                    except Exception:
                        reply = "⚠️ Sorry, I’m having trouble connecting right now."
                    st.session_state.chat_history.append({"sender": "bot", "text": reply})
                    st.experimental_rerun()
            st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------
# REPORT PAGE
# -------------------------------
elif st.session_state.page == "report":
    if not st.session_state.logged_in:
        go_to_page("login")
    username = st.session_state.username
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>📊 Hydration Report</h1>", unsafe_allow_html=True)
    st.write("---")

    # ensure structures
    daily_goal, _ = load_water_profile(username)
    completed_iso, current_streak = load_streaks(username)
    completed_dates = []
    for s in completed_iso:
        try:
            d = datetime.strptime(s, "%Y-%m-%d").date()
            completed_dates.append(d)
        except Exception:
            continue

    today = date.today()
    if today in completed_dates:
        today_pct = 100
    else:
        today_pct = min(round(st.session_state.total_intake / daily_goal * 100), 100) if st.session_state.total_intake else 0

    st.markdown("### Today's Progress")
    fig_daily = go.Figure(go.Indicator(mode="gauge+number", value=today_pct,
                                      title={'text': "Today's Hydration", 'font': {'size': 18}},
                                      gauge={'axis': {'range': [0,100]}, 'bar': {'color': "#1A73E8"}}))
    fig_daily.update_layout(height=300, margin=dict(l=20,r=20,t=30,b=20), paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_daily, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False})

    if today_pct >= 100:
        st.success("🏆 Goal achieved today! Excellent.")
    elif today_pct >= 75:
        st.info(f"💦 You're {today_pct}% there — almost there!")
    elif today_pct > 0:
        st.info(f"🙂 {today_pct}% completed — keep sipping!")
    else:
        st.info("🎯 Not started yet — let's drink some water!")

    st.write("---")
    st.markdown("### Weekly Progress (Mon → Sun)")
    monday = today - timedelta(days=today.weekday())
    week_days = [monday + timedelta(days=i) for i in range(7)]
    labels = [d.strftime("%a\n%d %b") for d in week_days]
    pct_list = []
    status_list = []
    for d in week_days:
        if d > today:
            pct = 0; status = "upcoming"
        else:
            if d in completed_dates:
                pct = 100; status = "achieved"
            else:
                if d == today and st.session_state.total_intake:
                    pct = min(round(st.session_state.total_intake / daily_goal * 100), 100)
                    if pct >= 100:
                        status = "achieved"
                    elif pct >= 75:
                        status = "almost"
                    elif pct > 0:
                        status = "partial"
                    else:
                        status = "missed"
                else:
                    pct = 0; status = "missed"
        pct_list.append(pct); status_list.append(status)

    def week_color_for_status(s):
        if s == "achieved": return "#1A73E8"
        if s == "almost": return "#FFD23F"
        if s == "partial": return "#FFD9A6"
        if s == "upcoming": return "rgba(255,255,255,0.06)"
        return "#FF6B6B"
    colors = [week_color_for_status(s) for s in status_list]
    df_week = pd.DataFrame({"label": labels, "pct": pct_list, "status": status_list})
    fig_week = go.Figure()
    fig_week.add_trace(go.Bar(x=df_week["label"], y=df_week["pct"], marker_color=colors,
                              text=[f"{v}%" if v>0 else "" for v in df_week["pct"]], textposition='outside'))
    fig_week.update_layout(yaxis={'title':'Completion %','range':[0,100]}, showlegend=False, margin=dict(l=20,r=20,t=20,b=40), height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_week, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False})

    # monthly stats & best streak
    year = today.year; month = today.month
    days_in_month = calendar.monthrange(year, month)[1]
    month_dates = [date(year, month, d) for d in range(1, days_in_month+1)]
    total_met = sum(1 for d in month_dates if (d in completed_dates) or (d == today and st.session_state.total_intake >= daily_goal))
    total_days = len(month_dates)

    if completed_dates:
        all_sorted = sorted(completed_dates)
        best_streak = 0; curr = 1
        for i in range(1, len(all_sorted)):
            if (all_sorted[i] - all_sorted[i-1]).days == 1:
                curr += 1
            else:
                if curr > best_streak: best_streak = curr
                curr = 1
        if curr > best_streak: best_streak = curr
    else:
        best_streak = 0

    st.write("---")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("🏠 Home"): go_to_page("home")
    with col2:
        if st.button("👤 Personal Settings"): go_to_page("settings")
    with col3:
        if st.button("🚰 Water Intake"): go_to_page("water_profile")
    with col4:
        st.info("You're on Report")
    with col5:
        if st.button("🔥 Daily Streak"): go_to_page("daily_streak")

# -------------------------------
# DAILY STREAK PAGE
# -------------------------------
elif st.session_state.page == "daily_streak":
    if not st.session_state.logged_in:
        go_to_page("login")
    username = st.session_state.username
    today = date.today()
    year, month = today.year, today.month
    days_in_month = calendar.monthrange(year, month)[1]

    completed_iso, current_streak = load_streaks(username)
    completed_dates = []
    for s in completed_iso:
        try:
            dt = datetime.strptime(s, "%Y-%m-%d").date()
            completed_dates.append(dt)
        except Exception:
            pass

    # star grid HTML (same visual UX you had)
    star_css = """
    <style>
    .star-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 14px; justify-items: center; align-items: center; padding: 6px 4%; }
    .star { width:42px; height:42px; display:flex; align-items:center; justify-content:center; font-size:16px; border-radius:6px; transition: transform .12s ease, box-shadow .12s ease; cursor: pointer; user-select: none; text-decoration:none; line-height:1; }
    .star:hover { transform: translateY(-6px) scale(1.06); }
    .star.dim { background: rgba(255,255,255,0.03); color: #bdbdbd; box-shadow: none; filter: grayscale(10%); }
    .star.upcoming { background: rgba(255,255,255,0.02); color: #999; box-shadow: none; filter: grayscale(30%); }
    .star.achieved { background: radial-gradient(circle at 30% 20%, #fff6c2, #ffd85c 40%, #ffb400 100%); color: #4b2a00; box-shadow: 0 8px 22px rgba(255,176,0,0.42), 0 2px 6px rgba(0,0,0,0.18); }
    .star.small { width:38px; height:38px; font-size:14px; }
    @media(max-width:600px){ .star-grid { grid-template-columns: repeat(4,1fr); gap:10px; } .star { width:36px; height:36px; font-size:14px; } }
    </style>
    """
    stars_html = "<div class='star-grid'>"
    for d in range(1, days_in_month+1):
        the_date = date(year, month, d)
        iso = the_date.strftime("%Y-%m-%d")
        if the_date > today:
            css_class = "upcoming small"
        else:
            css_class = "achieved small" if the_date in completed_dates else "dim small"
        href = f"?selected_day={iso}"
        stars_html += f"<a class='star {css_class}' href='{href}' title='Day {d}'>{d}</a>"
    stars_html += "</div>"
    st.markdown(star_css + stars_html, unsafe_allow_html=True)

    query_params = st.experimental_get_query_params()
    selected_day_param = query_params.get("selected_day", [None])[0]
    if selected_day_param:
        try:
            sel_date = datetime.strptime(selected_day_param, "%Y-%m-%d").date()
            sel_day_num = sel_date.day
            if sel_date > today:
                status_txt = "upcoming"
            else:
                status_txt = "achieved" if sel_date in completed_dates else "missed"
            card_html = "<div class='slide-card' style='position: fixed; left:50%; transform: translateX(-50%); bottom:18px; width:340px; max-width:92%; background:linear-gradient(180deg, rgba(255,255,255,0.98), rgba(250,250,250,0.98)); color:#111; border-radius:12px; box-shadow: 0 10px 30px rgba(0,0,0,0.35); padding:14px 16px; z-index:2000;'>"
            card_html += f"<h4 style='margin:0 0 6px 0; font-size:16px;'>Day {sel_day_num} — {sel_date.strftime('%b %d, %Y')}</h4>"
            if status_txt == "achieved":
                card_html += "<p style='margin:0; font-size:14px; color:#333;'>🎉 Goal completed on this day! Great job.</p>"
            elif status_txt == "upcoming":
                card_html += "<p style='margin:0; font-size:14px; color:#333;'>⏳ This day is upcoming — no data yet.</p>"
            else:
                card_html += "<p style='margin:0; font-size:14px; color:#333;'>💧 Goal missed on this day. Keep trying — tomorrow is new!</p>"
            card_html += "<div><span class='close-btn' style='display:inline-block; margin-top:10px; color:#1A73E8; text-decoration:none; font-weight:600; cursor:pointer;' onclick=\"history.replaceState(null, '', window.location.pathname);\">Close</span></div>"
            card_html += "</div>"
            js_hide_on_scroll = """
            <script>
            (function(){
                var hidden = false;
                window.addEventListener('scroll', function(){
                    if(window.location.search.indexOf('selected_day') !== -1 && !hidden){
                        history.replaceState(null, '', window.location.pathname);
                        hidden = true;
                    }
                }, {passive:true});
            })();
            </script>
            """
            st.markdown(card_html + js_hide_on_scroll, unsafe_allow_html=True)
        except Exception:
            pass

    st.write("---")
    st.markdown(f"<h2 style='text-align:center; color:#1A73E8;'>🔥 Daily Streak: {current_streak} Days</h2>", unsafe_allow_html=True)
    st.write("---")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("🏠 Home"): go_to_page("home")
    with col2:
        if st.button("👤 Personal Settings"): go_to_page("settings")
    with col3:
        if st.button("🚰 Water Intake"): go_to_page("water_profile")
    with col4:
        if st.button("📈 Report"): go_to_page("report")
    with col5:
        st.info("You're on Daily Streak")

# End of app
