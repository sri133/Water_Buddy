**WaterBuddy – Smart Hydration Web App (Streamlit + Firebase + AI + FCM Notifications)**

"A complete hydration tracking system built with Streamlit, Firebase, Gamification, AI (Gemini), and now Firebase Cloud Messaging (Push Notifications)"

**Table of Contents**

1. Overview
2. Problem Statement
3. Solution
4. Objectives
5. Features
6. Technology Stack
7. System Architecture
8. Project Structure
9. Firebase Setup
10. FCM Push Notification Setup ✅ NEW
11. How to Run Locally
12. Detailed Feature Explanation
13. Water Recommendation Logic
14. Pages Explanation
15. Database Structure
16. Challenges & Solutions
17. Future Enhancements
18. Output Screenshots
19. Conclusion

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
4. Firebase Realtime Database
5. APIs
6. Google Gemini AI
7. Firebase Cloud Messaging (FCM)
8. Visualization
9. Plotly
10. Matplotlib
11. Storage
12. Local JSON file + Firebase sync
13. Browser Notifications
14. firebase.js
15. messaging-sw.js

🔷 7. System Architecture
User
   ↓
Streamlit Frontend
   ↓
Firebase (Auth + Realtime DB)
   ↓
Gemini AI (Daily Goal Recommendation)
   ↓
Plotly / Matplotlib (Reports)
   ↓
FCM Push Notifications (Scheduled Reminders)

🔷 8. Project Structure
WaterBuddy/
│── app.py
│── firebase_config.json
│── water_data.json
│── requirements.txt
│── firebase.js              ← NEW (FCM Config)
│── messaging-sw.js          ← NEW (Service Worker)
│── images/
│     ├── login_bg.png
│     ├── mascot1.png
│     └── bottle.png
└── .streamlit/
      └── secrets.toml

🔷 9. Firebase Setup

   9.1 FCM Push Notification Setup (NEW 🆕)

To enable hydration reminders, integrate Firebase Cloud Messaging.

1️⃣ Create Web API Key + Sender ID

Go to:
Firebase Console → Project Settings → Cloud Messaging
Copy:

Web API Key

Sender ID

VAPID Key

2️⃣ Add firebase.js

Create a file named firebase.js:

import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";
import { getMessaging, getToken } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging.js";

const firebaseConfig = {
  apiKey: "YOUR_API_KEY",
  authDomain: "PROJECT_ID.firebaseapp.com",
  projectId: "PROJECT_ID",
  messagingSenderId: "SENDER_ID",
  appId: "APP_ID",
};

const app = initializeApp(firebaseConfig);
const messaging = getMessaging(app);

export function requestPermission() {
  return Notification.requestPermission().then((permission) => {
    if (permission === "granted") {
      return getToken(messaging, { vapidKey: "YOUR_VAPID_KEY" });
    }
  });
}

3️⃣ Add messaging-sw.js (service worker)
importScripts("https://www.gstatic.com/firebasejs/10.7.1/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging-compat.js");

firebase.initializeApp({
  apiKey: "YOUR_API_KEY",
  projectId: "PROJECT_ID",
  messagingSenderId: "SENDER_ID",
  appId: "APP_ID",
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
  self.registration.showNotification(payload.notification.title, {
    body: payload.notification.body,
  });
});

4️⃣ Store FCM Token in Firebase

Inside Streamlit:

token = js_token_from_browser
db.reference(f"users/{username}/notification_token").set(token)

5️⃣ Send Notifications

Example Cloud Function:

admin.messaging().sendToDevice(token, {
  notification: {
    title: "Hydrate Now 💧",
    body: "Take a sip! Your body needs water.",
  }
});

🔷 10. How to Run Locally

(Your same steps)

🔷 11. Feature Workflows

(Your same content; notifications automatically added to Daily Water Intake and Home Page.)

🔷 12. Water Recommendation Logic

(Your same logic)

🔷 13. Page-by-Page Explanation

Add under Home Page:

🔔 Hydration Notifications (NEW)

User grants permission

App registers FCM token

Sends reminders every 2–3 hours

Works in background

🔷 14. Database Structure

Add:

notification_token: "abc123xyz"

🔷 15. Challenges & Solutions
Challenge	Solution
Sending reminders while app is closed	Integrated Firebase Cloud Messaging
Web push permissions	Added JS + service worker
Token handling	Stored token per user in Firebase
🔷 16. Future Enhancements

Add:

Smart AI-based notification timing

Push reminders based on body weight & weather

Geolocation-based hydration alerts

🔷 17. Screenshots

(You will add yourself.)

🔷 18. Conclusion

WaterBuddy successfully tracks hydration, motivates users with AI, medals, games, and streaks, and now includes real-time push notifications through FCM for better user engagement.
