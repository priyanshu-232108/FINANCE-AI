import os
from app import app
from database import mongo_create_user, get_mongo_db
from werkzeug.security import generate_password_hash

app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False
client = app.test_client()

db = get_mongo_db()

# Create test user
pw = generate_password_hash('test1234')
user = mongo_create_user('testuser2', 'test2@example.com', pw)
user_id = str(user['_id'])

# Simulate login
with client.session_transaction() as sess:
    sess['user_id'] = user_id
    sess['username'] = 'testuser2'

# Test add expense endpoint
response = client.post('/add_expense', data={
    'amount': '500',
    'category': 'Food',
    'description': 'Test Expense via Script',
    'date': '2026-04-19'
})

print('Add Expense Status Code:', response.status_code)
print('Location Header (Redirect):', response.headers.get('Location'))

# Verify in database
expenses = list(db.expenses.find({'user_id': user_id}))
print('Expenses found in DB:', len(expenses))
if expenses:
    exp = expenses[0]
    print(f"Details - Amount: {exp['amount']}, Category: {exp['category']}, Date: {exp['date']}")

# Test delete expense endpoint
if expenses:
    expense_id = str(expenses[0]['_id'])
    del_response = client.post(f'/delete_expense/{expense_id}')
    print('Delete Expense Status Code:', del_response.status_code)
    expenses_after = list(db.expenses.find({'user_id': user_id}))
    print('Expenses found in DB after delete:', len(expenses_after))

# Cleanup
db.users.delete_one({'_id': user['_id']})
db.expenses.delete_many({'user_id': user_id})
print('Test completed and cleaned up.')
