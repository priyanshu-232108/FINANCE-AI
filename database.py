import os
from datetime import datetime, timedelta
import random
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId

load_dotenv()

# ─── MongoDB Atlas Connection ────────────────────────────────
MONGO_URI = os.getenv('MONGO_URI', '')
MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', 'fintech_app')

_mongo_client = None
_mongo_db = None


def get_mongo_db():
    """Get a MongoDB database connection (lazy singleton)."""
    global _mongo_client, _mongo_db
    if _mongo_client is None:
        _mongo_client = MongoClient(MONGO_URI)
        _mongo_db = _mongo_client[MONGO_DB_NAME]
        # Ensure unique indexes on username and email
        _mongo_db.users.create_index('username', unique=True)
        _mongo_db.users.create_index('email', unique=True)
        # Index on expenses for fast user lookups
        _mongo_db.expenses.create_index('user_id')
        _mongo_db.expenses.create_index([('user_id', 1), ('date', -1)])
        print("[MONGO] Connected to MongoDB Atlas successfully!")
    return _mongo_db


# ─── User Functions ──────────────────────────────────────────

def mongo_find_user_by_username(username):
    """Find a user by username in MongoDB."""
    db = get_mongo_db()
    return db.users.find_one({'username': username})


def mongo_find_user_by_username_or_email(username, email):
    """Check if a user with given username or email already exists."""
    db = get_mongo_db()
    return db.users.find_one({'$or': [{'username': username}, {'email': email}]})


def mongo_create_user(username, email, password_hash, email_verified=False, monthly_budget=50000):
    """Insert a new user into MongoDB. Returns the inserted document."""
    db = get_mongo_db()
    user_doc = {
        'username': username,
        'email': email,
        'password_hash': password_hash,
        'monthly_budget': monthly_budget,
        'email_verified': email_verified,
        'created_at': datetime.utcnow()
    }
    result = db.users.insert_one(user_doc)
    user_doc['_id'] = result.inserted_id
    return user_doc


def mongo_update_user_budget(user_id, budget):
    """Update a user's monthly budget in MongoDB."""
    db = get_mongo_db()
    db.users.update_one({'_id': ObjectId(user_id)}, {'$set': {'monthly_budget': budget}})


def mongo_get_user_by_id(user_id):
    """Get a user by their MongoDB _id."""
    db = get_mongo_db()
    return db.users.find_one({'_id': ObjectId(user_id)})


# ─── Initialize & Seed ──────────────────────────────────────

def init_db():
    """Initialize MongoDB collections and indexes (called at app startup)."""
    db = get_mongo_db()
    # Collections are created automatically on first insert in MongoDB.
    # Indexes are already set up in get_mongo_db().
    print("[MONGO] Database initialized.")


def seed_demo_data():
    """Seed the database with a demo user and sample expenses in MongoDB."""
    db = get_mongo_db()

    # Check if demo user already exists
    existing = db.users.find_one({'username': 'demo'})
    if existing:
        return

    # Create demo user (password: demo123)
    password_hash = generate_password_hash('demo123')
    user_doc = {
        'username': 'demo',
        'email': 'demo@example.com',
        'password_hash': password_hash,
        'monthly_budget': 50000,
        'email_verified': True,
        'created_at': datetime.utcnow()
    }
    result = db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)

    # Sample expense data spanning 6 months
    categories = {
        'Food': {
            'descriptions': [
                'Grocery shopping', 'Restaurant dinner', 'Swiggy order',
                'Zomato delivery', 'Coffee shop', 'Street food',
                'Weekly groceries', 'Birthday dinner', 'Lunch with friends'
            ],
            'range': (200, 3500)
        },
        'Travel': {
            'descriptions': [
                'Uber ride', 'Metro pass', 'Ola cab', 'Petrol fill-up',
                'Bus ticket', 'Train ticket', 'Parking fee', 'Toll charges'
            ],
            'range': (100, 5000)
        },
        'Shopping': {
            'descriptions': [
                'Amazon purchase', 'Flipkart order', 'Clothes shopping',
                'Electronics', 'Home decor', 'Shoes', 'Gift purchase',
                'Books from store', 'Phone accessories'
            ],
            'range': (500, 8000)
        },
        'Bills': {
            'descriptions': [
                'Electricity bill', 'Water bill', 'Internet bill',
                'Mobile recharge', 'Netflix subscription', 'Gym membership',
                'Insurance premium', 'Gas bill', 'Society maintenance'
            ],
            'range': (200, 5000)
        }
    }

    today = datetime.now()
    expenses = []

    for month_offset in range(6, -1, -1):
        month_date = today - timedelta(days=month_offset * 30)
        # Generate 8-15 expenses per month
        num_expenses = random.randint(8, 15)

        for _ in range(num_expenses):
            category = random.choice(list(categories.keys()))
            cat_info = categories[category]
            amount = round(random.uniform(*cat_info['range']), 2)
            description = random.choice(cat_info['descriptions'])
            day = random.randint(1, 28)

            try:
                expense_date = month_date.replace(day=day)
            except ValueError:
                expense_date = month_date.replace(day=28)

            expenses.append({
                'user_id': user_id,
                'amount': amount,
                'category': category,
                'description': description,
                'date': expense_date.strftime('%Y-%m-%d'),
                'created_at': datetime.utcnow()
            })

    # Add one unusually large transaction for fraud detection demo
    fraud_date = (today - timedelta(days=5)).strftime('%Y-%m-%d')
    expenses.append({
        'user_id': user_id,
        'amount': 45000.0,
        'category': 'Shopping',
        'description': 'Suspicious large electronics purchase',
        'date': fraud_date,
        'created_at': datetime.utcnow()
    })

    db.expenses.insert_many(expenses)
    print(f"[MONGO] Seeded {len(expenses)} expenses for demo user.")


