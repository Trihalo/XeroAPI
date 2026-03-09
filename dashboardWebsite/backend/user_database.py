# backend/user_database.py
import os
from google.cloud import firestore

_db = None

def _get_db():
    global _db
    if _db is None:
        _db = firestore.Client(project=os.getenv("GCP_PROJECT_ID"))
    return _db

def get_user(username):
    """Retrieve user details from Firestore."""
    doc_ref = _get_db().collection("users").document(username)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None
