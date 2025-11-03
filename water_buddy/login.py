# app.py
# Full Streamlit Hydration App — corrected JS embedding and direct Gemini config
# Requirements:
# pip install streamlit pycountry google-generativeai python-dotenv pandas plotly

import os
import json
import re
import calendar
from datetime import date, datetime, timedelta

import streamlit as st
import pycountry
import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv

# Gemini client imported and configured exactly as your original code required
import google.generativeai as genai

# Load .env then configure Gemini using your exact variable name
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
# Create the model handle (same model id you used before)
model = genai.GenerativeModel("models/gemini-2.5-flash")

# ---------------------------
# Streamlit config
# ---------------------------
st.set_page_config(page_title="HP PARTNER", page_icon="💧", layout="centered")

# ---------------------------
# Files & ensure existence
# ---------------------------
CREDENTIALS_FILE = "users.json"
USER_DATA_FILE = "user_data.json"

for fpath in (CREDENTIALS_FILE, USER_DATA_FILE):
    if not os.path.exists(fpath):
        with open(fpath, "w") as f:
            json.dump({}, f)

with open(CREDENTIALS_FILE, "r") as f:
    try:
        users = json.load(f)
    except Exception:
        users = {}
with open(USER_DATA_FILE, "r") as f:
    try:
        user_data = json.load(f)
    except Exception:
        user_data = {}

# ---------------------------
# Session defaults
# ---------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "page" not in st.session_state:
    st.session_state.page = "login"
if "username" not in st.session_state:
    st.session_state.username = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "show_chatbot" not in st.session_state:
    st.session_state.show_chatbot = False

# ---------------------------
# Helpers
# ---------------------------
def save_user_data(data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4, sort_keys=True)

def save_users(creds):
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(creds, f, indent=4, sort_keys=True)

def today_iso():
    return date.today().isoformat()

def safe_genie(prompt: str) -> str:
    """Call Gemini model and return text. Since you insisted on direct use, this will call the model."""
    response = model.generate_content(prompt)
    return response.text.strip()

countries = [c.name for c in pycountry.countries]

# ---------------------------
# Common CSS (keeps original colors + gentle modern upgrades)
# ---------------------------
COMMON_CSS = """
<style>
/* keep original blue theme with subtle modern touches */
body { background: linear-gradient(180deg, #ffffff, #f7fbff); }

/* headings */
h1 { font-weight:700; }
.hint { color:#666; font-size:13px; }

.centered { text-align:center; }

/* bottle hint */
.pulse-hint {
  display:inline-block; padding:6px 10px;
  background: linear-gradient(90deg, rgba(26,115,232,0.06), rgba(26,115,232,0.02));
  border-radius:8px; color:#1A73E8; font-size:13px;
}

/* mascots, speech bubbles */
.mascot-wrap { display:flex; gap:12px; align-items:center; }
.mascot-svg { width:120px; height:120px; }
.mascot-small { width:72px; height:72px; }

.speech-bubble {
  background:#fff; border-radius:12px; padding:10px 12px;
  box-shadow:0 8px 26px rgba(0,0,0,0.08); font-size:14px; color:#222;
  max-width:320px; line-height:1.25;
}
.speech-cloud { position:relative; }
.speech-cloud:after {
  content:""; position:absolute; left:18px; bottom:-10px; width:0; height:0;
  border-top:10px solid #fff; border-left:8px solid transparent; border-right:8px solid transparent;
}

/* float animations (gentle) */
@keyframes floaty { 0%{transform:translateY(0);}50%{transform:translateY(-8px);}100%{transform:translateY(0);} }
@keyframes floaty-small { 0%{transform:translateY(0);}50%{transform:translateY(-6px);}100%{transform:translateY(0);} }

/* sparkle style */
.sparkle { position:absolute; width:8px; height:8px; border-radius:50%; background:rgba(255,255,255,0.95); box-shadow:0 0 8px rgba(255,255,255,0.95); opacity:0; }
.sparkle.ani { animation: sparkleA 0.95s ease-out forwards; }
@keyframes sparkleA { 0%{opacity:0; transform:scale(0.5);} 20%{opacity:1; transform:scale(1);} 100%{opacity:0; transform:scale(1.2) translateY(-16px);} }

/* locked box */
.locked-box { width:140px; height:120px; border-radius:12px; background:linear-gradient(180deg,#e9f5ff,#dff0ff); display:flex; align-items:center; justify-content:center; box-shadow:0 8px 30px rgba(10,40,80,0.06); margin:auto; }
.unlock-anim { animation: unlockGlow 1.1s ease-out forwards; }
@keyframes unlockGlow { 0%{transform:scale(0.96); box-shadow:0 6px 16px rgba(0,0,0,0.06);} 50%{transform:scale(1.06); box-shadow:0 20px 60px rgba(255,220,80,0.45);} 100%{transform:scale(1); box-shadow:0 8px 30px rgba(0,0,0,0.06);} }

/* medals */
.medal-area { text-align:center; margin-bottom:10px; }
.medal-container { display:flex; justify-content:center; gap:26px; align-items:center; margin-bottom:8px; }
.medal { width:96px; height:96px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:34px; position:relative; box-shadow:0 6px 18px rgba(0,0,0,0.12); }
.medal.locked { filter:grayscale(100%); opacity:0.6; background:linear-gradient(180deg,#666,#444); color:#ddd; }
.medal.bronze { background: linear-gradient(180deg,#d78a52,#a65f32); color:#fff; }
.medal.silver { background: linear-gradient(180deg,#e8e8e8,#bdbdbd); color:#333; }
.medal.gold { background: linear-gradient(180deg,#ffe75c,#f0b500); color:#3a2e00; }

/* shining rotation + pop animation */
.shine { position:absolute; width:140px; height:140px; left:50%; top:50%; transform:translate(-50%,-50%) rotate(0deg); border-radius:50%; opacity:0; mix-blend-mode:screen; pointer-events:none; }
.shine.rotate { animation: rotateShine 2.6s linear infinite; opacity:1; }
@keyframes rotateShine { 0%{transform:translate(-50%,-50%) rotate(0deg);} 100%{transform:translate(-50%,-50%) rotate(360deg);} }
@keyframes popFlash { 0%{transform:scale(0.9); filter:brightness(0.9);} 35%{transform:scale(1.35); filter:brightness(1.6);} 70%{transform:scale(1.08);} 100%{transform:scale(1);} }
.flash { animation: popFlash 1.2s cubic-bezier(.2,.9,.2,1) forwards; z-index:3; }

/* small responsive tweaks */
@media(max-width:720px) {
  .mascot-svg { width:84px; height:84px; }
  .mascot-small { width:56px; height:56px; }
  .medal { width:72px; height:72px; font-size:26px; }
}
</style>
"""

