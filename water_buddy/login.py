# app.py
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
# ✅ Files & constants
# -------------------------------
CREDENTIALS_FILE = "users.json"
USER_DATA_FILE = "user_data.json"

# -------------------------------
# ✅ Load API key (same as before)
# -------------------------------
api_key = None
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    st.warning("⚠️ GOOGLE_API_KEY not found. Chatbot and AI suggestions will use defaults.")
else:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("models/gemini-2.5-flash")
    except Exception:
        model = None

# -------------------------------
# ✅ Helper: load/save files (create if missing)
# -------------------------------
def load_files():
    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, "r") as f:
                users = json.load(f)
        except Exception:
            users = {}
    else:
        users = {}
        with open(CREDENTIALS_FILE, "w") as f:
            json.dump(users, f, indent=4, sort_keys=True)

    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r") as f:
                user_data = json.load(f)
        except Exception:
            user_data = {}
    else:
        user_data = {}
        with open(USER_DATA_FILE, "w") as f:
            json.dump(user_data, f, indent=4, sort_keys=True)

    return users, user_data

def save_files(users, user_data):
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(users, f, indent=4, sort_keys=True)
    with open(USER_DATA_FILE, "w") as f:
        json.dump(user_data, f, indent=4, sort_keys=True)

# -------------------------------
# ✅ Initialize files & load
# -------------------------------
users, user_data = load_files()

# -------------------------------
# ✅ Streamlit Page Config
# -------------------------------
st.set_page_config(page_title="HP PARTNER", page_icon="💧", layout="centered")

# -------------------------------
# ✅ Session state defaults
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
if "today_str" not in st.session_state:
    st.session_state.today_str = str(date.today())

# -------------------------------
# ✅ Utility functions for user session & date handling
# -------------------------------
def init_user_defaults(username):
    """Ensure user_data has required structure for username."""
    user_data.setdefault(username, {})
    user_data[username].setdefault("profile", {})
    user_data[username].setdefault("ai_water_goal", 2.5)
    user_data[username].setdefault("water_profile", {"daily_goal": 2.5, "frequency": "30 minutes"})
    user_data[username].setdefault("streak", {"completed_days": [], "current_streak": 0})
    user_data[username].setdefault("intake_by_date", {})  # stores ml sums per date (as float liters)
    user_data[username].setdefault("last_active_date", None)

def ensure_new_day_reset(username):
    """
    Called on login/start to initialize session variables for today.
    It loads today's intake if present. If last_active_date differs, we
    keep the previous day's streak records but set today's intake to saved or 0.
    """
    init_user_defaults(username)
    today = date.today()
    today_str = str(today)
    st.session_state.today_str = today_str

    # read last saved date
    last_date = user_data[username].get("last_active_date")

    # Load today's intake if present
    intake_by_date = user_data[username].get("intake_by_date", {})
    if today_str in intake_by_date:
        # stored value is in liters
        st.session_state.total_intake = float(intake_by_date[today_str])
        st.session_state.water_intake_log = user_data[username].get("intake_log_by_date", {}).get(today_str, [])
    else:
        # No entry for today
        # if last_date == today_str, maybe session was cleared but file had today's entry—covered above
        # else start fresh for today
        st.session_state.total_intake = 0.0
        st.session_state.water_intake_log = []

    # Update last_active_date to today (we save later when user takes actions)
    user_data[username]["last_active_date"] = today_str
    save_files(users, user_data)

