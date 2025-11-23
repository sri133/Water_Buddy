# app.py
# Full Water Buddy app with mascots, Quiz page, Thirsty Cup, and Web Speech TTS
# Merged and updated: autoplay TTS for Gemini home motivational lines, TTS on add-water and game-win

import streamlit as st
from streamlit.components.v1 import html as st_html
import json
import firebase_admin
from firebase_admin import credentials, firestore
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
import time
from gtts import gTTS
import base64
import matplotlib.pyplot as plt
import numpy as np

if "firebase_initialized" not in st.session_state:
    firebase_json = json.loads(st.secrets["FIREBASE_JSON"])
    cred = credentials.Certificate(firebase_json)
    firebase_admin.initialize_app(cred)
    st.session_state.firebase_initialized = True

db = firestore.client()
# -----------------------------------------
# ADD THIS FUNCTION RIGHT HERE
# -----------------------------------------
def text_to_speech(text):
    from gtts import gTTS
    import tempfile

    tts = gTTS(text)
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tts.save(temp.name)
    return temp.name

def play_tts(text, lang="en"):
    tts = gTTS(text=text, lang=lang)
    tts.save("tts_output.mp3")
    
    audio_file = open("tts_output.mp3", "rb").read()
    audio_base64 = base64.b64encode(audio_file).decode()

    # JS autoplay hack for Streamlit
    autoplay_html = f"""
        <audio id="tts_audio" autoplay>
            <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
        </audio>
        <script>
            var audio = document.getElementById("tts_audio");
            audio.play();
        </script>
    """

    st.markdown(autoplay_html, unsafe_allow_html=True)

