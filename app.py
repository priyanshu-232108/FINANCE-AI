import os
import csv
import io
import random
from datetime import datetime, timedelta
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, Response
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

from database import (
    init_db, seed_demo_data, get_user_expenses,
    get_monthly_totals, get_category_totals, get_total_spending,
    get_current_month_spending, add_expense as db_add_expense, delete_expense as db_delete_expense,
    mongo_find_user_by_username, mongo_find_user_by_username_or_email,
    mongo_create_user, mongo_update_user_budget, mongo_get_user_by_id
)
from analytics import (
    analyze_spending, generate_ai_insights, predict_next_month,
    detect_fraud, check_alerts, get_gemini_insights
)

# ─── Load Environment Variables ──────────────────────────────
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'fallback-dev-key-change-me')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(
    minutes=int(os.getenv('SESSION_LIFETIME_MINUTES', 30))
)

# ─── Email Configuration ─────────────────────────────────────
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', '')
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME', '')

mail = Mail(app)

# ─── Security ────────────────────────────────────────────────
csrf = CSRFProtect(app)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# ─── Initialize MongoDB ─────────────────────────────────────
with app.app_context():
    init_db()
    seed_demo_data()


# ─── Auth Helper ─────────────────────────────────────────────
def login_required(f):
    """Decorator to protect routes that require authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ─── OTP Helper ──────────────────────────────────────────────
def generate_otp():
    """Generate a 6-digit OTP."""
    return str(random.randint(100000, 999999))


def send_otp_email(email, otp):
    """Send OTP to user's email. Returns True on success, False on failure."""
    try:
        if not app.config['MAIL_USERNAME']:
            print("[MAIL] Email not configured — skipping OTP send.")
            return False

        msg = Message(
            subject='🔐 Your FinTrack Verification OTP',
            recipients=[email]
        )
        msg.html = f"""
        <div style="font-family: 'Inter', sans-serif; max-width: 480px; margin: 0 auto;
                    background: #1a1a2e; color: #e0e0e0; padding: 32px; border-radius: 16px;">
            <h2 style="color: #a78bfa; margin-bottom: 8px;">FinTrack Verification</h2>
            <p style="color: #9ca3af;">Use the OTP below to verify your email address:</p>
            <div style="background: #16213e; padding: 20px; border-radius: 12px;
                        text-align: center; margin: 24px 0;">
                <span style="font-size: 36px; font-weight: 700; letter-spacing: 8px;
                             color: #a78bfa;">{otp}</span>
            </div>
            <p style="color: #6b7280; font-size: 13px;">
                This OTP is valid for {os.getenv('OTP_EXPIRY_MINUTES', '5')} minutes.
                If you didn't request this, please ignore this email.
            </p>
            <hr style="border-color: #2d2d44; margin: 24px 0;">
            <p style="color: #4b5563; font-size: 12px; text-align: center;">
                © 2024 FinTrack — AI Personal Finance Analytics
            </p>
        </div>
        """
        mail.send(msg)
        print(f"[MAIL] OTP sent to {email}")
        return True
    except Exception as e:
        print(f"[MAIL ERROR] Failed to send OTP: {e}")
        return False