def add_water_for_user(username, ml_amount):
    """Add water (ml) to the user's today's intake; update streak if goal met."""
    init_user_defaults(username)
    today_str = str(date.today())

    # convert to liters
    liters = float(ml_amount) / 1000.0

    # add to session and persistent store
    st.session_state.total_intake = round(st.session_state.total_intake + liters, 3)

    # save log entry (string like "700 ml") both in session and file
    st.session_state.water_intake_log.append(f"{ml_amount} ml")
    user_data[username].setdefault("intake_log_by_date", {})
    user_data[username]["intake_log_by_date"].setdefault(today_str, [])
    user_data[username]["intake_log_by_date"][today_str].append(f"{ml_amount} ml")

    # save liters sum
    user_data[username].setdefault("intake_by_date", {})
    user_data[username]["intake_by_date"][today_str] = round(st.session_state.total_intake, 3)

    # set last active date
    user_data[username]["last_active_date"] = today_str

    # Check if goal met now (and update streak if first time)
    daily_goal = user_data[username].get("water_profile", {}).get("daily_goal", user_data[username].get("ai_water_goal", 2.5))
    if st.session_state.total_intake >= float(daily_goal):
        # if this date not already in completed_days -> append
        completed = set(user_data[username].get("streak", {}).get("completed_days", []))
        if today_str not in completed:
            completed.add(today_str)
            user_data[username].setdefault("streak", {})
            user_data[username]["streak"]["completed_days"] = sorted(list(completed))
            # Recalculate current streak:
            completed_dates = sorted([datetime.strptime(d, "%Y-%m-%d").date() for d in user_data[username]["streak"]["completed_days"]])
            streak = 0
            day_cursor = date.today()
            while True:
                if day_cursor in completed_dates:
                    streak += 1
                    day_cursor = day_cursor - timedelta(days=1)
                else:
                    break
            user_data[username]["streak"]["current_streak"] = streak

    save_files(users, user_data)

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

# -------------------------------
# Small UI helper
# -------------------------------
def go_to_page(page_name: str):
    st.session_state.page = page_name
    st.experimental_rerun()

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
            elif username.strip() == "" or password.strip() == "":
                st.error("❌ Username and password cannot be empty.")
            else:
                # create account
                users[username] = password
                # initialize user data structure
                user_data.setdefault(username, {})
                user_data[username]["profile"] = {}
                user_data[username]["ai_water_goal"] = 2.5
                user_data[username]["water_profile"] = {"daily_goal": 2.5, "frequency": "30 minutes"}
                user_data[username]["streak"] = {"completed_days": [], "current_streak": 0}
                user_data[username]["intake_by_date"] = {}
                user_data[username]["intake_log_by_date"] = {}
                user_data[username]["last_active_date"] = None
                save_files(users, user_data)
                st.success("✅ Account created successfully! Please login.")
        elif option == "Login":
            if username in users and users[username] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                # initialize/load user's session (loads today's intake and logs)
                init_user_defaults(username)
                ensure_new_day_reset(username)
                # if profile exists -> home, else go to settings
                if user_data.get(username, {}).get("profile"):
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
    init_user_defaults(username)
    saved = user_data.get(username, {}).get("profile", {})

    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 Personal Settings</h1>", unsafe_allow_html=True)

    name = st.text_input("Name", value=saved.get("Name", username))
    age = st.text_input("Age", value=saved.get("Age", ""))
    country = st.selectbox("Country", countries, index=countries.index(saved.get("Country", "India")) if saved.get("Country") else countries.index("India"))
    language = st.text_input("Language", value=saved.get("Language", ""))

    st.write("---")

    height_unit = st.radio("Height Unit", ["cm", "feet"], horizontal=True)
    height_val = saved.get("Height", "0 cm")
    try:
        height_init = float(str(height_val).split()[0])
    except Exception:
        height_init = 0.0

    height = st.number_input(f"Height ({height_unit})", value=height_init)

    weight_unit = st.radio("Weight Unit", ["kg", "lbs"], horizontal=True)
    weight_val = saved.get("Weight", "0 kg")
    try:
        weight_init = float(str(weight_val).split()[0])
    except Exception:
        weight_init = 0.0

    weight = st.number_input(f"Weight ({weight_unit})", value=weight_init)

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
                    if model:
                        response = model.generate_content(prompt)
                        text_output = response.text.strip()
                        match = re.search(r"(\d+(\.\d+)?)", text_output)
                        if match:
                            suggested_water_intake = float(match.group(1))
                        else:
                            raise ValueError("No numeric value found.")
                    else:
                        raise RuntimeError("Model not available")
                except Exception as e:
                    st.warning(f"⚠️ Water Buddy suggestion failed, using default 2.5 L ({e})")
                    suggested_water_intake = 2.5
                    text_output = f"Error: {e}"
        else:
            suggested_water_intake = user_data.get(username, {}).get("ai_water_goal", 2.5)
            text_output = "Profile unchanged — using previous goal."

        user_data[username] = user_data.get(username, {})
        user_data[username]["profile"] = new_profile_data
        user_data[username]["ai_water_goal"] = round(suggested_water_intake, 2)
        user_data[username].setdefault("water_profile", {"daily_goal": suggested_water_intake, "frequency": "30 minutes"})
        user_data[username].setdefault("streak", {"completed_days": [], "current_streak": 0})
        save_files(users, user_data)

        st.success(f"✅ Profile saved! Water Buddy suggests {suggested_water_intake:.2f} L/day 💧")
        st.info(f"Water Buddy output: {text_output}")
        # Ensure session is up-to-date
        ensure_new_day_reset(username)
        go_to_page("water_profile")

