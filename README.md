**WaterBuddy – Smart Hydration Web App (Streamlit + Firebase + AI + FCM Notifications)**

"A complete hydration tracking system built with Streamlit, Firebase, Gamification, AI (Gemini), and now Firebase Cloud Messaging (Push Notifications)"

**Table of Contents**

1. Overview
2. Problem Statement
3. Solution
4. Objectives
5. Features
6. Technology Stack
7. Modules and Libraries used
7. System Architecture
8. Project Structure
10. Detailed Feature Explanation
11. Water Recommendation Logic
12. Pages Explanation
13. Database Structure
15. Future Enhancements
16. Output Screenshots
17. Conclusion

🔷 **1. Overview**

1. WaterBuddy is a smart hydration–tracking web application designed to help users monitor their daily water intake using Streamlit, Firebase, AI (Gemini), Gamification, and FCM Notifications.

2. The system automatically calculates recommended daily intake, tracks progress, provides weekly reports, and motivates users with streaks, medals, notifications, and animations.

🔷 **2. Problem Statement**

1. Most individuals struggle to drink sufficient water due to:
2. Lack of awareness
3. No continuous monitoring
4. Low motivation
5. No reminders
6. Therefore, a system is required that tracks, reminds, educates, and motivates users.

🔷 **3. Solution**

1. WaterBuddy addresses these challenges by:
2. Tracking daily water intake
3. Using AI to personalize daily goals
4. Providing weekly analytics
5. Including gamification rewards
6. Sending real-time hydration reminders using FCM Push Notifications
7. Storing all user data in Firebase

🔷 **4. Objectives**

1. Build healthy hydration habits
2. Provide personalized goals
3. Track daily, weekly & monthly progress
4. Motivate through gamification
5. Send hydration reminders via notifications
6. Offer clean, mobile-friendly UI
   
**🔷 6. Technology Stack
Frontend / Backend**

1. Python
2. Streamlit
3. Database
4. APIs
5. Google Gemini AI
6. Visualization
7. Plotly
8. Matplotlib
9. Storage
10.  Local JSON file and Sqlite

**🔷 7. Modules and Libraries used:**

**🔵 1. Streamlit**
import streamlit as st
from streamlit.components.v1 import html as st_html

Used for building the entire web UI, custom HTML components, animations, and pages.

**🔵 2. JSON & OS Handling**
import json
import os
from pathlib import Path

Used to store/load local water logs, handle file paths, load configuration files, and manage directories.

**🔵 3. Data Processing**
import pandas as pd

Used for weekly data grouping, data cleaning, tables, and calculations.

**🔵 4. Date & Time**
from datetime import datetime, date, timedelta, time as dtime
import calendar
import time
import pytz

Used for streaks, daily progress, reminders, date conversions, timezone handling, and weekly summaries.

**🔵 5. Environment Variables**
from dotenv import load_dotenv

Loads API keys (Gemini, Firebase) securely from .env.

**🔵 6. AI Model (Gemini AI)**
import google.generativeai as genai

Used for AI hydration recommendations, chatbot assistant, and suggestions.

**🔵 7. Country & Phone Validator**
import pycountry
import re

Used for validating inputs, filtering country lists, and regular-expression checks.

**🔵 8. Plotting & Visualizations**
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import numpy as np

Used for weekly charts, gauges, circular progress charts, and visual analytics.

**🔵 9. Database Handling**
import sqlite3

Used for temporary local storage or caching (if used in your build).

**🔵 10. URL & Requests**
from urllib.parse import quote
import requests

Used for external API calls, push notifications, audio file generation, and networking.

**🔵 11. Typing & Validation**
from typing import Dict, Any, Optional

Used for type annotations and clean function definitions.

**🔵 12. Text-to-Speech**
from gtts import gTTS
import base64

Used for generating AI mascot voice messages and embedding audio in Streamlit.

**🔷 7. System Architecture**
User
   ↓
Streamlit Frontend
   ↓
Sqlite and Json
   ↓
Gemini AI (Daily Goal Recommendation)
   ↓
Plotly / Matplotlib (Reports)
   ↓
Streamlit Notifications (Scheduled Reminders as per the time interval)

**🔷 8. Project Structure**
water_buddy/
│── login.py
│── data/
│      ├── user.json
│        ├── user_data.json
│── requirements.txt                  
│── assets/
│     ├── mascot1.png
│     ├── mascot2.png
│     ├── mascot3.png
│     ├── mascot9.png
│     ├── mascot4.png
│     ├── mascot5.jpg
│     ├── mascot6.jpg
│     ├── mascot7.png
└──   ├── mascot8.png

🔷 10. Detailed Feature Explanation:

🔷 11. Water Recommendation Logic:

🔷 12. Pages Explanation:

🔷 13. Database Structure:


🔷 13. Page-by-Page Explanation

1. Login page:

2. Personal settings page:

3. Water intake page:

4. Home page:

5. Daily streak page:

6. Report page:

7. Mini reflex game page:

🔷 16. Future Enhancements

Add:
1. Smart AI-based notification timing.
2. Push reminders based on body weight & weather.
3. Geolocation-based hydration alerts.
4. Use FireBase for data storage for permanant stroring and for notifications pop-ups even the app is closed or phone is off.

🔷 18. Conclusion

WaterBuddy successfully tracks hydration, motivates users with AI, medals, games, and streaks, and now includes real-time push notifications through streamlit for better user engagement.
