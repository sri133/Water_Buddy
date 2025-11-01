import streamlit as st
import json
import os
import re
import pycountry
from datetime import datetime
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv

# -------------------------------
# INITIAL SETUP
# -------------------------------
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash")

USER_FILE = "users.json"

# -------------------------------
# HELPER FUNCTIONS
# -------------------------------
def load_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USER_FILE, "w") as f:
        json.dump(users, f, indent=4)

def go_to_page(page_name):
    st.session_state.page = page_name
    st.rerun()

# -------------------------------
# PAGE SETUP
# -------------------------------
st.set_page_config(page_title="Water Buddy 💧", layout="wide")
if "page" not in st.session_state:
    st.session_state.page = "login"
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "total_intake" not in st.session_state:
    st.session_state.total_intake = 0.0
if "water_intake_log" not in st.session_state:
    st.session_state.water_intake_log = []
if "show_chatbot" not in st.session_state:
    st.session_state.show_chatbot = False

user_data = load_users()

# -------------------------------
# LOGIN PAGE
# -------------------------------
if st.session_state.page == "login":
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 Welcome to Water Buddy</h1>", unsafe_allow_html=True)
    username = st.text_input("Username:")
    password = st.text_input("Password:", type="password")

    if st.button("Login"):
        if username in user_data and user_data[username]["password"] == password:
            st.session_state.username = username
            st.session_state.logged_in = True
            go_to_page("home")
        else:
            st.error("❌ Invalid username or password")

    st.write("Don't have an account?")
    if st.button("Sign Up"):
        go_to_page("signup")

# -------------------------------
# SIGNUP PAGE
# -------------------------------
elif st.session_state.page == "signup":
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>🆕 Create Account</h1>", unsafe_allow_html=True)
    username = st.text_input("Choose a Username:")
    password = st.text_input("Choose a Password:", type="password")

    if st.button("Register"):
        if username in user_data:
            st.error("⚠️ Username already exists!")
        elif not username or not password:
            st.error("❌ Please fill in all fields.")
        else:
            user_data[username] = {"password": password, "water_profile": {}, "ai_water_goal": 2.5}
            save_users(user_data)
            st.success("✅ Account created! Please log in.")
            go_to_page("login")

    if st.button("🔙 Back to Login"):
        go_to_page("login")