# -------------------------------
# WATER INTAKE PAGE
# -------------------------------
elif st.session_state.page == "water_profile":
    username = st.session_state.username
    if not st.session_state.logged_in:
        go_to_page("login")

    init_user_defaults(username)
    ensure_new_day_reset(username)

    ai_goal = user_data.get(username, {}).get("ai_water_goal", 2.5)
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 Water Intake</h1>", unsafe_allow_html=True)
    st.success(f"Your ideal daily water intake is **{ai_goal} L/day**, as suggested by Water Buddy 💧")

    daily_goal = st.slider("Set your daily water goal (L):", 0.5, 10.0, float(user_data[username].get("water_profile", {}).get("daily_goal", ai_goal)), 0.1)

    # Save frequency and daily goal simple UI
    frequency_options = [f"{i} minutes" for i in range(5, 185, 5)]
    saved_freq = user_data[username].get("water_profile", {}).get("frequency", "30 minutes")
    selected_frequency = st.selectbox(
        "🔔 Reminder Frequency:",
        frequency_options,
        index=frequency_options.index(saved_freq) if saved_freq in frequency_options else 5
    )

    if st.button("💾 Save & Continue ➡️"):
        user_data[username]["water_profile"] = {"daily_goal": daily_goal, "frequency": selected_frequency}
        save_files(users, user_data)
        st.success("✅ Water profile saved successfully!")
        go_to_page("home")

