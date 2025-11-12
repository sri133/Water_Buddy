# app.py
# Full Water Buddy app with mascots and Quiz page (single-file)
# Updated: fixed reset crash, removed Home weather display, Home mascot special-case (13:40-14:30 IST)

import streamlit as st
import json
import os
import pycountry
import re
import pandas as pd
from datetime import datetime, date, timedelta, time as dtime
from dotenv import load_dotenv
import google.generativeai as genai
import calendar
import plotly.graph_objects as go
import sqlite3
from typing import Dict, Any, Optional
from urllib.parse import quote
import requests
import pytz
from pathlib import Path

# -------------------------------
# Load API key from .env or Streamlit Secrets
# -------------------------------
api_key = None
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    st.warning("⚠️ GOOGLE_API_KEY not found. Gemini features will be disabled.")
    model = None
else:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("models/gemini-2.5-flash")
    except Exception:
        model = None

# -------------------------------
# Streamlit Page Config
# -------------------------------
st.set_page_config(page_title="HP PARTNER", page_icon="💧", layout="centered")

# -------------------------------
# SQLite setup (permanent file in data/)
# -------------------------------
DATA_DIR = "data"
DB_PATH = os.path.join(DATA_DIR, "user_data.db")
os.makedirs(DATA_DIR, exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS credentials (
    username TEXT PRIMARY KEY,
    password TEXT NOT NULL
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS userdata (
    username TEXT PRIMARY KEY,
    data TEXT NOT NULL
)
""")
conn.commit()

def load_all_from_db() -> (Dict[str, str], Dict[str, Any]):
    creds = {}
    udata = {}
    try:
        cursor.execute("SELECT username, password FROM credentials")
        for row in cursor.fetchall():
            creds[row[0]] = row[1]
    except Exception:
        pass
    try:
        cursor.execute("SELECT username, data FROM userdata")
        for row in cursor.fetchall():
            try:
                u = json.loads(row[1])
            except Exception:
                u = {}
            udata[row[0]] = u
    except Exception:
        pass
    return creds, udata

def save_credentials_to_db(creds: Dict[str, str]):
    try:
        for username, password in creds.items():
            cursor.execute("""
            INSERT INTO credentials(username, password)
            VALUES (?, ?)
            ON CONFLICT(username) DO UPDATE SET password=excluded.password
            """, (username, password))
        conn.commit()
    except Exception:
        conn.rollback()
        raise

def save_userdata_to_db(userdata: Dict[str, Any]):
    try:
        for username, data in userdata.items():
            json_text = json.dumps(data, indent=4, sort_keys=True)
            cursor.execute("""
            INSERT INTO userdata(username, data)
            VALUES (?, ?)
            ON CONFLICT(username) DO UPDATE SET data=excluded.data
            """, (username, json_text))
        conn.commit()
    except Exception:
        conn.rollback()
        raise

# Initialize in-memory dictionaries from DB
users, user_data = load_all_from_db()

def save_credentials(creds):
    global users
    users = creds
    save_credentials_to_db(creds)

def save_user_data(data):
    global user_data
    user_data = data
    save_userdata_to_db(data)

# -------------------------------
# Helper functions for user data structure and weekly/daily handling
# -------------------------------
def go_to_page(page_name: str):
    st.session_state.page = page_name
    st.rerun()

def ensure_user_structures(username: str):
    """
    Ensure expected keys exist for the given user in user_data.
    Does not overwrite existing keys — only sets defaults when missing.
    """
    if username not in user_data:
        user_data[username] = {}
    user = user_data[username]
    user.setdefault("profile", {})
    user.setdefault("ai_water_goal", 2.5)
    user.setdefault("water_profile", {"daily_goal": 2.5, "frequency": "30 minutes"})
    user.setdefault("streak", {"completed_days": [], "current_streak": 0})
    user.setdefault("daily_intake", {})   # date -> liters, plus last_login_date meta
    user.setdefault("weekly_data", {"week_start": None, "days": {}})  # week_start (Mon), days map
    # Save any new defaults immediately so DB is consistent
    save_user_data(user_data)

def current_week_start(d: date = None) -> date:
    if d is None:
        d = date.today()
    return d - timedelta(days=d.weekday())  # Monday

def ensure_week_current(username: str):
    """
    If weekly_data.week_start differs from current week's Monday, reset weekly_data.days
    (this resets only when a new Monday arrives).
    """
    ensure_user_structures(username)
    weekly = user_data[username].setdefault("weekly_data", {"week_start": None, "days": {}})
    this_week_start = current_week_start()
    this_week_start_str = this_week_start.strftime("%Y-%m-%d")
    if weekly.get("week_start") != this_week_start_str:
        # Start a new week (clear only weekly days, keep profile/streak/daily_intake)
        weekly["week_start"] = this_week_start_str
        weekly["days"] = {}
        save_user_data(user_data)

def load_today_intake_into_session(username: str):
    """
    Loads today's intake into st.session_state.total_intake.
    If last_login_date != today, create today's entry and set session total to 0.0 (auto-reset).
    This function does NOT delete user profile or credentials.
    """
    ensure_user_structures(username)
    today_str = date.today().strftime("%Y-%m-%d")
    daily = user_data[username].setdefault("daily_intake", {})
    last_login = daily.get("last_login_date")
    if last_login != today_str:
        # New day: set today's intake to 0.0, but do not remove other historical daily_intake entries
        daily["last_login_date"] = today_str
        daily.setdefault(today_str, 0.0)
        save_user_data(user_data)
        st.session_state.total_intake = 0.0
        # ephemeral session log resets
        st.session_state.water_intake_log = []
    else:
        st.session_state.total_intake = float(daily.get(today_str, 0.0))

def update_weekly_record_on_add(username: str, date_str: str, liters: float):
    """
    Update weekly_data.days[date_str] = liters for the current week.
    This persists the day's total so the weekly graph remains even after a new day's auto-reset.
    """
    ensure_user_structures(username)
    ensure_week_current(username)
    weekly = user_data[username]["weekly_data"]
    weekly_days = weekly.setdefault("days", {})
    weekly_days[date_str] = liters
    save_user_data(user_data)

# -------------------------------
# Session initialization
# -------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "page" not in st.session_state:
    st.session_state.page = "login"
if "username" not in st.session_state:
    st.session_state.username = ""
if "water_intake_log" not in st.session_state:
    st.session_state.water_intake_log = []
if "total_intake" not in st.session_state:
    st.session_state.total_intake = 0.0
if "show_chatbot" not in st.session_state:
    st.session_state.show_chatbot = False
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_goal_completed_at" not in st.session_state:
    st.session_state.last_goal_completed_at = None

# -------------------------------
# Country list utility
# -------------------------------
countries = [c.name for c in pycountry.countries]

# -------------------------------
# Mascot utilities & logic
# -------------------------------
GITHUB_ASSETS_BASE = "https://raw.githubusercontent.com/sri133/Water_Buddy/main/water_buddy/assets/"

def build_image_url(filename: str) -> str:
    return GITHUB_ASSETS_BASE + quote(filename, safe='')

@st.cache_data(ttl=300)
def get_location_from_ip():
    try:
        # Use ip-api to get lat/lon
        resp = requests.get("http://ip-api.com/json/?fields=status,message,lat,lon", timeout=4)
        if resp.status_code == 200:
            j = resp.json()
            if j.get("status") == "success":
                return {"lat": float(j.get("lat")), "lon": float(j.get("lon"))}
    except Exception:
        pass
    return None

@st.cache_data(ttl=300)
def get_current_temperature_c(lat: float, lon: float) -> Optional[float]:
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&timezone=UTC"
        resp = requests.get(url, timeout=4)
        if resp.status_code == 200:
            j = resp.json()
            cw = j.get("current_weather")
            if cw and "temperature" in cw:
                return float(cw["temperature"])
    except Exception:
        pass
    return None

def read_current_temperature_c() -> Optional[float]:
    # This helper is left for compatibility with other logic, but Home no longer displays temperature.
    try:
        if "CURRENT_TEMPERATURE_C" in st.secrets:
            return float(st.secrets["CURRENT_TEMPERATURE_C"])
    except Exception:
        pass
    try:
        t = os.getenv("CURRENT_TEMPERATURE_C")
        if t:
            return float(t)
    except Exception:
        pass
    loc = get_location_from_ip()
    if loc:
        return get_current_temperature_c(loc["lat"], loc["lon"])
    return None

def time_in_range(start: dtime, end: dtime, check: dtime) -> bool:
    if start <= end:
        return start <= check <= end
    else:
        return check >= start or check <= end

def is_within_reminder_window(frequency_minutes: int, tolerance_minutes: int = 5) -> bool:
    india_tz = pytz.timezone("Asia/Kolkata")
    now = datetime.now(india_tz)
    minutes_since_midnight = now.hour * 60 + now.minute
    if frequency_minutes <= 0:
        return False
    remainder = minutes_since_midnight % frequency_minutes
    return (remainder <= tolerance_minutes) or (frequency_minutes - remainder <= tolerance_minutes)

def ask_gemini_for_message(context: str, fallback: str) -> str:
    try:
        if model:
            prompt = f"You are Water Buddy, a friendly hydration assistant. Respond briefly (one or two sentences) based on this context: {context}\nOnly return the message text."
            response = model.generate_content(prompt)
            text_output = response.text.strip()
            text_output = " ".join(text_output.splitlines())
            if len(text_output) > 240:
                text_output = text_output[:237] + "..."
            return text_output
    except Exception:
        pass
    return fallback

def choose_mascot_and_message(page: str, username: str) -> Optional[Dict[str, str]]:
    """
    Returns a dict like {"image": url_or_local_path, "message": "...", "id": "..."}
    Added special-case: show assets/image (7).png on home between 13:40 and 14:30 IST
    """
    india_tz = pytz.timezone("Asia/Kolkata")
    now = datetime.now(india_tz)
    t = now.time()
    temp_c = read_current_temperature_c()

    ensure_user_structures(username)
    wp = user_data.get(username, {}).get("water_profile", {})
    freq_text = wp.get("frequency", "30 minutes")
    try:
        freq_minutes = int(re.findall(r"(\d+)", freq_text)[0])
    except Exception:
        freq_minutes = 30

    # Highest priority: post-daily-goal (5 minutes)
    last_completed_iso = st.session_state.get("last_goal_completed_at")
    if last_completed_iso:
        try:
            last_dt = datetime.fromisoformat(last_completed_iso)
            if (datetime.now() - last_dt) <= timedelta(minutes=5):
                img = build_image_url("image (9).png")
                context = "User just completed the daily water goal. Provide a fun water fact and a brief congratulatory message."
                msg = ask_gemini_for_message(context, "🎉 Amazing job — you hit your daily water goal! Fun fact: water makes up about 60% of the human body.")
                return {"image": img, "message": msg, "id": "post_goal"}
        except Exception:
            pass

    # Page-specific mascots
    if page == "login":
        img = build_image_url("image (1).png")
        context = "Greeting message for a user opening the login page. Keep it friendly and short."
        msg = ask_gemini_for_message(context, "Hi there! Welcome back to HP PARTNER — log in to track your hydration.")
        return {"image": img, "message": msg, "id": "login"}

    if page == "daily_streak":
        img = build_image_url("image (2).png")
        context = "Motivational message for the daily streak page. Give a short encouraging line and a tip. Update hourly."
        msg = ask_gemini_for_message(context, "🔥 Keep going — every sip counts! Tip: set small, consistent reminders to stay hydrated.")
        return {"image": img, "message": msg, "id": "daily_streak"}

    # SPECIAL HOME-TIME MASCOT: between 13:40 and 14:30 show image (7).png from assets or remote
    if page == "home":
        try:
            if time_in_range(dtime(13, 40), dtime(14, 30), t):
                # try local assets path variants first
                candidates = [Path("assets") / "image (7).png", Path("assets") / "image(7).png"]
                chosen = None
                for p in candidates:
                    if p.exists():
                        chosen = str(p)
                        break
                if not chosen:
                    # fallback to remote build_image_url
                    chosen = build_image_url("image (7).png")
                context = "Special midday mascot for hydration reminder."
                msg = ask_gemini_for_message(context, "Midday reminder — have a refreshing sip of water!")
                return {"image": chosen, "message": msg, "id": "special_midday"}
        except Exception:
            pass

        # Night window 21:30 -> 05:00
        night_start = dtime(hour=21, minute=30)
        night_end = dtime(hour=5, minute=0)
        if time_in_range(night_start, night_end, t):
            img = build_image_url("image (8).png")
            context = "Night greeting and tip for winding down hydration (avoid heavy drinking close to sleep). Keep it short."
            msg = ask_gemini_for_message(context, "🌙 It's late — sip lightly if needed and avoid heavy drinking right before sleep.")
            return {"image": img, "message": msg, "id": "night"}

        # Morning 05:00 - 09:00
        if time_in_range(dtime(5,0), dtime(9,0), t):
            img = build_image_url("image (6).jpg")
            context = "Morning greeting: energetic, short. Encourage starting the day with water."
            msg = ask_gemini_for_message(context, "Good morning! A glass of water is a great way to start your day — you've got this! 💧")
            return {"image": img, "message": msg, "id": "morning"}

        # Meal windows: Breakfast 08:00–09:00, Lunch 13:00–14:00, Dinner 20:30–21:30
        if time_in_range(dtime(8,0), dtime(9,0), t) or time_in_range(dtime(13,0), dtime(14,0), t) or time_in_range(dtime(20,30), dtime(21,30), t):
            img = build_image_url("image (5).jpg")
            context = "Meal-time tip about avoiding heavy drinking right before or after meals. Keep it short and practical."
            msg = ask_gemini_for_message(context, "During meals, avoid drinking large amounts right before or after eating — small sips are fine.")
            return {"image": img, "message": msg, "id": "meal"}

        # Reminder window (5 min before/after reminders)
        if is_within_reminder_window(freq_minutes, tolerance_minutes=5):
            img = build_image_url("image (4).png")
            context = f"Reminder / motivation message: remind the user to drink water now. Frequency: every {freq_minutes} minutes."
            msg = ask_gemini_for_message(context, "⏰ Time for a sip! A quick drink will keep you on track for your daily goal.")
            return {"image": img, "message": msg, "id": "reminder"}

        # Hot weather (kept for logic, but Home doesn't show temperature)
        if temp_c is not None and temp_c >= 40.0:
            for fname in ["image (7).png", "image (7).jpg", "image (7).jpeg"]:
                img = build_image_url(fname)
                context = f"Hot weather advice for {temp_c}°C — short tip to hydrate more and avoid heat stress."
                msg = ask_gemini_for_message(context, f"It's hot outside ({temp_c}°C). Drink more frequently and avoid long sun exposure.")
                return {"image": img, "message": msg, "id": "hot_weather"}

        # Fallback home mascot
        img = build_image_url("image (3).png")
        today_str = date.today().strftime("%Y-%m-%d")
        today_intake = user_data.get(username, {}).get("daily_intake", {}).get(today_str, 0.0)
        if today_intake < user_data.get(username, {}).get("water_profile", {}).get("daily_goal", 2.5) * 0.5:
            context = "Friendly greeting and gentle reminder to drink a little water if the user is less than 50% to today's goal."
            msg = ask_gemini_for_message(context, "Hi! A little sip now will keep you feeling fresh — you're doing great!")
        else:
            context = "Friendly greeting for the home page."
            msg = ask_gemini_for_message(context, "Hello! Keep up the good work — you're doing well with your hydration today.")
        return {"image": img, "message": msg, "id": "home_fallback"}

    # Report page: intentionally NO mascot to keep it clean
    if page == "report":
        return None

    # Default fallback
    img = build_image_url("image (3).png")
    msg = ask_gemini_for_message("Default greeting", "Hi! I'm Water Buddy — how can I help you stay hydrated today?")
    return {"image": img, "message": msg, "id": "default"}

def render_mascot_inline(mascot: Optional[Dict[str, str]]):
    """
    Render the mascot inline in the page content.
    """
    if not mascot:
        return
    img = mascot.get("image")
    message = mascot.get("message", "")

    col_img, col_msg = st.columns([1, 4])
    with col_img:
        try:
            st.image(img, width=90)
        except Exception:
            try:
                # try local assets fallback
                local = Path("assets") / os.path.basename(img)
                if local.exists():
                    st.image(str(local), width=90)
                else:
                    raise
            except Exception:
                st.markdown("<div style='width:90px; height:90px; background:#f0f0f0; border-radius:12px;'></div>", unsafe_allow_html=True)
    with col_msg:
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(180deg, rgba(250,250,255,1), rgba(242,249,255,1));
                padding: 12px 14px;
                border-radius: 14px;
                box-shadow: 0 8px 22px rgba(0,0,0,0.06);
                color:#111;
                font-size:15px;
                line-height:1.35;
            ">
                {message}
            </div>
            """,
            unsafe_allow_html=True
        )

# -------------------------------
# Quiz utilities (unchanged)
# -------------------------------
def generate_quiz_via_model():
    """Ask Gemini to generate 10 MCQ questions in JSON format."""
    fallback = generate_quiz_fallback()
    try:
        if not model:
            return fallback
        prompt = """
Generate 10 multiple-choice questions about water (health/hydration facts, water history, and recent water-related news/documentaries).
Return as valid JSON array only. Each item must be an object with fields:
- "q": question text
- "options": array of 4 option strings
- "correct_index": index of correct option (0..3)
- "explanation": short explanation (1-2 sentences) why the correct answer is correct.
Keep each question concise and suitable for general audience.
"""
        resp = model.generate_content(prompt)
        text = resp.text.strip()
        json_start = text.find("[")
        json_text = text if json_start == 0 else text[json_start:]
        data = json.loads(json_text)
        if isinstance(data, list) and len(data) >= 10:
            return data[:10]
        else:
            return fallback
    except Exception:
        return fallback

def generate_quiz_fallback():
    sample = [
        {
            "q": "What percentage of the adult human body is roughly water?",
            "options": ["~30%", "~60%", "~80%", "~95%"],
            "correct_index": 1,
            "explanation": "About 60% of an adult human's body is water, though this varies with age, sex, and body composition."
        },
        {
            "q": "Which process returns water to the atmosphere from plants?",
            "options": ["Condensation", "Precipitation", "Transpiration", "Infiltration"],
            "correct_index": 2,
            "explanation": "Transpiration is the process where plants release water vapor to the atmosphere from their leaves."
        },
        {
            "q": "Which is the primary source of fresh water for most cities?",
            "options": ["Seawater", "Groundwater and rivers/lakes", "Glaciers only", "Rainwater only"],
            "correct_index": 1,
            "explanation": "Most cities rely on surface water (rivers/lakes) and groundwater; sources vary by region."
        },
        {
            "q": "Who invented the steam engine that helped early water pumping in the 1700s?",
            "options": ["James Watt", "Isaac Newton", "Thomas Edison", "Nikola Tesla"],
            "correct_index": 0,
            "explanation": "James Watt improved steam engine designs that were important for pumping and industrial uses."
        },
        {
            "q": "What is a common method to make seawater drinkable?",
            "options": ["Filtration only", "Chlorination", "Desalination", "Sedimentation"],
            "correct_index": 2,
            "explanation": "Desalination removes salts and minerals from seawater, making it suitable to drink."
        },
        {
            "q": "Which documentary theme would most likely be featured on a water-focused film?",
            "options": ["Space travel", "Water scarcity and conservation", "Mountain climbing", "Astrophysics"],
            "correct_index": 1,
            "explanation": "Water-focused documentaries often highlight scarcity, conservation, pollution, and solutions."
        },
        {
            "q": "What is the main reason to avoid drinking large volumes right before bed?",
            "options": ["It causes headaches", "It can disrupt sleep with bathroom trips", "It freezes in the body", "It removes vitamins"],
            "correct_index": 1,
            "explanation": "Drinking a lot before sleep may lead to waking up at night to use the bathroom, disrupting sleep."
        },
        {
            "q": "Which gas dissolves in water and is essential for plant photosynthesis?",
            "options": ["Oxygen", "Nitrogen", "Carbon dioxide", "Helium"],
            "correct_index": 2,
            "explanation": "Carbon dioxide dissolves in water and is used by aquatic plants in photosynthesis."
        },
        {
            "q": "Which ancient civilization developed advanced irrigation systems?",
            "options": ["Incas", "Indus Valley, Mesopotamia, and Egyptians", "Victorians", "Aztecs only"],
            "correct_index": 1,
            "explanation": "Civilizations like Mesopotamia, the Indus Valley, and ancient Egypt developed early irrigation to support agriculture."
        },
        {
            "q": "What is one simple way households can conserve water daily?",
            "options": ["Run taps while brushing teeth", "Take longer showers", "Repair leaks and use efficient fixtures", "Water the lawn midday"],
            "correct_index": 2,
            "explanation": "Fixing leaks and using efficient fixtures (low-flow faucets, showerheads) is an effective way to conserve water."
        }
    ]
    return sample

def get_daily_quiz():
    today_str = date.today().isoformat()
    if st.session_state.get("daily_quiz_date") == today_str and st.session_state.get("daily_quiz"):
        return st.session_state["daily_quiz"]
    quiz = generate_quiz_via_model()
    st.session_state["daily_quiz_date"] = today_str
    st.session_state["daily_quiz"] = quiz
    return quiz

def grade_quiz_and_explain(quiz, answers):
    results = []
    score = 0
    for i, item in enumerate(quiz):
        correct = item.get("correct_index", 0)
        selected = answers[i]
        is_correct = (selected == correct)
        if is_correct:
            score += 1
        explanation = item.get("explanation")
        if not explanation:
            context = f"Explain why the option '{item['options'][correct]}' is the correct answer for the question: {item['q']}"
            explanation = ask_gemini_for_message(context, "This is the correct answer because of established facts.")
        results.append({
            "q": item["q"],
            "options": item["options"],
            "correct_index": correct,
            "selected_index": selected,
            "is_correct": is_correct,
            "explanation": explanation
        })
    return results, score

# -------------------------------
# RESET helper (safe, fixed)
# -------------------------------
def reset_page_inputs_session():
    """
    Safely clear session-only user inputs and ephemeral page-level values.
    Do NOT modify database (user_data) or credentials. Only session-level entries cleared.
    Then rerun so Streamlit widgets reflect cleared state.
    """
    # Keys to preserve (auth & navigation)
    preserve = {"logged_in", "username", "page"}
    # Collect keys to delete
    keys_to_delete = [k for k in list(st.session_state.keys()) if k not in preserve]

    for k in keys_to_delete:
        try:
            del st.session_state[k]
        except Exception:
            # some Streamlit internal keys might be protected; skip them
            pass

    # Recreate important defaults (without assigning None where possible)
    st.session_state.total_intake = 0.0
    st.session_state.water_intake_log = []
    st.session_state.chat_history = []
    st.session_state.show_chatbot = False
    # quiz defaults
    st.session_state.quiz_answers = None
    st.session_state.quiz_submitted = False
    st.session_state.quiz_results = None
    st.session_state.quiz_score = 0
    st.session_state.daily_quiz = None
    st.session_state.daily_quiz_date = None
    # last_goal_completed_at might be absent; do not force None assignment if problematic
    try:
        st.session_state.last_goal_completed_at = None
    except Exception:
        pass

    # Rerun app so widgets reflect cleared values
    st.experimental_rerun()

# -------------------------------
# LOGIN PAGE
# -------------------------------
if st.session_state.page == "login":
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 HP PARTNER</h1>", unsafe_allow_html=True)
    st.markdown("### Login or Sign Up to Continue")

    option = st.radio("Choose Option", ["Login", "Sign Up"])
    username = st.text_input("Enter Username", key="login_username")
    password = st.text_input("Enter Password", type="password", key="login_password")

    if st.button("Submit"):
        users, user_data = load_all_from_db()

        if option == "Sign Up":
            if username in users:
                st.error("❌ Username already exists.")
            elif username == "" or password == "":
                st.error("❌ Username and password cannot be empty.")
            else:
                users[username] = password
                save_credentials(users)
                if username not in user_data:
                    user_data[username] = {}
                user_data[username].setdefault("profile", {})
                user_data[username]["ai_water_goal"] = 2.5
                user_data[username]["water_profile"] = {"daily_goal": 2.5, "frequency": "30 minutes"}
                user_data[username]["streak"] = {"completed_days": [], "current_streak": 0}
                user_data[username]["daily_intake"] = {}
                yesterday_str = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
                user_data[username]["daily_intake"]["last_login_date"] = yesterday_str
                user_data[username]["weekly_data"] = {"week_start": None, "days": {}}
                save_user_data(user_data)
                st.success("✅ Account created successfully! Please login.")
        
        elif option == "Login":
            if username in users and users[username] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                ensure_user_structures(username)
                load_today_intake_into_session(username)
                ensure_week_current(username)
                if username in user_data and user_data[username].get("profile"):
                    go_to_page("home")
                else:
                    go_to_page("settings")
            else:
                st.error("❌ Invalid username or password.")

    # Inline mascot for login
    mascot = choose_mascot_and_message("login", st.session_state.username or "")
    render_mascot_inline(mascot)

    # Login note (requested)
    st.markdown(
        '<p style="font-size:14px; color:gray;">If you don’t have an account, please sign up first, then change the option to Login and submit again so you can log in.</p>',
        unsafe_allow_html=True
    )

    # Reset button (bottom) - clears page-level inputs
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Reset Page", key="reset_login"):
        reset_page_inputs_session()

# -------------------------------
# PERSONAL SETTINGS PAGE (unchanged behaviour)
# -------------------------------
elif st.session_state.page == "settings":
    if not st.session_state.logged_in:
        go_to_page("login")

    username = st.session_state.username
    ensure_user_structures(username)
    saved = user_data.get(username, {}).get("profile", {})
    
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 Personal Settings</h1>", unsafe_allow_html=True)
    
    name = st.text_input("Name", value=saved.get("Name", username), key="settings_name")
    age = st.text_input("Age", value=saved.get("Age", ""), key="settings_age")
    country = st.selectbox("Country", countries, index=countries.index(saved.get("Country", "India")) if saved.get("Country") else countries.index("India"), key="settings_country")
    language = st.text_input("Language", value=saved.get("Language", ""), key="settings_language")
    
    st.write("---")
    
    height_unit = st.radio("Height Unit", ["cm", "feet"], horizontal=True, key="settings_height_unit")
    height = st.number_input(
        f"Height ({height_unit})",
        value=float(saved.get("Height", "0").split()[0]) if "Height" in saved else 0.0,
        key="settings_height"
    )
    
    weight_unit = st.radio("Weight Unit", ["kg", "lbs"], horizontal=True, key="settings_weight_unit")
    weight = st.number_input(
        f"Weight ({weight_unit})",
        value=float(saved.get("Weight", "0").split()[0]) if "Weight" in saved else 0.0,
        key="settings_weight"
    )

    def calculate_bmi(weight, height, weight_unit, height_unit):
        if height_unit == "feet":
            height_m = height * 0.3048
        else:
            height_m = height / 100
            
        if weight_unit == "lbs":
            weight_kg = weight * 0.453592
        else:
            weight_kg = weight
            
        return round(weight_kg / (height_m ** 2), 2) if height_m > 0 else 0

    bmi = calculate_bmi(weight, height, weight_unit, height_unit)
    st.write(f"**Your BMI is:** {bmi}")

    health_condition = st.radio(
        "Health condition", ["Excellent", "Fair", "Poor"],
        horizontal=True,
        index=["Excellent", "Fair", "Poor"].index(saved.get("Health Condition", "Excellent")),
        key="settings_health_condition"
    )
    health_problems = st.text_area("Health problems", value=saved.get("Health Problems", ""), key="settings_health_problems")

    st.write("---")

    old_profile = user_data.get(username, {}).get("profile", {})
    new_profile_data = {
        "Name": name,
        "Age": age,
        "Country": country,
        "Language": language,
        "Height": f"{height} {height_unit}",
        "Weight": f"{weight} {weight_unit}",
        "BMI": bmi,
        "Health Condition": health_condition,
        "Health Problems": health_problems,
    }

    if st.button("Save & Continue ➡️"):
        recalc_needed = new_profile_data != old_profile
        
        if recalc_needed:
            with st.spinner("🤖 Water Buddy is calculating your ideal water intake..."):
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
                            suggested_water_intake = float(match.group(1))
                        else:
                            raise ValueError("No numeric value found.")
                    else:
                        raise RuntimeError("Model not configured")
                except Exception as e:
                    st.warning(f"⚠️ Water Buddy suggestion failed, using default 2.5 L ({e})")
                    suggested_water_intake = 2.5
                    text_output = f"Error: {e}"
        else:
            suggested_water_intake = user_data.get(username, {}).get("ai_water_goal", 2.5)
            text_output = "Profile unchanged — using previous goal."
            
        ensure_user_structures(username)
        user_data[username]["profile"] = new_profile_data
        user_data[username]["ai_water_goal"] = round(suggested_water_intake, 2)
        user_data[username].setdefault("water_profile", {"daily_goal": suggested_water_intake, "frequency": "30 minutes"})
        user_data[username].setdefault("streak", {"completed_days": [], "current_streak": 0})
        user_data[username].setdefault("daily_intake", user_data[username].get("daily_intake", {}))
        user_data[username].setdefault("weekly_data", user_data[username].get("weekly_data", {"week_start": None, "days": {}}))
        
        save_user_data(user_data)
        
        st.success(f"✅ Profile saved! Water Buddy suggests {suggested_water_intake:.2f} L/day 💧")
        st.info(f"Water Buddy output: {text_output}")
        go_to_page("water_profile")

    # Reset button (bottom)
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Reset Page", key="reset_settings"):
        reset_page_inputs_session()

# -------------------------------
# WATER INTAKE PAGE
# -------------------------------
elif st.session_state.page == "water_profile":
    if not st.session_state.logged_in:
        go_to_page("login")

    username = st.session_state.username
    ensure_user_structures(username)
    ai_goal = user_data.get(username, {}).get("ai_water_goal", 2.5)
    saved = user_data.get(username, {}).get("water_profile", {})

    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 Water Intake</h1>", unsafe_allow_html=True)
    st.success(f"Your ideal daily water intake is **{ai_goal} L/day**, as suggested by Water Buddy 💧")
    
    daily_goal = st.slider("Set your daily water goal (L):", 0.5, 10.0, float(ai_goal), 0.1, key="water_profile_daily_goal")
    
    frequency_options = [f"{i} minutes" for i in range(5, 185, 5)]
    selected_frequency = st.selectbox(
        "🔔 Reminder Frequency:",
        frequency_options,
        index=frequency_options.index(saved.get("frequency", "30 minutes")),
        key="water_profile_frequency"
    )
    
    if st.button("💾 Save & Continue ➡️"):
        user_data[username]["water_profile"] = {"daily_goal": daily_goal, "frequency": selected_frequency}
        save_user_data(user_data)
        st.success("✅ Water profile saved successfully!")
        go_to_page("home")

    # Reset button (bottom)
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Reset Page", key="reset_water_profile"):
        reset_page_inputs_session()

# -------------------------------
# HOME PAGE (persistent bottle + auto-reset at midnight)
# -------------------------------
elif st.session_state.page == "home":
    if not st.session_state.logged_in:
        go_to_page("login")

    username = st.session_state.username
    ensure_user_structures(username)
    today_dt = date.today()
    today_str = today_dt.strftime("%Y-%m-%d")

    # Load / auto-reset today's intake for this user (doesn't wipe profile)
    load_today_intake_into_session(username)
    # Ensure weekly record exists and is for current week
    ensure_week_current(username)

    daily_goal = user_data.get(username, {}).get("water_profile", {}).get(
        "daily_goal", user_data.get(username, {}).get("ai_water_goal", 2.5)
    )
    
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 HP PARTNER</h1>", unsafe_allow_html=True)

    # NOTE: Home temperature/weather removed per request.
    # Mascot display is handled by choose_mascot_and_message (special-case between 13:40-14:30)

    fill_percent = min(st.session_state.total_intake / daily_goal, 1.0) if daily_goal > 0 else 0
    
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
                liters = ml / 1000
                st.session_state.total_intake += liters
                st.session_state.water_intake_log.append(f"{ml} ml")
                st.success(f"✅ Added {ml} ml of water!")
                
                # Persist today's total intake (only update daily_intake and weekly_data)
                ensure_user_structures(username)
                user_data[username].setdefault("daily_intake", {})
                user_data[username].setdefault("weekly_data", {"week_start": None, "days": {}})
                user_data[username].setdefault("streak", {"completed_days": [], "current_streak": 0})
                user_data[username].setdefault("water_profile", {"daily_goal": 2.5, "frequency": "30 minutes"})

                # Save today's intake without wiping other user fields
                user_data[username]["daily_intake"][today_str] = st.session_state.total_intake
                user_data[username]["daily_intake"]["last_login_date"] = today_str

                # Also update weekly_data so the weekly graph remains
                update_weekly_record_on_add(username, today_str, st.session_state.total_intake)

                # Update streak info (unchanged logic)
                user_streak = user_data[username]["streak"]
                daily_goal_for_checks = user_data[username]["water_profile"].get("daily_goal", 2.5)
                
                if st.session_state.total_intake >= daily_goal_for_checks:
                    if today_str not in user_streak.get("completed_days", []):
                        user_streak.setdefault("completed_days", []).append(today_str)
                        user_streak["completed_days"] = sorted(list(set(user_streak["completed_days"])))
                        
                        completed_dates = sorted([datetime.strptime(d, "%Y-%m-%d").date() for d in user_streak["completed_days"]])
                        
                        streak = 0
                        day_cursor = date.today()
                        while True:
                            if day_cursor in completed_dates:
                                streak += 1
                                day_cursor = day_cursor - timedelta(days=1)
                            else:
                                break
                        
                        user_streak["current_streak"] = streak
                        user_data[username]["streak"] = user_streak

                # Save user_data after modifications
                save_user_data(user_data)
                
                # Trigger post-goal mascot: set session timestamp when user first completes
                if st.session_state.total_intake >= daily_goal:
                    if not st.session_state.last_goal_completed_at:
                        st.session_state.last_goal_completed_at = datetime.now().isoformat()
                
                # Rerun to refresh UI
                st.rerun()
                st.stop()
                
            except ValueError:
                st.error("❌ Please enter a valid number like 700, 700ml, or 700 ml.")
        else:
            st.error("❌ Please enter a valid number like 700, 700ml, or 700 ml.")

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
            # clear session-only state, keep files intact
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.total_intake = 0.0
            st.session_state.water_intake_log = []
            go_to_page("login")

    # NEW: Quiz navigation button (like other page buttons)
    st.write("")
    if st.button("🧠 Take Today's Quiz"):
        go_to_page("quiz")

    # Chatbot (unchanged)
    st.markdown("""
    <style>
    .chat-button {
        position: fixed;
        bottom: 25px;
        right: 25px;
        background-color: #1A73E8;
        border-radius: 50%;
        width: 60px;
        height: 60px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 28px;
        cursor: pointer;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        z-index: 999;
    }
    .chat-window {
        position: fixed;
        bottom: 100px;
        right: 25px;
        width: 350px;
        background: white;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        padding: 15px;
        z-index: 1000;
        overflow-y: auto;
        max-height: 400px;
        scrollbar-width: none;
    }
    .chat-window::-webkit-scrollbar {
        display: none;
    }
    .bot-message {
        text-align: left;
        color: #222;
        background: #F1F1F1;
        padding: 8px 10px;
        border-radius: 10px;
        margin: 5px 0;
        display: inline-block;
    }
    </style>
    """, unsafe_allow_html=True)

    chat_button_clicked = st.button("🤖", key="chat_button", help="Chat with Water Buddy")
    if chat_button_clicked:
        st.session_state.show_chatbot = not st.session_state.show_chatbot

    if st.session_state.show_chatbot:
        with st.container():
            st.markdown("<div class='chat-window'>", unsafe_allow_html=True)
            st.markdown("""
            <div style='text-align:center; color:#1A73E8; font-weight:600; font-size:18px;'>
                💬 Water Buddy <span style='font-size:14px; color:#555;'>— powered by Gemini 2.5 Flash</span>
            </div>
            """, unsafe_allow_html=True)
            
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
                    st.rerun()

    # Mascot inline on Home page (below the main content)
    mascot = choose_mascot_and_message("home", username)
    render_mascot_inline(mascot)

    # Home page note (requested)
    st.markdown(
        '<p style="font-size:14px; color:gray;">Use a calibrated water bottle to enter correct value of water intake. If needed, you can ask the Water Buddy chatbot for a buying link.</p>',
        unsafe_allow_html=True
    )

    # Reset button (bottom) - clears session-level inputs only (not DB)
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Reset Page", key="reset_home"):
        reset_page_inputs_session()

# -------------------------------
# QUIZ PAGE
# -------------------------------
elif st.session_state.page == "quiz":
    if not st.session_state.logged_in:
        go_to_page("login")
    username = st.session_state.username
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>🧠 Daily Water Quiz</h1>", unsafe_allow_html=True)
    st.write("Test your water knowledge — 10 questions. Explanations will be shown after you submit.")
    st.write("---")

    # Load or generate today's quiz
    quiz = get_daily_quiz()  # returns list of 10 dicts
    # ensure length 10
    if not quiz or len(quiz) < 1:
        st.error("❗ Could not load quiz right now. Try again later.")
    else:
        # Display questions with radio options A-D
        if "quiz_answers" not in st.session_state:
            st.session_state.quiz_answers = [None] * len(quiz)
        if "quiz_submitted" not in st.session_state:
            st.session_state.quiz_submitted = False
            st.session_state.quiz_results = None
            st.session_state.quiz_score = None

        # For each question show radios
        for i, item in enumerate(quiz):
            q_text = item.get("q", f"Question {i+1}")
            options = item.get("options", [])
            # ensure 4 options
            if len(options) < 4:
                # pad if needed
                while len(options) < 4:
                    options.append("N/A")
            st.markdown(f"**Q{i+1}. {q_text}**")
            # map options to labels A-D
            labels = ["A", "B", "C", "D"]
            full_options = [f"{labels[j]}. {options[j]}" for j in range(4)]
            default_index = 0
            existing = st.session_state.quiz_answers[i]
            selected = st.radio(f"Select answer for Q{i+1}", full_options, index=existing if existing is not None else 0, key=f"q_{i}")
            # store selected index
            sel_index = full_options.index(selected)
            st.session_state.quiz_answers[i] = sel_index
            st.write("")

        # Submit button
        if not st.session_state.quiz_submitted:
            if st.button("Submit Answers"):
                # grade
                answers = [ans if ans is not None else 0 for ans in st.session_state.quiz_answers]
                results, score = grade_quiz_and_explain(quiz, answers)
                st.session_state.quiz_results = results
                st.session_state.quiz_score = score
                st.session_state.quiz_submitted = True
                # optionally persist user quiz history under user_data
                ensure_user_structures(username)
                user_hist = user_data[username].setdefault("quiz_history", {})
                today = date.today().isoformat()
                user_hist[today] = {"score": score, "total": len(quiz), "timestamp": datetime.now().isoformat()}
                save_user_data(user_data)
                st.experimental_rerun()

        else:
            # show results
            results = st.session_state.quiz_results
            score = st.session_state.quiz_score or 0
            st.markdown(f"## Results — Score: **{score} / {len(quiz)}**")
            for i, r in enumerate(results):
                q = r["q"]
                options = r["options"]
                correct_index = r["correct_index"]
                selected_index = r["selected_index"]
                is_correct = r["is_correct"]
                explanation = r["explanation"]
                label_map = ["A","B","C","D"]
                st.markdown(f"**Q{i+1}. {q}**")
                for idx, opt in enumerate(options):
                    prefix = "✅" if idx == correct_index else ("🔸" if idx == selected_index and not is_correct else "•")
                    st.write(f"{prefix} {label_map[idx]}. {opt}")
                if is_correct:
                    st.success(f"Correct — {explanation}")
                else:
                    st.error(f"Wrong. {explanation}")
                st.write("---")
            # final motivational message via gemini
            try:
                msg = ask_gemini_for_message(f"Congratulate user for taking today's water quiz and give a short motivational line based on score {score} out of {len(quiz)}.", "Nice work — keep learning about water and stay hydrated!")
                st.info(msg)
            except Exception:
                pass

    # Navigation buttons (same style as other pages)
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("🏠 Home"):
            go_to_page("home")
    with col2:
        if st.button("👤 Personal Settings"):
            go_to_page("settings")
    with col3:
        if st.button("🚰 Water Intake"):
            go_to_page("water_profile")
    with col4:
        if st.button("📈 Report"):
            go_to_page("report")
    with col5:
        if st.button("🔥 Daily Streak"):
            go_to_page("daily_streak")

    # Reset button (bottom)
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Reset Page", key="reset_quiz"):
        reset_page_inputs_session()

# -------------------------------
# REPORT PAGE (no mascot)
# -------------------------------
elif st.session_state.page == "report":
    if not st.session_state.logged_in:
        go_to_page("login")

    username = st.session_state.username
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>📊 Hydration Report</h1>", unsafe_allow_html=True)
    st.write("---")

    ensure_user_structures(username)
    ensure_week_current(username)

    completed_iso = user_data[username]["streak"].get("completed_days", [])
    completed_dates = []
    for s in completed_iso:
        try:
            d = datetime.strptime(s, "%Y-%m-%d").date()
            completed_dates.append(d)
        except Exception:
            continue
    
    today = date.today()
    daily_goal = user_data[username]["water_profile"].get("daily_goal", user_data[username].get("ai_water_goal", 2.5))

    if today in completed_dates:
        today_pct = 100
    else:
        if st.session_state.total_intake:
            today_pct = min(round(st.session_state.total_intake / daily_goal * 100), 100)
        else:
            today_pct = 0

    st.markdown("### Today's Progress")
    fig_daily = go.Figure(go.Indicator(
        mode="gauge+number",
        value=today_pct,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Today's Hydration", 'font': {'size': 18}},
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': "#1A73E8"},
            'steps': [
                {'range': [0, 50], 'color': "#FFD9D9"},
                {'range': [50, 75], 'color': "#FFF1B6"},
                {'range': [75, 100], 'color': "#D7EEFF"}
            ],
            'threshold': {
                'line': {'color': "#0B63C6", 'width': 6},
                'thickness': 0.75,
                'value': 100
            }
        }
    ))
    fig_daily.update_layout(height=300, margin=dict(l=20, r=20, t=30, b=20), paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_daily, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False})

    if today_pct >= 100:
        st.success("🏆 Goal achieved today! Fantastic work — keep the streak alive! 💧")
    elif today_pct >= 75:
        st.info(f"💦 You're {today_pct}% there — a little more and you hit the goal!")
    elif today_pct > 0:
        st.info(f"🙂 You've completed {today_pct}% of your goal today — keep sipping!")
    else:
        st.info("🎯 Not started yet — let's drink some water and get moving!")

    st.write("---")

    st.markdown("### Weekly Progress (Mon → Sun) — Current Week")
    weekly = user_data[username].get("weekly_data", {"week_start": None, "days": {}})
    week_start_str = weekly.get("week_start")
    if not week_start_str:
        week_start_dt = current_week_start()
        week_start_str = week_start_dt.strftime("%Y-%m-%d")
        weekly["week_start"] = week_start_str
        save_user_data(user_data)

    week_start_dt = datetime.strptime(week_start_str, "%Y-%m-%d").date()
    week_days = [week_start_dt + timedelta(days=i) for i in range(7)]
    labels = [d.strftime("%a\n%d %b") for d in week_days]
    week_days_str = [d.strftime("%Y-%m-%d") for d in week_days]

    liters_list = []
    pct_list = []
    status_list = []

    for d_str, d in zip(week_days_str, week_days):
        liters = weekly.get("days", {}).get(d_str)
        if liters is None:
            # if it's today, show session value; otherwise 0
            if d == today:
                liters = st.session_state.total_intake
            else:
                liters = 0.0
        liters_list.append(liters)
        pct = min(round((liters / daily_goal) * 100), 100) if daily_goal > 0 else 0
        pct_list.append(pct)

        if d > today:
            status = "upcoming"
        else:
            if pct >= 100:
                status = "achieved"
            elif pct >= 75:
                status = "almost"
            elif pct > 0:
                status = "partial"
            else:
                status = "missed"
        status_list.append(status)

    def week_color_for_status(s):
        if s == "achieved":
            return "#1A73E8"
        if s == "almost":
            return "#FFD23F"
        if s == "partial":
            return "#FFD9A6"
        if s == "upcoming":
            return "rgba(255,255,255,0.06)"
        return "#FF6B6B"

    colors = [week_color_for_status(s) for s in status_list]
    df_week = pd.DataFrame({"label": labels, "pct": pct_list, "liters": liters_list, "status": status_list})

    fig_week = go.Figure()
    fig_week.add_trace(go.Bar(
        x=df_week["label"],
        y=df_week["pct"],
        marker_color=colors,
        text=[f"{v}%" if v > 0 else "" for v in df_week["pct"]],
        textposition='outside',
        hovertemplate="%{x}<br>%{y}%<br>Liters: %{customdata} L<extra></extra>",
        customdata=[round(v,2) for v in df_week["liters"]]
    ))
    fig_week.update_layout(yaxis={'title': 'Completion %', 'range': [0, 100]}, showlegend=False,
                            margin=dict(l=20, r=20, t=20, b=40), height=340,
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_week, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': True})

    # Report note about zoom behavior (requested)
    st.markdown(
        '<p style="font-size:14px; color:gray;">Please double-tap to zoom out from the graph.</p>',
        unsafe_allow_html=True
    )

    achieved_days = sum(1 for s, d in zip(status_list, week_days) if d <= today and s == "achieved")
    almost_days = sum(1 for s, d in zip(status_list, week_days) if d <= today and s == "almost")
    missed_days = sum(1 for s, d in zip(status_list, week_days) if d <= today and s == "missed")

    st.write("---")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("🏠 Home"):
            go_to_page("home")
    with col2:
        if st.button("👤 Personal Settings"):
            go_to_page("settings")
    with col3:
        if st.button("🚰 Water Intake"):
            go_to_page("water_profile")
    with col4:
        st.info("You're on Report")
    with col5:
        if st.button("🔥 Daily Streak"):
            go_to_page("daily_streak")

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

    ensure_user_structures(username)
    streak_info = user_data[username].get("streak", {"completed_days": [], "current_streak": 0})
    completed_iso = streak_info.get("completed_days", [])
    current_streak = streak_info.get("current_streak", 0)

    completed_dates = []
    for s in completed_iso:
        try:
            d = datetime.strptime(s, "%Y-%m-%d").date()
            completed_dates.append(d)
        except Exception:
            continue

    star_css = """
    <style>
    .star-grid {
       display: grid;
       grid-template-columns: repeat(6, 1fr);
       gap: 14px;
       justify-items: center;
       align-items: center;
       padding: 6px 4%;
    }
    .star {
       width:42px;
       height:42px;
       display:flex;
       align-items:center;
       justify-content:center;
       font-size:16px;
       border-radius:6px;
       transition: transform .12s ease, box-shadow .12s ease, background-color .12s ease, filter .12s ease;
       cursor: pointer;
       user-select: none;
       text-decoration:none;
       line-height:1;
    }
    .star:hover { transform: translateY(-6px) scale(1.06); }
    .star.dim {
       background: rgba(255,255,255,0.03);
       color: #bdbdbd;
       box-shadow: none;
       filter: grayscale(10%);
    }
    .star.upcoming {
       background: rgba(255,255,255,0.02);
       color: #999;
       box-shadow: none;
       filter: grayscale(30%);
    }
    .star.achieved {
       background: radial-gradient(circle at 30% 20%, #fff6c2, #ffd85c 40%, #ffb400 100%);
       color: #4b2a00;
       box-shadow: 0 8px 22px rgba(255,176,0,0.42), 0 2px 6px rgba(0,0,0,0.18);
    }
    .star.small { width:38px; height:38px; font-size:14px; }
    @media(max-width:600px){
       .star-grid { grid-template-columns: repeat(4, 1fr); gap:10px; }
       .star { width:36px; height:36px; font-size:14px; }
    }
    </style>
    """

    stars_html = "<div class='star-grid'>"
    for d in range(1, days_in_month + 1):
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
                card_html += "<p.style='margin:0; font-size:14px; color:#333;'>🎉 Goal completed on this day! Great job.</p>"
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
    completed_dates_in_month = sorted([d for d in completed_dates if d.year == year and d.month == month])
    completed_days_numbers = [d.day for d in completed_dates_in_month]
    last_completed_day_num = max(completed_days_numbers) if completed_days_numbers else None

    st.markdown(f"<h2 style='text-align:center; color:#1A73E8;'>🔥 Daily Streak: {current_streak} Days</h2>", unsafe_allow_html=True)
    st.write("---")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("🏠 Home"):
            go_to_page("home")
    with col2:
        if st.button("👤 Personal Settings"):
            go_to_page("settings")
    with col3:
        if st.button("🚰 Water Intake"):
            go_to_page("water_profile")
    with col4:
        if st.button("📈 Report"):
            go_to_page("report")
    with col5:
        st.info("You're on Daily Streak")

    # Mascot inline next to streak header / content
    mascot = choose_mascot_and_message("daily_streak", username)
    render_mascot_inline(mascot)

# -------------------------------
# End of App
# -------------------------------

# conn remains open for lifetime
# conn.close()  # if needed