# -------------------------------
# HOME PAGE (with Chatbot)
# -------------------------------
elif st.session_state.page == "home":
    username = st.session_state.username
    daily_goal = user_data.get(username, {}).get("water_profile", {}).get(
        "daily_goal", user_data.get(username, {}).get("ai_water_goal", 2.5)
    )

    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 HP Partner</h1>", unsafe_allow_html=True)
    fill_percent = min(st.session_state.total_intake / daily_goal, 1.0)
    bottle_html = f"""
    <div style='width: 120px; height: 300px; border: 3px solid #1A73E8; border-radius: 20px;
        position: relative; margin: auto; background: linear-gradient(to top, #1A73E8 {fill_percent*100}%, #E0E0E0 {fill_percent*100}%);'>
        <div style='position: absolute; bottom: 5px; width: 100%; text-align: center; color: #fff; font-weight: bold; font-size: 18px;'>
            {round(st.session_state.total_intake,2)}L / {daily_goal}L
        </div>
    </div>
    """
    st.markdown(bottle_html, unsafe_allow_html=True)

    st.write("---")
    water_input = st.text_input("Enter water amount (in ml):", key="water_input")

    # ✅ Add water
    if st.button("➕ Add Water"):
        value = re.sub("[^0-9.]", "", water_input).strip()
        if value:
            try:
                ml = float(value)
                liters = ml / 1000
                st.session_state.total_intake += liters
                st.session_state.water_intake_log.append(f"{ml} ml")
                st.success(f"✅ Added {ml} ml of water!")
                st.rerun()
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
        if st.button("👤 Personal Settings"): go_to_page("settings")
    with col2:
        if st.button("🚰 Water Intake"): go_to_page("water_profile")
    with col3:
        if st.button("📈 Report"): go_to_page("report")
    with col4:
        if st.button("🔥 Daily Streak"): go_to_page("daily_streak")
    with col5:
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            go_to_page("login")

    # -------------------------------
    # 🤖 Water Buddy Chatbot Popup (Improved)
    # -------------------------------
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
            transition: transform 0.3s ease;
        }
        .chat-button:hover {
            transform: scale(1.1);
        }
        .chat-window {
            position: fixed;
            bottom: 100px;
            right: 25px;
            width: 350px;
            background: #111;
            border-radius: 15px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.4);
            padding: 15px;
            z-index: 1000;
            animation: slideUp 0.3s ease;
            color: white;
        }
        @keyframes slideUp {
            from { transform: translateY(30px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
        .chat-header {
            text-align: center;
            font-size: 18px;
            font-weight: bold;
            color: #1A73E8;
            margin-bottom: 10px;
        }
        .chat-message {
            margin: 8px 0;
            color: #E8EAED;
            font-size: 15px;
            line-height: 1.4;
        }
        </style>
    """, unsafe_allow_html=True)

    chat_button_clicked = st.button("🤖", key="chat_button", help="Chat with Water Buddy")

    if chat_button_clicked:
        st.session_state.show_chatbot = not st.session_state.show_chatbot

    if st.session_state.show_chatbot:
        with st.container():
            st.markdown("<div class='chat-window'>", unsafe_allow_html=True)
            st.markdown("<div class='chat-header'>💬 Water Buddy</div>", unsafe_allow_html=True)

            if "chat_replies" not in st.session_state:
                st.session_state.chat_replies = []

            for reply in st.session_state.chat_replies:
                st.markdown(f"<div class='chat-message'>🤖 {reply}</div>", unsafe_allow_html=True)

            user_msg = st.text_input("Type your message...", key="chat_input")

            if st.button("Send", key="send_btn"):
                if user_msg.strip():
                    try:
                        prompt = f"You are Water Buddy, a friendly hydration assistant. Respond clearly and warmly.\nUser: {user_msg}"
                        response = model.generate_content(prompt)
                        reply = response.text.strip()
                    except Exception:
                        reply = "⚠️ Sorry, I’m having trouble connecting right now."

                    st.session_state.chat_replies.append(reply)
                    st.session_state.chat_input = ""
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------
# PERSONAL SETTINGS PAGE
# -------------------------------
elif st.session_state.page == "settings":
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>👤 Personal Settings</h1>", unsafe_allow_html=True)
    age = st.number_input("Age:", min_value=5, max_value=100, value=20)
    weight = st.number_input("Weight (kg):", min_value=10.0, max_value=200.0, value=60.0)
    height = st.number_input("Height (cm):", min_value=50.0, max_value=250.0, value=170.0)
    health_issue = st.text_input("Health Issue (optional):")
    gender = st.selectbox("Gender:", ["Male", "Female", "Other"])
    activity = st.selectbox("Activity Level:", ["Low", "Moderate", "High"])
    country = st.selectbox("Country:", [c.name for c in pycountry.countries])

    if st.button("💾 Save Settings"):
        bmi = weight / ((height / 100) ** 2)
        user_data[st.session_state.username]["water_profile"] = {
            "age": age, "weight": weight, "height": height,
            "bmi": round(bmi, 2), "gender": gender,
            "activity": activity, "health_issue": health_issue, "country": country,
        }
        save_users(user_data)
        st.success(f"✅ Saved! Your BMI is {round(bmi, 2)}")
    if st.button("🏠 Back to Home"): go_to_page("home")

# -------------------------------
# WATER PROFILE PAGE
# -------------------------------
elif st.session_state.page == "water_profile":
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>🚰 Water Intake Profile</h1>", unsafe_allow_html=True)
    user = user_data[st.session_state.username]
    profile = user.get("water_profile", {})

    if not profile:
        st.warning("⚠️ Please fill Personal Settings first.")
    else:
        prompt = f"Suggest a healthy daily water intake (in litres) for: {profile}."
        try:
            response = model.generate_content(prompt)
            goal = re.findall(r'\d+\.?\d*', response.text)
            goal_l = float(goal[0]) if goal else 2.5
        except Exception:
            goal_l = 2.5

        user_data[st.session_state.username]["ai_water_goal"] = goal_l
        save_users(user_data)
        st.success(f"💧 Your daily goal: {goal_l} litres")
    if st.button("🏠 Back to Home"): go_to_page("home")

# -------------------------------
# WEEKLY REPORT PAGE
# -------------------------------
elif st.session_state.page == "report":
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>📈 Weekly Water Intake Report</h1>", unsafe_allow_html=True)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    intake = [2.0, 1.8, 2.5, 2.2, 1.9, 2.7, 2.3]
    df = pd.DataFrame({"Day": days, "Water Intake (L)": intake})
    st.bar_chart(df.set_index("Day"))
    st.success("✅ Keep it up! Try reaching your daily goal consistently.")
    if st.button("🏠 Back to Home"): go_to_page("home")

# -------------------------------
# DAILY STREAK PAGE
# -------------------------------
elif st.session_state.page == "daily_streak":
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>🔥 Daily Streak</h1>", unsafe_allow_html=True)
    st.write("You've stayed hydrated for 14 days in a row! 💪 Keep going!")
    today = datetime.now()
    completed_days = list(range(1, today.day + 1))
    days_in_month = 30
    grid_html = "<div style='display:grid; grid-template-columns:repeat(7, 1fr); gap:8px; text-align:center;'>"
    for i in range(1, days_in_month + 1):
        color = "#1A73E8" if i in completed_days else "#E0E0E0"
        text_color = "white" if i in completed_days else "black"
        grid_html += f"<div style='background-color:{color}; border-radius:8px; padding:10px; color:{text_color}; font-weight:bold;'>{i}</div>"
    grid_html += "</div>"
    st.markdown(grid_html, unsafe_allow_html=True)
    st.success("🔥 You're on a 14-day streak! Keep it up!")

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
