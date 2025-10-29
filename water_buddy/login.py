import streamlit as st
import json
import os
from datetime import datetime
import pycountry
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

# --------------------------
# SESSION STATE SETUP
# --------------------------
if "page" not in st.session_state:
    st.session_state.page = "home"

if "username" not in st.session_state:
    st.session_state.username = "Guest"

user_data = load_user_data()

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
# DAILY STREAK PAGE
# --------------------------
elif st.session_state.page == "daily_streak":
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 DAILY STREAK</h1>", unsafe_allow_html=True)

    streak_days = 14
    today = datetime.now()
    month = today.strftime("%B %Y")

    st.markdown(f"""
        <div style='text-align:center; margin-top:-20px;'>
            <div style='
                background: linear-gradient(180deg, #3EA1F2, #1A73E8);
                width:180px; height:180px; border-radius:50%;
                margin:auto; display:flex; align-items:center; justify-content:center;
                color:white; font-size:40px; font-weight:bold;'>
                {streak_days} DAYS
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown(f"<h3 style='text-align:center; color:#1A73E8; margin-top:30px;'>{month}</h3>", unsafe_allow_html=True)

    days_in_month = 30
    completed_days = [1, 2, 5, 6, 7, 10, 11, 12, 13, 14, 15, 18, 19, 20]

    cols = st.columns(7)
    week_day = 0
    for day in range(1, days_in_month + 1):
        if week_day == 7:
            week_day = 0
            cols = st.columns(7)
        with cols[week_day]:
            if day in completed_days:
                st.markdown(f"<div style='text-align:center; color:#1A73E8; font-weight:bold;'>💧<br>{day}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='text-align:center; color:gray;'>{day}</div>", unsafe_allow_html=True)
        week_day += 1

    st.markdown("---")
    st.markdown("<h4 style='color:#1A73E8;'>🏅 Achievement Badges</h4>", unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("<div style='text-align:center;'>🥉<br><b>7-Day</b><br>Unlocked ✅</div>", unsafe_allow_html=True)
    with col2:
        st.markdown("<div style='text-align:center;'>🥈<br><b>30-Day</b><br>Locked 🔒</div>", unsafe_allow_html=True)
    with col3:
        st.markdown("<div style='text-align:center;'>🥇<br><b>90-Day</b><br>Locked 🔒</div>", unsafe_allow_html=True)
    with col4:
        st.markdown("<div style='text-align:center;'>🏆<br><b>Next Badge</b><br>180 Days</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""
        <div style='background-color:#E3F2FD; border-radius:12px; padding:15px; text-align:center; color:#1A73E8; font-size:18px;'>
            💧 You're on fire! Keep the streak going for better health! 🔥
        </div>
    """, unsafe_allow_html=True)

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
