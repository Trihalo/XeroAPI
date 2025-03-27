# backend/user_database.py
from google.cloud import firestore

db = firestore.Client()

def get_user(username):
    """Retrieve user details from Firestore."""
    doc_ref = db.collection("users").document(username)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None
