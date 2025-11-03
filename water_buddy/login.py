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

def save_streak_data():
    with open(STREAK_FILE, "w") as f:
        json.dump(streak_data, f, indent=4)

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
    if not st st.session_state.logged_in:
        go_to_page("login")

    username = st.session_state.username
    saved = user_data.get(username, {}).get("profile", {})

    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 Personal Settings</h1>", unsafe_allow_html=True)
    # (All your existing settings code here remains unchanged)
    # ...

# -------------------------------
# WATER INTAKE PAGE
# -------------------------------
elif st.session_state.page == "water_profile":
    # (Unchanged Water Intake code)
    # ...

# -------------------------------
# HOME PAGE (with Chatbot)
# -------------------------------
elif st.session_state.page == "home":
    # (Unchanged Home + Chatbot code)
    # ...

# -------------------------------
# REPORT PAGE (restored old design)
# -------------------------------
elif st.session_state.page == "report":
    # (Unchanged Report code)
    # ...

# -------------------------------
# ✅ UPDATED DAILY STREAK PAGE
# -------------------------------
elif st.session_state.page == "daily_streak":
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>🔥 Daily Streak</h1>", unsafe_allow_html=True)

    username = st.session_state.username
    today = datetime.now().date()
    month = today.strftime("%B %Y")
    days_in_month = calendar.monthrange(today.year, today.month)[1]

    if username not in streak_data:
        streak_data[username] = {}

    if "completed_days" not in streak_data[username]:
        streak_data[username]["completed_days"] = []

    completed_days = streak_data[username]["completed_days"]

    # If today's goal met
    daily_goal = user_data.get(username, {}).get("water_profile", {}).get(
        "daily_goal", user_data.get(username, {}).get("ai_water_goal", 2.5)
    )
    if st.session_state.total_intake >= daily_goal:
        day_num = today.day
        if day_num not in completed_days:
            completed_days.append(day_num)
            completed_days.sort()
            streak_data[username]["completed_days"] = completed_days
            save_streak_data()

    # Calculate current streak
    streak = 0
    for i in range(len(completed_days) - 1, -1, -1):
        if i == len(completed_days) - 1:
            streak = 1
        elif completed_days[i] == completed_days[i + 1] - 1:
            streak += 1
        else:
            break

    # Display main circle
    st.markdown(f"""
    <div style='text-align:center;'>
        <div style='background: linear-gradient(180deg, #3EA1F2, #1A73E8); width:180px; height:180px; border-radius:50%;
        margin:auto; display:flex; align-items:center; justify-content:center; color:white; font-size:40px; font-weight:bold;'>
            {streak} DAYS
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Display month header
    st.markdown(f"<h3 style='text-align:center; color:#1A73E8; margin-top:30px;'>{month}</h3>", unsafe_allow_html=True)

    # Calendar grid
    grid_html = "<div style='display:grid; grid-template-columns:repeat(7, 1fr); gap:8px; text-align:center;'>"
    for i in range(1, days_in_month + 1):
        if i in completed_days:
            color = "#1A73E8"
            text_color = "white"
        elif i < today.day:
            color = "#FF4B4B"
            text_color = "white"
        else:
            color = "#E0E0E0"
            text_color = "black"
        grid_html += f"<div style='background-color:{color}; border-radius:8px; padding:10px; color:{text_color}; font-weight:bold;'>{i}</div>"
    grid_html += "</div>"

    st.markdown(grid_html, unsafe_allow_html=True)

    # Dynamic message
    if streak > 0:
        st.success(f"🔥 You're on a {streak}-day streak! Keep it up!")
    else:
        st.info("🎯 You haven’t started your streak yet!")

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
