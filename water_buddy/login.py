import streamlit as st
import json
import os
import pycountry
import re
from datetime import datetime, date, timedelta, time as dtime
from dotenv import load_dotenv
import google.generativeai as genai
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
# SQLite setup for credentials and userdata
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

# Load and save helpers
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
# Utilities
# -------------------------------
countries = [c.name for c in pycountry.countries]
GITHUB_ASSETS_BASE = "https://raw.githubusercontent.com/sri133/Water_Buddy/main/water_buddy/assets/"

def build_image_url(filename: str) -> str:
    return GITHUB_ASSETS_BASE + quote(filename, safe='')

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
    return d - timedelta(days=d.weekday())  # Monday

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

def go_to_page(page_name: str):
    st.session_state.page = page_name
    st.experimental_rerun()

# -------------------------------
# Session initialization defaults
# -------------------------------
if "total_intake" not in st.session_state:
    st.session_state.total_intake = 0.0
if "water_intake_log" not in st.session_state:
    st.session_state.water_intake_log = []
if "reset_home_bottle" not in st.session_state:
    st.session_state.reset_home_bottle = False
if "page" not in st.session_state:
    st.session_state.page = "login"
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

# -------------------------------
# Quiz generation helpers using Gemini API
# -------------------------------
def generate_quiz_via_model():
    today_str = date.today().isoformat()
    if st.session_state.get("daily_quiz_date") == today_str and st.session_state.get("daily_quiz"):
        return st.session_state["daily_quiz"]

    question_prompt = """
    Generate 10 unique multiple-choice questions about water science, water history, and recent news related to water.
    Return as valid JSON array only. Each item must be an object with fields:
    - "q": question text
    - "options": array of 4 option strings
    - "correct_index": index of correct option (0..3)
    - "explanation": short explanation (1-2 sentences) why the correct answer is correct.
    Keep each question concise and suitable for general audience.
    """
    fallback = [  # default questions - same as before
        {
            "q": "What percentage of the adult human body is roughly water?",
            "options": ["~30%", "~60%", "~80%", "~95%"],
            "correct_index": 1,
            "explanation": "About 60% of an adult human's body is water."
        },
        # ... (other 9 default questions as per your original set)
    ]

    try:
        if not model:
            return fallback
        prompt = question_prompt.strip()
        response = model.generate_content(prompt)
        text_output = response.text.strip()
        json_start = text_output.find("[")
        json_text = text_output if json_start == 0 else text_output[json_start:]
        data = json.loads(json_text)
        if isinstance(data, list) and len(data) == 10:
            st.session_state["daily_quiz_date"] = today_str
            st.session_state["daily_quiz"] = data
            return data
        else:
            return fallback
    except Exception:
        return fallback

# -------------------------------
# Page - Login (no reset button as requested)
# -------------------------------
if st.session_state.page == "login":
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 HP PARTNER</h1>", unsafe_allow_html=True)
    st.markdown("### Login or Sign Up to Continue")

    option = st.radio("Choose Option", ["Login", "Sign Up"])
    username_input = st.text_input("Enter Username", key="login_username")
    password_input = st.text_input("Enter Password", type="password", key="login_password")

    if st.button("Submit"):
        users, user_data = load_all_from_db()
        if option == "Sign Up":
            if username_input in users:
                st.error("❌ Username already exists.")
            elif username_input == "" or password_input == "":
                st.error("❌ Username and password cannot be empty.")
            else:
                users[username_input] = password_input
                save_credentials(users)
                if username_input not in user_data:
                    user_data[username_input] = {}
                user_data[username_input].setdefault("profile", {})
                user_data[username_input]["ai_water_goal"] = 2.5
                user_data[username_input]["water_profile"] = {"daily_goal": 2.5, "frequency": "30 minutes"}
                user_data[username_input]["streak"] = {"completed_days": [], "current_streak": 0}
                user_data[username_input]["daily_intake"] = {}
                yesterday_str = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
                user_data[username_input]["daily_intake"]["last_login_date"] = yesterday_str
                user_data[username_input]["weekly_data"] = {"week_start": None, "days": {}}
                save_user_data(user_data)
                st.success("✅ Account created successfully! Please login.")
        elif option == "Login":
            if username_input in users and users[username_input] == password_input:
                st.session_state.logged_in = True
                st.session_state.username = username_input
                ensure_user_structures(username_input)
                load_today_intake_into_session(username_input)
                ensure_week_current(username_input)
                if username_input in user_data and user_data[username_input].get("profile"):
                    go_to_page("home")
                else:
                    go_to_page("settings")
            else:
                st.error("❌ Invalid username or password.")

