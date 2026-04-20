import os
import json
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from database import get_mongo_db, mongo_get_user_by_id
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


def get_expense_dataframe(user_id):
    """Load user expenses from MongoDB into a Pandas DataFrame."""
    db = get_mongo_db()
    expenses = list(db.expenses.find(
        {'user_id': user_id},
        {'_id': 1, 'user_id': 1, 'amount': 1, 'category': 1, 'description': 1, 'date': 1}
    ).sort('date', 1))

    if not expenses:
        return pd.DataFrame(columns=['_id', 'user_id', 'amount', 'category', 'description', 'date'])

    df = pd.DataFrame(expenses)
    # Convert string _id to string for compatibility
    df['id'] = df['_id'].astype(str)
    # Parse date strings to datetime
    df['date'] = pd.to_datetime(df['date'])
    return df


def analyze_spending(user_id):
    """Perform comprehensive spending analysis."""
    df = get_expense_dataframe(user_id)

    if df.empty:
        return {
            'total': 0,
            'monthly_avg': 0,
            'highest_category': 'N/A',
            'category_breakdown': {},
            'monthly_trend': [],
            'expense_count': 0
        }

    # Category breakdown
    category_breakdown = df.groupby('category')['amount'].agg(
        ['sum', 'mean', 'count']
    ).to_dict('index')

    # Monthly trend
    df['month'] = df['date'].dt.to_period('M').astype(str)
    monthly = df.groupby('month')['amount'].sum().reset_index()
    monthly_trend = monthly.to_dict('records')

    # Highest spending category
    highest_category = df.groupby('category')['amount'].sum().idxmax()

    # Monthly average
    months_active = max(df['month'].nunique(), 1)
    monthly_avg = df['amount'].sum() / months_active

    return {
        'total': round(df['amount'].sum(), 2),
        'monthly_avg': round(monthly_avg, 2),
        'highest_category': highest_category,
        'category_breakdown': {
            cat: {
                'total': round(vals['sum'], 2),
                'average': round(vals['mean'], 2),
                'count': int(vals['count'])
            }
            for cat, vals in category_breakdown.items()
        },
        'monthly_trend': monthly_trend,
        'expense_count': len(df)
    }


def generate_ai_insights(user_id):
    """Generate rule-based AI insights and savings suggestions."""
    df = get_expense_dataframe(user_id)
    insights = []

    if df.empty:
        return [{'type': 'info', 'icon': '📊', 'message': 'Add some expenses to get personalized insights!'}]

    # Get user's monthly budget from MongoDB
    user = mongo_get_user_by_id(str(user_id))
    monthly_budget = user['monthly_budget'] if user else 50000

    # --- Category analysis ---
    category_totals = df.groupby('category')['amount'].sum()
    total_spending = category_totals.sum()
    category_pcts = (category_totals / total_spending * 100).round(1)

    # Flag categories that dominate spending (> 35%)
    for cat, pct in category_pcts.items():
        if pct > 35:
            insights.append({
                'type': 'warning',
                'icon': '⚠️',
                'message': f'You are spending too much on {cat} — it accounts for {pct}% of your total expenses.'
            })

    # --- Monthly trend analysis ---
    df['month'] = df['date'].dt.to_period('M')
    monthly_totals = df.groupby('month')['amount'].sum().sort_index()

    if len(monthly_totals) >= 2:
        last_month = monthly_totals.iloc[-1]
        prev_month = monthly_totals.iloc[-2]
        change = last_month - prev_month
        change_pct = (change / prev_month * 100) if prev_month > 0 else 0

        if change_pct > 20:
            insights.append({
                'type': 'danger',
                'icon': '📈',
                'message': f'Your spending increased by {change_pct:.0f}% compared to last month (+₹{change:,.0f}).'
            })
        elif change_pct < -10:
            insights.append({
                'type': 'success',
                'icon': '🎉',
                'message': f'Great job! You saved {abs(change_pct):.0f}% compared to last month (₹{abs(change):,.0f} less).'
            })

    # --- Savings suggestions ---
    monthly_avg = total_spending / max(monthly_totals.count(), 1)

    if monthly_avg > monthly_budget:
        potential_savings = monthly_avg - monthly_budget
        insights.append({
            'type': 'tip',
            'icon': '💡',
            'message': f'You can save ₹{potential_savings:,.0f} per month by sticking to your ₹{monthly_budget:,.0f} budget.'
        })

    # Food-specific advice
    if 'Food' in category_totals:
        food_monthly = category_totals['Food'] / max(monthly_totals.count(), 1)
        if food_monthly > 8000:
            savings = food_monthly - 6000
            insights.append({
                'type': 'tip',
                'icon': '🍽️',
                'message': f'Your monthly food spending averages ₹{food_monthly:,.0f}. Cooking at home more could save you ~₹{savings:,.0f}/month.'
            })

    # Travel optimization
    if 'Travel' in category_totals:
        travel_monthly = category_totals['Travel'] / max(monthly_totals.count(), 1)
        if travel_monthly > 5000:
            insights.append({
                'type': 'tip',
                'icon': '🚗',
                'message': f'Consider using public transport more — your monthly travel spend is ₹{travel_monthly:,.0f}.'
            })

    # Shopping control
    if 'Shopping' in category_totals:
        shopping_monthly = category_totals['Shopping'] / max(monthly_totals.count(), 1)
        if shopping_monthly > 10000:
            insights.append({
                'type': 'warning',
                'icon': '🛒',
                'message': f'High shopping expenses detected (₹{shopping_monthly:,.0f}/month). Try the 48-hour rule before purchases.'
            })

    # Positive reinforcement if spending is under control
    if monthly_avg <= monthly_budget * 0.8:
        insights.append({
            'type': 'success',
            'icon': '🏆',
            'message': f'Excellent! You\'re spending well below your budget. Consider investing the surplus!'
        })

    # Add a general tip if few insights
    if len(insights) < 2:
        insights.append({
            'type': 'info',
            'icon': '📊',
            'message': f'Your average monthly spend is ₹{monthly_avg:,.0f} across {len(category_totals)} categories.'
        })

    return insights


