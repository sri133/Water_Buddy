import streamlit as st
import json, os, pycountry, re
from datetime import datetime, timedelta
from dotenv import load_dotenv
import google.generativeai as genai
import pandas as pd

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

USERS_FILE = "users.json"
DATA_FILE = "user_data.json"

# Initialize files
for file in [USERS_FILE, DATA_FILE]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({}, f)

# Utility functions
def load_json(file):
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# --- User Authentication ---
def signup(username, password):
    users = load_json(USERS_FILE)
    if username in users:
        return False
    users[username] = {"password": password}
    save_json(USERS_FILE, users)
    return True

def login(username, password):
    users = load_json(USERS_FILE)
    return username in users and users[username]["password"] == password

# --- AI Goal Calculation ---
def get_ai_water_goal(profile):
    try:
        prompt = f"""
        Based on this user info: 
        Age: {profile.get('age')} 
        Height: {profile.get('height')} cm
        Weight: {profile.get('weight')} kg
        Health Condition: {profile.get('health')}
        Country: {profile.get('country')}
        Suggest daily water intake in liters.
        """
        model = genai.GenerativeModel("gemini-1.5-flash")
        res = model.generate_content(prompt)
        text = res.text.lower()
        match = re.search(r"(\d+(\.\d+)?)\s*(l|litre|liters)", text)
        return float(match.group(1)) if match else 2.5
    except Exception:
        return 2.5

# --- App ---
st.set_page_config(page_title="💧HP PARTNER", layout="centered")
st.title("💧 HP PARTNER")

menu = ["Login", "Sign Up"]
choice = st.sidebar.radio("Menu", menu)

user_data = load_json(DATA_FILE)

if choice == "Sign Up":
    st.subheader("Create Account")
    user = st.text_input("Username")
    pwd = st.text_input("Password", type="password")
    if st.button("Sign Up"):
        if signup(user, pwd):
            st.success("Account created! Please login.")
        else:
            st.error("Username already exists!")

elif choice == "Login":
    st.subheader("Login to Continue")
    user = st.text_input("Username")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        if login(user, pwd):
            st.session_state["user"] = user
            st.success("Logged in successfully!")
        else:
            st.error("Invalid credentials!")

if "user" in st.session_state:
    username = st.session_state["user"]
    st.sidebar.success(f"Welcome {username}!")

    if username not in user_data:
        user_data[username] = {
            "profile": {},
            "water_goal": 2.5,
            "intake": [],
        }

    profile = user_data[username]["profile"]
    goal = user_data[username]["water_goal"]

    page = st.sidebar.radio("Navigation", ["Profile", "Add Water", "Weekly Report"])

    # --- PROFILE PAGE ---
    if page == "Profile":
        st.header("👤 Personal Settings")
        profile["age"] = st.number_input("Age", min_value=1, value=int(profile.get("age", 18)))
        profile["height"] = st.number_input("Height (cm)", min_value=50, value=int(profile.get("height", 170)))
        profile["weight"] = st.number_input("Weight (kg)", min_value=10, value=int(profile.get("weight", 60)))
        profile["country"] = st.selectbox("Country", [c.name for c in pycountry.countries], 
                                          index=100 if "country" not in profile else 
                                          [c.name for c in pycountry.countries].index(profile["country"]))
        profile["health"] = st.text_input("Health Condition", value=profile.get("health", "Healthy"))

        if st.button("💡 Recalculate AI Goal"):
            with st.spinner("Calculating AI water goal..."):
                goal = get_ai_water_goal(profile)
                user_data[username]["water_goal"] = goal
                save_json(DATA_FILE, user_data)
            st.success(f"✅ AI suggested daily water goal: {goal:.2f} L")

        save_json(DATA_FILE, user_data)

    # --- ADD WATER PAGE ---
    elif page == "Add Water":
        st.header("🥤 Track Your Water Intake")
        st.markdown(f"**Your daily goal:** {goal:.2f} L")

        amount = st.text_input("Enter water amount (in ml):", placeholder="e.g. 700 or 700ml")
        add = st.button("➕ Add Water")

        if add:
            match = re.match(r"^\s*(\d+(\.\d+)?)\s*(ml)?\s*$", amount.strip().lower())
            if match:
                water_ml = float(match.group(1))
                timestamp = datetime.now().isoformat()
                user_data[username]["intake"].append({"ml": water_ml, "time": timestamp})
                save_json(DATA_FILE, user_data)
                st.success(f"✅ Added {water_ml:.1f} ml of water!")
            else:
                st.error("❌ Please enter a valid number like 700, 700ml, or 700 ml.")

    # --- WEEKLY REPORT PAGE ---
    elif page == "Weekly Report":
        st.header("📊 Weekly Report")

        data = user_data[username]["intake"]
        if not data:
            st.info("No water data yet.")
        else:
            df = pd.DataFrame(data)
            df["time"] = pd.to_datetime(df["time"])
            df["date"] = df["time"].dt.date

            last_7 = df[df["date"] >= datetime.now().date() - timedelta(days=6)]
            daily_sum = last_7.groupby("date")["ml"].sum().reset_index()

            daily_sum["Progress (%)"] = (daily_sum["ml"] / (goal * 1000)) * 100
            daily_sum["Progress (%)"] = daily_sum["Progress (%)"].clip(upper=100)

            st.bar_chart(data=daily_sum.set_index("date")["Progress (%)"])

            total_ml = daily_sum["ml"].sum()
            st.metric("💧 Total Intake This Week", f"{total_ml/1000:.2f} L")
            st.metric("🎯 Goal (per day)", f"{goal:.2f} L")

        save_json(DATA_FILE, user_data)