# ─── Auth Routes ─────────────────────────────────────────────
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Please fill in all fields.', 'danger')
            return render_template('login.html')

        # Look up user in MongoDB
        user = mongo_find_user_by_username(username)

        if user and check_password_hash(user['password_hash'], password):
            session.permanent = True
            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            flash(f'Welcome back, {user["username"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def signup():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not all([username, email, password, confirm]):
            flash('Please fill in all fields.', 'danger')
            return render_template('signup.html')

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('signup.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('signup.html')

        # Check if user already exists in MongoDB
        existing = mongo_find_user_by_username_or_email(username, email)

        if existing:
            flash('Username or email already exists.', 'danger')
            return render_template('signup.html')

        # ─── Email OTP Verification ────────────────────────
        # Check if email is configured
        if app.config['MAIL_USERNAME']:
            otp = generate_otp()
            session['signup_otp'] = otp
            session['signup_data'] = {
                'username': username,
                'email': email,
                'password': password
            }
            session['otp_created_at'] = datetime.now().isoformat()

            if send_otp_email(email, otp):
                flash('An OTP has been sent to your email. Please verify.', 'info')
                return render_template('verify_otp.html', email=email)
            else:
                # Email sending failed — proceed without OTP
                flash('Could not send OTP. Proceeding with signup.', 'warning')

        # ─── Direct signup (no email configured or OTP failed) ─
        password_hash = generate_password_hash(password)
        user = mongo_create_user(username, email, password_hash)

        session['user_id'] = str(user['_id'])
        session['username'] = user['username']
        flash('Account created successfully! Welcome!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('signup.html')


@app.route('/verify_otp', methods=['POST'])
@limiter.limit("10 per minute")
def verify_otp():
    entered_otp = request.form.get('otp', '').strip()
    stored_otp = session.get('signup_otp', '')
    signup_data = session.get('signup_data', {})
    otp_created = session.get('otp_created_at', '')

    if not stored_otp or not signup_data:
        flash('Session expired. Please sign up again.', 'danger')
        return redirect(url_for('signup'))

    # Check OTP expiry
    expiry_minutes = int(os.getenv('OTP_EXPIRY_MINUTES', 5))
    if otp_created:
        created_time = datetime.fromisoformat(otp_created)
        if datetime.now() - created_time > timedelta(minutes=expiry_minutes):
            session.pop('signup_otp', None)
            session.pop('signup_data', None)
            session.pop('otp_created_at', None)
            flash('OTP has expired. Please sign up again.', 'danger')
            return redirect(url_for('signup'))

    if entered_otp != stored_otp:
        flash('Invalid OTP. Please try again.', 'danger')
        return render_template('verify_otp.html', email=signup_data.get('email', ''))

    # OTP verified — create account in MongoDB
    password_hash = generate_password_hash(signup_data['password'])
    user = mongo_create_user(
        signup_data['username'], signup_data['email'],
        password_hash, email_verified=True
    )

    # Clean up session
    session.pop('signup_otp', None)
    session.pop('signup_data', None)
    session.pop('otp_created_at', None)

    session['user_id'] = str(user['_id'])
    session['username'] = user['username']
    flash('Email verified! Account created successfully! 🎉', 'success')
    return redirect(url_for('dashboard'))


@app.route('/resend_otp', methods=['POST'])
@limiter.limit("3 per minute")
def resend_otp():
    signup_data = session.get('signup_data', {})
    if not signup_data:
        flash('Session expired. Please sign up again.', 'danger')
        return redirect(url_for('signup'))

    otp = generate_otp()
    session['signup_otp'] = otp
    session['otp_created_at'] = datetime.now().isoformat()

    if send_otp_email(signup_data['email'], otp):
        flash('A new OTP has been sent to your email.', 'info')
    else:
        flash('Failed to resend OTP. Please try again.', 'danger')

    return render_template('verify_otp.html', email=signup_data.get('email', ''))


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ─── Dashboard ───────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    expenses = get_user_expenses(user_id)
    total = get_total_spending(user_id)
    current_month = get_current_month_spending(user_id)
    categories = get_category_totals(user_id)
    alerts = check_alerts(user_id)

    # Top category
    top_category = categories[0]['category'] if categories else 'N/A'

    return render_template('dashboard.html',
                           expenses=expenses,
                           total=total,
                           current_month=current_month,
                           top_category=top_category,
                           expense_count=len(expenses),
                           alerts=alerts)


# ─── Expense CRUD ────────────────────────────────────────────
@app.route('/add_expense', methods=['GET', 'POST'])
@login_required
def add_expense():
    if request.method == 'POST':
        amount = request.form.get('amount', '')
        category = request.form.get('category', '')
        description = request.form.get('description', '').strip()
        date = request.form.get('date', '')

        if not all([amount, category, date]):
            flash('Amount, category, and date are required.', 'danger')
            return render_template('add_expense.html')

        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            flash('Please enter a valid positive amount.', 'danger')
            return render_template('add_expense.html')

        # Add expense to MongoDB
        db_add_expense(session['user_id'], amount, category, description, date)

        flash(f'Expense of ₹{amount:,.2f} added successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('add_expense.html')


@app.route('/delete_expense/<expense_id>', methods=['POST'])
@login_required
def delete_expense(expense_id):
    # Delete expense from MongoDB
    db_delete_expense(session['user_id'], expense_id)
    flash('Expense deleted.', 'info')
    return redirect(url_for('dashboard'))


# ─── Analytics ───────────────────────────────────────────────
@app.route('/analytics')
@login_required
def analytics():
    user_id = session['user_id']
    analysis = analyze_spending(user_id)
    insights = generate_ai_insights(user_id)
    prediction = predict_next_month(user_id)
    fraud_alerts = detect_fraud(user_id)

    # Get Gemini AI insights if API key is configured
    gemini_insights = None
    if os.getenv('GEMINI_API_KEY'):
        gemini_insights = get_gemini_insights(user_id)

    return render_template('analytics.html',
                           analysis=analysis,
                           insights=insights,
                           prediction=prediction,
                           fraud_alerts=fraud_alerts,
                           gemini_insights=gemini_insights)


# ─── API Endpoints (for Chart.js) ────────────────────────────
@app.route('/api/monthly_data')
@login_required
def api_monthly_data():
    data = get_monthly_totals(session['user_id'])
    return jsonify(data)


@app.route('/api/category_data')
@login_required
def api_category_data():
    data = get_category_totals(session['user_id'])
    return jsonify(data)


@app.route('/api/alerts')
@login_required
def api_alerts():
    alerts = check_alerts(session['user_id'])
    return jsonify(alerts)


# ─── Gemini AI Chat API ─────────────────────────────────────
@app.route('/api/ai_chat', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
@csrf.exempt
def ai_chat():
    """Chat with virtual advisor about finances."""
    if not os.getenv('GEMINI_API_KEY'):
        return jsonify({'error': 'Advisor not configured. Add GEMINI_API_KEY to .env'}), 503

    question = request.json.get('question', '').strip()
    if not question:
        return jsonify({'error': 'Please ask a question.'}), 400

    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        model = genai.GenerativeModel('gemini-2.0-flash')

        # Get user's expense context
        user_id = session['user_id']
        analysis = analyze_spending(user_id)

        prompt = f"""You are a friendly Indian personal finance advisor for the app "FinTrack Pro".
Never mention that you are an AI, language model, or virtual assistant. Speak as if you are a real human financial expert working at FinTrack.
The user's spending data:
- Total spending: ₹{analysis['total']:,.0f}
- Monthly average: ₹{analysis['monthly_avg']:,.0f}
- Top category: {analysis['highest_category']}
- Categories: {', '.join(f"{k}: ₹{v['total']:,.0f}" for k, v in analysis['category_breakdown'].items())}

User's question: {question}

Give a helpful, concise answer in 2-3 sentences. Use ₹ for Indian Rupees. Be practical and friendly."""

        response = model.generate_content(prompt)
        return jsonify({'answer': response.text})

    except Exception as e:
        print(f"[GEMINI ERROR] {e}")
        return jsonify({'error': 'Advisor service temporarily unavailable.'}), 500


# ─── CSV Export ──────────────────────────────────────────────
@app.route('/export_csv')
@login_required
def export_csv():
    expenses = get_user_expenses(session['user_id'])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Category', 'Amount (₹)', 'Description'])

    for exp in expenses:
        writer.writerow([exp['date'], exp['category'], exp['amount'], exp['description']])

    output.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=expenses_{timestamp}.csv'
        }
    )


# ─── New Modules ────────────────────────────────────────────
@app.route('/loans')
@login_required
def loans():
    """Loan Comparison — compare interest rates from top Indian banks."""
    return render_template('loans.html')


@app.route('/ca')
@login_required
def ca_finder():
    """CA Finder — discover top chartered accountancy firms."""
    return render_template('ca.html')


@app.route('/tax')
@login_required
def tax_planner():
    """Smart Tax Planner — compare Old vs New tax regime."""
    return render_template('tax.html')


# ─── Settings (Budget) ──────────────────────────────────────
@app.route('/update_budget', methods=['POST'])
@login_required
def update_budget():
    budget = request.form.get('budget', '')
    try:
        budget = float(budget)
        if budget <= 0:
            raise ValueError
    except ValueError:
        flash('Please enter a valid budget amount.', 'danger')
        return redirect(url_for('dashboard'))

    # Update budget in MongoDB
    mongo_update_user_budget(session['user_id'], budget)

    flash(f'Monthly budget updated to ₹{budget:,.0f}!', 'success')
    return redirect(url_for('dashboard'))


# ─── Error Handlers ──────────────────────────────────────────
@app.errorhandler(429)
def ratelimit_handler(e):
    flash('Too many requests. Please slow down.', 'warning')
    return redirect(url_for('index'))


# ─── Run ─────────────────────────────────────────────────────
if __name__ == '__main__':
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    port = int(os.getenv('FLASK_PORT', 5000))
    app.run(debug=debug, port=port)
