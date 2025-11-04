"""
HP PARTNER - Complete Streamlit app (single file)

Features:
- Local username/password login & signup (stored in users.json)
- Personal Settings (profile, BMI calc, AI water goal via Gemini if configured)
- Water Intake page (add ml amounts, update daily streak when goal met)
- Home page with water bottle visual and quick nav
- Report page: ONLY the star grid (dates inside stars, colored by achieved/missed/upcoming)
- Daily Streak page: star grid (same as Report) + current streak header and small slide-card when selecting a day
- Gemini-based chatbot popup (works if GOOGLE_API_KEY provided in Streamlit secrets or .env)
- All user data stored in user_data.json
Notes:
- Replace or supply GOOGLE_API_KEY in Streamlit secrets or .env to enable Gemini calls.
- Run with: streamlit run app.py
"""

import streamlit as st
import json
import os
import re
import pycountry
import calendar
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

# Try to import google generative AI (optional)
try:
    import google.generativeai as genai
except Exception:
    genai = None

# -------------------------------
# Config / API key
# -------------------------------
api_key = None
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    load_dotenv(silent=True)
    api_key = os.getenv("GOOGLE_API_KEY")

model = None
if genai and api_key:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("models/gemini-2.5-flash")
    except Exception:
        model = None

# -------------------------------
# Streamlit page config
# -------------------------------
st.set_page_config(page_title="HP PARTNER", page_icon="💧", layout="centered")

# -------------------------------
# Files
# -------------------------------
CREDENTIALS_FILE = "users.json"
USER_DATA_FILE = "user_data.json"

if os.path.exists(CREDENTIALS_FILE):
    try:
        with open(CREDENTIALS_FILE, "r") as f:
            users = json.load(f)
    except Exception:
        users = {}
else:
    users = {}

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

# -------------------------------
# Session state defaults
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
# Helpers: save/load
# -------------------------------
def save_user_data(data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4, sort_keys=True)

def save_users():
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(users, f, indent=4, sort_keys=True)

def go_to_page(page_name: str):
    st.session_state.page = page_name
    st.experimental_rerun()

# country list
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
                save_users()

                # initialize user_data entries
                user_data[username] = {}
                user_data[username]["profile"] = {}
                user_data[username]["ai_water_goal"] = 2.5
                user_data[username]["water_profile"] = {"daily_goal": 2.5, "frequency": "30 minutes"}
                user_data[username]["streak"] = {"completed_days": [], "current_streak": 0}
                save_user_data(user_data)

                st.success("✅ Account created successfully! Please login.")
        else:  # Login
            if username in users and users[username] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                if username in user_data and "profile" in user_data[username] and user_data[username]["profile"]:
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
    # default to India if saved not present
    default_country = saved.get("Country", "India") if saved.get("Country") else "India"
    country = st.selectbox("Country", countries, index=countries.index(default_country) if default_country in countries else 0)
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

    def calculate_bmi(weight_val, height_val, weight_unit_val, height_unit_val):
        if height_unit_val == "feet":
            height_m = height_val * 0.3048
        else:
            height_m = height_val / 100
        if weight_unit_val == "lbs":
            weight_kg = weight_val * 0.453592
        else:
            weight_kg = weight_val
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
                    if model:
                        response = model.generate_content(prompt)
                        text_output = response.text.strip()
                        match = re.search(r"(\d+(\.\d+)?)", text_output)
                        if match:
                            suggested_water_intake = float(match.group(1))
                        else:
                            raise ValueError("No numeric value found.")
                    else:
                        raise RuntimeError("Model not configured")
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
    # ensure default index exists
    default_freq = saved.get("frequency", "30 minutes")
    try:
        idx = frequency_options.index(default_freq)
    except Exception:
        idx = frequency_options.index("30 minutes")
    selected_frequency = st.selectbox("🔔 Reminder Frequency:", frequency_options, index=idx)

    if st.button("💾 Save & Continue ➡️"):
        user_data.setdefault(username, {})
        user_data[username]["water_profile"] = {"daily_goal": daily_goal, "frequency": selected_frequency}
        save_user_data(user_data)
        st.success("✅ Water profile saved successfully!")
        go_to_page("home")