# ─── Expense Functions ───────────────────────────────────────

def get_user_expenses(user_id, limit=None):
    """Get all expenses for a user, ordered by date descending."""
    db = get_mongo_db()
    query = {'user_id': user_id}
    cursor = db.expenses.find(query).sort('date', -1)
    if limit:
        cursor = cursor.limit(limit)
    # Convert MongoDB documents to dicts with string _id
    expenses = []
    for doc in cursor:
        doc['id'] = str(doc['_id'])
        expenses.append(doc)
    return expenses


def add_expense(user_id, amount, category, description, date):
    """Add a new expense for a user."""
    db = get_mongo_db()
    expense_doc = {
        'user_id': user_id,
        'amount': amount,
        'category': category,
        'description': description,
        'date': date,
        'created_at': datetime.utcnow()
    }
    result = db.expenses.insert_one(expense_doc)
    return str(result.inserted_id)


def delete_expense(user_id, expense_id):
    """Delete an expense by its ID, ensuring it belongs to the user."""
    db = get_mongo_db()
    db.expenses.delete_one({'_id': ObjectId(expense_id), 'user_id': user_id})


def get_monthly_totals(user_id):
    """Get monthly spending totals."""
    db = get_mongo_db()
    pipeline = [
        {'$match': {'user_id': user_id}},
        {'$addFields': {
            'month': {'$substr': ['$date', 0, 7]}
        }},
        {'$group': {
            '_id': '$month',
            'total': {'$sum': '$amount'}
        }},
        {'$sort': {'_id': 1}},
        {'$project': {
            '_id': 0,
            'month': '$_id',
            'total': 1
        }}
    ]
    return list(db.expenses.aggregate(pipeline))


def get_category_totals(user_id):
    """Get total spending per category."""
    db = get_mongo_db()
    pipeline = [
        {'$match': {'user_id': user_id}},
        {'$group': {
            '_id': '$category',
            'total': {'$sum': '$amount'}
        }},
        {'$sort': {'total': -1}},
        {'$project': {
            '_id': 0,
            'category': '$_id',
            'total': 1
        }}
    ]
    return list(db.expenses.aggregate(pipeline))


def get_total_spending(user_id):
    """Get total spending for a user."""
    db = get_mongo_db()
    pipeline = [
        {'$match': {'user_id': user_id}},
        {'$group': {
            '_id': None,
            'total': {'$sum': '$amount'}
        }}
    ]
    result = list(db.expenses.aggregate(pipeline))
    return result[0]['total'] if result else 0


def get_current_month_spending(user_id):
    """Get total spending for the current month."""
    db = get_mongo_db()
    current_month = datetime.now().strftime('%Y-%m')
    pipeline = [
        {'$match': {
            'user_id': user_id,
            'date': {'$regex': f'^{current_month}'}
        }},
        {'$group': {
            '_id': None,
            'total': {'$sum': '$amount'}
        }}
    ]
    result = list(db.expenses.aggregate(pipeline))
    return result[0]['total'] if result else 0
