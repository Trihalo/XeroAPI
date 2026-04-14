import os
import sys
from google.cloud import firestore
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Import the old mapping to seed the DB
from databaseMappings import consultant_area_mapping

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
credentials_path = os.getenv("FUTUREYOU_FIRESTOREACCESS")
if not credentials_path:
    print("No credentials found")
    sys.exit(1)

db = firestore.Client.from_service_account_json(
    credentials_path, project="futureyou-458212", database="futureyou"
)

recruiters_ref = db.collection("recruiters")
docs = list(recruiters_ref.stream())

updated_count = 0
existing_tracking_names = set()

for d in docs:
    data = d.to_dict()
    updates = {}
    if "active" not in data:
        updates["active"] = True
    
    # Try to find their xeroTrackingName from the legacy mapping
    name = data.get("name", "")
    legacy_key = ""
    if "xeroTrackingName" not in data:
        for k, v in consultant_area_mapping.items():
            if name.lower() in k.lower():
                legacy_key = k
                break
        
        if legacy_key:
            updates["xeroTrackingName"] = legacy_key
            existing_tracking_names.add(legacy_key)
        else:
            updates["xeroTrackingName"] = ""
    else:
        existing_tracking_names.add(data.get("xeroTrackingName"))
    
    if updates:
        d.reference.update(updates)
        updated_count += 1

print(f"Updated {updated_count} existing recruiters in Firestore.")

missing_count = 0
for k, v in consultant_area_mapping.items():
    if k not in existing_tracking_names:
        name_parts = k.split(" ", 1)
        name = name_parts[1] if len(name_parts) > 1 else k
        
        recruiters_ref.add({
            "name": name,
            "area": v,
            "headcount": 0,
            "active": False,
            "xeroTrackingName": k
        })
        missing_count += 1

print(f"Added {missing_count} historical mapping keys as inactive recruiters.")