# ---------------------------
# Simple SVG mascots (inline)
# ---------------------------
def svg_login_mascot():
    return """
    <svg class="mascot-svg" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="lg1" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="#7fe7ff"/>
          <stop offset="90%" stop-color="#2fb8ff"/>
        </linearGradient>
      </defs>
      <path d="M100 10 C120 12,150 40,150 85 C150 130,120 160,100 165 C80 160,50 130,50 85 C50 40,80 12,100 10 Z" fill="url(#lg1)" stroke="#12304a" stroke-width="3"/>
      <circle cx="75" cy="85" r="6" fill="#fff" opacity="0.95"/><circle cx="125" cy="85" r="6" fill="#fff" opacity="0.95"/>
      <path d="M85 118 Q100 132 115 118" stroke="#3a1f2a" stroke-width="3" fill="none" stroke-linecap="round"/>
    </svg>
    """

def svg_home_mascot():
    return """
    <svg class="mascot-svg" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
      <defs><linearGradient id="hg1" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#a8eeff"/><stop offset="100%" stop-color="#2fb8ff"/></linearGradient></defs>
      <path d="M100 12 C130 40,160 70,150 115 C140 150,115 170,100 170 C85 170,60 150,50 115 C40 70,70 40,100 12 Z" fill="url(#hg1)" stroke="#0e3550" stroke-width="3"/>
      <circle cx="78" cy="90" r="7" fill="#fff"/><circle cx="122" cy="90" r="7" fill="#fff"/>
      <path d="M78 96 Q100 120 122 96" stroke="#08202a" stroke-width="3" fill="none" stroke-linecap="round"/>
    </svg>
    """

def svg_streak_mascot():
    return """
    <svg class="mascot-svg" viewBox="0 0 220 220" xmlns="http://www.w3.org/2000/svg">
      <defs><linearGradient id="sg1" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#8bebff"/><stop offset="100%" stop-color="#2fa8ff"/></linearGradient></defs>
      <path d="M110 18 C140 48,170 78,160 125 C150 160,125 186,110 186 C95 186,70 160,60 125 C50 78,80 48,110 18 Z" fill="url(#sg1)" stroke="#073446" stroke-width="3"/>
      <circle cx="92" cy="103" r="8" fill="#fff"/><circle cx="128" cy="103" r="8" fill="#fff"/>
      <path d="M88 125 Q110 145 132 125" stroke="#08202a" stroke-width="3" fill="none"/>
    </svg>
    """

def svg_professor_mascot():
    return """
    <svg class="mascot-svg" viewBox="0 0 220 220" xmlns="http://www.w3.org/2000/svg">
      <defs><linearGradient id="pg1" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#bff1ff"/><stop offset="100%" stop-color="#69d0ff"/></linearGradient></defs>
      <path d="M110 20 C140 52,170 86,160 130 C150 162,125 190,110 190 C95 190,70 162,60 130 C50 86,80 52,110 20 Z" fill="url(#pg1)" stroke="#0b3750" stroke-width="3"/>
      <rect x="78" y="85" width="12" height="6" fill="#12304a" />
      <rect x="130" y="85" width="12" height="6" fill="#12304a" />
      <circle cx="92" cy="100" r="6" fill="#fff"/><circle cx="128" cy="100" r="6" fill="#fff"/>
      <path d="M80 140 Q110 160 140 140" stroke="#083" stroke-width="3" fill="none"/>
    </svg>
    """

