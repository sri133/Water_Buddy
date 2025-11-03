import streamlit as st
import json
import os
import pycountry
import re
import pandas as pd
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
import google.generativeai as genai
import calendar
import plotly.graph_objects as go

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
    st.error("⚠️ Google API Key not found. Please set it in Streamlit Secrets or .env file.")
else:
    genai.configure(api_key=api_key)

# -------------------------------
# 📦 Constants and Helper Data
# -------------------------------
COUNTRIES = [country.name for country in pycountry.countries]

def load_data():
    if "user_data" not in st.session_state:
        st.session_state.user_data = {
            "name": "",
            "age": "",
            "gender": "",
            "country": "",
            "height": "",
            "weight": "",
            "water_goal": 2000,
            "water_intake": 0,
            "last_logged_date": str(date.today()),
            "streak": 0,
        }

load_data()

# -------------------------------
# 🧮 AI Water Goal Recommendation
# -------------------------------
def get_ai_water_goal(age, gender, weight, country):
    prompt = f"""
    You are a hydration expert AI. Based on:
    - Age: {age}
    - Gender: {gender}
    - Weight: {weight} kg
    - Country: {country}
    Give a simple, short, numeric daily water intake goal in milliliters for a healthy person.
    Example: 2500 ml
    """
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    text = response.text.strip()
    value = re.findall(r'\d+', text)
    return int(value[0]) if value else 2000

# -------------------------------
# 💧 Track Water Intake and Streak
# -------------------------------
def update_streak():
    today = date.today()
    last_logged = datetime.strptime(st.session_state.user_data["last_logged_date"], "%Y-%m-%d").date()

    if today == last_logged:
        pass  # same day
    elif today - last_logged == timedelta(days=1):
        st.session_state.user_data["streak"] += 1
        st.session_state.user_data["last_logged_date"] = str(today)
    else:
        st.session_state.user_data["streak"] = 1
        st.session_state.user_data["last_logged_date"] = str(today)

# -------------------------------
# 🏠 Home Page
# -------------------------------
def home_page():
    st.title("💧 HP PARTNER")
    st.subheader("Stay Hydrated. Stay Healthy.")

    st.markdown("### Track your daily water intake")
    intake = st.number_input("Enter water intake (ml):", min_value=0, step=100)
    if st.button("Log Intake"):
        st.session_state.user_data["water_intake"] += intake
        update_streak()
        st.success(f"Logged {intake} ml of water!")

    # Animated water level
    goal = st.session_state.user_data["water_goal"]
    intake = st.session_state.user_data["water_intake"]
    percentage = min(intake / goal * 100, 100)

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=percentage,
        title={'text': "Hydration Progress"},
        gauge={'axis': {'range': [0, 100]},
               'bar': {'color': "blue"},
               'steps': [{'range': [0, 50], 'color': "lightgray"},
                         {'range': [50, 100], 'color': "lightblue"}]}
    ))
    st.plotly_chart(fig)

    st.write(f"**Daily Goal:** {goal} ml")
    st.write(f"**Today's Intake:** {intake} ml")
    st.write(f"🔥 **Current Streak:** {st.session_state.user_data['streak']} days")

# -------------------------------
# ⚙️ Personal Settings
# -------------------------------
def settings_page():
    st.header("⚙️ Personal Settings")

    with st.form("settings_form"):
        name = st.text_input("Name", st.session_state.user_data["name"])
        age = st.number_input("Age", min_value=1, max_value=120, value=int(st.session_state.user_data["age"] or 18))
        gender = st.selectbox("Gender", ["Male", "Female", "Other"])
        country = st.selectbox("Country", COUNTRIES)
        height = st.number_input("Height (cm)", min_value=50, max_value=250, value=int(st.session_state.user_data["height"] or 170))
        weight = st.number_input("Weight (kg)", min_value=20, max_value=200, value=int(st.session_state.user_data["weight"] or 60))

        if st.form_submit_button("💾 Save and Get AI Goal"):
            st.session_state.user_data.update({
                "name": name, "age": age, "gender": gender, "country": country,
                "height": height, "weight": weight
            })
            ai_goal = get_ai_water_goal(age, gender, weight, country)
            st.session_state.user_data["water_goal"] = ai_goal
            st.success(f"✅ Saved! Your AI-recommended goal is {ai_goal} ml/day.")

# -------------------------------
# 📈 Report Page
# -------------------------------
def report_page():
    st.header("📈 Hydration Report")
    today = date.today()
    streak = st.session_state.user_data["streak"]

    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    intake = [max(0, st.session_state.user_data["water_goal"] - (i * 100)) for i in range(7)]

    df = pd.DataFrame({"Date": days, "Intake (ml)": intake})
    st.line_chart(df, x="Date", y="Intake (ml)")

    st.metric("🔥 Current Streak", f"{streak} days")
    st.metric("💧 Water Goal", f"{st.session_state.user_data['water_goal']} ml")

# -------------------------------
# 💬 Chatbot Page
# -------------------------------
def chatbot_page():
    st.header("💬 HP Partner Chatbot")
    st.write("Ask anything about hydration, health, or daily wellness!")

    user_input = st.text_area("Your Question:")
    if st.button("Ask"):
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(user_input)
        st.info(response.text)

# -------------------------------
# 🌐 Navigation
# -------------------------------
st.sidebar.title("🚀 Navigation")
page = st.sidebar.radio("Go to", ["Home", "Settings", "Report", "Chatbot"])

if page == "Home":
    home_page()
elif page == "Settings":
    settings_page()
elif page == "Report":
    report_page()
elif page == "Chatbot":
    chatbot_page()

st.sidebar.markdown("---")
st.sidebar.caption("Made with ❤️ using Streamlit and Google Gemini AI")
