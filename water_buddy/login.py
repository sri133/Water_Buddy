import streamlit as st
import json
import os
from datetime import datetime, date
import pycountry
import calendar
from dotenv import load_dotenv
import google.generativeai as genai

# --------------------------
# INITIAL SETUP
# --------------------------
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

st.set_page_config(page_title="Water Buddy 💧", layout="centered")

# --------------------------
# HELPER FUNCTIONS
# --------------------------
def go_to_page(page_name):
    st.session_state.page = page_name

def load_user_data():
    if os.path.exists("user_data.json"):
        with open("user_data.json", "r") as f:
            return json.load(f)
    return {}

def save_user_data(data):
    with open("user_data.json", "w") as f:
        json.dump(data, f, indent=4)

def load_streak_data():
    if os.path.exists("streak_data.json"):
        with open("streak_data.json", "r") as f:
            return json.load(f)
    return {}

def save_streak_data(data):
    with open("streak_data.json", "w") as f:
        json.dump(data, f, indent=4)

# --------------------------
# SESSION STATE SETUP
# --------------------------
if "page" not in st.session_state:
    st.session_state.page = "home"

if "username" not in st.session_state:
    st.session_state.username = "Guest"

user_data = load_user_data()
streak_data = load_streak_data()

# --------------------------
# HOME PAGE
# --------------------------
if st.session_state.page == "home":
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 Welcome to Water Buddy!</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;'>Your smart hydration assistant powered by AI.</p>", unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("🏠 Home"):
            st.info("You're already on the Home page.")
    with col2:
        if st.button("👤 Personal Settings"):
            go_to_page("settings")
    with col3:
        if st.button("🚰 Water Intake"):
            go_to_page("intake")
    with col4:
        if st.button("📈 Report"):
            go_to_page("report")

    st.write("")
    st.image("https://cdn-icons-png.flaticon.com/512/6645/6645092.png", width=200)
    st.markdown("<p style='text-align:center; color:gray;'>Stay hydrated, stay healthy!</p>", unsafe_allow_html=True)

# --------------------------
# PERSONAL SETTINGS PAGE
# --------------------------
elif st.session_state.page == "settings":
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>👤 Personal Settings</h1>", unsafe_allow_html=True)

    username = st.text_input("Enter your name", value=st.session_state.username)
    age = st.number_input("Age", min_value=5, max_value=100, value=17)
    country = st.selectbox("Select your country", [country.name for country in pycountry.countries])
    height = st.number_input("Height (cm)", min_value=50, max_value=250, value=170)
    health_issue = st.text_area("Health issues (optional)", placeholder="E.g., kidney stone, dehydration, etc.")

    if st.button("💾 Save Settings"):
        user_data[username] = {
            "age": age,
            "country": country,
            "height": height,
            "health_issue": health_issue,
        }
        save_user_data(user_data)
        st.session_state.username = username
        st.success("✅ Personal settings saved successfully!")

    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("🏠 Home"): go_to_page("home")
    with col2:
        st.info("You're already on Personal Settings.")
    with col3:
        if st.button("🚰 Water Intake"): go_to_page("intake")
    with col4:
        if st.button("📈 Report"): go_to_page("report")

# --------------------------
# WATER INTAKE PAGE
# --------------------------
elif st.session_state.page == "intake":
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>🚰 Water Intake</h1>", unsafe_allow_html=True)
    username = st.session_state.username

    intake_goal = 2000  # default in ml
    if username in user_data:
        health_info = user_data[username].get("health_issue", "").lower()
        if "stone" in health_info or "dehydration" in health_info:
            intake_goal = 2500
        elif "heart" in health_info:
            intake_goal = 1800

    st.markdown(f"<h4 style='text-align:center;'>Your daily goal: <span style='color:#1A73E8;'>{intake_goal} ml</span></h4>", unsafe_allow_html=True)
    water_intake = st.number_input("Enter water intake (ml)", min_value=0, value=0, step=50)

    if st.button("💧 Add Water"):
        if "total_intake" not in st.session_state:
            st.session_state.total_intake = 0
        st.session_state.total_intake += water_intake
        st.success(f"Added {water_intake} ml! Total today: {st.session_state.total_intake} ml.")

        # Check if goal met and update streak data
        today_str = str(date.today())
        if st.session_state.total_intake >= intake_goal:
            streak_data[today_str] = "completed"
            save_streak_data(streak_data)
        else:
            streak_data[today_str] = "not_completed"
            save_streak_data(streak_data)

    if "total_intake" in st.session_state:
        progress = min(st.session_state.total_intake / intake_goal, 1.0)
        st.progress(progress)
        st.markdown(f"<p style='text-align:center;'>Progress: {progress * 100:.1f}%</p>", unsafe_allow_html=True)

    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("🏠 Home"): go_to_page("home")
    with col2:
        if st.button("👤 Personal Settings"): go_to_page("settings")
    with col3:
        st.info("You're already on Water Intake.")
    with col4:
        if st.button("📈 Report"): go_to_page("report")

