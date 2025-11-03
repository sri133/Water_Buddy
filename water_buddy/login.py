import streamlit as st
import json
import os
import pycountry
import re
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
import google.generativeai as genai
import calendar

# -------------------------------
# ✅ Load API key from .env or Streamlit Secrets
# -------------------------------
api_key = None
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    st.error("❌ Missing API key. Please add GOOGLE_API_KEY in your .env or Streamlit Secrets.")
else:
    genai.configure(api_key=api_key)

model = genai.GenerativeModel("models/gemini-2.5-flash")

# -------------------------------
# ✅ Streamlit Page Config
# -------------------------------
st.set_page_config(page_title="HP PARTNER", page_icon="💧", layout="centered")

# -------------------------------
# File setup
# -------------------------------
CREDENTIALS_FILE = "users.json"
USER_DATA_FILE = "user_data.json"
STREAK_FILE = "streak_data.json"

if os.path.exists(CREDENTIALS_FILE):
    with open(CREDENTIALS_FILE, "r") as f:
        users = json.load(f)
else:
    users = {}

if os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, "r") as f:
        user_data = json.load(f)
else:
    user_data = {}

# Load streak data
if os.path.exists(STREAK_FILE):
    with open(STREAK_FILE, "r") as f:
        streak_data = json.load(f)
else:
    streak_data = {}

# -------------------------------
# Streamlit session setup
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

