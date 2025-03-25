# backend/user_database.py

# Mock database (replace with real database connection in production)
USER_DATABASE = {
    "admin": {"password": "1234", "name": "Leo", "email": "leo@trihalo.com.au", "username": "admin" },
    "user1": {"password": "password123", "name": "John Doe", "email": "john@example.com", "username": "user1" },
}

def get_user(username):
    """Retrieve user details from the database."""
    return USER_DATABASE.get(username)