# -------------------------------
# Page - Personal Settings (with improved reset)
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
    country = st.selectbox(
        "Country",
        countries,
        index=countries.index(saved.get("Country", "India")) if saved.get("Country") else countries.index("India"),
        key="settings_country"
    )
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

    if st.button("🔄 Reset Page", key="reset_settings"):
        if username in user_data:
            user_data[username]["profile"] = {}
            save_user_data(user_data)
        for key in list(st.session_state.keys()):
            if key.startswith("settings_"):
                del st.session_state[key]
        st.experimental_rerun()

# -------------------------------
# Page - Water Intake
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

    if st.button("🔄 Reset Page", key="reset_water_profile"):
        for key in list(st.session_state.keys()):
            if key.startswith("water_profile_"):
                del st.session_state[key]
        st.experimental_rerun()

# -------------------------------
# Page - Home
# -------------------------------
elif st.session_state.page == "home":
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

    fill_percent = min(st.session_state.total_intake / daily_goal, 1.0) if daily_goal > 0 else 0

    bottle_html = f"""
    <div style='width: 120px; height: 300px; border: 3px solid #1A73E8; border-radius: 20px; position: relative; margin: auto; 
    background: linear-gradient(to top, #1A73E8 {fill_percent*100}%, #E0E0E0 {fill_percent*100}%);'>
        <div style='position: absolute; bottom: 5px; width: 100%; text-align: center; color: #fff; font-weight: bold; font-size: 18px;'>
            {round(st.session_state.total_intake, 2)}L / {daily_goal}L
        </div>
    </div>
    """
    st.markdown(bottle_html, unsafe_allow_html=True)

    # Reset button near water bottle to reset intake & animation
    if st.button("🔄 Reset Water Bottle", key="reset_home_bottle"):
        st.session_state.total_intake = 0.0
        st.session_state.water_intake_log = []
        if username in user_data:
            today_data = user_data[username].get("daily_intake", {})
            today_data[today_str] = 0.0
            today_data["last_login_date"] = today_str
            save_user_data(user_data)
        st.experimental_rerun()

    st.write("---")

    water_input = st.text_input("Enter water amount (in ml):", key="water_input")

    if st.button("➕ Add Water"):
        value_str = re.sub(r"[^0-9.]", "", water_input).strip()
        if value_str:
            value = float(value_str) / 1000.0
            st.session_state.total_intake += value
            st.session_state.water_intake_log.append(value)
            if username in user_data:
                today_str = date.today().strftime("%Y-%m-%d")
                daily_intake = user_data[username].setdefault("daily_intake", {})
                current_intake = daily_intake.get(today_str, 0.0)
                daily_intake[today_str] = round(current_intake + value, 2)
                daily_intake["last_login_date"] = today_str
                update_weekly_record_on_add(username, today_str, daily_intake[today_str])
                save_user_data(user_data)
            st.session_state.water_input = ""

# -------------------------------
# Page - Quiz
# -------------------------------
elif st.session_state.page == "quiz":
    if not st.session_state.logged_in:
        go_to_page("login")

    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 Daily Water Quiz</h1>", unsafe_allow_html=True)

    quiz = generate_quiz_via_model()

    if "quiz_index" not in st.session_state:
        st.session_state.quiz_index = 0
        st.session_state.quiz_answers = []

    if "quiz_submitted" not in st.session_state:
        st.session_state.quiz_submitted = False

    if "quiz_results" not in st.session_state:
        st.session_state.quiz_results = None

    if not st.session_state.quiz_submitted:
        question = quiz[st.session_state.quiz_index]
        st.write(f"**Question {st.session_state.quiz_index + 1}:** {question['q']}")

        options = question["options"]
        selected = st.radio("Select your answer:", options, key="quiz_answer")

        if st.button("Submit Answer"):
            correct_index = question["correct_index"]
            is_correct = (options.index(selected) == correct_index)
            st.session_state.quiz_answers.append({
                "question": question["q"],
                "selected": selected,
                "correct": options[correct_index],
                "is_correct": is_correct,
                "explanation": question.get("explanation", "")
            })

            if st.session_state.quiz_index + 1 < len(quiz):
                st.session_state.quiz_index += 1
            else:
                st.session_state.quiz_submitted = True
            st.experimental_rerun()
    else:
        score = sum(1 for ans in st.session_state.quiz_answers if ans["is_correct"])
        st.write(f"### Quiz Results: {score} out of {len(quiz)} correct.")
        for ans in st.session_state.quiz_answers:
            st.write(f"Q: {ans['question']}")
            st.write(f"Your answer: {ans['selected']}")
            st.write(f"Correct answer: {ans['correct']}")
            st.write(f"Explanation: {ans['explanation']}")
            st.write("---")

        if st.button("Restart Quiz"):
            st.session_state.quiz_index = 0
            st.session_state.quiz_answers = []
            st.session_state.quiz_submitted = False
            st.experimental_rerun()
