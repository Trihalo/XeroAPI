from flask import Flask, request, jsonify
import sys
import os
from flask_cors import CORS
import jwt
from datetime import datetime, timedelta, timezone
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas_gbq
from google.cloud import firestore
from datetime import datetime
import pytz

from dotenv import load_dotenv
load_dotenv()

db = firestore.Client.from_service_account_json(
    "service-account.json",
    project="futureyou-458212",
    database="futureyou"
)

app = Flask(__name__)
CORS(app)  # Allow CORS for local frontend development

# Dummy user database
users = {
    "leo":   { "password": "leo", "name": "Leo Shi", "role": "admin" },
    "bob":   { "password": "bob", "name": "Bob Bob", "role": "user" },
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
target_table_id = "MonthlyTargets"

STAGING_TABLE = f"{project_id}.{recruiter_dataset_id}.{staging_table_id}"
MAIN_TABLE = f"{project_id}.{recruiter_dataset_id}.{table_id}"
REVENUE_TABLE = f"{project_id}.{revenue_dataset_id}.{revenue_table_id}"
TARGET_TABLE = f"{project_id}.{recruiter_dataset_id}.{target_table_id}"


credentials = service_account.Credentials.from_service_account_file(
    key_path, 
    scopes=["https://www.googleapis.com/auth/bigquery"]
)
client = bigquery.Client(credentials=credentials, project=project_id)

# Convert to AEST
aest = pytz.timezone("Australia/Sydney")

@app.route("/login", methods=["POST"])
def login():
    revenue_table_last_modified_time = client.get_table(REVENUE_TABLE).modified
    revenue_table_last_modified_time_local = revenue_table_last_modified_time.astimezone(aest)
    formatted_time = revenue_table_last_modified_time_local.strftime("%d/%m/%Y %-I:%M%p").lower()
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
            "name": user["name"],
            "revenue_table_last_modified_time": formatted_time
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
            "message": f"Updated forecast records for {recruiterName}."
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
    
    
@app.route("/forecasts/weekly", methods=["GET"])
def get_forecast_weekly():
    fy = request.args.get("fy")
    month = request.args.get("month")
    uploadWeek = request.args.get("uploadWeek")

    if not fy or not month:
        return jsonify({"error": "Missing 'fy' or 'month' parameter"}), 400

    query = f"""
        SELECT
        name,
        week,
        SUM(IFNULL(revenue, 0) + IFNULL(tempRevenue, 0)) AS total_revenue,
        uploadWeek
        FROM `{MAIN_TABLE}`
        WHERE fy = @fy AND month = @month AND uploadWeek = @uploadWeek
        GROUP BY name, week, uploadWeek
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("fy", "STRING", fy),
            bigquery.ScalarQueryParameter("month", "STRING", month),
            bigquery.ScalarQueryParameter("uploadWeek", "STRING", uploadWeek),
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


@app.route("/monthly-targets", methods=["POST"])
def submit_monthly_target():
    data = request.get_json()

    fy = data.get("FinancialYear")
    month = data.get("Month")
    target = data.get("Target")
    upload_user = data.get("uploadUser")
    raw_timestamp = data.get("uploadTimestamp")  # ISO string from frontend

    if not fy or not month or target is None or not upload_user or not raw_timestamp:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        utc_dt = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
        local_dt = utc_dt.astimezone(aest)
        formatted_timestamp = local_dt.strftime("%-I:%M%p %-d/%-m/%Y").lower()

        table_ref = client.dataset("RecruiterForecasts").table("MonthlyTargets")
        table = client.get_table(table_ref)

        row = {
            "FinancialYear": fy,
            "Month": month,
            "Target": target,
            "uploadUser": upload_user,
            "uploadTimestamp": formatted_timestamp,
            "uploadTimeRaw": raw_timestamp,
        }

        errors = client.insert_rows_json(table, [row])
        if errors:
            print("❌ Insert errors:", errors)
            return jsonify({"success": False, "error": str(errors)}), 500

        return jsonify({"success": True, "message": "Monthly target submitted."})
    except Exception as e:
        print("❌ BigQuery error:", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/monthly-targets", methods=["GET"])
def get_monthly_targets():
    fy = request.args.get("fy")
    if not fy:
        return jsonify({"error": "Missing 'fy'"}), 400

    query = f"""
    SELECT Month, Target, uploadTimestamp, uploadTimeRaw, uploadUser
    FROM `{TARGET_TABLE}`
    WHERE FinancialYear = @fy
    QUALIFY ROW_NUMBER() OVER (PARTITION BY Month ORDER BY uploadTimeRaw DESC) = 1
    ORDER BY
      CASE
        WHEN Month = 'Jan' THEN 1
        WHEN Month = 'Feb' THEN 2
        WHEN Month = 'Mar' THEN 3
        WHEN Month = 'Apr' THEN 4
        WHEN Month = 'May' THEN 5
        WHEN Month = 'Jun' THEN 6
        WHEN Month = 'Jul' THEN 7
        WHEN Month = 'Aug' THEN 8
        WHEN Month = 'Sep' THEN 9
        WHEN Month = 'Oct' THEN 10
        WHEN Month = 'Nov' THEN 11
        WHEN Month = 'Dec' THEN 12
      END
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("fy", "STRING", fy)]
    )

    try:
        results = client.query(query, job_config=job_config).result()
        return jsonify([dict(row) for row in results])
    except Exception as e:
        print("❌ BigQuery error:", e)
        return jsonify({"error": str(e)}), 500
    
    
# ============ FIRESTORE FUNCTIONS ==================
@app.route("/recruiters", methods=["GET"])
def get_recruiters():
    try:
        docs = db.collection("recruiters").stream()
        return jsonify([
            {"id": doc.id, **doc.to_dict()} for doc in docs
        ])
    except Exception as e:
        print("❌ Firestore error:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/recruiters", methods=["POST"])
def add_recruiter():
    data = request.json
    name = data.get("name")
    area = data.get("area")
    if not name or not area:
        return jsonify({"error": "Missing name or area"}), 400

    try:
        doc_ref = db.collection("recruiters").add({"name": name, "area": area})
        return jsonify({"success": True, "id": doc_ref[1].id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/recruiters/<id>", methods=["DELETE"])
def delete_recruiter(id):
    try:
        db.collection("recruiters").document(id).delete()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/areas", methods=["GET"])
def get_areas():
    try:
        docs = db.collection("areas").stream()
        return jsonify([
            {"id": doc.id, **doc.to_dict()} for doc in docs
        ])
    except Exception as e:
        print("❌ Firestore error:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/areas/<id>", methods=["PATCH"])
def update_area(id):
    data = request.get_json()
    headcount = data.get("headcount")

    if headcount is None:
        return jsonify({"error": "Missing 'headcount'"}), 400

    try:
        db.collection("areas").document(id).update({"headcount": float(headcount)})
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500





if __name__ == "__main__":
    app.run(debug=True, port=8080)