def predict_next_month(user_id):
    """Predict next month's spending using Linear Regression."""
    df = get_expense_dataframe(user_id)

    if df.empty or len(df) < 5:
        return {
            'predicted': None,
            'confidence': 'low',
            'message': 'Not enough data for prediction. Add more expenses over multiple months.'
        }

    # Aggregate by month
    df['month_num'] = df['date'].dt.to_period('M')
    monthly = df.groupby('month_num')['amount'].sum().reset_index()
    monthly['month_idx'] = range(len(monthly))

    if len(monthly) < 3:
        return {
            'predicted': None,
            'confidence': 'low',
            'message': 'Need at least 3 months of data for accurate predictions.'
        }

    # Linear Regression
    X = monthly[['month_idx']].values
    y = monthly['amount'].values

    model = LinearRegression()
    model.fit(X, y)

    # Predict next month
    next_month_idx = np.array([[len(monthly)]])
    predicted = model.predict(next_month_idx)[0]
    predicted = max(predicted, 0)  # No negative predictions

    # R² score for confidence
    r2 = model.score(X, y)
    if r2 > 0.7:
        confidence = 'high'
    elif r2 > 0.4:
        confidence = 'medium'
    else:
        confidence = 'low'

    # Trend direction
    slope = model.coef_[0]
    if slope > 500:
        trend = 'increasing'
    elif slope < -500:
        trend = 'decreasing'
    else:
        trend = 'stable'

    return {
        'predicted': round(predicted, 2),
        'confidence': confidence,
        'r2_score': round(r2, 3),
        'trend': trend,
        'message': f'Based on your spending pattern, you are likely to spend approximately ₹{predicted:,.0f} next month.',
        'monthly_data': [
            {'month': str(row['month_num']), 'amount': round(row['amount'], 2)}
            for _, row in monthly.iterrows()
        ]
    }


def detect_fraud(user_id):
    """Detect potentially fraudulent or unusual transactions."""
    df = get_expense_dataframe(user_id)

    if df.empty or len(df) < 5:
        return []

    flagged = []
    mean_amount = df['amount'].mean()
    std_amount = df['amount'].std()
    threshold = mean_amount + (3 * std_amount)  # 3 standard deviations

    # Flag transactions that are unusually large
    suspicious = df[df['amount'] > threshold]

    for _, row in suspicious.iterrows():
        multiplier = row['amount'] / mean_amount
        flagged.append({
            'id': str(row['_id']),
            'amount': round(row['amount'], 2),
            'category': row['category'],
            'description': row['description'],
            'date': row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date']),
            'reason': f'Amount is {multiplier:.1f}× your average spending (₹{mean_amount:,.0f})',
            'severity': 'high' if multiplier > 5 else 'medium'
        })

    # Also flag duplicate-looking transactions on same day
    same_day = df.groupby(['date', 'amount', 'category']).size().reset_index(name='count')
    duplicates = same_day[same_day['count'] > 1]

    for _, row in duplicates.iterrows():
        flagged.append({
            'amount': round(row['amount'], 2),
            'category': row['category'],
            'date': row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date']),
            'reason': f'Duplicate transaction detected ({int(row["count"])} identical entries)',
            'severity': 'medium'
        })

    return flagged


