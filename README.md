# AI Personal Finance Analytics System

A premium, AI-powered personal finance tracking application built with Flask, SQLite, and Chart.js. Features spending analytics, ML-based predictions, smart insights, and fraud detection.

## Features

- **User Authentication** — Signup, login, session management
- **Expense Management** — Add, view, delete expenses across 4 categories
- **Interactive Dashboard** — Stat cards, monthly line chart, category doughnut chart
- **AI Insights** — Rule-based spending advice and savings suggestions
- **ML Predictions** — Linear Regression to predict next month's spending
- **Fraud Detection** — Flags transactions > 3σ above average
- **Budget Alerts** — Warnings when spending crosses thresholds
- **CSV Export** — Download all expenses as CSV
- **Dark Mode UI** — Glassmorphism, animations, fully responsive

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the application
python app.py

# 3. Open in browser
# http://localhost:5000
```

## Demo Account

A pre-seeded demo account is available:
- **Username:** `demo`
- **Password:** `demo123`

## Tech Stack

| Layer      | Technology                      |
|------------|---------------------------------|
| Backend    | Python Flask                    |
| Database   | SQLite                          |
| Frontend   | HTML, CSS, JavaScript           |
| Charts     | Chart.js                        |
| Analytics  | Pandas, scikit-learn, NumPy     |
| Fonts      | Google Fonts (Inter)            |

## Project Structure

```
├── app.py              # Flask routes and API endpoints
├── database.py         # SQLite schema and queries
├── analytics.py        # ML predictions, AI insights, fraud detection
├── requirements.txt    # Python dependencies
├── static/
│   ├── css/style.css   # Design system
│   └── js/dashboard.js # Chart.js and interactions
└── templates/
    ├── base.html       # Base layout
    ├── login.html      # Login page
    ├── signup.html      # Signup page
    ├── dashboard.html   # Main dashboard
    ├── add_expense.html # Add expense form
    └── analytics.html   # Analytics and predictions
```
