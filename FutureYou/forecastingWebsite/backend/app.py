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
recruiter_dataset_id = "RecruiterForecasts"
revenue_dataset_id = "InvoiceData"
revenue_table_id = "InvoiceEnquiry"
table_id = "RecruiterForecasts"
staging_table_id = "StagingTable"

STAGING_TABLE = f"{project_id}.{recruiter_dataset_id}.{staging_table_id}"
MAIN_TABLE = f"{project_id}.{recruiter_dataset_id}.{table_id}"
REVENUE_TABLE = f"{project_id}.{revenue_dataset_id}.{revenue_table_id}"

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
        forecasts = data.get("forecasts")
        recruiterName = forecasts[0]["name"] if forecasts else None

        # ✅ Add "key" to each row
        for entry in forecasts:
            entry["key"] = f"{entry['fy']}:{entry['month']}:{entry['week']}:{entry['name']}"
            try:
                entry["revenue"] = int(entry["revenue"]) if entry["revenue"] else 0
            except (ValueError, TypeError):
                entry["revenue"] = 0

        print(f"✅ Received {len(forecasts)} rows for {recruiterName}.")

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
            "message": f"Uploaded {len(forecasts)} records for {recruiterName}."
        })

    except Exception as e:
        print("❌ Error:", str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/forecasts/<recruiter_name>", methods=["GET"])
def get_forecast_for_recruiter(recruiter_name):
    fy = request.args.get("fy")
    month = request.args.get("month")

    if not fy or not month:
        return jsonify({"error": "Missing 'fy' or 'month' parameter"}), 400

    query = f"""
        SELECT fy, month, week, `range`, revenue, notes, name
        FROM `{MAIN_TABLE}`
        WHERE name = @name AND fy = @fy AND month = @month
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("name", "STRING", recruiter_name),
            bigquery.ScalarQueryParameter("fy", "STRING", fy),
            bigquery.ScalarQueryParameter("month", "STRING", month),
        ]
    )

    try:
        results = client.query(query, job_config=job_config).result()
        rows = [dict(row) for row in results]
        return jsonify(rows)
    except Exception as e:
        print("❌ BigQuery error:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/forecasts/view", methods=["GET"])
def get_forecast_summary():
    fy = request.args.get("fy")
    month = request.args.get("month")

    if not fy or not month:
        return jsonify({"error": "Missing 'fy' or 'month' parameter"}), 400

    query = f"""
        SELECT name, week, SUM(revenue) as total_revenue
        FROM `{MAIN_TABLE}`
        WHERE fy = @fy AND month = @month
        GROUP BY name, week
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("fy", "STRING", fy),
            bigquery.ScalarQueryParameter("month", "STRING", month),
        ]
    )

    try:
        results = client.query(query, job_config=job_config).result()
        data = [dict(row) for row in results]
        return jsonify(data)
    except Exception as e:
        print("❌ BigQuery error:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/invoices", methods=["GET"])
def get_invoices_for_month():
    fy = request.args.get("fy")
    month = request.args.get("month")

    if not fy or not month:
        return jsonify({"error": "Missing 'fy' or 'month'"}), 400

    query = f"""
        SELECT *
        FROM `{REVENUE_TABLE}`
        WHERE FutureYouMonth = @month AND FinancialYear = @fy
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("month", "STRING", month),
            bigquery.ScalarQueryParameter("fy", "STRING", fy),
        ]
    )

    try:
        rows = client.query(query, job_config=job_config).result()
        data = [dict(row) for row in rows]
        return jsonify(data)
    except Exception as e:
        print("❌ BigQuery error:", e)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=8080)