# -------------------------------
# HOME PAGE
# -------------------------------
elif st.session_state.page == "home":
    username = st.session_state.username
    if not st.session_state.logged_in:
        go_to_page("login")

    init_user_defaults(username)
    ensure_new_day_reset(username)

    daily_goal = user_data.get(username, {}).get("water_profile", {}).get(
        "daily_goal", user_data.get(username, {}).get("ai_water_goal", 2.5)
    )

    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 HP PARTNER</h1>", unsafe_allow_html=True)

    # fill percent for bottle (0.0 - 1.0)
    fill_percent = min(st.session_state.total_intake / float(daily_goal), 1.0) if float(daily_goal) > 0 else 0

    bottle_html = f"""
    <div style='width: 120px; height: 300px; border: 3px solid #1A73E8; border-radius: 20px; position: relative; margin: auto; 
    background: linear-gradient(to top, #1A73E8 {fill_percent*100}%, #E0E0E0 {fill_percent*100}%);'>
        <div style='position: absolute; bottom: 5px; width: 100%; text-align: center; color: #fff; font-weight: bold; font-size: 18px;'>{round(st.session_state.total_intake,2)}L / {daily_goal}L</div>
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
                add_water_for_user(username, ml)
                st.success(f"✅ Added {int(ml)} ml of water!")
                # After updating, reload page to reflect persistent changes immediately
                st.experimental_rerun()
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
            st.session_state.username = ""
            st.session_state.total_intake = 0.0
            st.session_state.water_intake_log = []
            go_to_page("login")

    # Chatbot UI (same as before)
    st.markdown("""<style>
    .chat-button { position: fixed; bottom: 25px; right: 25px; background-color: #1A73E8; border-radius: 50%; width: 60px; height: 60px; display: flex; align-items: center; justify-content: center; color: white; font-size: 28px; cursor: pointer; box-shadow: 0 4px 10px rgba(0,0,0,0.3); z-index: 999; }
    .chat-window { position: fixed; bottom: 100px; right: 25px; width: 350px; background: white; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); padding: 15px; z-index: 1000; overflow-y: auto; max-height: 400px; scrollbar-width: none; }
    .chat-window::-webkit-scrollbar { display: none; }
    .bot-message { text-align: left; color: #222; background: #F1F1F1; padding: 8px 10px; border-radius: 10px; margin: 5px 0; display: inline-block; }
    </style>""", unsafe_allow_html=True)

    chat_button_clicked = st.button("🤖", key="chat_button", help="Chat with Water Buddy")
    if chat_button_clicked:
        st.session_state.show_chatbot = not st.session_state.show_chatbot

    if st.session_state.show_chatbot:
        with st.container():
            st.markdown("<div class='chat-window'>", unsafe_allow_html=True)
            st.markdown("<div style='text-align:center; color:#1A73E8; font-weight:600; font-size:18px;'>💬 Water Buddy <span style='font-size:14px; color:#555;'>— powered by Gemini</span></div>", unsafe_allow_html=True)

            for entry in st.session_state.chat_history:
                if entry["sender"] == "bot":
                    st.markdown(f"<div class='bot-message'>🤖 {entry['text']}</div>", unsafe_allow_html=True)

            user_msg = st.text_input("Type your message...", key="chat_input")
            if st.button("Send", key="send_btn"):
                if user_msg.strip():
                    try:
                        if model:
                            prompt = f"You are Water Buddy, a friendly AI hydration assistant. Respond conversationally.\nUser: {user_msg}"
                            response = model.generate_content(prompt)
                            reply = response.text.strip()
                        else:
                            reply = "⚠️ Chatbot not configured currently."
                    except Exception:
                        reply = "⚠️ Sorry, I’m having trouble connecting right now."

                    st.session_state.chat_history.append({"sender": "bot", "text": reply})
                    st.experimental_rerun()

# -------------------------------
# REPORT PAGE
# -------------------------------
elif st.session_state.page == "report":
    username = st.session_state.username
    if not st.session_state.logged_in:
        go_to_page("login")

    init_user_defaults(username)
    ensure_new_day_reset(username)

    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>📊 Hydration Report</h1>", unsafe_allow_html=True)
    st.write("---")

    completed_iso = user_data[username]["streak"].get("completed_days", [])
    completed_dates = []
    for s in completed_iso:
        try:
            d = datetime.strptime(s, "%Y-%m-%d").date()
            completed_dates.append(d)
        except Exception:
            continue

    today = date.today()
    daily_goal = user_data[username]["water_profile"].get("daily_goal", user_data[username].get("ai_water_goal", 2.5))

    # Today's progress gauge
    if today in completed_dates:
        today_pct = 100
    else:
        if st.session_state.total_intake:
            today_pct = min(round(st.session_state.total_intake / float(daily_goal) * 100), 100)
        else:
            today_pct = 0

    st.markdown("### Today's Progress")
    fig_daily = go.Figure(go.Indicator(
        mode="gauge+number",
        value=today_pct,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Today's Hydration", 'font': {'size': 18}},
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': "#1A73E8"},
            'steps': [
                {'range': [0, 50], 'color': "#FFD9D9"},
                {'range': [50, 75], 'color': "#FFF1B6"},
                {'range': [75, 100], 'color': "#D7EEFF"}
            ],
            'threshold': {
                'line': {'color': "#0B63C6", 'width': 6},
                'thickness': 0.75,
                'value': 100
            }
        }
    ))
    fig_daily.update_layout(height=300, margin=dict(l=20, r=20, t=30, b=20), paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_daily, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False})

    if today_pct >= 100:
        st.success("🏆 Goal achieved today! Fantastic work — keep the streak alive! 💧")
    elif today_pct >= 75:
        st.info(f"💦 You're {today_pct}% there — a little more and you hit the goal!")
    elif today_pct > 0:
        st.info(f"🙂 You've completed {today_pct}% of your goal today — keep sipping!")
    else:
        st.info("🎯 Not started yet — let's drink some water and get moving!")

    st.write("---")

    # Weekly Progress
    st.markdown("### Weekly Progress (Mon → Sun)")
    monday = today - timedelta(days=today.weekday())
    week_days = [monday + timedelta(days=i) for i in range(7)]
    labels = [d.strftime("%a\n%d %b") for d in week_days]

    pct_list = []
    status_list = []

    for d in week_days:
        d_str = str(d)
        if d > today:
            pct = 0
            status = "upcoming"
        else:
            if d in completed_dates:
                pct = 100
                status = "achieved"
            else:
                if d == today and st.session_state.total_intake:
                    pct = min(round(st.session_state.total_intake / float(daily_goal) * 100), 100)
                    if pct >= 100:
                        status = "achieved"
                    elif pct >= 75:
                        status = "almost"
                    elif pct > 0:
                        status = "partial"
                    else:
                        status = "missed"
                else:
                    pct = 0
                    status = "missed"
        pct_list.append(pct)
        status_list.append(status)

    def week_color_for_status(s):
        if s == "achieved":
            return "#1A73E8"
        if s == "almost":
            return "#FFD23F"
        if s == "partial":
            return "#FFD9A6"
        if s == "upcoming":
            return "rgba(255,255,255,0.06)"
        return "#FF6B6B"

    colors = [week_color_for_status(s) for s in status_list]
    df_week = pd.DataFrame({"label": labels, "pct": pct_list, "status": status_list})

    fig_week = go.Figure()
    fig_week.add_trace(go.Bar(
        x=df_week["label"],
        y=df_week["pct"],
        marker_color=colors,
        text=[f"{v}%" if v > 0 else "" for v in df_week["pct"]],
        textposition='outside',
        hovertemplate="%{x}<br>%{y}%<extra></extra>"
    ))
    fig_week.update_layout(yaxis={'title': 'Completion %', 'range': [0, 100]}, showlegend=False,
                            margin=dict(l=20, r=20, t=20, b=40), height=340,
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_week, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False})

    achieved_days = sum(1 for s, d in zip(status_list, week_days) if d <= today and s == "achieved")
    almost_days = sum(1 for s, d in zip(status_list, week_days) if d <= today and s == "almost")
    missed_days = sum(1 for s, d in zip(status_list, week_days) if d <= today and s == "missed")

    # Monthly stats
    year = today.year
    month = today.month
    days_in_month = calendar.monthrange(year, month)[1]
    month_dates = [date(year, month, d) for d in range(1, days_in_month + 1)]

    total_met = sum(1 for d in month_dates if (d in completed_dates) or (d == today and st.session_state.total_intake and st.session_state.total_intake >= float(daily_goal)))
    total_days = len(month_dates)

    if completed_dates:
        all_sorted = sorted(completed_dates)
        best_streak = 0
        current = 1
        for i in range(1, len(all_sorted)):
            if (all_sorted[i] - all_sorted[i-1]).days == 1:
                current += 1
            else:
                if current > best_streak:
                    best_streak = current
                current = 1
        if current > best_streak:
            best_streak = current
    else:
        best_streak = 0

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
# DAILY STREAK PAGE
# -------------------------------
elif st.session_state.page == "daily_streak":
    username = st.session_state.username
    if not st.session_state.logged_in:
        go_to_page("login")

    init_user_defaults(username)
    ensure_new_day_reset(username)

    today = date.today()
    year, month = today.year, today.month
    days_in_month = calendar.monthrange(year, month)[1]

    streak_info = user_data[username].get("streak", {"completed_days": [], "current_streak": 0})
    completed_iso = streak_info.get("completed_days", [])
    current_streak = streak_info.get("current_streak", 0)

    completed_dates = []
    for s in completed_iso:
        try:
            d = datetime.strptime(s, "%Y-%m-%d").date()
            completed_dates.append(d)
        except Exception:
            continue

    # Build star-grid styles and HTML (showing date numbers inside each star)
    star_css = """
    <style>
    .star-grid {
       display: grid;
       grid-template-columns: repeat(6, 1fr);
       gap: 14px;
       justify-items: center;
       align-items: center;
       padding: 6px 4%;
    }
    .star {
       width:42px;
       height:42px;
       display:flex;
       align-items:center;
       justify-content:center;
       font-size:16px;
       border-radius:6px;
       transition: transform .12s ease, box-shadow .12s ease, background-color .12s ease, filter .12s ease;
       cursor: pointer;
       user-select: none;
       text-decoration:none;
       line-height:1;
    }
    .star:hover { transform: translateY(-6px) scale(1.06); }
    .star.dim {
       background: rgba(255,255,255,0.03);
       color: #bdbdbd;
       box-shadow: none;
       filter: grayscale(10%);
    }
    .star.upcoming {
       background: rgba(255,255,255,0.02);
       color: #999;
       box-shadow: none;
       filter: grayscale(30%);
    }
    .star.achieved {
       background: radial-gradient(circle at 30% 20%, #fff6c2, #ffd85c 40%, #ffb400 100%);
       color: #4b2a00;
       box-shadow: 0 8px 22px rgba(255,176,0,0.42), 0 2px 6px rgba(0,0,0,0.18);
    }
    .star.small { width:38px; height:38px; font-size:14px; }
    @media(max-width:600px){
       .star-grid { grid-template-columns: repeat(4, 1fr); gap:10px; }
       .star { width:36px; height:36px; font-size:14px; }
    }
    </style>
    """

    # Generate stars HTML with date numbers and status classes
    stars_html = "<div class='star-grid'>"
    for d in range(1, days_in_month + 1):
        the_date = date(year, month, d)
        iso = the_date.strftime("%Y-%m-%d")
        if the_date > today:
            css_class = "upcoming small"
        else:
            css_class = "achieved small" if the_date in completed_dates else "dim small"
        href = f"?selected_day={iso}"
        stars_html += f"<a class='star {css_class}' href='{href}' title='Day {d}'>{d}</a>"
    stars_html += "</div>"

    st.markdown(star_css + stars_html, unsafe_allow_html=True)

    # If a day is selected via query param, show slide card details
    query_params = st.experimental_get_query_params()
    selected_day_param = query_params.get("selected_day", [None])[0]
    if selected_day_param:
        try:
            sel_date = datetime.strptime(selected_day_param, "%Y-%m-%d").date()
            sel_day_num = sel_date.day

            if sel_date > today:
                status_txt = "upcoming"
            else:
                status_txt = "achieved" if sel_date in completed_dates else "missed"

            card_html = "<div class='slide-card' style='position: fixed; left:50%; transform: translateX(-50%); bottom:18px; width:340px; max-width:92%; background:linear-gradient(180deg, rgba(255,255,255,0.98), rgba(250,250,250,0.98)); color:#111; border-radius:12px; box-shadow: 0 10px 30px rgba(0,0,0,0.35); padding:14px 16px; z-index:2000;'>"
            card_html += f"<h4 style='margin:0 0 6px 0; font-size:16px;'>Day {sel_day_num} — {sel_date.strftime('%b %d, %Y')}</h4>"

            if status_txt == "achieved":
                card_html += "<p style='margin:0; font-size:14px; color:#333;'>🎉 Goal completed on this day! Great job.</p>"
            elif status_txt == "upcoming":
                card_html += "<p style='margin:0; font-size:14px; color:#333;'>⏳ This day is upcoming — no data yet.</p>"
            else:
                card_html += "<p style='margin:0; font-size:14px; color:#333;'>💧 Goal missed on this day. Keep trying — tomorrow is new!</p>"

            card_html += "<div><span class='close-btn' style='display:inline-block; margin-top:10px; color:#1A73E8; text-decoration:none; font-weight:600; cursor:pointer;' onclick=\"history.replaceState(null, '', window.location.pathname);\">Close</span></div>"
            card_html += "</div>"

            js_hide_on_scroll = """
            <script>
            (function(){
                var hidden = false;
                window.addEventListener('scroll', function(){
                    if(window.location.search.indexOf('selected_day') !== -1 && !hidden){
                        history.replaceState(null, '', window.location.pathname);
                        hidden = true;
                    }
                }, {passive:true});
            })();
            </script>
            """

            st.markdown(card_html + js_hide_on_scroll, unsafe_allow_html=True)
        except Exception:
            pass

    st.write("---")

    completed_dates_in_month = sorted([d for d in completed_dates if d.year == year and d.month == month])
    completed_days_numbers = [d.day for d in completed_dates_in_month]
    last_completed_day_num = max(completed_days_numbers) if completed_days_numbers else None

    st.markdown(f"<h2 style='text-align:center; color:#1A73E8;'>🔥 Daily Streak: {current_streak} Days</h2>", unsafe_allow_html=True)
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

# -------------------------------
# End of App
# -------------------------------
