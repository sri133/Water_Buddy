import streamlit as st
import json
import os
import pycountry
import re
from datetime import time
import google.generativeai as genai
from dotenv import load_dotenv

# -------------------------------
# Load API key
# -------------------------------
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY", None)
if not api_key:
    st.error("❌ Missing API key. Please add GOOGLE_API_KEY in your .env or Streamlit Secrets.")
else:
    genai.configure(api_key=api_key)
model = genai.GenerativeModel("models/gemini-2.5-flash")

# -------------------------------
# Page setup
# -------------------------------
st.set_page_config(page_title="HP PARTNER", page_icon="💧", layout="centered")

USER_DATA_FILE = "user_data.json"

def save_user_data(data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "r") as f:
            return json.load(f)
    return {}

user_data = load_user_data()

# -------------------------------
# Session setup
# -------------------------------
if "page" not in st.session_state:
    st.session_state.page = "login"
if "username" not in st.session_state:
    st.session_state.username = ""
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "total_intake" not in st.session_state:
    st.session_state.total_intake = 0.0
if "water_intake_log" not in st.session_state:
    st.session_state.water_intake_log = []

def go_to_page(page):
    st.session_state.page = page
    st.rerun()

# -------------------------------
# LOGIN PAGE
# -------------------------------
if st.session_state.page == "login":
    st.title("💧 HP PARTNER")
    st.markdown("### Login or Sign Up")

    option = st.radio("Choose Option", ["Login", "Sign Up"])
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Submit"):
        if option == "Sign Up":
            if username in user_data:
                st.error("Username already exists.")
            else:
                user_data[username] = {"password": password}
                save_user_data(user_data)
                st.success("Account created! Please log in.")
        else:
            if username in user_data and user_data[username]["password"] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("Login successful!")

                # Load existing intake data
                user_info = user_data.get(username, {}).get("water_profile", {})
                st.session_state.total_intake = user_info.get("total_intake", 0.0)
                st.session_state.water_intake_log = user_info.get("intake_log", [])
                go_to_page("home")
            else:
                st.error("Invalid username or password.")

# -------------------------------
# HOME PAGE
# -------------------------------
elif st.session_state.page == "home":
    username = st.session_state.username
    user_info = user_data.get(username, {})
    water_info = user_info.get("water_profile", {})
    daily_goal = water_info.get("daily_goal", 2.5)

    st.markdown(f"### 👋 Welcome, {username}")
    st.write(f"Your daily goal: **{daily_goal} L**")

    fill_percent = min(st.session_state.total_intake / daily_goal, 1.0)
    st.markdown(
        f"""
        <div style='
            width:120px;height:300px;margin:auto;
            border:3px solid #1A73E8;border-radius:20px;
            background:linear-gradient(to top,#1A73E8 {fill_percent*100}%,#E0E0E0 {fill_percent*100}%);
            position:relative;text-align:center;color:white;font-weight:bold;'>
            <div style='position:absolute;bottom:10px;width:100%;'>
                {round(st.session_state.total_intake,2)}L / {daily_goal}L
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("---")
    st.subheader("💧 Add Water Intake")
    water_input = st.text_input("Enter water amount (ml):")

    if st.button("➕ Add Water"):
        try:
            value = re.sub("[^0-9.]", "", water_input)
            ml = float(value)
            liters = ml / 1000
            st.session_state.total_intake += liters
            st.session_state.water_intake_log.append(f"{ml} ml")

            # Save permanently
            user_data[username].setdefault("water_profile", {})
            user_data[username]["water_profile"]["total_intake"] = st.session_state.total_intake
            user_data[username]["water_profile"]["intake_log"] = st.session_state.water_intake_log
            save_user_data(user_data)

            st.success(f"✅ Added {ml} ml!")
            st.rerun()
        except:
            st.error("Please enter a valid number like 700 or 700ml.")

    if st.session_state.water_intake_log:
        st.write("### Today's Log:")
        for i, entry in enumerate(st.session_state.water_intake_log, 1):
            st.write(f"{i}. {entry}")

    st.write("---")
    if st.button("🚪 Logout"):
        st.session_state.logged_in = False
        go_to_page("login")
