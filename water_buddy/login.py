import streamlit as st
import json
import os
import re
from datetime import datetime

# ---------------------------
# App Configuration
# ---------------------------
st.set_page_config(page_title="Water Buddy 💧", page_icon="💙", layout="wide")

# ---------------------------
# File Handling Helpers
# ---------------------------
USER_DATA_FILE = "user_data.json"

def load_user_data():
    if not os.path.exists(USER_DATA_FILE):
        return {}
    with open(USER_DATA_FILE, "r") as f:
        return json.load(f)

def save_user_data(data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ---------------------------
# Initialize Session State
# ---------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "page" not in st.session_state:
    st.session_state.page = "login"
if "total_intake" not in st.session_state:
    st.session_state.total_intake = 0
if "water_intake_log" not in st.session_state:
    st.session_state.water_intake_log = []
if "goal" not in st.session_state:
    st.session_state.goal = 2.0  # default goal in liters

# ---------------------------
# Login Page
# ---------------------------
def login_page():
    st.title("💧 Welcome to Water Buddy!")
    st.subheader("Stay hydrated and healthy with your personal AI hydration tracker 💙")

    user_data = load_user_data()

    username = st.text_input("👤 Username:")
    password = st.text_input("🔑 Password:", type="password")

    if st.button("Login"):
        if username in user_data and user_data[username]["password"] == password:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.goal = user_data[username].get("goal", 2.0)
            st.session_state.total_intake = user_data[username].get("total_intake", 0)
            st.session_state.water_intake_log = user_data[username].get("water_intake_log", [])
            st.success(f"Welcome back, {username}! 💧")
            st.session_state.page = "home"
            st.rerun()
        else:
            st.error("Invalid username or password 😔")

    if st.button("Create Account"):
        st.session_state.page = "register"
        st.rerun()

# ---------------------------
# Register Page
# ---------------------------
def register_page():
    st.title("📝 Create Your Account")

    username = st.text_input("Choose a Username:")
    password = st.text_input("Create Password:", type="password")
    confirm = st.text_input("Confirm Password:", type="password")

    if st.button("Register"):
        user_data = load_user_data()

        if username in user_data:
            st.error("Username already exists 😔")
        elif password != confirm:
            st.error("Passwords do not match ⚠️")
        elif username.strip() == "" or password.strip() == "":
            st.error("Please fill in all fields!")
        else:
            user_data[username] = {
                "password": password,
                "goal": 2.0,
                "total_intake": 0,
                "water_intake_log": [],
            }
            save_user_data(user_data)
            st.success("Account created successfully! 🎉 Please login.")
            st.session_state.page = "login"
            st.rerun()

    if st.button("Back to Login"):
        st.session_state.page = "login"
        st.rerun()

# ---------------------------
# Home Page
# ---------------------------
def home_page():
    st.title(f"💙 Hello, {st.session_state.username}!")
    st.subheader("Let's track your water intake today 💧")

    user_data = load_user_data()
    goal = user_data[st.session_state.username].get("goal", 2.0)
    st.session_state.goal = goal

    st.write(f"🎯 **Your daily goal:** {goal} Liters")
    st.write(f"💧 **Total intake today:** {round(st.session_state.total_intake, 2)} Liters")

    progress = min(st.session_state.total_intake / goal, 1.0)
    st.progress(progress)

    # Input section
    water_input = st.text_input("Enter water amount (in ml):", key="water_input")

    # ✅ FIXED SECTION — only this part changed
    if st.button("➕ Add Water"):
        value = re.sub("[^0-9.]", "", water_input).strip()
        if value and re.match(r"^\d+(\.\d+)?$", value):
            ml = float(value)
            liters = ml / 1000
            st.session_state.total_intake += liters
            st.session_state.water_intake_log.append(f"{ml} ml")
            st.success(f"✅ Added {ml} ml of water!")
            st.session_state.water_input = ""  # Clears the input box
            st.rerun()
        else:
            st.error("❌ Please enter a valid number like 700, 700ml, or 700 ml.")

    if st.button("📊 Weekly Report"):
        st.session_state.page = "weekly"
        st.rerun()

    if st.button("⚙️ Settings"):
        st.session_state.page = "settings"
        st.rerun()

    if st.button("🚪 Logout"):
        user_data[st.session_state.username]["total_intake"] = st.session_state.total_intake
        user_data[st.session_state.username]["water_intake_log"] = st.session_state.water_intake_log
        save_user_data(user_data)
        st.session_state.logged_in = False
        st.session_state.page = "login"
        st.rerun()

# ---------------------------
# Weekly Report Page
# ---------------------------
def weekly_page():
    st.title("📊 Weekly Report")

    user_data = load_user_data()
    username = st.session_state.username
    total_intake = user_data[username].get("total_intake", 0)

    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    progress = [round(total_intake * (i / 7), 2) for i in range(1, 8)]

    st.bar_chart({"Progress (L)": progress}, x=days)
    st.write("💧 Keep going! You're building a healthy habit 🌿")

    if st.button("🏠 Back to Home"):
        st.session_state.page = "home"
        st.rerun()

# ---------------------------
# Settings Page
# ---------------------------
def settings_page():
    st.title("⚙️ Personal Settings")

    user_data = load_user_data()
    username = st.session_state.username
    goal = st.number_input("Set your daily water goal (in Liters):", min_value=0.5, max_value=10.0, step=0.1, value=user_data[username].get("goal", 2.0))

    if st.button("Save Goal"):
        user_data[username]["goal"] = goal
        save_user_data(user_data)
        st.success(f"✅ Your new goal of {goal}L has been saved!")

    if st.button("🏠 Back to Home"):
        st.session_state.page = "home"
        st.rerun()

# ---------------------------
# Page Navigation
# ---------------------------
if st.session_state.page == "login":
    login_page()
elif st.session_state.page == "register":
    register_page()
elif st.session_state.page == "home":
    home_page()
elif st.session_state.page == "weekly":
    weekly_page()
elif st.session_state.page == "settings":
    settings_page()
