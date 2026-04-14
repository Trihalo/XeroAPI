import os
import sys
from google.cloud import firestore
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
credentials_path = os.getenv("FUTUREYOU_FIRESTOREACCESS")

db = firestore.Client.from_service_account_json(
    credentials_path, project="futureyou-458212", database="futureyou"
)
recruiters_ref = db.collection("recruiters")
docs = list(recruiters_ref.stream())

updated = 0
for d in docs:
    if "headcount" in d.to_dict():
        d.reference.update({"headcount": firestore.DELETE_FIELD})
        updated += 1
        
print(f"Cleaned up headcount fields from {updated} docs.")