# ---------------------------
# Pages
# ---------------------------

# LOGIN PAGE
if st.session_state.page == "login":
    st.markdown(COMMON_CSS, unsafe_allow_html=True)
    st.markdown("<h1 class='centered' style='color:#1A73E8;'>💧 HP PARTNER</h1>", unsafe_allow_html=True)
    st.markdown("<h4 class='centered' style='color:#333; margin-top:-10px;'>Login or Sign Up to Continue</h4>", unsafe_allow_html=True)

    col1, col2 = st.columns([1,1])
    with col1:
        login_msg = "💧 Please enter your username and password. If not, create a new account and sign in again!"
        masc_html = f"""
        <div style="display:flex; gap:12px; align-items:center;">
          <div style="animation:floaty 3.6s ease-in-out infinite;">{svg_login_mascot()}</div>
          <div class="speech-cloud" style="animation:floaty-small 3s ease-in-out infinite;">
            <div class="speech-bubble">{login_msg}</div>
          </div>
        </div>
        <div style="position:relative; width:120px; height:22px;">
          <div class="sparkle" style="position:absolute; left:12px; top:2px;"></div>
          <div class="sparkle" style="position:absolute; left:78px; top:4px;"></div>
        </div>
        """
        st.markdown(masc_html, unsafe_allow_html=True)

        # embed JS for sparkles properly via st.markdown
        st.markdown("""
        <script>
        (function(){
            var nodes = document.querySelectorAll('.sparkle');
            function flick() {
                var n = nodes[Math.floor(Math.random()*nodes.length)];
                if(!n) return;
                n.classList.remove('ani');
                void n.offsetWidth;
                n.classList.add('ani');
            }
            setInterval(flick, 1700);
        })();
        </script>
        """, unsafe_allow_html=True)

    with col2:
        option = st.radio("Choose Option", ["Login", "Sign Up"])
        username = st.text_input("Enter Username", key="username_input")
        password = st.text_input("Enter Password", type="password", key="password_input")
        if st.button("Submit"):
            if option == "Sign Up":
                if username in users:
                    st.error("❌ Username already exists.")
                elif username == "" or password == "":
                    st.error("❌ Username and password cannot be empty.")
                else:
                    users[username] = password
                    save_users(users)
                    # default user data
                    user_data[username] = {
                        "profile": {},
                        "ai_water_goal": 2.5,
                        "water_profile": {"daily_goal": 2.5, "frequency":"30 minutes"},
                        "streak": {"completed_days": [], "current_streak": 0},
                        "today_progress": {"date": today_iso(), "liters": 0.0},
                        "unlocked_medals": {"bronze": False, "silver": False, "gold": False},
                        "seen_unlocks": {"bronze": False, "silver": False, "gold": False},
                        "seen_funfact_dates": []
                    }
                    save_user_data(user_data)
                    st.success("✅ Account created successfully! Please login.")
            else:
                if username in users and users[username] == password:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    # ensure defaults
                    user_data.setdefault(username, {})
                    user_data[username].setdefault("profile", {})
                    user_data[username].setdefault("ai_water_goal", 2.5)
                    user_data[username].setdefault("water_profile", {"daily_goal": 2.5, "frequency":"30 minutes"})
                    user_data[username].setdefault("streak", {"completed_days": [], "current_streak": 0})
                    user_data[username].setdefault("today_progress", {"date": today_iso(), "liters": 0.0})
                    user_data[username].setdefault("unlocked_medals", {"bronze": False, "silver": False, "gold": False})
                    user_data[username].setdefault("seen_unlocks", {"bronze": False, "silver": False, "gold": False})
                    user_data[username].setdefault("seen_funfact_dates", [])
                    save_user_data(user_data)
                    if user_data[username]["profile"]:
                        st.session_state.page = "home"
                        st.experimental_rerun()
                    else:
                        st.session_state.page = "settings"
                        st.experimental_rerun()
                else:
                    st.error("❌ Invalid username or password.")

