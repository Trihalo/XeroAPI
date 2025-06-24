# import_users.py

from google.cloud import firestore

# Authenticate using service account key

db = firestore.Client()

def create_user(username, data):
    db.collection("users").document(username).set(data)

# Your mock users
USER_DATABASE = {
    # STRUCTURE: "test": {"password": "password", "name": "name", "email": "email", "username": "username"}
    # "leo": {"password": "leoshii111", "name": "leo", "email": "leo@trihalo.com.au", "username": "leo"}
    "billy": {"password": "billy", "name": "billy", "email": "billy@trihalo.com.au", "username": "billy"},
    "burton": {"password": "burton", "name": "burton", "email": "burton@trihalo.com.au", "username": "burton"},
    "edward": {"password": "edward", "name": "edward", "email": "edward@trihalo.com.au", "username": "edward"},
    "silvia": {"password": "BlueTiger75%", "name": "silvia", "email": "silvia@trihalo.com.au", "username": "silvia"},
}

# Upload them to Firestore
for username, data in USER_DATABASE.items():
    create_user(username, data)
    print(f"Added user: {username}")
