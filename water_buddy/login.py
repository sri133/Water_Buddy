import streamlit as st
import json
import os
import pycountry
import re
from datetime import time
import google.generativeai as genai

# ✅ Load API key from Streamlit Secrets or .env
api_key = None
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    st.error("❌ Missing API key. Please add GOOGLE_API_KEY in your .env or Streamlit Secrets.")
else:
    genai.configure(api_key=api_key)

model = genai.GenerativeModel("models/gemini-2.5-flash")

# ✅ Streamlit Page Config (only once)
st.set_page_config(page_title="HP PARTNER", page_icon="💧", layout="centered")

# -------------------------------
# File setup
# -------------------------------
CREDENTIALS_FILE = "users.json"
USER_DATA_FILE = "user_data.json"

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

# -------------------------------
# Streamlit session setup
# -------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "page" not in st.session_state:
    st.session_state.page = "login"
if "username" not in st.session_state:
    st.session_state.username = ""
if "country" not in st.session_state:
    st.session_state.country = "India"
if "water_intake_log" not in st.session_state:
    st.session_state.water_intake_log = []
if "total_intake" not in st.session_state:
    st.session_state.total_intake = 0.0  # in liters
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
        f"Height ({height_unit})", value=float(saved.get("Height", "0").split()[0]) if "Height" in saved else 0.0
    )

    weight_unit = st.radio("Weight Unit", ["kg", "lbs"], horizontal=True)
    weight = st.number_input(
        f"Weight ({weight_unit})", value=float(saved.get("Weight", "0").split()[0]) if "Weight" in saved else 0.0
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
# WATER PROFILE PAGE
# -------------------------------
elif st.session_state.page == "water_profile":
    username = st.session_state.username
    saved = user_data.get(username, {}).get("water_profile", {})
    ai_goal = user_data.get(username, {}).get("ai_water_goal", 2.5)

    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 Water Intake Profile</h1>", unsafe_allow_html=True)
    st.write(f"### Hello, {username}! 👋")
    st.success(f"Your ideal daily water intake is **{ai_goal} L/day**, as suggested by Water Buddy 💧")

    saved_goal = saved.get("daily_goal")
    daily_goal = ai_goal if saved_goal in (None, "") else saved_goal

    st.write("---")
    st.subheader("⚙️ Customize Your Daily Goal")

    daily_goal = st.slider(
        "Set your daily water goal (L):",
        0.5, 10.0,
        float(daily_goal),
        0.1,
        help="Adjust if you want a different goal than Water Buddy's suggestion."
    )

    st.success(f"💧 Current goal: {daily_goal} L/day")

    frequency_options = [f"{i} minutes" for i in range(5, 185, 5)]
    selected_frequency = st.selectbox(
        "🔔 Reminder Frequency:",
        frequency_options,
        index=frequency_options.index(saved.get("frequency", "30 minutes"))
    )

    if st.button("💾 Save & Continue ➡️"):
        user_data[username]["water_profile"] = {
            "daily_goal": daily_goal,
            "frequency": selected_frequency,
        }
        save_user_data(user_data)
        st.success("✅ Water profile saved successfully!")
        go_to_page("home")

# -------------------------------
# HOME PAGE
# -------------------------------
elif st.session_state.page == "home":
    username = st.session_state.username
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 HP PARTNER</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:gray;'>Welcome back! Stay hydrated 💦</p>", unsafe_allow_html=True)
    st.write("---")

    daily_goal = user_data.get(username, {}).get("water_profile", {}).get(
        "daily_goal", user_data.get(username, {}).get("ai_water_goal", 2.5)
    )

    st.subheader("🥤 Your Daily Water Bottle")

    fill_percent = min(st.session_state.total_intake / daily_goal, 1.0)
    bottle_html = f"""
    <div style='
        width: 120px;
        height: 300px;
        border: 3px solid #1A73E8;
        border-radius: 20px;
        position: relative;
        margin: auto;
        background: linear-gradient(to top, #1A73E8 {fill_percent*100}%, #E0E0E0 {fill_percent*100}%);
        transition: background 0.5s ease;
    '>
        <div style='
            position: absolute;
            bottom: 5px;
            width: 100%;
            text-align: center;
            color: #fff;
            font-weight: bold;
            font-size: 18px;
        '>{round(st.session_state.total_intake,2)}L / {daily_goal}L</div>
    </div>
    """
    st.markdown(bottle_html, unsafe_allow_html=True)

    st.write("---")
    st.subheader("💧 Add Water Intake")
    water_input = st.text_input("Enter water amount (in ml):", key="water_input")

    if st.button("➕ Add Water"):
        try:
            value = re.sub("[^0-9.]", "", water_input)
            ml = float(value)
            liters = ml / 1000
            st.session_state.total_intake += liters
            st.session_state.water_intake_log.append(f"{ml} ml")
            st.success(f"✅ Added {ml} ml of water!")
            st.rerun()
        except:
            st.error("❌ Please enter a valid number like 700, 700ml, or 700 ml.")

    if st.session_state.water_intake_log:
        st.write("### Today's Log:")
        for i, entry in enumerate(st.session_state.water_intake_log, 1):
            st.write(f"{i}. {entry}")

    st.write("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("👤 Profile"):
            go_to_page("settings")
    with col2:
        if st.button("📊 Water Profile"):
            go_to_page("water_profile")
    with col3:
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            go_to_page("login")

    # 💬 Chatbot Section
    if st.button("💬 Chat with WaterBuddy"):
        st.session_state.show_chatbot = not st.session_state.show_chatbot
        st.rerun()

    if st.session_state.show_chatbot:
        st.markdown("---")
        st.subheader("🤖 WaterBuddy Chat")
        user_message = st.text_input("Say something to WaterBuddy:")

        if st.button("Send"):
            if user_message.strip() != "":
                try:
                    response = model.generate_content(user_message)
                    bot_reply = response.text.strip()
                    st.session_state.chat_history.append(("You", user_message))
                    st.session_state.chat_history.append(("WaterBuddy", bot_reply))
                    st.rerun()
                except Exception as e:
                    st.error(f"WaterBuddy had an issue: {e}")

        for speaker, msg in reversed(st.session_state.chat_history[-10:]):
            st.write(f"**{speaker}:** {msg}")
