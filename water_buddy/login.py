import streamlit as st
import json
import os
import pycountry
import re
import pandas as pd
from datetime import datetime, date
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
        f"Height ({height_unit})",
        value=float(saved.get("Height", "0").split()[0]) if "Height" in saved else 0.0
    )
    weight_unit = st.radio("Weight Unit", ["kg", "lbs"], horizontal=True)
    weight = st.number_input(
        f"Weight ({weight_unit})",
        value=float(saved.get("Weight", "0").split()[0]) if "Weight" in saved else 0.0
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
# WATER INTAKE PAGE
# -------------------------------
elif st.session_state.page == "water_profile":
    username = st.session_state.username
    saved = user_data.get(username, {}).get("water_profile", {})
    ai_goal = user_data.get(username, {}).get("ai_water_goal", 2.5)

    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 Water Intake</h1>", unsafe_allow_html=True)
    st.success(f"Your ideal daily water intake is **{ai_goal} L/day**, as suggested by Water Buddy 💧")

    daily_goal = st.slider("Set your daily water goal (L):", 0.5, 10.0, float(ai_goal), 0.1)
    frequency_options = [f"{i} minutes" for i in range(5, 185, 5)]
    selected_frequency = st.selectbox(
        "🔔 Reminder Frequency:",
        frequency_options,
        index=frequency_options.index(saved.get("frequency", "30 minutes"))
    )

    if st.button("💾 Save & Continue ➡️"):
        user_data[username]["water_profile"] = {"daily_goal": daily_goal, "frequency": selected_frequency}
        save_user_data(user_data)
        st.success("✅ Water profile saved successfully!")
        go_to_page("home")

# -------------------------------
# HOME PAGE
# -------------------------------
elif st.session_state.page == "home":
    username = st.session_state.username
    daily_goal = user_data.get(username, {}).get("water_profile", {}).get(
        "daily_goal", user_data.get(username, {}).get("ai_water_goal", 2.5)
    )

    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 HP PARTNER</h1>", unsafe_allow_html=True)

    fill_percent = min(st.session_state.total_intake / daily_goal, 1.0) if daily_goal > 0 else 0
    bottle_html = f"""
    <div style='width: 120px; height: 300px; border: 3px solid #1A73E8; border-radius: 20px; position: relative; margin: auto;
    background: linear-gradient(to top, #1A73E8 {fill_percent*100}%, #E0E0E0 {fill_percent*100}%);'>
        <div style='position: absolute; bottom: 5px; width: 100%; text-align: center; color: #fff; font-weight: bold; font-size: 18px;'>
            {round(st.session_state.total_intake,2)}L / {daily_goal}L
        </div>
    </div>
    """
    st.markdown(bottle_html, unsafe_allow_html=True)
    st.write("---")

    water_input = st.text_input("Enter water amount (in ml):", key="water_input")
    if st.button("➕ Add Water"):
        value = re.sub("[^0-9.]", "", water_input).strip()
        if value:
            try:
                ml = float(value)
                liters = ml / 1000
                st.session_state.total_intake += liters
                st.session_state.water_intake_log.append(f"{ml} ml")
                st.success(f"✅ Added {ml} ml of water!")

                # ✅ Update daily streak data when user meets their goal
                username = st.session_state.username
                today_str = str(date.today())
                user_streak = user_data.get(username, {}).get("streak", {"completed_days": [], "current_streak": 0})
                daily_goal = user_data.get(username, {}).get("water_profile", {}).get("daily_goal", 2.5)

                # If daily goal reached, add today's date to completed_days and recompute streak
                if st.session_state.total_intake >= daily_goal:
                    if today_str not in user_streak.get("completed_days", []):
                        # append today's date as YYYY-MM-DD
                        user_streak.setdefault("completed_days", []).append(today_str)
                        # keep unique & sorted
                        user_streak["completed_days"] = sorted(list(set(user_streak["completed_days"])))
                    # Recalculate continuous streak ending today
                    completed_dates = sorted([datetime.strptime(d, "%Y-%m-%d").date() for d in user_streak["completed_days"]])
                    streak = 0
                    day_cursor = date.today()
                    while True:
                        if day_cursor in completed_dates:
                            streak += 1
                            day_cursor = day_cursor - pd.Timedelta(days=1)
                            # use datetime.date arithmetic using timedelta from pandas or datetime
                            # convert to datetime.date deltas:
                            day_cursor = day_cursor
                        else:
                            break
                    user_streak["current_streak"] = streak
                    user_data[username]["streak"] = user_streak
                    save_user_data(user_data)

                st.rerun()
                st.stop()
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
        if st.button("👤 Personal Settings"):
            go_to_page("settings")
    with col2:
        if st.button("🚰 Water Intake"):
            go_to_page("water_profile")
    with col3:
        if st.button("📈 Report"):
            go_to_page("report")
    with col4:
        if st.button("🔥 Daily Streak"):
            go_to_page("daily_streak")
    with col5:
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            go_to_page("login")

    # -------------------------------
    # 🤖 Water Buddy Chatbot Popup (Fixed header + removed scrollbar)
    # (unchanged from your original - kept as-is)
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
    }
    .chat-window {
        position: fixed;
        bottom: 100px;
        right: 25px;
        width: 350px;
        background: white;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        padding: 15px;
        z-index: 1000;
        overflow-y: auto;
        max-height: 400px;
        scrollbar-width: none;
    }
    .chat-window::-webkit-scrollbar {
        display: none;
    }
    .bot-message {
        text-align: left;
        color: #222;
        background: #F1F1F1;
        padding: 8px 10px;
        border-radius: 10px;
        margin: 5px 0;
        display: inline-block;
    }
    </style>
    """, unsafe_allow_html=True)

    chat_button_clicked = st.button("🤖", key="chat_button", help="Chat with Water Buddy")
    if chat_button_clicked:
        st.session_state.show_chatbot = not st.session_state.show_chatbot

    if st.session_state.show_chatbot:
        with st.container():
            st.markdown("<div class='chat-window'>", unsafe_allow_html=True)
            st.markdown("""
            <div style='text-align:center; color:#1A73E8; font-weight:600; font-size:18px;'>
                💬 Water Buddy <span style='font-size:14px; color:#555;'>— powered by Gemini 2.5 Flash</span>
            </div>
            """, unsafe_allow_html=True)

            # Only show bot messages (hide user text)
            for entry in st.session_state.chat_history:
                if entry["sender"] == "bot":
                    st.markdown(f"<div class='bot-message'>🤖 {entry['text']}</div>", unsafe_allow_html=True)

            user_msg = st.text_input("Type your message...", key="chat_input")
            if st.button("Send", key="send_btn"):
                if user_msg.strip():
                    try:
                        prompt = f"You are Water Buddy, a friendly AI hydration assistant. Respond conversationally.\nUser: {user_msg}"
                        response = model.generate_content(prompt)
                        reply = response.text.strip()
                    except Exception:
                        reply = "⚠️ Sorry, I’m having trouble connecting right now."
                    st.session_state.chat_history.append({"sender": "bot", "text": reply})
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------
# REPORT PAGE
# -------------------------------
elif st.session_state.page == "report":
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>📊 Weekly Report</h1>", unsafe_allow_html=True)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    progress = [100, 100, 75, 100, 90, 60, 100]
    avg = sum(progress) / len(progress)
    df = pd.DataFrame({"Day": days, "Progress (%)": progress})
    st.bar_chart(df.set_index("Day"))
    st.write(f"### Weekly Avg: {avg:.0f}%")
    st.write("Goals Met: 5/7 days | Streak: 3 days")
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
        st.info("You're on Report")
    with col5:
        if st.button("🔥 Daily Streak"):
            go_to_page("daily_streak")

# -------------------------------
# DAILY STREAK PAGE (updated)
# -------------------------------
elif st.session_state.page == "daily_streak":
    username = st.session_state.username
    today = date.today()
    year, month = today.year, today.month
    month_name = today.strftime("%B %Y")
    days_in_month = calendar.monthrange(year, month)[1]

    # Ensure streak structure exists
    if username not in user_data:
        user_data[username] = {}
    streak_info = user_data[username].get("streak", {"completed_days": [], "current_streak": 0})
    completed_iso = streak_info.get("completed_days", [])  # list of "YYYY-MM-DD" strings
    current_streak = streak_info.get("current_streak", 0)

    # Convert completed days to date objects and filter to this month
    completed_dates = []
    for s in completed_iso:
        try:
            d = datetime.strptime(s, "%Y-%m-%d").date()
            completed_dates.append(d)
        except Exception:
            continue
    completed_dates_in_month = sorted([d for d in completed_dates if d.year == year and d.month == month])
    completed_days_numbers = [d.day for d in completed_dates_in_month]

    # Determine last completed day in this month (if any)
    last_completed_day_num = max(completed_days_numbers) if completed_days_numbers else None

    # Build calendar grid: 7 columns
    grid_html = "<div style='display:grid; grid-template-columns:repeat(7, 1fr); gap:8px; text-align:center;'>"
    for day in range(1, days_in_month + 1):
        # decide color
        if day in completed_days_numbers:
            color = "#1A73E8"  # Blue for completed
            text_color = "white"
        else:
            # if there's any completed day and this day is before the last completed day and is not completed -> red
            if last_completed_day_num and day < last_completed_day_num:
                color = "#FF4B4B"  # Red missed (streak broken / between streaks)
                text_color = "white"
            else:
                color = "#E0E0E0"  # Gray upcoming / not met yet
                text_color = "black"
        grid_html += f"<div style='background-color:{color}; border-radius:8px; padding:10px; color:{text_color}; font-weight:bold;'>{day}</div>"
    grid_html += "</div>"

    # Display header + circle with dynamic streak count
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>🔥 Daily Streak</h1>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='text-align:center; color:#1A73E8; margin-top:6px;'>{month_name}</h3>", unsafe_allow_html=True)

    st.markdown(f"""
    <div style='text-align:center; margin-top:12px;'>
        <div style='background: linear-gradient(180deg, #3EA1F2, #1A73E8); width:160px; height:160px; border-radius:50%;
        margin:auto; display:flex; align-items:center; justify-content:center; color:white; font-size:36px; font-weight:bold;'>
            {current_streak} DAYS
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Message below circle
    if current_streak > 0:
        st.success(f"🔥 You're on a {current_streak}-day streak! Keep it up!")
    else:
        # If user has no recorded completed days at all, show the "haven't started" message
        all_completed_any_month = any(user_data[username].get("streak", {}).get("completed_days", []))
        if not all_completed_any_month:
            st.info("🎯 You haven't started your streak yet")
        else:
            st.info("⚠️ You have no active streak right now — start drinking to build one!")

    st.write("---")

    # Show calendar grid
    st.markdown(grid_html, unsafe_allow_html=True)

    st.write("---")
    # Legend
    st.markdown("""
    <div style='display:flex; gap:12px; justify-content:center; align-items:center; margin-top:10px;'>
      <div style='display:flex; align-items:center; gap:6px;'><div style='width:18px; height:18px; background:#1A73E8; border-radius:4px;'></div> Blue = Goal met</div>
      <div style='display:flex; align-items:center; gap:6px;'><div style='width:18px; height:18px; background:#E0E0E0; border-radius:4px;'></div> Gray = Not met / upcoming</div>
      <div style='display:flex; align-items:center; gap:6px;'><div style='width:18px; height:18px; background:#FF4B4B; border-radius:4px;'></div> Red = Missed (streak broken)</div>
    </div>
    """, unsafe_allow_html=True)

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
