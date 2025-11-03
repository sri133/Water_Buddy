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
    st.error("❌ Google API key not found. Please add it in Streamlit Secrets or .env file.")
else:
    genai.configure(api_key=api_key)

# -------------------------------
# Helper functions
# -------------------------------
def calculate_streak(logs):
    logs = sorted([datetime.strptime(d, "%Y-%m-%d") for d in logs])
    streak = 0
    today = datetime.today().date()
    for i in range(len(logs) - 1, -1, -1):
        if (today - logs[i].date()).days == streak:
            streak += 1
        else:
            break
    return streak

def load_user_data():
    if os.path.exists("user_data.json"):
        with open("user_data.json", "r") as f:
            return json.load(f)
    return {}

def save_user_data(data):
    with open("user_data.json", "w") as f:
        json.dump(data, f, indent=4)

def calculate_daily_goal(weight, activity_level):
    base = weight * 35
    if activity_level == "Moderate":
        base *= 1.1
    elif activity_level == "High":
        base *= 1.25
    return round(base, 1)

# -------------------------------
# App Layout
# -------------------------------
st.set_page_config(page_title="💧 HP Partner", layout="wide")

st.title("💧 HP Partner – Smart Hydration Tracker")
st.markdown(
    "<p style='color: #0077cc; font-size: 16px; margin-top: -8px;'>"
    "💧 <b>Recommended:</b> Use calibrated water bottles for accurate tracking."
    "</p>",
    unsafe_allow_html=True
)

menu = ["Home", "Profile", "Report", "Chatbot"]
choice = st.sidebar.selectbox("Navigation", menu)

# -------------------------------
# Load User Data
# -------------------------------
data = load_user_data()
if "logs" not in data:
    data["logs"] = {}

# -------------------------------
# HOME PAGE
# -------------------------------
if choice == "Home":
    st.header("🏠 Home - Water Intake Log")

    today = date.today().strftime("%Y-%m-%d")

    col1, col2 = st.columns(2)
    with col1:
        intake = st.number_input("Enter today's water intake (ml)", min_value=0, step=50)
    with col2:
        if st.button("Save Intake"):
            data["logs"][today] = intake
            save_user_data(data)
            st.success("💧 Water intake logged successfully!")

    if data.get("logs"):
        streak = calculate_streak(list(data["logs"].keys()))
        st.info(f"🔥 Current streak: {streak} days")

        # Daily goal progress
        if "weight" in data and "activity_level" in data:
            goal = calculate_daily_goal(data["weight"], data["activity_level"])
            today_intake = data["logs"].get(today, 0)
            progress = min(today_intake / goal, 1.0)
            st.progress(progress)
            st.write(f"📊 Today's progress: {today_intake} / {goal} ml")
        else:
            st.warning("⚙️ Set your profile details to get personalized water goals.")

# -------------------------------
# PROFILE PAGE
# -------------------------------
elif choice == "Profile":
    st.header("👤 Personal Settings")

    name = st.text_input("Name", data.get("name", ""))
    age = st.number_input("Age", min_value=1, max_value=120, value=data.get("age", 25))
    weight = st.number_input("Weight (kg)", min_value=1, value=data.get("weight", 60))
    activity_level = st.selectbox(
        "Activity Level",
        ["Low", "Moderate", "High"],
        index=["Low", "Moderate", "High"].index(data.get("activity_level", "Moderate"))
    )

    if st.button("Save Profile"):
        data.update({"name": name, "age": age, "weight": weight, "activity_level": activity_level})
        save_user_data(data)
        st.success("✅ Profile updated successfully!")

# -------------------------------
# REPORT PAGE
# -------------------------------
elif choice == "Report":
    st.header("📊 Water Intake Report")

    if data.get("logs"):
        df = pd.DataFrame(list(data["logs"].items()), columns=["Date", "Water (ml)"])
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date")

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["Date"], y=df["Water (ml)"], mode="lines+markers", name="Water Intake"))
        fig.update_layout(
            title="Water Intake Over Time",
            xaxis_title="Date",
            yaxis_title="Water (ml)",
            hovermode="x unified"
        )

        st.plotly_chart(fig, use_container_width=True)

        # 💡 Added Tip Below Chart
        st.markdown(
            "<p style='color: gray; font-size: 14px; margin-top: -10px;'>"
            "🖱️ <b>Tip:</b> Double click on the graph to return to normal view or zoom out."
            "</p>",
            unsafe_allow_html=True
        )

        avg_intake = round(df["Water (ml)"].mean(), 1)
        st.metric("📈 Average Daily Intake", f"{avg_intake} ml")

    else:
        st.warning("⚠️ No water intake logs found. Add your first entry on the Home page.")

# -------------------------------
# CHATBOT PAGE
# -------------------------------
elif choice == "Chatbot":
    st.header("🤖 Hydration Assistant Chatbot")
    st.caption("Ask me about hydration tips, bottle sizes, or how to stay consistent!")

    user_message = st.text_input("💬 Type your question:")
    if st.button("Ask"):
        if user_message.strip():
            try:
                model = genai.GenerativeModel("gemini-1.5-flash")
                response = model.generate_content(
                    f"Answer as a friendly hydration assistant, briefly and clearly: {user_message}"
                )
                st.write(response.text)
            except Exception as e:
                st.error(f"⚠️ Gemini API error: {e}")
        else:
            st.warning("Please enter a question first.")

# -------------------------------
# FOOTER
# -------------------------------
st.markdown(
    "<hr><center>💧 <i>Stay Hydrated, Stay Healthy – HP Partner © 2025</i></center>",
    unsafe_allow_html=True
)