def check_alerts(user_id):
    """Check if spending has crossed threshold limits."""
    user = mongo_get_user_by_id(str(user_id))

    if not user:
        return []

    monthly_budget = user['monthly_budget']
    alerts = []

    # Get current month spending
    df = get_expense_dataframe(user_id)
    if df.empty:
        return alerts

    current_month = datetime.now().strftime('%Y-%m')
    df['month'] = df['date'].dt.strftime('%Y-%m')
    current_spending = df[df['month'] == current_month]['amount'].sum()

    pct = (current_spending / monthly_budget * 100) if monthly_budget > 0 else 0

    if pct >= 100:
        alerts.append({
            'type': 'danger',
            'icon': '🚨',
            'message': f'Budget exceeded! You\'ve spent ₹{current_spending:,.0f} this month ({pct:.0f}% of your ₹{monthly_budget:,.0f} budget).'
        })
    elif pct >= 80:
        alerts.append({
            'type': 'warning',
            'icon': '⚠️',
            'message': f'Warning: You\'ve used {pct:.0f}% of your monthly budget (₹{current_spending:,.0f} of ₹{monthly_budget:,.0f}).'
        })
    elif pct >= 50:
        alerts.append({
            'type': 'info',
            'icon': 'ℹ️',
            'message': f'You\'ve spent {pct:.0f}% of your monthly budget so far (₹{current_spending:,.0f} of ₹{monthly_budget:,.0f}).'
        })

    # Category-specific alerts
    category_spending = df[df['month'] == current_month].groupby('category')['amount'].sum()
    category_limits = {'Food': 10000, 'Shopping': 15000, 'Travel': 8000, 'Bills': 12000}

    for cat, limit in category_limits.items():
        if cat in category_spending and category_spending[cat] > limit:
            alerts.append({
                'type': 'warning',
                'icon': '📊',
                'message': f'{cat} spending this month (₹{category_spending[cat]:,.0f}) exceeds recommended limit of ₹{limit:,.0f}.'
            })

    return alerts


def get_gemini_insights(user_id):
    """Get personalized AI insights from Google Gemini."""
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')

        # Gather spending data
        analysis = analyze_spending(user_id)
        if analysis['total'] == 0:
            return None

        # Build context
        cat_summary = ', '.join(
            f"{cat}: ₹{info['total']:,.0f} ({info['count']} txns)"
            for cat, info in analysis['category_breakdown'].items()
        )

        prompt = f"""You are an expert Indian personal finance advisor.
Never mention that you are an AI, language model, or virtual assistant. Speak as if you are a real human financial expert working at FinTrack Pro.

Analyze this user's spending and provide exactly 3 actionable insights.

Spending Summary:
- Total: ₹{analysis['total']:,.0f}
- Monthly Average: ₹{analysis['monthly_avg']:,.0f}
- Top Category: {analysis['highest_category']}
- Breakdown: {cat_summary}
- Total Transactions: {analysis['expense_count']}

Rules:
1. Be specific with numbers and ₹ amounts
2. Suggest practical Indian investment options (PPF, ELSS, NPS, FD, SIP)
3. Give one savings tip, one investment tip, and one warning/alert
4. Keep each insight to 2 sentences max
5. Use a friendly, professional tone

Return your response as a JSON array with exactly 3 objects:
[{{"type": "tip|success|warning", "icon": "emoji", "title": "short title", "message": "detail"}}, ...]

Return ONLY the JSON array, no other text."""

        response = model.generate_content(prompt)
        text = response.text.strip()

        # Clean up response — remove markdown code fences if present
        if text.startswith('```'):
            text = text.split('\n', 1)[1]  # remove first line
            text = text.rsplit('```', 1)[0]  # remove last fence
            text = text.strip()

        insights = json.loads(text)
        return insights

    except Exception as e:
        print(f"[GEMINI ERROR] {e}")
        return None