# SETTINGS PAGE
elif st.session_state.page == "settings":
    if not st.session_state.logged_in:
        st.session_state.page = "login"
        st.experimental_rerun()
    username = st.session_state.username
    saved = user_data.get(username, {}).get("profile", {})

    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 Personal Settings</h1>", unsafe_allow_html=True)
    name = st.text_input("Name", value=saved.get("Name", username))
    age = st.text_input("Age", value=saved.get("Age", ""))
    country = st.selectbox("Country", countries, index=countries.index(saved.get("Country", "India")) if saved.get("Country") else countries.index("India"))
    language = st.text_input("Language", value=saved.get("Language", ""))

    st.write("---")
    height_unit = st.radio("Height Unit", ["cm", "feet"], horizontal=True)
    height = st.number_input(f"Height ({height_unit})", value=float(saved.get("Height", "0").split()[0]) if "Height" in saved else 0.0)
    weight_unit = st.radio("Weight Unit", ["kg", "lbs"], horizontal=True)
    weight = st.number_input(f"Weight ({weight_unit})", value=float(saved.get("Weight", "0").split()[0]) if "Weight" in saved else 0.0)

    def calc_bmi(w, h, wunit, hunit):
        if hunit == "feet":
            hm = h * 0.3048
        else:
            hm = h / 100.0
        if wunit == "lbs":
            wk = w * 0.453592
        else:
            wk = w
        return round(wk / (hm**2), 2) if hm > 0 else 0

    bmi = calc_bmi(weight, height, weight_unit, height_unit)
    st.write(f"**Your BMI is:** {bmi}")

    health_condition = st.radio("Health condition", ["Excellent", "Fair", "Poor"], horizontal=True, index=["Excellent","Fair","Poor"].index(saved.get("Health Condition","Excellent")))
    health_problems = st.text_area("Health problems", value=saved.get("Health Problems",""))

    st.write("---")
    old_profile = user_data.get(username, {}).get("profile", {})
    new_profile = {"Name": name, "Age": age, "Country": country, "Language": language, "Height": f"{height} {height_unit}", "Weight": f"{weight} {weight_unit}", "BMI": bmi, "Health Condition": health_condition, "Health Problems": health_problems}

    if st.button("Save & Continue ➡️"):
        recalc = new_profile != old_profile
        if recalc:
            with st.spinner("🤖 Water Buddy is calculating your ideal water intake..."):
                prompt = f"""
                You are Water Buddy. Based on user info, suggest daily water intake in liters as a single numeric value.
                Age: {age}
                Height: {height} {height_unit}
                Weight: {weight} {weight_unit}
                BMI: {bmi}
                Health Condition: {health_condition}
                Health Problems: {health_problems if health_problems else 'None'}
                """
                # direct Gemini call
                try:
                    r = model.generate_content(prompt)
                    txt = r.text.strip()
                    m = re.search(r"(\d+(?:\.\d+)?)", txt)
                    if m:
                        suggested = float(m.group(1))
                    else:
                        suggested = 2.5
                except Exception:
                    # if Gemini call errors, default to 2.5 but don't skip call attempt
                    suggested = 2.5
        else:
            suggested = user_data.get(username, {}).get("ai_water_goal", 2.5)

        user_data[username] = user_data.get(username, {})
        user_data[username]["profile"] = new_profile
        user_data[username]["ai_water_goal"] = round(suggested, 2)
        user_data[username].setdefault("water_profile", {"daily_goal": suggested, "frequency":"30 minutes"})
        user_data[username].setdefault("streak", {"completed_days": [], "current_streak": 0})
        user_data[username].setdefault("today_progress", {"date": today_iso(), "liters": 0.0})
        save_user_data(user_data)
        st.success(f"✅ Profile saved! Water Buddy suggests {suggested:.2f} L/day 💧")
        st.experimental_rerun()

# WATER PROFILE
elif st.session_state.page == "water_profile":
    if not st.session_state.logged_in:
        st.session_state.page = "login"
        st.experimental_rerun()
    username = st.session_state.username
    saved = user_data.get(username, {}).get("water_profile", {})
    ai_goal = user_data.get(username, {}).get("ai_water_goal", 2.5)

    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 Water Intake</h1>", unsafe_allow_html=True)
    st.success(f"Your ideal daily water intake is **{ai_goal} L/day**")

    daily_goal = st.slider("Set your daily water goal (L):", 0.5, 10.0, float(ai_goal), 0.1)
    freq_opts = [f"{i} minutes" for i in range(5,185,5)]
    freq = st.selectbox("🔔 Reminder Frequency:", freq_opts, index=freq_opts.index(saved.get("frequency","30 minutes")))

    if st.button("💾 Save & Continue ➡️"):
        user_data[username]["water_profile"] = {"daily_goal": daily_goal, "frequency": freq}
        save_user_data(user_data)
        st.success("✅ Saved!")
        st.experimental_rerun()

