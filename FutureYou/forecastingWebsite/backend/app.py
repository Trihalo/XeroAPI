from flask import Flask, request, jsonify
import sys
import os
from flask_cors import CORS
import jwt
from datetime import datetime, timedelta, timezone
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas_gbq
from datetime import datetime
import pytz

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

        # ✅ Add "key" and sanitize fields
        for entry in forecasts:
            entry["key"] = f"{entry['fy']}:{entry['month']}:{entry['week']}:{entry['name']}"
            entry["revenue"] = int(entry.get("revenue", 0) or 0)
            entry["tempRevenue"] = int(entry.get("tempRevenue", 0) or 0)
            entry["uploadMonth"] = entry.get("uploadMonth", "")
            entry["uploadWeek"] = int(entry.get("uploadWeek", 0) or 0)
            entry["uploadYear"] = entry.get("uploadYear", 0) or 0
            
            aest = pytz.timezone("Australia/Sydney")
            entry["uploadTimestamp"] = datetime.now(aest).strftime("%-I:%M%p %-d/%-m/%Y").lower()
            entry['uploadUser'] = entry.get("uploadUser", "Kermit the Frog")


        print(f"✅ Received {len(forecasts)} rows for {recruiterName}.")

        insert_errors = client.insert_rows_json(STAGING_TABLE, forecasts)
        if insert_errors:
            print("❌ BigQuery insert errors:", insert_errors)
            return jsonify({"error": insert_errors}), 400

        merge_query = f"""
            MERGE `{MAIN_TABLE}` T
            USING `{STAGING_TABLE}` S
            ON T.key = S.key
            AND T.uploadMonth = S.uploadMonth
            AND T.uploadWeek = S.uploadWeek
            AND T.uploadYear = S.uploadYear
            WHEN MATCHED THEN
            UPDATE SET
                fy = S.fy,
                month = S.month,
                week = S.week,
                `range` = S.`range`,
                revenue = S.revenue,
                tempRevenue = S.tempRevenue,
                notes = S.notes,
                name = S.name,
                uploadMonth = S.uploadMonth,
                uploadWeek = S.uploadWeek,
                uploadYear = S.uploadYear,
                uploadTimestamp = S.uploadTimestamp,
                uploadUser = S.uploadUser
            WHEN NOT MATCHED THEN
            INSERT (`key`, fy, month, week, `range`, revenue, tempRevenue, notes, name, uploadMonth, uploadWeek, uploadYear, uploadTimestamp, uploadUser)
            VALUES (S.`key`, S.fy, S.month, S.week, S.`range`, S.revenue, S.tempRevenue, S.notes, S.name, S.uploadMonth, S.uploadWeek, S.uploadYear, S.uploadTimestamp, S.uploadUser)
        """

        client.query(merge_query).result()

        return jsonify({
            "success": True,
            "message": f"Uploaded {len(forecasts)} records for {recruiterName}."
        })

    except Exception as e:
        print("❌ Error:", str(e))
        return jsonify({"error": str(e)}), 500


from collections import defaultdict

@app.route("/forecasts/<recruiter_name>", methods=["GET"])
def get_forecast_for_recruiter(recruiter_name):
    fy = request.args.get("fy")
    month = request.args.get("month")

    if not fy or not month:
        return jsonify({"error": "Missing 'fy' or 'month' parameter"}), 400

    query = f"""
        SELECT fy, month, week, `range`, revenue, tempRevenue, notes, name,
               uploadMonth, uploadWeek, uploadYear, uploadTimestamp, uploadUser
        FROM `{MAIN_TABLE}`
        WHERE name = @name AND fy = @fy AND month = @month
        ORDER BY week ASC, uploadWeek DESC, uploadTimestamp DESC
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("name", "STRING", recruiter_name),
            bigquery.ScalarQueryParameter("fy", "STRING", fy),
            bigquery.ScalarQueryParameter("month", "STRING", month),
        ]
    )

    try:
        results = list(client.query(query, job_config=job_config).result())
        week_map = defaultdict(list)
        for row in results:
            week_map[row.week].append(dict(row))

        final_result = []
        for week in sorted(week_map.keys()):
            if week_map[week]:
                final_result.append(week_map[week][0])  # latest entry
            else:
                # ⬇️ Fallback: use most recent from earlier weeks
                fallback = None
                for w in range(week - 1, 0, -1):
                    if week_map[w]:
                        fallback = week_map[w][0]
                        break
                if fallback:
                    fallback_copy = fallback.copy()
                    fallback_copy["week"] = week
                    fallback_copy["range"] = f""
                    final_result.append(fallback_copy)
                else:
                    # ❌ No data at all
                    final_result.append({
                        "fy": fy,
                        "month": month,
                        "week": week,
                        "range": "",
                        "revenue": 0,
                        "tempRevenue": 0,
                        "notes": "",
                        "name": recruiter_name,
                        "uploadMonth": "",
                        "uploadWeek": 0,
                        "uploadYear": 0,
                        "uploadTimestamp": "",
                        "uploadUser": "",
                    })

        return jsonify(final_result)

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
        SELECT
        name,
        week,
        SUM(IFNULL(revenue, 0) + IFNULL(tempRevenue, 0)) AS total_revenue,
        uploadWeek
        FROM `{MAIN_TABLE}`
        WHERE fy = @fy AND month = @month
        GROUP BY name, week, uploadWeek
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