# --------------------------
# REPORT PAGE
# --------------------------
elif st.session_state.page == "report":
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>📈 Weekly Report</h1>", unsafe_allow_html=True)

    week_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    completion = [100, 100, 75, 100, 90, 60, 100]

    st.markdown("### 💧 Water Intake Summary")
    for i in range(7):
        bar = "💧" * (completion[i] // 10)
        st.markdown(f"{week_days[i]} — {completion[i]}% {bar}")

    avg = sum(completion) / len(completion)
    st.markdown(f"### 🧾 Weekly Avg: **{avg:.0f}%**")
    st.markdown("✅ Goals Met: **5/7 Days**")
    st.markdown("🔥 Current Streak: **3 Days**")

    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("🏠 Home"): go_to_page("home")
    with col2:
        if st.button("👤 Personal Settings"): go_to_page("settings")
    with col3:
        if st.button("🚰 Water Intake"): go_to_page("intake")
    with col4:
        if st.button("🔥 Daily Streak"): go_to_page("daily_streak")

# --------------------------
# UPDATED DAILY STREAK PAGE
# --------------------------
elif st.session_state.page == "daily_streak":
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 DAILY STREAK</h1>", unsafe_allow_html=True)

    today = date.today()
    month_name = today.strftime("%B %Y")
    days_in_month = calendar.monthrange(today.year, today.month)[1]

    # Calculate streak count
    sorted_days = sorted(streak_data.keys())
    current_streak = 0
    for d in reversed(sorted_days):
        if streak_data[d] == "completed":
            current_streak += 1
        else:
            break

    # Circle display
    st.markdown(f"""
        <div style='text-align:center; margin-top:-20px;'>
            <div style='
                background: linear-gradient(180deg, #3EA1F2, #1A73E8);
                width:180px; height:180px; border-radius:50%;
                margin:auto; display:flex; align-items:center; justify-content:center;
                color:white; font-size:40px; font-weight:bold;'>
                {current_streak} DAYS
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown(f"<h3 style='text-align:center; color:#1A73E8; margin-top:30px;'>{month_name}</h3>", unsafe_allow_html=True)

    # Calendar grid
    cols = st.columns(7)
    week_day = 0
    for day in range(1, days_in_month + 1):
        day_str = str(date(today.year, today.month, day))
        color = "#D3D3D3"  # default gray
        text_color = "black"

        if day_str in streak_data:
            if streak_data[day_str] == "completed":
                color = "#1A73E8"  # blue
                text_color = "white"
            elif streak_data[day_str] == "not_completed":
                color = "#FF4C4C"  # red

        if week_day == 7:
            week_day = 0
            cols = st.columns(7)

        with cols[week_day]:
            st.markdown(
                f"<div style='text-align:center; background-color:{color}; color:{text_color}; padding:10px; margin:4px; border-radius:8px;'>{day}</div>",
                unsafe_allow_html=True,
            )
        week_day += 1

    # Dynamic message
    st.markdown("---")
    if current_streak == 0:
        st.markdown("<p style='text-align:center; color:red;'>🎯 You haven’t started your streak yet.</p>", unsafe_allow_html=True)
    elif current_streak < 7:
        st.markdown(f"<p style='text-align:center; color:#1A73E8;'>🔥 You’re on a {current_streak}-day streak! Keep going!</p>", unsafe_allow_html=True)
    else:
        st.markdown(f"<p style='text-align:center; color:#1A73E8;'>🏅 Amazing! {current_streak}-day streak strong!</p>", unsafe_allow_html=True)

    # Navigation
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("🏠 Home"): go_to_page("home")
    with col2:
        if st.button("👤 Personal Settings"): go_to_page("settings")
    with col3:
        if st.button("📈 Report"): go_to_page("report")
    with col4:
        st.info("You're already on Daily Streak.")