# HOME PAGE
elif st.session_state.page == "home":
    if not st.session_state.logged_in:
        st.session_state.page = "login"
        st.experimental_rerun()
    username = st.session_state.username

    # ensure structures
    user_data.setdefault(username, {})
    user_data[username].setdefault("water_profile", {"daily_goal": user_data.get(username, {}).get("ai_water_goal",2.5), "frequency":"30 minutes"})
    user_data[username].setdefault("today_progress", {"date": today_iso(), "liters": 0.0})
    user_data[username].setdefault("unlocked_medals", {"bronze": False, "silver": False, "gold": False})
    user_data[username].setdefault("seen_unlocks", {"bronze": False, "silver": False, "gold": False})
    user_data[username].setdefault("seen_funfact_dates", [])

    # reset daily progress automatically
    if user_data[username]["today_progress"].get("date") != today_iso():
        user_data[username]["today_progress"] = {"date": today_iso(), "liters": 0.0}
        save_user_data(user_data)

    daily_goal = user_data[username]["water_profile"].get("daily_goal", 2.5)
    liters = user_data[username]["today_progress"].get("liters", 0.0)
    fill_percent = min(liters / daily_goal, 1.0) if daily_goal > 0 else 0.0

    st.markdown(COMMON_CSS, unsafe_allow_html=True)
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>💧 HP PARTNER</h1>", unsafe_allow_html=True)

    # layout: bottle left, mascots & box right
    colL, colR = st.columns([1,1])
    with colL:
        bottle_html = f"""
        <div style="text-align:center;">
          <div style="width:150px; height:360px; border:3px solid #1A73E8; border-radius:20px; margin:auto; overflow:hidden;
                      background: linear-gradient(to top, #1A73E8 {fill_percent*100}%, #E9F6FF {fill_percent*100}%);
                      transition: background 600ms ease;">
            <div style="position:relative; bottom:12px; width:100%; text-align:center; color:#fff; font-weight:700; font-size:16px;">
               {liters:.2f} L / {daily_goal} L
            </div>
          </div>
          <div style="height:12px;"></div>
          <div class="pulse-hint">⚠️ Use a calibrated water bottle for accurate tracking.</div>
        </div>
        """
        st.markdown(bottle_html, unsafe_allow_html=True)

        st.write("---")
        with st.form("add_water", clear_on_submit=True):
            water_input = st.text_input("Enter water amount (in ml):", key="home_ml")
            submitted = st.form_submit_button("➕ Add Water")
            if submitted:
                val = re.sub("[^0-9.]", "", water_input).strip()
                if val:
                    try:
                        ml = float(val)
                        liters_add = ml / 1000.0
                        if user_data[username]["today_progress"].get("date") != today_iso():
                            user_data[username]["today_progress"] = {"date": today_iso(), "liters": 0.0}
                        user_data[username]["today_progress"]["liters"] += liters_add
                        save_user_data(user_data)
                        st.success(f"✅ Added {int(ml)} ml")
                        # if goal just met, update streak and medals
                        t_lit = user_data[username]["today_progress"]["liters"]
                        if t_lit >= daily_goal:
                            streak = user_data[username].setdefault("streak", {"completed_days": [], "current_streak": 0})
                            if today_iso() not in streak["completed_days"]:
                                streak["completed_days"].append(today_iso())
                                streak["completed_days"] = sorted(list(set(streak["completed_days"])))
                                # recalc streak
                                cd = sorted([datetime.strptime(d, "%Y-%m-%d").date() for d in streak["completed_days"]])
                                cur = 0; cursor = date.today()
                                while True:
                                    if cursor in cd:
                                        cur += 1
                                        cursor = cursor - timedelta(days=1)
                                    else:
                                        break
                                streak["current_streak"] = cur
                                user_data[username]["streak"] = streak
                                # unlock medals persistently
                                um = user_data[username].setdefault("unlocked_medals", {"bronze": False, "silver": False, "gold": False})
                                if cur >= 7: um["bronze"] = True
                                if cur >= 18: um["silver"] = True
                                if cur >= 25: um["gold"] = True
                                user_data[username]["unlocked_medals"] = um
                                save_user_data(user_data)
                        st.experimental_rerun()
                    except Exception:
                        st.error("❌ Please enter a valid number like 700, 700ml, or 700 ml.")
                else:
                    st.error("❌ Please enter a valid number like 700, 700ml, or 700 ml.")

    with colR:
        # Home mascot + daily greeting (Gemini)
        if user_data[username].get("last_greeting_date") != today_iso():
            prompt = f"Write a short friendly hydration greeting for a user named {username}. One sentence starting with an emoji."
            greeting = safe_genie(prompt)
            user_data[username]["last_greeting_date"] = today_iso()
            user_data[username]["greeting_text"] = greeting
            save_user_data(user_data)
        greeting_text = user_data[username].get("greeting_text", f"🌞 Hello {username}! Stay hydrated 💧")

        greeting_html = f"""
        <div style="display:flex; gap:10px; align-items:center;">
          <div style="animation:floaty 3.2s ease-in-out infinite;">{svg_home_mascot()}</div>
          <div class="speech-cloud" style="animation:floaty-small 3.2s ease-in-out infinite;">
            <div class="speech-bubble">{greeting_text}</div>
          </div>
        </div>
        """
        st.markdown(greeting_html, unsafe_allow_html=True)

        # Locked box + professor fun fact logic
        box_locked = user_data[username]["today_progress"].get("liters", 0.0) < daily_goal
        # If unlocked and not yet shown today, fetch funfact
        if not box_locked and today_iso() not in user_data[username].get("seen_funfact_dates", []):
            prompt = "Give one short, interesting fun fact about water (one or two sentences)."
            fact = safe_genie(prompt)
            user_data[username].setdefault("funfacts", {})[today_iso()] = fact
            user_data[username].setdefault("seen_funfact_dates", []).append(today_iso())
            save_user_data(user_data)
        if box_locked:
            box_html = """
            <div style="text-align:center; margin-top:18px;">
              <div class="locked-box" id="locked_box">
                <div class="lock">🔒</div>
              </div>
              <div style="margin-top:8px; text-align:center; color:#444;">🔒 Reach your daily goal to unlock the fun fact about water</div>
            </div>
            """
            st.markdown(box_html, unsafe_allow_html=True)
        else:
            fact_text = user_data[username].get("funfacts", {}).get(today_iso(), "💡 Fun fact: Water is essential for life.")
            box_html = f"""
            <div style="text-align:center; margin-top:18px;">
              <div class="locked-box unlock-anim" id="unlocked_box">
                 <div style="display:flex; flex-direction:column; align-items:center;">
                    {svg_professor_mascot()}
                    <div style="font-weight:600; color:#0b63c6;">Professor Droplet</div>
                 </div>
              </div>
              <div style="margin-top:10px; max-width:320px; margin-left:auto;margin-right:auto;">
                 <div class="speech-cloud"><div class="speech-bubble">{fact_text}</div></div>
              </div>
            </div>
            """
            st.markdown(box_html, unsafe_allow_html=True)

    st.write("---")
    st.markdown(f"### Today's intake: **{user_data[username]['today_progress'].get('liters',0.0):.2f} L**")
    st.write("---")

    # nav
    a,b,c,d,e = st.columns(5)
    with a:
        if st.button("👤 Personal Settings"): st.session_state.page="settings"; st.experimental_rerun()
    with b:
        if st.button("🚰 Water Intake"): st.session_state.page="water_profile"; st.experimental_rerun()
    with c:
        if st.button("📈 Report"): st.session_state.page="report"; st.experimental_rerun()
    with d:
        if st.button("🔥 Daily Streak"): st.session_state.page="daily_streak"; st.experimental_rerun()
    with e:
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.page = "login"
            st.experimental_rerun()

