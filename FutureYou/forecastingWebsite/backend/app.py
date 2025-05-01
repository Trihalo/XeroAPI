from flask import Flask, request, jsonify
import sys
import os
from flask_cors import CORS
import jwt
from datetime import datetime, timedelta, timezone
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas_gbq

from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
CORS(app)  # Allow CORS for local frontend development

# Dummy user database
users = {
    "leo":   { "password": "leo", "name": "Leo Shi", "role": "admin" },
    "bob":   { "password": "bob", "role": "user" },
    "corinroberts": { "password": "corin", "name": "Corin Roberts", "role": "admin" },
}

# 🔐 Secret key for encoding the token
SECRET_KEY = "trihalohehe"  # Store this securely in environment variables in production

# Path to your service account key file
key_path = os.getenv("BQACCESS")
project_id = "futureyou-458212"
dataset_id = "RecruiterForecasts"
table_id = "RecruiterForecasts"
staging_table_id = "StagingTable"

STAGING_TABLE = f"{project_id}.{dataset_id}.{staging_table_id}"
MAIN_TABLE = f"{project_id}.{dataset_id}.{table_id}"

credentials = service_account.Credentials.from_service_account_file(
    key_path, 
    scopes=["https://www.googleapis.com/auth/bigquery"]
)
client = bigquery.Client(credentials=credentials, project=project_id)

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({
            "success": False,
            "error": "Username and password are required."
        }), 400

    user = users.get(username)
    if user and user["password"] == password:
        # ✅ Create JWT token
        payload = {
            "username": username,
            "role": user["role"],
            "name": user["name"],
            "exp": datetime.now(timezone.utc) + timedelta(hours=2)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

        return jsonify({
            "success": True,
            "message": f"Welcome, {username}!",
            "token": token,
            "role": user["role"],
            "name": user["name"]
        })

    return jsonify({
        "success": False,
        "error": "Invalid username or password."
    }), 401
    
def get_token_payload(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    
    
@app.route("/forecasts", methods=["POST"])
def test_receive_forecasts():
    try:
        client.query(f"TRUNCATE TABLE `{STAGING_TABLE}`").result()
        data = request.get_json()

        username = data.get("username")
        password = data.get("password")
        forecasts = data.get("forecasts")

        # ✅ Add "key" to each row
        for entry in forecasts:
            entry["key"] = f"{entry['fy']}:{entry['month']}:{entry['week']}:{entry['name']}"
            try:
                entry["revenue"] = int(entry["revenue"]) if entry["revenue"] else 0
            except (ValueError, TypeError):
                entry["revenue"] = 0

        print(f"✅ Received {len(forecasts)} rows from {username}")

        # ✅ Insert into staging table
        insert_errors = client.insert_rows_json(STAGING_TABLE, forecasts)
        if insert_errors:
            print("❌ BigQuery insert errors:", insert_errors)
            return jsonify({"error": insert_errors}), 400

        # ✅ Merge into main table
        merge_query = f"""
        MERGE `{MAIN_TABLE}` T
        USING `{STAGING_TABLE}` S
        ON T.key = S.key
        WHEN MATCHED THEN
          UPDATE SET
            fy = S.fy,
            month = S.month,
            week = S.week,
            `range` = S.`range`,
            revenue = S.revenue,
            notes = S.notes,
            name = S.name
        WHEN NOT MATCHED THEN
        INSERT (`key`, fy, month, week, `range`, revenue, notes, name)
        VALUES (S.`key`, S.fy, S.month, S.week, S.`range`, S.revenue, S.notes, S.name)
        """
        client.query(merge_query).result()

        return jsonify({
            "success": True,
            "message": f"Uploaded & merged {len(forecasts)} records for {username}"
        })

    except Exception as e:
        print("❌ Error:", str(e))
        return jsonify({"error": str(e)}), 500




if __name__ == "__main__":
    app.run(debug=True, port=8080)