# -------------------------------
# Helper Functions
# -------------------------------
def save_user_data(data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def save_streak_data(data):
    with open(STREAK_FILE, "w") as f:
        json.dump(data, f, indent=4)

def go_to_page(page_name: str):
    st.session_state.page = page_name
    st.rerun()

countries = [c.name for c in pycountry.countries]

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
            if username in users:
                st.error("❌ Username already exists.")
            elif username == "" or password == "":
                st.error("❌ Username and password cannot be empty.")
            else:
                users[username] = password
                with open(CREDENTIALS_FILE, "w") as f:
                    json.dump(users, f)
                user_data[username] = {}
                save_user_data(user_data)
                st.success("✅ Account created successfully! Please login.")

        elif option == "Login":
            if username in users and users[username] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                if username in user_data and "profile" in user_data[username]:
                    go_to_page("home")
                else:
                    go_to_page("settings")
            else:
                st.error("❌ Invalid username or password.")

# -------------------------------
# PERSONAL SETTINGS PAGE
# -------------------------------
elif st.session_state.page == "settings":
    if not st.session_state.logged_in:
        go_to_page("login")

    username = st.session_state.username
    saved = user_data.get(username, {}).get("profile", {})

    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 Personal Settings</h1>", unsafe_allow_html=True)

    name = st.text_input("Name", value=saved.get("Name", username))
    age = st.text_input("Age", value=saved.get("Age", ""))
    country = st.selectbox("Country", countries, index=countries.index(saved.get("Country", "India")))
    language = st.text_input("Language", value=saved.get("Language", ""))

    st.write("---")
    height_unit = st.radio("Height Unit", ["cm", "feet"], horizontal=True)
    height = st.number_input(
        f"Height ({height_unit})",
        value=float(saved.get("Height", "0").split()[0]) if "Height" in saved else 0.0
    )
    weight_unit = st.radio("Weight Unit", ["kg", "lbs"], horizontal=True)
    weight = st.number_input(
        f"Weight ({weight_unit})",
        value=float(saved.get("Weight", "0").split()[0]) if "Weight" in saved else 0.0
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
        index=["Excellent", "Fair", "Poor"].index(saved.get("Health Condition", "Excellent"))
    )
    health_problems = st.text_area("Health problems", value=saved.get("Health Problems", ""))

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
                    response = model.generate_content(prompt)
                    text_output = response.text.strip()
                    match = re.search(r"(\d+(\.\d+)?)", text_output)
                    if match:
                        suggested_water_intake = float(match.group(1))
                    else:
                        raise ValueError("No numeric value found in Water Buddy response.")
                except Exception as e:
                    st.warning(f"⚠️ Water Buddy suggestion failed, using default 2.5 L ({e})")
                    suggested_water_intake = 2.5
        else:
            suggested_water_intake = user_data.get(username, {}).get("ai_water_goal", 2.5)
            text_output = "Profile unchanged — using previous goal."

        user_data[username] = user_data.get(username, {})
        user_data[username]["profile"] = new_profile_data
        user_data[username]["ai_water_goal"] = round(suggested_water_intake, 2)
        save_user_data(user_data)

        st.success(f"✅ Profile saved! Water Buddy suggests {suggested_water_intake:.2f} L/day 💧")
        st.info(f"Water Buddy output: {text_output}")
        go_to_page("water_profile")

# -------------------------------
# WATER INTAKE PAGE
# -------------------------------
elif st.session_state.page == "water_profile":
    username = st.session_state.username
    saved = user_data.get(username, {}).get("water_profile", {})
    ai_goal = user_data.get(username, {}).get("ai_water_goal", 2.5)

    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 Water Intake</h1>", unsafe_allow_html=True)
    st.success(f"Your ideal daily water intake is **{ai_goal} L/day**, as suggested by Water Buddy 💧")

    daily_goal = st.slider("Set your daily water goal (L):", 0.5, 10.0, float(ai_goal), 0.1)
    frequency_options = [f"{i} minutes" for i in range(5, 185, 5)]
    selected_frequency = st.selectbox(
        "🔔 Reminder Frequency:",
        frequency_options,
        index=frequency_options.index(saved.get("frequency", "30 minutes"))
    )

    if st.button("💾 Save & Continue ➡️"):
        user_data[username]["water_profile"] = {"daily_goal": daily_goal, "frequency": selected_frequency}
        save_user_data(user_data)
        st.success("✅ Water profile saved successfully!")
        go_to_page("home")

# -------------------------------
# HOME PAGE + CHATBOT (unchanged)
# -------------------------------
elif st.session_state.page == "home":
    # (same as your current working code)
    ...
# -------------------------------
# REPORT PAGE (unchanged)
# -------------------------------
elif st.session_state.page == "report":
    # (same as your current working code)
    ...
# -------------------------------
# NEW DAILY STREAK PAGE (updated only this part)
# -------------------------------
elif st.session_state.page == "daily_streak":
    username = st.session_state.username
    today = datetime.now()
    month = today.strftime("%B %Y")
    days_in_month = calendar.monthrange(today.year, today.month)[1]

    user_streak = streak_data.get(username, {"completed": [], "streak": 0, "last_update": ""})
    completed_days = user_streak["completed"]

    # Reset if new month
    last_update = user_streak.get("last_update", "")
    if last_update and datetime.strptime(last_update, "%Y-%m-%d").month != today.month:
        user_streak = {"completed": [], "streak": 0, "last_update": ""}

    # Update streak automatically if today's goal met
    daily_goal = user_data.get(username, {}).get("water_profile", {}).get("daily_goal", 2.5)
    total_intake = st.session_state.total_intake

    if total_intake >= daily_goal and today.day not in completed_days:
        user_streak["completed"].append(today.day)
        if user_streak["streak"] == 0 or (today.day - 1) in user_streak["completed"]:
            user_streak["streak"] += 1
        else:
            user_streak["streak"] = 1
        user_streak["last_update"] = today.strftime("%Y-%m-%d")
        streak_data[username] = user_streak
        save_streak_data(streak_data)

    streak_days = user_streak.get("streak", 0)

    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>🔥 Daily Streak</h1>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style='text-align:center;'>
        <div style='background: linear-gradient(180deg, #3EA1F2, #1A73E8);
        width:180px; height:180px; border-radius:50%;
        margin:auto; display:flex; align-items:center; justify-content:center;
        color:white; font-size:40px; font-weight:bold;'>
            {streak_days} DAYS
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"<h3 style='text-align:center; color:#1A73E8; margin-top:30px;'>{month}</h3>", unsafe_allow_html=True)

    grid_html = "<div style='display:grid; grid-template-columns:repeat(7, 1fr); gap:8px; text-align:center;'>"
    for i in range(1, days_in_month + 1):
        if i in completed_days:
            color = "#1A73E8"  # Blue for goal met
            text_color = "white"
        elif i < today.day and (i - 1) in completed_days:
            color = "#FF4C4C"  # Red for streak broken
            text_color = "white"
        else:
            color = "#E0E0E0"  # Gray for not yet done
            text_color = "black"
        grid_html += f"<div style='background-color:{color}; border-radius:8px; padding:10px; color:{text_color}; font-weight:bold;'>{i}</div>"
    grid_html += "</div>"
    st.markdown(grid_html, unsafe_allow_html=True)

    if streak_days == 0:
        st.info("🎯 You haven’t started your streak yet!")
    else:
        st.success(f"🔥 You’re on a {streak_days}-day streak! Keep it up!")

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