# REPORT PAGE
elif st.session_state.page == "report":
    if not st.session_state.logged_in:
        st.session_state.page = "login"
        st.experimental_rerun()
    username = st.session_state.username
    user_data.setdefault(username, {})
    user_data[username].setdefault("streak", {"completed_days": [], "current_streak": 0})
    user_data[username].setdefault("water_profile", {"daily_goal": user_data.get(username, {}).get("ai_water_goal",2.5), "frequency":"30 minutes"})
    save_user_data(user_data)

    completed_iso = user_data[username]["streak"].get("completed_days", [])
    completed_dates = []
    for s in completed_iso:
        try:
            completed_dates.append(datetime.strptime(s, "%Y-%m-%d").date())
        except Exception:
            continue

    today = date.today()
    daily_goal = user_data[username]["water_profile"].get("daily_goal", user_data[username].get("ai_water_goal",2.5))

    tprog = user_data[username].get("today_progress", {})
    liters_today = tprog.get("liters", 0.0) if tprog.get("date") == today_iso() else 0.0
    today_pct = min(round(liters_today/daily_goal*100), 100) if liters_today else (100 if today in completed_dates else 0)

    st.markdown(COMMON_CSS, unsafe_allow_html=True)
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>📊 Hydration Report</h1>", unsafe_allow_html=True)
    st.write("---")

    st.markdown("### Today's Progress")
    fig_daily = go.Figure(go.Indicator(
        mode="gauge+number",
        value=today_pct,
        domain={'x':[0,1],'y':[0,1]},
        title={'text':"Today's Hydration"},
        gauge={'axis':{'range':[0,100]}, 'bar':{'color':"#1A73E8"}}
    ))
    fig_daily.update_layout(height=300, margin=dict(l=20,r=20,t=30,b=20), paper_bgcolor="rgba(0,0,0,0)")
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
    st.markdown("### Weekly Progress (Mon → Sun)")
    monday = today - timedelta(days=today.weekday())
    week_days = [monday + timedelta(days=i) for i in range(7)]
    labels = [d.strftime("%a\n%d %b") for d in week_days]

    pct_list = []
    status_list = []
    for d in week_days:
        if d > today:
            pct = 0; status = "upcoming"
        else:
            if d in completed_dates:
                pct = 100; status = "achieved"
            else:
                if d == today:
                    pct = min(round(liters_today/daily_goal*100),100) if liters_today else 0
                    if pct >= 100: status = "achieved"
                    elif pct >= 75: status = "almost"
                    elif pct > 0: status = "partial"
                    else: status = "missed"
                else:
                    pct = 0; status = "missed"
        pct_list.append(pct); status_list.append(status)

    def week_color_for_status(s):
        if s=="achieved": return "#1A73E8"
        if s=="almost": return "#FFD23F"
        if s=="partial": return "#FFD9A6"
        if s=="upcoming": return "rgba(255,255,255,0.06)"
        return "#FF6B6B"
    colors = [week_color_for_status(s) for s in status_list]
    df_week = pd.DataFrame({"label": labels, "pct": pct_list, "status": status_list})

    fig_week = go.Figure()
    fig_week.add_trace(go.Bar(x=df_week["label"], y=df_week["pct"], marker_color=colors,
                              text=[f"{v}%" if v>0 else "" for v in df_week["pct"]],
                              textposition='outside'))
    fig_week.update_layout(yaxis={'title':'Completion %','range':[0,100]}, showlegend=False, margin=dict(l=20,r=20,t=20,b=40), height=340, paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_week, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': True})

    # permanent note below graph
    st.markdown("<div style='margin-top:8px; color:#666; font-style:italic;'>💡 Double-click on the graph to zoom out.</div>", unsafe_allow_html=True)

    st.write("---")
    c1,c2,c3,c4,c5 = st.columns(5)
    with c1:
        if st.button("🏠 Home"): st.session_state.page="home"; st.experimental_rerun()
    with c2:
        if st.button("👤 Personal Settings"): st.session_state.page="settings"; st.experimental_rerun()
    with c3:
        if st.button("🚰 Water Intake"): st.session_state.page="water_profile"; st.experimental_rerun()
    with c4:
        st.info("You're on Report")
    with c5:
        if st.button("🔥 Daily Streak"): st.session_state.page="daily_streak"; st.experimental_rerun()

# DAILY STREAK PAGE
elif st.session_state.page == "daily_streak":
    if not st.session_state.logged_in:
        st.session_state.page = "login"
        st.experimental_rerun()
    username = st.session_state.username
    user_data.setdefault(username, {})
    user_data[username].setdefault("streak", {"completed_days": [], "current_streak": 0})
    streak_info = user_data[username]["streak"]
    completed_iso = streak_info.get("completed_days", [])
    current_streak = streak_info.get("current_streak", 0)

    completed_dates = []
    for s in completed_iso:
        try:
            completed_dates.append(datetime.strptime(s, "%Y-%m-%d").date())
        except Exception:
            continue

    st.markdown(COMMON_CSS, unsafe_allow_html=True)
    st.markdown("<h1 style='text-align:center; color:#1A73E8;'>🔥 Daily Streak</h1>", unsafe_allow_html=True)

    # thresholds
    bronze_th, silver_th, gold_th = 7, 18, 25
    bronze_unlocked = current_streak >= bronze_th
    silver_unlocked = current_streak >= silver_th
    gold_unlocked = current_streak >= gold_th

    # flash only once per medal unlock (persisted)
    seen = user_data[username].setdefault("seen_unlocks", {"bronze":False,"silver":False,"gold":False})
    flash_b = flash_s = flash_g = False
    if bronze_unlocked and not seen.get("bronze"):
        flash_b = True; seen["bronze"] = True
    if silver_unlocked and not seen.get("silver"):
        flash_s = True; seen["silver"] = True
    if gold_unlocked and not seen.get("gold"):
        flash_g = True; seen["gold"] = True
    user_data[username]["seen_unlocks"] = seen
    save_user_data(user_data)

    medals_html = f"""
    <div class="medal-area">
      <div style="font-weight:700; color:#1A73E8; font-size:18px; margin-bottom:6px;">🏅 Streak Medals</div>
      <div class="medal-container">
        <div id="medal_bronze" class="medal {'bronze' if bronze_unlocked else 'locked'} {'flash' if flash_b else ''}" data-flash="{str(flash_b).lower()}">
          <div class="shine {'rotate' if bronze_unlocked else ''}" style="color:rgba(210,140,90,0.95);"></div>
          <div style="position:relative; z-index:3;">🥉</div>
          <div id="spark_bronze" style="position:absolute; inset:0;"></div>
        </div>
        <div id="medal_silver" class="medal {'silver' if silver_unlocked else 'locked'} {'flash' if flash_s else ''}" data-flash="{str(flash_s).lower()}">
          <div class="shine {'rotate' if silver_unlocked else ''}" style="color:rgba(220,220,220,0.95);"></div>
          <div style="position:relative; z-index:3;">🥈</div>
          <div id="spark_silver" style="position:absolute; inset:0;"></div>
        </div>
        <div id="medal_gold" class="medal {'gold' if gold_unlocked else 'locked'} {'flash' if flash_g else ''}" data-flash="{str(flash_g).lower()}">
          <div class="shine {'rotate' if gold_unlocked else ''}" style="color:rgba(255,220,100,0.95);"></div>
          <div style="position:relative; z-index:3;">🥇</div>
          <div id="spark_gold" style="position:absolute; inset:0;"></div>
        </div>
      </div>
    </div>
    """
    st.markdown(medals_html, unsafe_allow_html=True)

    # motivational mascot + message (Gemini)
    if user_data[username].get("last_motiv_date") != today_iso():
        prompt = "Write a short, punchy motivational message (one sentence) about staying consistent with hydration."
        motiv = safe_genie(prompt)
        user_data[username]["last_motiv_date"] = today_iso()
        user_data[username]["last_motiv_text"] = motiv
        save_user_data(user_data)
    motiv_text = user_data[username].get("last_motiv_text", "Keep going — every sip brings you closer to your goal!")

    masc_html = f"""
    <div style="display:flex; justify-content:center; gap:10px; align-items:center; margin-top:8px;">
      <div style="animation:floaty 2.8s ease-in-out infinite;">{svg_streak_mascot()}</div>
      <div class="speech-cloud"><div class="speech-bubble">{motiv_text}</div></div>
    </div>
    """
    st.markdown(masc_html, unsafe_allow_html=True)

    # JS: generate sparkles & play WebAudio "ta-da" synth (no files). Embedded safely.
    st.markdown("""
    <script>
    (function(){
      function playTaDa() {
        try {
          var ctx = new (window.AudioContext || window.webkitAudioContext)();
          var now = ctx.currentTime;
          var o1 = ctx.createOscillator(); var g1 = ctx.createGain();
          o1.type='sawtooth'; o1.frequency.setValueAtTime(880, now);
          g1.gain.setValueAtTime(0, now); g1.gain.linearRampToValueAtTime(0.22, now+0.01); g1.gain.exponentialRampToValueAtTime(0.0001, now+0.55);
          o1.connect(g1); g1.connect(ctx.destination); o1.start(now); o1.stop(now+0.55);
          var o2 = ctx.createOscillator(); var g2 = ctx.createGain();
          o2.type='triangle'; o2.frequency.setValueAtTime(1320, now+0.06);
          g2.gain.setValueAtTime(0, now+0.06); g2.gain.linearRampToValueAtTime(0.12, now+0.08); g2.gain.exponentialRampToValueAtTime(0.0001, now+0.56);
          o2.connect(g2); g2.connect(ctx.destination); o2.start(now+0.06); o2.stop(now+0.56);
        } catch(e) { console.warn('Audio failed', e); }
      }
      function burstSparks(containerId) {
        var cont = document.getElementById(containerId);
        if(!cont) return;
        cont.innerHTML = '';
        var cnt = 12;
        for(var i=0;i<cnt;i++) {
          var s = document.createElement('div');
          s.style.position='absolute';
          s.style.width = (5+Math.random()*8)+'px';
          s.style.height = s.style.width;
          s.style.borderRadius='50%';
          s.style.left = (40 + Math.random()*20) + '%';
          s.style.top = (40 + Math.random()*20) + '%';
          s.style.background = 'white';
          s.style.boxShadow = '0 0 8px rgba(255,255,255,0.95)';
          s.style.opacity = '0';
          cont.appendChild(s);
          (function(el){ setTimeout(function(){ el.style.transition='transform 900ms ease-out, opacity 900ms ease-out'; var ang=Math.random()*Math.PI*2; var dist=30+Math.random()*60; el.style.transform='translate('+ (Math.cos(ang)*dist) +'px,'+ (Math.sin(ang)*dist) +'px) scale(1.1)'; el.style.opacity='1'; setTimeout(function(){ el.style.opacity='0'; },750); }, Math.random()*80); })(s);
        }
      }
      try {
        var b = document.getElementById('medal_bronze'); if(b && b.dataset.flash==='true'){ setTimeout(function(){ burstSparks('spark_bronze'); playTaDa(); },220); }
        var s = document.getElementById('medal_silver'); if(s && s.dataset.flash==='true'){ setTimeout(function(){ burstSparks('spark_silver'); playTaDa(); },240); }
        var g = document.getElementById('medal_gold'); if(g && g.dataset.flash==='true'){ setTimeout(function(){ burstSparks('spark_gold'); playTaDa(); },260); }
      } catch(e) { console.warn('medal script err', e); }
    })();
    </script>
    """, unsafe_allow_html=True)

    st.markdown(f"<h2 style='text-align:center; color:#1A73E8;'>🔥 Daily Streak: {current_streak} Days</h2>", unsafe_allow_html=True)
    st.write("---")
    c1,c2,c3,c4,c5 = st.columns(5)
    with c1:
        if st.button("🏠 Home"): st.session_state.page="home"; st.experimental_rerun()
    with c2:
        if st.button("👤 Personal Settings"): st.session_state.page="settings"; st.experimental_rerun()
    with c3:
        if st.button("🚰 Water Intake"): st.session_state.page="water_profile"; st.experimental_rerun()
    with c4:
        if st.button("📈 Report"): st.session_state.page="report"; st.experimental_rerun()
    with c5:
        st.info("You're on Daily Streak")

# End of app