# -------------------------------
# HOME PAGE
# -------------------------------
elif st.session_state.page == "home":
    username = st.session_state.username
    daily_goal = user_data.get(username, {}).get("water_profile", {}).get("daily_goal", user_data.get(username, {}).get("ai_water_goal", 2.5))

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

                # update streak if goal met
                username = st.session_state.username
                today_str = str(date.today())

                user_data.setdefault(username, {})
                user_data[username].setdefault("streak", {"completed_days": [], "current_streak": 0})
                user_data[username].setdefault("water_profile", {"daily_goal": 2.5, "frequency": "30 minutes"})

                user_streak = user_data[username]["streak"]
                daily_goal = user_data[username]["water_profile"].get("daily_goal", 2.5)

                if st.session_state.total_intake >= daily_goal:
                    if today_str not in user_streak.get("completed_days", []):
                        user_streak.setdefault("completed_days", []).append(today_str)
                        user_streak["completed_days"] = sorted(list(set(user_streak["completed_days"])))

                        # recalc current streak
                        completed_dates = sorted([datetime.strptime(d, "%Y-%m-%d").date() for d in user_streak["completed_days"]])

                        streak = 0
                        day_cursor = date.today()
                        while True:
                            if day_cursor in completed_dates:
                                streak += 1
                                day_cursor = day_cursor - timedelta(days=1)
                            else:
                                break

                        user_streak["current_streak"] = streak
                        user_data[username]["streak"] = user_streak
                        save_user_data(user_data)

                # refresh app state (keeps input cleared)
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
            go_to_page("login")

    # Chatbot floating button & window
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
                💬 Water Buddy <span style='font-size:14px; color:#555;'>— powered by Gemini</span>
            </div>
            """, unsafe_allow_html=True)

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

            st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------
# REPORT PAGE: ONLY STAR GRID (no heading/legend/stats)
# -------------------------------
elif st.session_state.page == "report":
    username = st.session_state.username

    # Ensure user data exists
    user_data.setdefault(username, {})
    user_data[username].setdefault("streak", {"completed_days": [], "current_streak": 0})
    user_data[username].setdefault("water_profile", {"daily_goal": user_data.get(username, {}).get("ai_water_goal", 2.5), "frequency": "30 minutes"})
    save_user_data(user_data)

    completed_iso = user_data[username]["streak"].get("completed_days", [])
    completed_dates = []
    for s in completed_iso:
        try:
            d = datetime.strptime(s, "%Y-%m-%d").date()
            completed_dates.append(d)
        except Exception:
            continue

    # Today's context
    today = date.today()

    # Build star grid (dates inside each star), colored by status
    year = today.year
    month = today.month
    days_in_month = calendar.monthrange(year, month)[1]

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

    stars_html = "<div class='star-grid'>"
    for d in range(1, days_in_month + 1):
        the_date = date(year, month, d)
        iso = the_date.strftime("%Y-%m-%d")
        if the_date > today:
            css_class = "upcoming small"
        else:
            css_class = "achieved small" if the_date in completed_dates else "dim small"
        # date number inside the star (clickable to set query param)
        href = f"?selected_day={iso}"
        stars_html += f"<a class='star {css_class}' href='{href}' title='Day {d}'>{d}</a>"
    stars_html += "</div>"

    st.markdown(star_css + stars_html, unsafe_allow_html=True)

    # Keep navigation buttons but remove any stats/legends
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
# DAILY STREAK PAGE: STAR GRID + CURRENT STREAK
# -------------------------------
elif st.session_state.page == "daily_streak":
    username = st.session_state.username
    today = date.today()
    year, month = today.year, today.month
    days_in_month = calendar.monthrange(year, month)[1]

    if username not in user_data:
        user_data[username] = {}
    user_data[username].setdefault("streak", {"completed_days": [], "current_streak": 0})
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

    # Build star-grid HTML (dates inside stars), no title / no legend
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
    .slide-card {
       position: fixed;
       left: 50%;
       transform: translateX(-50%);
       bottom: 18px;
       width: 340px;
       max-width: 92%;
       background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(250,250,250,0.98));
       color:#111;
       border-radius:12px;
       box-shadow: 0 10px 30px rgba(0,0,0,0.35);
       padding:14px 16px;
       z-index: 2000;
       animation: slideUp .36s ease;
    }
    @keyframes slideUp { from { transform: translateX(-50%) translateY(24px); opacity:0; } to { transform: translateX(-50%) translateY(0); opacity:1; } }
    .slide-card h4 { margin:0 0 6px 0; font-size:16px; }
    .slide-card p { margin:0; font-size:14px; color:#333; }
    .close-btn { display:inline-block; margin-top:10px; color:#1A73E8; text-decoration:none; font-weight:600; cursor:pointer; }
    @media(max-width:600px){
       .star-grid { grid-template-columns: repeat(4, 1fr); gap:10px; }
       .star { width:36px; height:36px; font-size:14px; }
       .slide-card { width:92%; bottom: 12px; }
    }
    </style>
    """

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

    # Day selected slide-card (same UX as Report but on Daily Streak)
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

            card_html = "<div class='slide-card'>"
            card_html += f"<h4>Day {sel_day_num} — {sel_date.strftime('%b %d, %Y')}</h4>"

            if status_txt == "achieved":
                card_html += "<p>🎉 Goal completed on this day! Great job.</p>"
            elif status_txt == "upcoming":
                card_html += "<p>⏳ This day is upcoming — no data yet.</p>"
            else:
                card_html += "<p>💧 Goal missed on this day. Keep trying — tomorrow is new!</p>"

            card_html += "<div><span class='close-btn' onclick=\"history.replaceState(null, '', window.location.pathname);\">Close</span></div>"
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
# End of flow - fallback
# -------------------------------
else:
    st.error("Unknown page. Resetting to login.")
    st.session_state.page = "login"
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.experimental_rerun()
