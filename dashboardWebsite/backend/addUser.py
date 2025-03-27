# import_users.py

from google.cloud import firestore

# Authenticate using service account key

db = firestore.Client()

def create_user(username, data):
    db.collection("users").document(username).set(data)

# Your mock users
USER_DATABASE = {
    # STRUCTURE: "test": {"password": "password", "name": "name", "email": "email", "username": "username"}
}

# Upload them to Firestore
for username, data in USER_DATABASE.items():
    create_user(username, data)
    print(f"Added user: {username}")