# --- helper to set CSS background
def set_background():
    color = st.session_state.get("background_color", "white")
    st.markdown(
        f"""
        <style>
        body, .stApp {{
            background-color: {color};
        }}
        .main .block-container {{
            padding-top: 1rem;
            padding-bottom: 1rem;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

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
    if username not in user_data:
        user_data[username] = {}
    user = user_data[username]
    user.setdefault("profile", {})
    user.setdefault("ai_water_goal", 2.5)
    user.setdefault("water_profile", {"daily_goal": 2.5, "frequency": "30 minutes"})
    user.setdefault("streak", {"completed_days": [], "current_streak": 0})
    user.setdefault("daily_intake", {})
    user.setdefault("weekly_data", {"week_start": None, "days": {}})
    save_user_data(user_data)

def current_week_start(d: date = None) -> date:
    if d is None:
        d = date.today()
    return d - timedelta(days=d.weekday())

def ensure_week_current(username: str):
    ensure_user_structures(username)
    weekly = user_data[username].setdefault("weekly_data", {"week_start": None, "days": {}})
    this_week_start = current_week_start()
    this_week_start_str = this_week_start.strftime("%Y-%m-%d")
    if weekly.get("week_start") != this_week_start_str:
        weekly["week_start"] = this_week_start_str
        weekly["days"] = {}
        save_user_data(user_data)

def load_today_intake_into_session(username: str):
    ensure_user_structures(username)
    today_str = date.today().strftime("%Y-%m-%d")
    daily = user_data[username].setdefault("daily_intake", {})
    last_login = daily.get("last_login_date")
    if last_login != today_str:
        daily["last_login_date"] = today_str
        daily.setdefault(today_str, 0.0)
        save_user_data(user_data)
        st.session_state.total_intake = 0.0
        st.session_state.water_intake_log = []
    else:
        st.session_state.total_intake = float(daily.get(today_str, 0.0))

def update_weekly_record_on_add(username: str, date_str: str, liters: float):
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
# track mascot TTS played (avoid repeats)
if "mascot_tts_played_for" not in st.session_state:
    st.session_state.mascot_tts_played_for = set()

# -------------------------------
# Country list utility
# -------------------------------
countries = [c.name for c in pycountry.countries]

# -------------------------------
# Mascot utilities & logic (fixed)
# -------------------------------
GITHUB_ASSETS_BASE = "https://raw.githubusercontent.com/sri133/Water_Buddy/main/water_buddy/assets/"

def build_image_url(filename: str) -> str:
    return GITHUB_ASSETS_BASE + quote(filename, safe='')

@st.cache_data(ttl=300)
def get_location_from_ip():
    try:
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

def choose_mascot_and_message(page: str, username: str) -> Optional[Dict[str, Any]]:
    india_tz = pytz.timezone("Asia/Kolkata")
    now = datetime.now(india_tz)
    t = now.time()

    ensure_user_structures(username)
    wp = user_data.get(username, {}).get("water_profile", {})
    freq_text = wp.get("frequency", "30 minutes")
    try:
        freq_minutes = int(re.findall(r"(\d+)", freq_text)[0])
    except Exception:
        freq_minutes = 30

    # Post-daily-goal (highest priority)
    last_completed_iso = st.session_state.get("last_goal_completed_at")
    if last_completed_iso:
        try:
            last_dt = datetime.fromisoformat(last_completed_iso)
            if (datetime.now() - last_dt) <= timedelta(minutes=5):
                img = build_image_url("image (9).png")
                context = "User just completed the daily water goal. Provide a fun water fact and a brief congratulatory message."
                msg = ask_gemini_for_message(context, "🎉 Amazing job — you hit your daily water goal! Fun fact: water makes up about 60% of the human body.")
                return {"image": img, "message": msg, "id": "post_goal", "tts": True}
        except Exception:
            pass

    # Page-specific mascots
    if page == "login":
        img = build_image_url("image (1).png")
        msg = ask_gemini_for_message("Greeting message for login page.",
                                     "Hi there! Welcome back to HP PARTNER — log in to track your hydration.")
        return {"image": img, "message": msg, "id": "login", "tts": False}

    if page == "daily_streak":
        img = build_image_url("image (2).png")
        msg = ask_gemini_for_message("Motivational message for daily streak page.",
                                     "🔥 Keep going — every sip counts! Tip: set small, consistent reminders to stay hydrated.")
        return {"image": img, "message": msg, "id": "daily_streak", "tts": False}

    # ---------------- Home Page Mascots ----------------
    if page == "home":
        # Special Midday 13:40–14:30
        if time_in_range(dtime(13,40), dtime(14,30), t):
            candidates = [Path("assets") / "image(7).png", Path("assets") / "image (7).png"]
            chosen = next((str(p) for p in candidates if p.exists()), build_image_url("image(7).png"))
            msg = ask_gemini_for_message("Special midday mascot for hydration reminder.", 
                                         "Midday reminder — have a refreshing sip of water!")
            return {"image": chosen, "message": msg, "id": "special_midday", "tts": True}

        # Meal windows: 08:00–09:00, 13:00–14:00, 20:30–21:30
        if (time_in_range(dtime(8,0), dtime(9,0), t) or 
            time_in_range(dtime(13,0), dtime(14,0), t) or 
            time_in_range(dtime(20,30), dtime(21,30), t)):
            candidates = [Path("assets") / "image(5).jpg", Path("assets") / "image (5).jpg"]
            chosen = next((str(p) for p in candidates if p.exists()), build_image_url("image(5).jpg"))
            msg = ask_gemini_for_message("Meal-time hydration tip.", 
                                         "During meals, avoid drinking large amounts — small sips are fine.")
            return {"image": chosen, "message": msg, "id": "meal", "tts": True}

        # Night: 21:30–05:00
        if time_in_range(dtime(21,30), dtime(5,0), t):
            candidates = [Path("assets") / "image(8).png", Path("assets") / "image (8).png"]
            chosen = next((str(p) for p in candidates if p.exists()), build_image_url("image(8).png"))
            msg = ask_gemini_for_message("Night hydration tip.", 
                                         "🌙 It's late — sip lightly if needed and avoid heavy drinking right before sleep.")
            return {"image": chosen, "message": msg, "id": "night", "tts": True}

        # Morning: 05:00–08:00
        if time_in_range(dtime(5,0), dtime(8,0), t):
            candidates = [Path("assets") / "image 6).jpg", Path("assets") / "image(6).jpg"]
            chosen = next((str(p) for p in candidates if p.exists()), build_image_url("image 6).jpg"))
            msg = ask_gemini_for_message("Morning greeting.", 
                                         "Good morning! Start your day with water — you've got this! 💧")
            return {"image": chosen, "message": msg, "id": "morning", "tts": True}

        # Reminder window
        if is_within_reminder_window(freq_minutes, tolerance_minutes=5):
            candidates = [Path("assets") / "image(4).png", Path("assets") / "image (4).png"]
            chosen = next((str(p) for p in candidates if p.exists()), build_image_url("image(4).png"))
            msg = ask_gemini_for_message(f"Time to drink water (every {freq_minutes} mins).", 
                                         "⏰ Time for a sip! Keep on track for your daily goal.")
            return {"image": chosen, "message": msg, "id": "reminder", "tts": True}

        # Default home fallback
        candidates = [Path("assets") / "image (3).png", Path("assets") / "image(3).png"]
        chosen = next((str(p) for p in candidates if p.exists()), build_image_url("image (3).png"))
        msg = ask_gemini_for_message("Friendly greeting for home page.", 
                                     "Hello! Keep up the good work — you're doing well with your hydration today.")
        return {"image": chosen, "message": msg, "id": "home_fallback_full", "tts": True}

    # Report page → no mascot
    if page == "report":
        return None

    # Default fallback (non-home)
    img = build_image_url("image (3).png")
    msg = ask_gemini_for_message("Default greeting", 
                                 "Hi! I'm Water Buddy — how can I help you stay hydrated today?")
    return {"image": img, "message": msg, "id": "default", "tts": False}


def render_mascot_inline(mascot: Optional[Dict[str, Any]]):
    if not mascot:
        return
    img = mascot.get("image")
    message = mascot.get("message", "")
    mid = mascot.get("id", "mascot")
    tts_flag = bool(mascot.get("tts", False))

    # Initialize TTS tracker
    if "mascot_tts_played_for" not in st.session_state:
        st.session_state.mascot_tts_played_for = set()

    col_img, col_msg = st.columns([1, 4])
    with col_img:
        try:
            st.image(img, width=90)
        except Exception:
            try:
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

    # Home-related TTS
    if tts_flag and mid not in st.session_state.mascot_tts_played_for:
        safe_text = message.replace('"', '\\"').replace("\n", " ")
        html = f"""
        <script>
        (function(){{
            try {{
                const utter = new SpeechSynthesisUtterance("{safe_text}");
                utter.rate = 1.0;
                utter.pitch = 1.0;
                window.speechSynthesis.cancel();
                window.speechSynthesis.speak(utter);
            }} catch(e) {{
                console.warn("TTS failed", e);
            }}
        }})();
        </script>
        """
        st.components.v1.html(html, height=10)
        st.session_state.mascot_tts_played_for.add(mid)

# -------------------------------
# Quiz utilities (persistent)
# -------------------------------
def generate_quiz_via_model(username):
    # Check if user already has a quiz for today
    today_str = date.today().isoformat()
    ensure_user_structures(username)
    user_quiz_data = user_data[username].setdefault("daily_quiz_data", {})
    if user_quiz_data.get("date") == today_str and user_quiz_data.get("quiz"):
        return user_quiz_data["quiz"]

    # Generate new quiz
    fallback = generate_quiz_fallback()
    try:
        if not model:
            quiz = fallback
        else:
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
                quiz = data[:10]
            else:
                quiz = fallback
    except Exception:
        quiz = fallback

    # Save to user_data for persistence
    user_quiz_data["quiz"] = quiz
    user_quiz_data["date"] = today_str
    save_user_data(user_data)
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
        explanation = item.get("explanation") or f"This is correct because '{item['options'][correct]}' is the right answer."
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
                ensure_user_structures(username)
                st.success("✅ Account created successfully! Please login.")
        elif option == "Login":
            if username in users and users[username] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                ensure_user_structures(username)
                load_today_intake_into_session(username)
                ensure_week_current(username)
                # Go to home if profile exists
                if user_data.get(username, {}).get("profile"):
                    go_to_page("home")
                else:
                    go_to_page("settings")
            else:
                st.error("❌ Invalid username or password.")

    # Inline mascot
    mascot = choose_mascot_and_message("login", st.session_state.username or "")
    render_mascot_inline(mascot)
    st.markdown('<p style="font-size:14px; color:gray;">Sign up first, then login with your credentials.</p>', unsafe_allow_html=True)

# -------------------------------
# PERSONAL SETTINGS PAGE
# -------------------------------
elif st.session_state.page == "settings":
    # RESET GATE (MUST BE FIRST)
    if st.session_state.get("just_reset"):
        st.session_state.just_reset = False
        st.rerun()

    if not st.session_state.logged_in:
        go_to_page("login")

    set_background()
    username = st.session_state.username
    ensure_user_structures(username)
    saved = user_data.get(username, {}).get("profile", {})

    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 Personal Settings</h1>", unsafe_allow_html=True)

    # Inputs
    name = st.text_input("Name", value=saved.get("Name", username), key="settings_name")
    age = st.text_input("Age", value=saved.get("Age", ""), key="settings_age")
    country = st.selectbox(
        "Country",
        countries,
        index=countries.index(saved.get("Country", "India")) if saved.get("Country") else countries.index("India"),
        key="settings_country"
    )
    language = st.text_input("Language", value=saved.get("Language", ""), key="settings_language")
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
        "Health condition",
        ["Excellent", "Fair", "Poor"],
        horizontal=True,
        index=["Excellent", "Fair", "Poor"].index(saved.get("Health Condition", "Excellent")),
        key="settings_health_condition"
    )
    health_problems = st.text_area("Health problems", value=saved.get("Health Problems", ""), key="settings_health_problems")

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
        ensure_user_structures(username)
        user_data[username]["profile"] = new_profile_data
        user_data[username].setdefault("water_profile", {"daily_goal": 2.5, "frequency": "30 minutes"})
        save_user_data(user_data)
        st.success(f"✅ Profile saved! Water Buddy suggests {user_data[username].get('ai_water_goal',2.5)} L/day 💧")
        go_to_page("water_profile")

# -------------------------------
# WATER INTAKE PAGE
# -------------------------------
elif st.session_state.page == "water_profile":

    # RESET GATE (MUST BE FIRST)
    if st.session_state.get("just_reset"):
        st.session_state.just_reset = False
        st.rerun()

    if not st.session_state.logged_in:
        go_to_page("login")

    set_background()
    username = st.session_state.username
    ensure_user_structures(username)

    saved = user_data.get(username, {}).get("water_profile", {})
    ai_goal = user_data.get(username, {}).get("ai_water_goal", 2.5)

    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 Water Intake</h1>", unsafe_allow_html=True)
    st.success(f"Your ideal daily water intake is **{ai_goal} L/day** 💧")

    # ------------------
    # INPUT WIDGETS
    # ------------------
    daily_goal = st.slider(
        "Set your daily water goal (L):",
        0.5, 10.0, float(ai_goal), 0.1,
        key="water_profile_daily_goal"
    )

    frequency_options = [f"{i} minutes" for i in range(5, 185, 5)]

    selected_frequency = st.selectbox(
        "🔔 Reminder Frequency:",
        frequency_options,
        index=frequency_options.index(saved.get("frequency", "30 minutes"))
        if saved.get("frequency")
        else frequency_options.index("30 minutes"),
        key="water_profile_frequency"
    )

    # ------------------
    # SAVE BUTTON
    # ------------------
    if st.button("💾 Save & Continue ➡️"):
        user_data[username]["water_profile"] = {
            "daily_goal": daily_goal,
            "frequency": selected_frequency
        }
        user_data[username]["ai_water_goal"] = daily_goal
        save_user_data(user_data)

        st.success("✅ Water profile saved successfully!")
        go_to_page("home")


# -------------------------------
# THIRSTY CUP - Full Screen Game Page (FULL with Shop)
# -------------------------------
elif st.session_state.page == "thirsty_cup":
    from streamlit.components.v1 import html as st_html

    if not st.session_state.logged_in:
        go_to_page("login")
    set_background()

    username = st.session_state.username

    st.session_state.setdefault("coins", 0)
    st.session_state.setdefault("thirsty_playing", False)
    st.session_state.setdefault("thirsty_claimed", False)
    st.session_state.setdefault("thirsty_result", None)
    st.session_state.setdefault("thirsty_selected_cup", None)
    st.session_state.setdefault("show_shop", False)

    ensure_user_structures(username)
    user_profile = user_data.setdefault(username, {})
    user_purchases = user_profile.setdefault("purchases", {})
    user_profile.setdefault("coins", user_profile.get("coins", st.session_state.get("coins", 0)))
    user_selected = user_profile.get("selected_cup", None)
    if user_selected and not st.session_state.thirsty_selected_cup:
        st.session_state.thirsty_selected_cup = user_selected
    if "coins_synced" not in st.session_state:
        st.session_state.coins = user_profile.get("coins", st.session_state.coins)
        st.session_state.coins_synced = True

    cols = st.columns([1, 0.2, 0.25])
    with cols[0]:
        st.markdown("<h1 style='margin:0; color:#1A73E8;'>💧 Thirsty Cup</h1>", unsafe_allow_html=True)
    with cols[1]:
        st.markdown(
            f"""
            <div style="text-align:right; font-weight:700;">
                <span style="font-size:18px;">🪙</span>
                <span id="coin-count" style="margin-left:6px; font-size:16px;">{st.session_state['coins']}</span>
            </div>
            """,
            unsafe_allow_html=True
        )
    with cols[2]:
        if st.button("🛒 Shop", key="open_shop"):
            st.session_state.show_shop = not st.session_state.show_shop

    st.markdown("<hr/>", unsafe_allow_html=True)

    if not st.session_state.thirsty_playing:
        st.markdown(
            """
            <div style="width:100%; display:flex; align-items:center; justify-content:center; flex-direction:column; margin-top:20px;">
                <div style="font-size:96px; font-weight:900; color: rgba(0,0,0,0.06); letter-spacing:8px; user-select:none; text-align:center;">
                    THIRSTY CUP
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        cup_preview_col1, cup_preview_col2 = st.columns([1,3])
        with cup_preview_col1:
            st.write("Current Cup:")
        with cup_preview_col2:
            sel = st.session_state.get("thirsty_selected_cup") or "cup_default"
            st.markdown(f"<div style='padding:8px 12px; border-radius:10px; display:inline-block; background:#f7fbff; font-weight:700;'>{sel.replace('_',' ').title()}</div>", unsafe_allow_html=True)

        if st.button("▶️ Play Thirsty Cup", key="tc_play_btn"):
            st.session_state.thirsty_playing = True
            st.session_state.thirsty_result = None
            st.session_state.thirsty_claimed = False
            st.rerun()

    if st.session_state.show_shop:
        st.markdown("### 🛒 Cup Shop")
        st.write("Choose a cup skin. Buy with coins. Click a purchased cup to select it for playing.")
        st.write("---")
        cups = [
            {"id":"cup_default","title":"Classic Blue","price":0, "type":"color", "desc":"Default cup (free)"},
            {"id":"cup_red","title":"Red Burst","price":5, "type":"color", "desc":"Bright red simple cup."},
            {"id":"cup_green","title":"Mint Splash","price":5, "type":"color", "desc":"Cool mint cup."},
            {"id":"cup_smile","title":"Smiley Cup","price":7, "type":"cartoon", "desc":"Cute smiling cup."},
            {"id":"cup_cat","title":"Cat Cup","price":8, "type":"cartoon", "desc":"Cat face cup."},
            {"id":"cup_robot","title":"Robot Cup","price":9, "type":"cartoon", "desc":"Futuristic robot cup."},
            {"id":"cup_gold","title":"Gold Cup","price":10, "type":"premium", "desc":"Shiny premium gold cup."},
            {"id":"cup_glass","title":"Glass Cup","price":9, "type":"premium", "desc":"Transparent glass look."},
            {"id":"cup_neon","title":"Neon Glow","price":7, "type":"color", "desc":"Vivid neon cup."},
        ]
        shop_cols = st.columns([1,1,1])
        for idx, cup in enumerate(cups):
            col = shop_cols[idx % 3]
            with col:
                purchased = user_purchases.get(cup["id"], False)
                selected = (st.session_state.get("thirsty_selected_cup") == cup["id"])
                card_html = f"""
                <div style="padding:12px; border-radius:12px; box-shadow:0 6px 20px rgba(0,0,0,0.06); margin:6px; background: linear-gradient(180deg,#ffffff,#f7fbff);">
                    <div style="font-weight:800; font-size:16px;">{cup['title']}</div>
                    <div style="font-size:12px; color:#666; margin-bottom:8px;">{cup['desc']}</div>
                    <div style="height:40px; display:flex; align-items:center; justify-content:center;">
                        <div style="width:60px; height:36px; border-radius:8px; background:#e6f2ff; display:flex; align-items:center; justify-content:center; font-weight:700;">
                            {cup['title'][0]}
                        </div>
                    </div>
                """
                if not purchased and cup["price"] > 0:
                    card_html += f"<div style='margin-top:8px; font-weight:700; color:#333;'>{cup['price']} 🪙</div>"
                else:
                    card_html += f"<div style='margin-top:8px; color:#2a7bdb; font-weight:700;'>Purchased</div>" if purchased else "<div style='margin-top:8px; color:#2a7bdb; font-weight:700;'>Free</div>"
                if not purchased and cup["price"] > 0:
                    card_html += "<div style='font-size:22px; color:rgba(0,0,0,0.25); margin-top:6px;'>🔒</div>"
                if selected:
                    card_html += "<div style='margin-top:6px; color:#0B63C6; font-weight:700;'>Selected</div>"
                card_html += "</div>"
                st.markdown(card_html, unsafe_allow_html=True)
                if purchased or cup["price"] == 0:
                    if st.button(f"Select {cup['title']}", key=f"select_{cup['id']}"):
                        st.session_state.thirsty_selected_cup = cup["id"]
                        user_profile["selected_cup"] = cup["id"]
                        save_user_data(user_data)
                        st.success(f"Selected {cup['title']} for playing.")
                else:
                    if st.button(f"Buy {cup['title']} ({cup['price']}🪙)", key=f"buy_{cup['id']}"):
                        if st.session_state.coins >= cup["price"]:
                            st.session_state.coins -= cup["price"]
                            user_profile["coins"] = st.session_state.coins
                            user_purchases[cup["id"]] = True
                            user_profile["purchases"] = user_purchases
                            save_user_data(user_data)
                            st.success(f"Purchased {cup['title']} ✅")
                        else:
                            st.warning("Not enough coins. Play more to earn coins!")
        st.write("---")
        if st.button("Close Shop"):
            st.session_state.show_shop = False
            st.rerun()

    if st.session_state.thirsty_playing:
        from streamlit.components.v1 import html
        selected = st.session_state.get("thirsty_selected_cup") or "cup_default"
        cup_styles = {
            "cup_default": {"color":"#1A73E8","shape":"rect"},
            "cup_red": {"color":"#E53935","shape":"rect"},
            "cup_green": {"color":"#00BFA5","shape":"rect"},
            "cup_smile": {"color":"#FFB74D","shape":"smile"},
            "cup_cat": {"color":"#BA68C8","shape":"cat"},
            "cup_robot": {"color":"#90A4AE","shape":"robot"},
            "cup_gold": {"color":"#FFD54F","shape":"premium"},
            "cup_glass": {"color":"#B3E5FC","shape":"glass"},
            "cup_neon": {"color":"#39FF14","shape":"neon"},
        }
        style = cup_styles.get(selected, {"color":"#1A73E8","shape":"rect"})
        cup_color = style["color"]
        cup_shape = style["shape"]

        # Game HTML with JS TTS for win inside showResult('win')
        game_html = f"""
        <style>
        html, body {{ margin:0; padding:0; height:100%; }}
        .tc-root {{ position:relative; width:100vw; height:calc(100vh - 120px); display:flex; align-items:center; justify-content:center; }}
        #tc-canvas {{ width:100%; height:100%; display:block; background: linear-gradient(#C9E8FF, #E0F7FA); }}
        #tc-overlay {{ position:absolute; inset:0; display:flex; align-items:center; justify-content:center; pointer-events:none; }}
        .tc-panel {{ pointer-events:auto; backdrop-filter: blur(6px); background: rgba(255,255,255,0.9); padding:24px; border-radius:12px; box-shadow:0 12px 40px rgba(0,0,0,0.12); text-align:center; }}
        .tc-btn {{ padding:10px 16px; border-radius:10px; border:none; cursor:pointer; font-weight:700; background:#1A73E8; color:white; }}
        </style>

        <div class="tc-root">
            <canvas id="tc-canvas"></canvas>
            <div id="tc-overlay"></div>
        </div>

        <script>
        (function(){{
            const canvas = document.getElementById('tc-canvas');
            const overlay = document.getElementById('tc-overlay');
            const ctx = canvas.getContext('2d');
            function resizeCanvas() {{
                const rect = canvas.getBoundingClientRect();
                canvas.width = rect.width;
                canvas.height = rect.height;
            }}
            resizeCanvas();
            window.addEventListener('resize', resizeCanvas);

            const totalDrops = 16;
            const dropSpeedMin = 6;
            const dropSpeedMax = 8;
            const cupWidthBase = Math.max(80, Math.round(canvas.width * 0.12));
            const cupHeightBase = Math.max(36, Math.round(canvas.height * 0.06));
            let cupY = canvas.height - cupHeightBase - 40;
            const cupColor = "{cup_color}";
            const cupShape = "{cup_shape}";

            let currentDrop = null;
            let caught = 0;
            let missed = 0;
            let running = true;
            let lastTime = performance.now();
            let pointerX = canvas.width/2;
            let keyboardVel = 0;

            function spawnOneDrop() {{
                const size = Math.max(8, Math.round(Math.min(canvas.width, canvas.height) * 0.01));
                const x = Math.random() * (canvas.width - size*2) + size;
                const speed = Math.random() * (dropSpeedMax-dropSpeedMin) + dropSpeedMin;
                return {{x:x, y:-20, speed:speed, size:size, active:true}};
            }}

            function startNextDrop() {{
                currentDrop = spawnOneDrop();
            }}

            CanvasRenderingContext2D.prototype.roundRect = function (x, y, w, h, r) {{
                if (w < 2 * r) r = w / 2;
                if (h < 2 * r) r = h / 2;
                this.beginPath();
                this.moveTo(x + r, y);
                this.arcTo(x + w, y, x + w, y + h, r);
                this.arcTo(x + w, y + h, x, y + h, r);
                this.arcTo(x, y + h, x, y, r);
                this.arcTo(x, y, x + w, y, r);
                this.closePath();
                return this;
            }};

            function drawCup(x) {{
                const cx = x - cupWidthBase/2;
                const cy = cupY;
                ctx.save();
                ctx.fillStyle = cupColor;
                if (cupShape === 'rect' || cupShape === 'neon' || cupShape === 'glass' || cupShape === 'premium') {{
                    ctx.beginPath();
                    ctx.roundRect(cx, cy, cupWidthBase, cupHeightBase, 12);
                    ctx.fill();
                }} else if (cupShape === 'smile') {{
                    ctx.beginPath();
                    ctx.ellipse(x, cy+cupHeightBase/2, cupWidthBase/2, cupHeightBase/1.6, 0, 0, Math.PI*2);
                    ctx.fill();
                    ctx.fillStyle = 'white'; ctx.fillRect(x-18, cy+8, 6,6); ctx.fillRect(x+12, cy+8,6,6);
                }} else if (cupShape === 'cat') {{
                    ctx.beginPath();
                    ctx.ellipse(x, cy+cupHeightBase/2, cupWidthBase/2, cupHeightBase/1.6, 0, 0, Math.PI*2);
                    ctx.fill();
                    ctx.fillStyle = cupColor;
                    ctx.beginPath(); ctx.moveTo(x - cupWidthBase/2 + 6, cy); ctx.lineTo(x - cupWidthBase/2 + 18, cy-18); ctx.lineTo(x - cupWidthBase/2 + 30, cy); ctx.fill();
                    ctx.beginPath(); ctx.moveTo(x + cupWidthBase/2 - 6, cy); ctx.lineTo(x + cupWidthBase/2 - 18, cy-18); ctx.lineTo(x + cupWidthBase/2 - 30, cy); ctx.fill();
                }} else if (cupShape === 'robot') {{
                    ctx.fillStyle = cupColor;
                    ctx.fillRect(cx, cy, cupWidthBase, cupHeightBase);
                    ctx.fillStyle = '#222'; ctx.fillRect(cx + cupWidthBase/2 - 6, cy + 6, 12, 12);
                }} else {{
                    ctx.beginPath();
                    ctx.roundRect(cx, cy, cupWidthBase, cupHeightBase, 12);
                    ctx.fill();
                }}
                ctx.restore();
            }}

            function drawDrop(d) {{
                ctx.save();
                const grd = ctx.createLinearGradient(d.x, d.y - d.size, d.x, d.y + d.size*1.5);
                grd.addColorStop(0, '#E0F7FA');
                grd.addColorStop(1, '#1CA3A3');
                ctx.fillStyle = grd;
                ctx.beginPath();
                ctx.ellipse(d.x, d.y, d.size, d.size*1.4, 0, 0, Math.PI*2);
                ctx.fill();
                ctx.restore();
            }}

            function update(dt) {{
                cupY = canvas.height - cupHeightBase - 40;
                if (keyboardVel !== 0) {{
                    pointerX += keyboardVel * dt * 0.18;
                }}
                pointerX = Math.max(cupWidthBase/2, Math.min(canvas.width - cupWidthBase/2, pointerX));

                if (!currentDrop) {{
                    // slight random delay between drops
                    const delay = Math.random() * 300 + 80; // ms
                    setTimeout(startNextDrop, delay);
                }} else {{
                    currentDrop.y += currentDrop.speed * dt * 0.06;
                    const cupLeft = pointerX - cupWidthBase/2;
                    const cupRight = pointerX + cupWidthBase/2;
                    const cupTop = cupY;
                    if (currentDrop.y + currentDrop.size >= cupTop && currentDrop.x > cupLeft && currentDrop.x < cupRight) {{
                        currentDrop.active = false;
                        caught += 1;
                        currentDrop = null;
                    }} else if (currentDrop.y > canvas.height + 20) {{
                        currentDrop.active = false;
                        missed += 1;
                        currentDrop = null;
                    }}
                }}
            }}

            function draw() {{
                ctx.clearRect(0,0,canvas.width,canvas.height);
                ctx.save();
                ctx.globalAlpha = 0.06;
                for (let i=0;i<4;i++){{
                    ctx.beginPath();
                    ctx.ellipse(canvas.width/2, canvas.height/2 + i*26, canvas.width*0.9, 90 + i*12, 0, 0, Math.PI*2);
                    ctx.fillStyle = '#1CA3A3';
                    ctx.fill();
                }}
                ctx.restore();

                if (currentDrop && currentDrop.active) drawDrop(currentDrop);
                drawCup(pointerX);

                ctx.save();
                ctx.fillStyle = '#0b63c6';
                ctx.font = Math.max(14, Math.round(canvas.width * 0.015)) + 'px Inter, Arial';
                ctx.fillText('Caught: ' + caught + ' / ' + totalDrops, 18, 36);
                ctx.fillStyle = '#555';
                ctx.fillText('Missed: ' + missed, 18, 62);
                ctx.restore();
            }}

            function checkEnd() {{
                if (caught >= totalDrops) return 'win';
                const spawned = caught + missed + (currentDrop ? 1 : 0);
                if (spawned >= totalDrops && !currentDrop) {{
                    return (caught >= totalDrops) ? 'win' : 'lose';
                }}
                return null;
            }}

            function loop(ts) {{
                const dt = ts - lastTime;
                lastTime = ts;
                if (!running) return;
                update(dt);
                draw();
                const res = checkEnd();
                if (res) {{
                    running = false;
                    showResult(res);
                }} else {{
                    requestAnimationFrame(loop);
                }}
            }}

            function showResult(type) {{
                overlay.innerHTML = '';
                const panel = document.createElement('div');
                panel.className = 'tc-panel';
                if (type === 'win') {{
                    panel.innerHTML = `<div style="font-size:36px; font-weight:800; color:#1A73E8;">You Win! 🏆</div>
                                       <div style="margin-top:8px;">Perfect catch — you earned a coin!</div>`;
                }} else {{
                    panel.innerHTML = `<div style="font-size:36px; font-weight:800; color:#ff6b6b;">You Lose</div>
                                       <div style="margin-top:8px;">Some drops were missed — try again!</div>`;
                }}

                const claimBtn = document.createElement('button');
                claimBtn.className = 'tc-btn';
                claimBtn.style.marginTop = '12px';
                claimBtn.innerText = 'Set Result';
                claimBtn.onclick = function() {{
                    try {{
                        localStorage.setItem('tc_result', type);
                        alert('Result set: ' + type + '\\nNow click \"Retrieve Game Result\" in the Streamlit UI to register it.');
                    }} catch(e) {{
                        alert('Unable to write result to localStorage due to browser restrictions.');
                    }}
                }};
                panel.appendChild(claimBtn);
                overlay.appendChild(panel);
                try {{ localStorage.setItem('tc_result', type); }} catch(e){{}}
                window.__tc_result = type;

                // Speak on win
                if (type === 'win') {{
                    try {{
                        const utter = new SpeechSynthesisUtterance("You win! Great job!");
                        utter.rate = 1.0; utter.pitch = 1.0;
                        window.speechSynthesis.cancel();
                        window.speechSynthesis.speak(utter);
                    }} catch(e) {{ console.warn("TTS error", e); }}
                }}
            }}

            canvas.addEventListener('mousemove', (e)=>{{
                const rect = canvas.getBoundingClientRect();
                pointerX = (e.clientX - rect.left) * (canvas.width / rect.width);
            }});
            canvas.addEventListener('touchstart', (e)=>{{
                const rect = canvas.getBoundingClientRect();
                pointerX = (e.touches[0].clientX - rect.left) * (canvas.width / rect.width);
            }}, {{passive:true}});
            canvas.addEventListener('touchmove', (e)=>{{
                const rect = canvas.getBoundingClientRect();
                pointerX = (e.touches[0].clientX - rect.left) * (canvas.width / rect.width);
            }}, {{passive:true}});

            window.addEventListener('keydown', (e)=>{{
                if (e.key === 'ArrowLeft') keyboardVel = -6;
                if (e.key === 'ArrowRight') keyboardVel = 6;
            }});
            window.addEventListener('keyup', (e)=>{{
                if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') keyboardVel = 0;
            }});

            lastTime = performance.now();
            requestAnimationFrame(loop);

            window.__tc_get_result = function(){{ try{{return localStorage.getItem('tc_result');}}catch(e){{return null;}} }};
            window.__tc_clear_result = function(){{ try{{localStorage.removeItem('tc_result');}}catch(e){{}} }};
        }})();
        </script>
        """
        st_html(game_html, height=860)

        st.markdown("")
        if st.session_state.thirsty_result is None:
            st.info("Play the round. When the round ends, click 'Set Result' inside the game overlay (or it will be stored automatically). Then click 'Retrieve Game Result' below to register the result with the server.")
        c1, c2, c3, c4 = st.columns([1,1,1,1])
        with c1:
            if st.button("Retrieve Game Result", key="retrieve_game_result"):
                bridge_html = r"""
                <script>
                (function(){
                    try {
                        var res = null;
                        try { res = window.localStorage.getItem('tc_result'); } catch(e) { res = null; }
                        if(res) {
                            document.body.innerHTML = "<div id='bridge_result'>"+res+"</div>";
                        } else {
                            document.body.innerHTML = "<div id='bridge_result'>__NONE__</div>";
                        }
                    } catch(e){
                        document.body.innerHTML = "<div id='bridge_result'>__ERR__</div>";
                    }
                })();
                </script>
                """
                st.components.v1.html(bridge_html, height=80)
                try:
                    time.sleep(0.25)
                except Exception:
                    pass
                st.info("Attempted to retrieve the result from the game. If your browser allowed it, the result will be registered. Otherwise, please press 'I Won' or 'I Lost' to register the result honestly.")
        with c2:
            if st.button("I Won (Register Win)", key="i_won_btn"):
                st.session_state.thirsty_result = "win"
                st.success("Registered: win")
        with c3:
            if st.button("I Lost (Register Loss)", key="i_lost_btn"):
                st.session_state.thirsty_result = "lose"
                st.info("Registered: lose")
        with c4:
            if st.button("Retry", key="tc_retry_btn"):
                st.session_state.thirsty_playing = False
                st.session_state.thirsty_result = None
                st.session_state.thirsty_claimed = False
                st.rerun()

        st.markdown("")
        if st.button("Claim Coin (if you won)", key="claim_coin_btn"):
            if st.session_state.thirsty_result == "win":
                if not st.session_state.thirsty_claimed:
                    st.session_state.coins += 1
                    user_profile["coins"] = st.session_state.coins
                    save_user_data(user_data)
                    st.session_state.thirsty_claimed = True
                    st.success("🪙 Coin added! Check top-right.")
                else:
                    st.info("You already claimed the reward for this round.")
            elif st.session_state.thirsty_result == "lose":
                st.warning("You did not win this round — you cannot claim a coin.")
            else:
                st.warning("Game result not recorded. Please click 'Retrieve Game Result' and then 'I Won' / 'I Lost' to register the result, or click 'Set Result' inside the game overlay after the round finishes.")

    st.markdown("---")
    nav1, nav2, nav3, nav4, nav5 = st.columns(5)
    with nav1:
        if st.button("🏠 Home"):
            go_to_page("home")
    with nav2:
        if st.button("👤 Personal Settings"):
            go_to_page("settings")
    with nav3:
        if st.button("🚰 Water Intake"):
            go_to_page("water_profile")
    with nav4:
        if st.button("📈 Report"):
            go_to_page("report")
    with nav5:
        if st.button("🔥 Daily Streak"):
            go_to_page("daily_streak")

# -------------------------------
# HOME PAGE (persistent bottle + Gemini chat fully functional)
# -------------------------------
elif st.session_state.page == "home":
    set_background()
    if not st.session_state.logged_in:
        go_to_page("login")

    username = st.session_state.username
    ensure_user_structures(username)
    today_dt = date.today()
    today_str = today_dt.strftime("%Y-%m-%d")
    load_today_intake_into_session(username)
    ensure_week_current(username)

    daily_goal = user_data.get(username, {}).get("water_profile", {}).get(
        "daily_goal", user_data.get(username, {}).get("ai_water_goal", 2.5)
    )

    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 HP PARTNER</h1>", unsafe_allow_html=True)

    # Bottle UI
    fill_percent = min(st.session_state.total_intake / daily_goal, 1.0) if daily_goal > 0 else 0
    bottle_html = f"""
    <div style='width: 120px; height: 300px; border: 3px solid #1A73E8; border-radius: 20px; position: relative; margin: auto; 
    background: linear-gradient(to top, #1A73E8 {fill_percent*100}%, #E0E0E0 {fill_percent*100}%);'>
        <div style='position: absolute; bottom: 5px; width: 100%; text-align: center; color: #fff; font-weight: bold; font-size: 18px;'>{round(st.session_state.total_intake,2)}L / {daily_goal}L</div>
    </div>
    """
    st.markdown(bottle_html, unsafe_allow_html=True)

    # ---------------------------------
    # 🔄 RESET BUTTON (Empty the Bottle)
    # ---------------------------------
    if st.button("🔄 Reset Bottle"):
        # Reset session values
        st.session_state.total_intake = 0.0
        st.session_state.water_intake_log = []

        # Reset DB value for today
        user_data[username]["daily_intake"][today_str] = 0.0
        save_user_data(user_data)

        st.success("Bottle is now empty! 💧")
        st.rerun()

    # Water intake input
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

                # Update user data
                ensure_user_structures(username)
                user_data[username].setdefault("daily_intake", {})
                user_data[username]["daily_intake"][today_str] = st.session_state.total_intake
                update_weekly_record_on_add(username, today_str, st.session_state.total_intake)
                save_user_data(user_data)

                # TTS
                safe_ml = str(int(ml)) if ml.is_integer() else str(ml)
                speak_text = f"Added {safe_ml} milliliters of water."
                tts_html = f"""
                <script>
                (function(){{
                    try {{
                        const utter = new SpeechSynthesisUtterance("{speak_text.replace('"','\\"')}");
                        utter.rate = 1.0; utter.pitch = 1.0;
                        window.speechSynthesis.cancel();
                        window.speechSynthesis.speak(utter);
                    }} catch(e) {{
                        console.warn("TTS failed", e);
                    }}
                }})();
                </script>
                """
                st.components.v1.html(tts_html, height=10)

                st.rerun()
            except ValueError:
                st.error("❌ Enter a valid number.")
        else:
            st.error("❌ Enter a valid number.")

    # Today's log
    if st.session_state.water_intake_log:
        st.write("### Today's Log:")
        for i, entry in enumerate(st.session_state.water_intake_log, 1):
            st.write(f"{i}. {entry}")

    st.write("---")
    # Bottom nav
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
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.total_intake = 0.0
            st.session_state.water_intake_log = []
            go_to_page("login")
            
    if st.button("Test Firestore"):
    db.collection("test").document("example").set({
        "message": "Firestore connection successful!",
    })
    st.success("Data saved!")

    if st.button("🧠 Take Today's Quiz"):
        go_to_page("quiz")

    # Mascot
    mascot = choose_mascot_and_message("home", username)
    render_mascot_inline(mascot)

    st.markdown('<p style="font-size:14px; color:gray;">Use a calibrated water bottle for correct measurements.</p>',
                unsafe_allow_html=True)

    # -----------------------------
    # THIRSTY CUP GAME BUTTON
    # -----------------------------
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        if st.button("🎮 Play Thirsty Cup", use_container_width=True):
            st.session_state.page = "thirsty_cup"
            st.rerun()

    # -----------------------------
    # BACKGROUND COLOR PICKER
    # -----------------------------
    st.markdown("---")
    st.subheader("Customize Background Color 🎨")
    if "show_color_picker" not in st.session_state:
        st.session_state.show_color_picker = False
    if st.button("Pick Background Color"):
        st.session_state.show_color_picker = True
    if st.session_state.show_color_picker:
        new_color = st.color_picker("Choose a background color:", st.session_state.get("background_color", "#FFFFFF"))
        st.session_state.background_color = new_color
        st.success("Background color updated!")

   # -------------------------------
# GEMINI CHATBOT FUNCTIONAL
# -------------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

st.markdown("<br><br>", unsafe_allow_html=True)

# Chat toggle UI
st.markdown("""
    <div style='position:fixed; bottom:20px; right:20px; z-index:9999;'>
        <button id="chat_toggle" style='background:#1A73E8; color:white; border:none; border-radius:50%; width:60px; height:60px; font-size:24px; cursor:pointer;'>🤖</button>
        <div id="chat_box" style='display:none; width:320px; height:400px; background:white; border:2px solid #1A73E8; border-radius:10px; margin-bottom:10px; overflow:auto; padding:10px;'>

""", unsafe_allow_html=True)

# Display chat history
for msg in st.session_state.chat_history:
    if msg["role"] == "user":
        st.markdown(f"<div style='text-align:right;'><b>You:</b> {msg['text']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='text-align:left;'><b>Buddy:</b> {msg['text']}</div>", unsafe_allow_html=True)

st.markdown("</div></div>", unsafe_allow_html=True)

# Streamlit input for chat (no HTML form)
chat_input = st.text_input("Ask Water Buddy anything about hydration:", key="chat_input")
if st.button("Send", key="chat_send"):
    user_msg = chat_input.strip()
    if user_msg:
        st.session_state.chat_history.append({"role": "user", "text": user_msg})
        if model:
            prompt = f"You are Water Buddy. Answer user's question about hydration.\nUser: {user_msg}\nBuddy:"
            try:
                response = model.generate_content(prompt)
                reply = response.text.strip()
            except Exception as e:
                reply = f"Error: {e}"
        else:
            reply = "Gemini not configured."
        st.session_state.chat_history.append({"role": "assistant", "text": reply})
        st.rerun()


# -------------------------------
# QUIZ PAGE
# -------------------------------
elif st.session_state.page == "quiz":
    if not st.session_state.logged_in:
        go_to_page("login")

    set_background()
    username = st.session_state.username
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>🧠 Daily Water Quiz</h1>", unsafe_allow_html=True)
    st.write("Test your water knowledge — 10 questions. Explanations will appear after you submit.")
    st.write("---")

    quiz = get_daily_quiz()
    if not quiz or len(quiz) < 1:
        st.error("❗ Could not load quiz right now. Please try again later.")
    else:
        if "quiz_answers" not in st.session_state:
            st.session_state.quiz_answers = [None] * len(quiz)
        if "quiz_submitted" not in st.session_state:
            st.session_state.quiz_submitted = False
            st.session_state.quiz_results = None
            st.session_state.quiz_score = None

        labels = ["A", "B", "C", "D"]
        for i, item in enumerate(quiz):
            q_text = item.get("q", f"Question {i+1}")
            options = item.get("options", [])
            while len(options) < 4:
                options.append("N/A")
            st.markdown(f"**Q{i+1}. {q_text}**")
            full_options = [f"{labels[j]}. {options[j]}" for j in range(4)]
            existing = st.session_state.quiz_answers[i]
            selected = st.radio(
                f"Select answer for Q{i+1}",
                full_options,
                index=existing if isinstance(existing, int) else None,
                key=f"quiz_q_{i}"
            )
            if selected in full_options:
                st.session_state.quiz_answers[i] = full_options.index(selected)
            st.write("")

        if not st.session_state.quiz_submitted:
            if st.button("Submit Answers"):
                if None in st.session_state.quiz_answers:
                    st.warning("⚠ Please answer all questions before submitting the quiz.")
                    st.stop()
                answers = st.session_state.quiz_answers
                results, score = grade_quiz_and_explain(quiz, answers)
                st.session_state.quiz_results = results
                st.session_state.quiz_score = score
                st.session_state.quiz_submitted = True
                ensure_user_structures(username)
                today = date.today().isoformat()
                user_hist = user_data[username].setdefault("quiz_history", {})
                user_hist[today] = {
                    "score": score,
                    "total": len(quiz),
                    "timestamp": datetime.now().isoformat()
                }
                save_user_data(user_data)
                st.rerun()
        else:
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
                st.markdown(f"**Q{i+1}. {q}**")
                for idx, opt in enumerate(options):
                    if idx == correct_index:
                        prefix = "✅"
                    elif idx == selected_index and not is_correct:
                        prefix = "🔸"
                    else:
                        prefix = "•"
                    st.write(f"{prefix} {labels[idx]}. {opt}")
                if is_correct:
                    st.success(f"Correct — {explanation}")
                else:
                    st.error(f"Wrong — {explanation}")
                st.write("---")
            try:
                msg = ask_gemini_for_message(f"Congratulate the user for completing the daily water quiz and motivate them. Score = {score} out of {len(quiz)}.", "Nice work! Keep learning about water and stay hydrated!")
                st.info(msg)
            except Exception:
                pass

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

# -------------------------------
# REPORT PAGE (Matplotlib Circular Daily Goal + Persistent Data)
# -------------------------------
elif st.session_state.page == "report":
    if not st.session_state.logged_in:
        go_to_page("login")

    set_background()  # keep background consistent
    username = st.session_state.username

    st.markdown(
        "<h1 style='text-align:center; color:#1A73E8;'>📊 Hydration Report</h1>",
        unsafe_allow_html=True
    )
    st.write("---")

    ensure_user_structures(username)
    ensure_week_current(username)

    # -------------------------------
    # Save today's intake to weekly data (persistent)
    # -------------------------------
    today = date.today()
    today_str = today.isoformat()
    daily_goal = user_data[username]["water_profile"].get(
        "daily_goal", user_data[username].get("ai_water_goal", 2.5)
    )

    weekly = user_data[username].setdefault("weekly_data", {"week_start": None, "days": {}})
    # Initialize week start if missing
    if not weekly.get("week_start"):
        week_start_dt = current_week_start()
        weekly["week_start"] = week_start_dt.strftime("%Y-%m-%d")
    # Save today's intake to weekly data
    weekly["days"][today_str] = st.session_state.total_intake
    save_user_data(user_data)  # persist to disk

    # -------------------------------
    # Compute today's percentage completion
    # -------------------------------
    completed_iso = user_data[username]["streak"].get("completed_days", [])
    completed_dates = []
    for s in completed_iso:
        try:
            d = datetime.strptime(s, "%Y-%m-%d").date()
            completed_dates.append(d)
        except Exception:
            continue

    if today in completed_dates:
        today_pct = 100
    else:
        today_pct = min(round(st.session_state.total_intake / daily_goal * 100), 100) if st.session_state.total_intake else 0

    st.markdown("### Today's Progress")

    # -------------------------------
    # Plotly Gauge for Today's Hydration
    # -------------------------------
    fig_daily = go.Figure(
        go.Indicator(
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
        )
    )
    fig_daily.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=30, b=20),
        paper_bgcolor="rgba(0,0,0,0)"
    )
    st.plotly_chart(fig_daily, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False})

    # -------------------------------
    # Dynamic completion message
    # -------------------------------
    if today_pct >= 100:
        st.success("🏆 Goal achieved today! Fantastic work — keep the streak alive! 💧")
    elif today_pct > 0:
        st.info(f"💦 You've completed {today_pct}% of your daily goal.")
    else:
        st.info("🎯 Not started yet — let's drink some water and get moving!")

    st.write("---")
    st.markdown("### Weekly Progress (Mon → Sun) — Current Week")

    week_start_str = weekly["week_start"]
    week_start_dt = datetime.strptime(week_start_str, "%Y-%m-%d").date()
    week_days = [week_start_dt + timedelta(days=i) for i in range(7)]
    labels = [d.strftime("%a\n%d %b") for d in week_days]
    week_days_str = [d.strftime("%Y-%m-%d") for d in week_days]

    liters_list = []
    pct_list = []
    status_list = []

    for d_str, d in zip(week_days_str, week_days):
        liters = weekly["days"].get(d_str, 0.0)
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

    df_week = pd.DataFrame({
        "label": labels,
        "pct": pct_list,
        "liters": liters_list,
        "status": status_list
    })

    # -------------------------------
    # Plotly Weekly Bar Chart
    # -------------------------------
    fig_week = go.Figure()
    fig_week.add_trace(
        go.Bar(
            x=df_week["label"],
            y=df_week["pct"],
            marker_color=colors,
            text=[f"{v}%" if v > 0 else "" for v in df_week["pct"]],
            textposition='outside',
            hovertemplate="%{x}<br>%{y}%<br>Liters: %{customdata} L<extra></extra>",
            customdata=[round(v, 2) for v in df_week["liters"]]
        )
    )
    fig_week.update_layout(
        yaxis={'title': 'Completion %', 'range': [0, 100]},
        showlegend=False,
        margin=dict(l=20, r=20, t=20, b=40),
        height=340,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    st.plotly_chart(fig_week, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': True})

    st.markdown(
        '<p style="font-size:14px; color:gray;">Please double-tap to zoom out from the graph.</p>',
        unsafe_allow_html=True
    )

    # -------------------------------
    # Matplotlib Circular Daily Progress (Dynamic)
    # -------------------------------
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(4,4))
    ax.axis('equal')  # Keep circle round

    # Draw background ring
    ax.pie([100], radius=1, colors=["#E0E0E0"], startangle=90, counterclock=False,
           wedgeprops=dict(width=0.15, edgecolor='white'))

    # Draw progress portion based on today_pct
    ax.pie([today_pct, 100-today_pct], radius=1, colors=["#1A73E8", "none"], startangle=90,
           counterclock=False, wedgeprops=dict(width=0.15, edgecolor='white'))

    # Display percentage text in center
    ax.text(0, 0, f"{today_pct}%", ha='center', va='center', fontsize=20, fontweight='bold', color="#1A73E8")

    # Title above the ring
    plt.text(0, 1.2, "Daily Water Intake in Percentage(Circular graph)", ha='center', fontsize=13, fontweight='bold', color="#333")

    plt.tight_layout()
    st.pyplot(fig)

    # -------------------------------
    # Footer buttons and navigation
    # -------------------------------
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
# DAILY STREAK PAGE (with medals + data saving)
# -------------------------------
elif st.session_state.page == "daily_streak":
    if not st.session_state.logged_in:
        go_to_page("login")

    set_background()  # Keep consistent background
    username = st.session_state.username
    today = date.today()
    year, month = today.year, today.month
    days_in_month = calendar.monthrange(year, month)[1]

    # Ensure user data exists
    ensure_user_structures(username)

    # ------------------- Update streak if daily goal achieved -------------------
    daily_goal = user_data[username]["water_profile"].get(
        "daily_goal", user_data[username].get("ai_water_goal", 2.5)
    )
    # If today's intake >= goal and not already recorded
    if st.session_state.total_intake >= daily_goal:
        streak_info = user_data[username].setdefault("streak", {"completed_days": [], "current_streak": 0})
        today_iso = today.isoformat()
        if today_iso not in streak_info["completed_days"]:
            streak_info["completed_days"].append(today_iso)
            # Update current streak
            sorted_days = sorted([datetime.strptime(d, "%Y-%m-%d").date() for d in streak_info["completed_days"]])
            current_streak = 0
            for d in reversed(sorted_days):
                if (today - d).days == 0 or (today - d).days == current_streak:
                    current_streak += 1
                else:
                    break
            streak_info["current_streak"] = current_streak
            save_user_data(user_data)

    # Load streak info
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

    # ------------------- Medal Unlocks -------------------
    medals = [
        {"name": "Bronze", "days_required": 3, "icon": "🥉"},
        {"name": "Silver", "days_required": 7, "icon": "🥈"},
        {"name": "Gold", "days_required": 14, "icon": "🥇"},
    ]

    st.markdown(
        "<h3 style='text-align:center; color:#1A73E8;'>🏅 Medal Achievements</h3>",
        unsafe_allow_html=True
    )
    medal_html = "<div style='display:flex; justify-content:center; gap:20px; margin-bottom:20px;'>"
    for medal in medals:
        if current_streak >= medal["days_required"]:  # unlocked medal
            medal_html += f"<div style='text-align:center; font-size:36px;' title='{medal['name']} Medal Unlocked!'>{medal['icon']}</div>"
        else:  # locked medal (dimmed)
            medal_html += f"<div style='text-align:center; font-size:36px; color:lightgray;' title='{medal['name']} Medal Locked'>{medal['icon']}</div>"
    medal_html += "</div>"
    st.markdown(medal_html, unsafe_allow_html=True)

    # ------------------- Stars Grid -------------------
    star_css = """
    <style>
    .star-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 14px; justify-items: center; align-items: center; padding: 6px 4%; }
    .star { width:42px; height:42px; display:flex; align-items:center; justify-content:center; font-size:16px; border-radius:6px; transition: transform .12s ease, box-shadow .12s ease, background-color .12s ease, filter .12s ease; cursor: pointer; user-select: none; text-decoration:none; line-height:1; }
    .star:hover { transform: translateY(-6px) scale(1.06); }
    .star.dim { background: rgba(255,255,255,0.03); color: #bdbdbd; box-shadow: none; filter: grayscale(10%); }
    .star.upcoming { background: rgba(255,255,255,0.02); color: #999; box-shadow: none; filter: grayscale(30%); }
    .star.achieved { background: radial-gradient(circle at 30% 20%, #fff6c2, #ffd85c 40%, #ffb400 100%); color: #4b2a00; box-shadow: 0 8px 22px rgba(255,176,0,0.42), 0 2px 6px rgba(0,0,0,0.18); }
    .star.small { width:38px; height:38px; font-size:14px; }
    @media(max-width:600px){ .star-grid { grid-template-columns: repeat(4, 1fr); gap:10px; } .star { width:36px; height:36px; font-size:14px; } }
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

    st.markdown(
        f"<h2 style='text-align:center; color:#1A73E8;'>🔥 Daily Streak: {current_streak} Days</h2>",
        unsafe_allow_html=True
    )
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







































