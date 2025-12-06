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
1. Age‐based goal input with AI auto‐suggested.
2. Standard daily target (plus option to adjust).
3. Custom water intake Button or field to
quickly log water intake .
4. Real‐time visual feedback (weekly progress
bar graph, Daily progress meter).
5. Motivational message with
mascot/character.
6. Reacting to progress milestones.
7. Reset button to clear data of same day daily
water intake (also auto reseting after each
day).
8. Compare the user current intake vs
standard target visually.
9. Daily hydration tips / reminders (streamlit
pop‐ups).
10. Mascot reacting to the water intake
11. Personalized Background setting of the app.
12. Has quiz page related to water.
13. Has a mini reflex game.
14 Easy sign up and login with just user name and
password and no need to google account.
15. Personal data are safe as everytime you open
your app it asks for password and username.
16. Has a personalized Water buddy Partner Chat
bot powered by Gemini 2.5 flash.
17. Mascots appear as per the time.
18. Daily streaks are marked for a whole month.
19. Has a voice that will motivate you.

🔷 11. Water Recommendation Logic:
1. Take the user’s personal data (weight, age, height, health problem etc.).
2. Send it as a prompt to Gemini 2.5 flash (an LLM).
3. Get back a daily water recommendation.
4. Automatically set the user’s daily water goal in the app.

🔷 12. Database Structure:


🔷 13. Page-by-Page Explanation

1. Login page:
The Login Page serves as the entry point to the Water Buddy web app. It features:
Sign Up & Login Options: Users can either create a new account or log in using their username and password.
Friendly Mascot: A cheerful mascot greets users every time they open the app, providing a warm and engaging welcome experience.
Intuitive Layout: The interface is simple and user-friendly, ensuring a smooth login experience for all users.

2. Personal settings page:
The Personal Setting Page allows users to input their essential personal information to tailor the Water Buddy experience:
Data Collection Fields:
Height (cm or ft)
Weight (kg or lbs)
Age
Country
Existing health conditions or problems
Save & Continue Button: After entering the information, users can save their data and proceed to the next step in the app.
Purpose: This information is used to personalize water intake recommendations and other health-related features in the app.

4. Water intake page:
The Water Intake Page helps users manage and track their daily hydration:
Automatic Daily Goal: Using the personal data provided, Gemini calculates and sets the user’s recommended daily water intake automatically.
Manual Adjustment: Users have the option to manually adjust their daily water goal if desired.
Water Drinking Reminders: Users can set custom reminders at intervals (e.g., every 30 minutes, 45 minutes) to stay hydrated throughout the day.
Save & Continue Button: After configuring their goals and reminders, users can save the settings and proceed to the next stage in the app.
Purpose: This page ensures users receive personalized hydration recommendations and helps them maintain consistent water intake habits.

5. Home page:
The Home Page serves as the main dashboard of the Water Buddy web app, providing quick access to essential features and a personalized interactive experience:
Navigation Hub: Users can easily navigate to all other pages from the home screen.

Interactive Water Bottle Animation:
A small animated water bottle visually fills up as the user logs their water intake.
Users can manually enter their water intake at any time.

Customization Options:
Users can change the background color to match their mood or preference.
User Account Controls:
A clear Logout button allows users to securely exit the app.

Game Page Access:
A dedicated button leads to fun hydration-themed games to encourage consistent water drinking habits.

Mascot with Dynamic Expressions:
The friendly Water Buddy mascot appears with different expressions based on the time of day.
It provides motivation, fun facts, reminders, and positive messages throughout the day.

Water Buddy Chatbot:

An integrated chat assistant powered by Gemini 2.5 Flash.
Users can ask questions, get hydration tips, receive guidance, and chat with the AI for support.

Overall Purpose:
This page brings together functionality, engagement, and personalization, making the user’s hydration journey enjoyable and motivating.

6. Daily streak page:
The Daily Streak Page helps users track their hydration consistency and stay motivated through visual progress tracking:
Monthly Progress Calendar:
Displays the current month in a calendar-style layout.
Each day highlights whether the daily water goal was completed.
Completed days glow in golden color, visually rewarding the user for staying on track.

Motivational Mascot:
A friendly mascot appears with encouraging messages to help maintain streaks and celebrate progress.

Page Navigation:
Includes easy access to navigate back to the Home Page or other sections of the app.

Purpose:
This page strengthens habit-building by providing a clear, visual record of the user’s commitment to their hydration goals.

7. Report page:
The Report Page provides detailed analytics to help users understand their hydration habits and overall progress:
Daily Progress Meter:
Shows how much water the user has consumed for the day compared to their daily goal.
Offers a quick visual snapshot of current hydration status.

Weekly Progress Graph:
A clear, easy-to-read graph displaying water intake trends over the past week.
Helps users identify patterns and stay consistent.

Percentage Circle:
A circular progress indicator showing the percentage of the daily goal completed.
Gives an instant overview of daily achievement.

Navigation Controls:
Allows users to seamlessly move to other pages such as Home, Streaks, or Settings.

Purpose:
This page helps users stay informed, motivated, and aware of their hydration performance through clean, visually appealing analytics.

8. Mini reflex game page:
The Mini Reflex Game Page offers a fun, fast-paced activity designed to engage users through a simple challenge with a deeper meaning:
Core Game Objective:
Players must “catch” 16 falling water droplets one by one without missing any, filling the virtual cup completely.
After the attempt, the game displays whether the player won or lost.

Manual Win/Loss Selection (Psychological Twist):
Instead of automatically validating performance, the game allows players to manually select “Win” or “Loss.”
This means the player could lie and claim victory for an easy reward.
However, the real purpose is to test honesty, self-discipline, and personal integrity in a low-risk environment.
It transforms the game into a small psychological experiment—“The coin isn’t the challenge… the choice is.”

Rewards System:
Winning earns the player a coin, which is automatically added to their cart.
Coins can be used to purchase various custom-designed cups available in the in-page shop.

Replay Option:
Players may replay the game anytime to challenge themselves again and earn more coins based on their honest choices.

Integrated Shop:
Within the same page, users can browse and buy unique cup designs using the coins they’ve collected.

Purpose:
This page blends simple gameplay with emotional and psychological depth, offering entertainment while subtly encouraging integrity and thoughtful decision-making.

Quiz page: 
The Quiz Page provides an interactive and educational way for users to test their knowledge about water:
Ten Randomized Questions:
Each quiz session generates 10 random questions covering topics such as:
Water science
Water history
Hydration facts
Environmental water knowledge

Answer & Submit System:
Users select their answers and submit them once completed.
The system evaluates the responses instantly.

Score Display:
After submission, users receive their total score based on the number of correct answers.

Correct Answer Review:
The quiz also displays the correct answers for all questions, allowing users to learn and improve their understanding.

Purpose:
This page helps users build awareness about water science while making the learning experience enjoyable and informative.

🔷 14. Future Enhancements

Add:
1. Smart AI-based notification timing.
2. Push reminders based on body weight & weather.
3. Geolocation-based hydration alerts.
4. Use FireBase for data storage for permanant stroring and for notifications pop-ups even the app is closed or phone is off.

🔷 15. Conclusion

WaterBuddy successfully tracks hydration, motivates users with AI, medals, games, and streaks, and now includes real-time push notifications through streamlit for better user engagement.
Credits: 
1. Name:Sri Prasath. P
2. Grade: IBCP Year1
3. Course: Python Programming
4. Mentor: Syed Ali Beema.S
