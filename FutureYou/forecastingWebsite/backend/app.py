from flask import Flask, request, jsonify
import sys
import os
from flask_cors import CORS
from functools import wraps
import jwt
from datetime import datetime, timedelta, timezone
from google.cloud import bigquery
from google.cloud import firestore
from google.oauth2 import service_account
import pandas_gbq
from datetime import datetime
import pytz
from dotenv import load_dotenv
load_dotenv()

project_id = "futureyou-458212"
FIRESTORE_KEY_PATH = os.getenv("FUTUREYOU_FIRESTOREACCESS")
BQACCESS_KEY_PATH = os.getenv("FUTUREYOU_BQACCESS")

# Firestore Client
if FIRESTORE_KEY_PATH and os.path.exists(FIRESTORE_KEY_PATH):
    print("🔐 Using Firestore service account file for local dev")
    db = firestore.Client.from_service_account_json(FIRESTORE_KEY_PATH, project=project_id, database="futureyou")
else:
    print("✅ Using default Firestore credentials (e.g., Cloud Run)")
    db = firestore.Client(project=project_id, database="futureyou")

# BigQuery Client
if BQACCESS_KEY_PATH and os.path.exists(BQACCESS_KEY_PATH):
    print("🔐 Using BigQuery service account file for local dev")
    credentials = service_account.Credentials.from_service_account_file(
        BQACCESS_KEY_PATH,
        scopes=["https://www.googleapis.com/auth/bigquery"]
    )
    client = bigquery.Client(credentials=credentials, project=project_id)
else:
    print("✅ Using default BigQuery credentials (e.g., Cloud Run)")
    client = bigquery.Client(project=project_id)


app = Flask(__name__)
CORS(app)  # Allow CORS for local frontend development

# 🔐 Secret key for encoding the token
SECRET_KEY = os.getenv("FUTUREYOU_FORECAST_SECRET_KEY")

# Path to your service account key file
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

aest = pytz.timezone("Australia/Sydney")

@app.route("/", methods=["GET"])
def index():
    return "✅ Forecasting API is live @leoshi@future-you.com.au", 200


@app.route("/login", methods=["POST"])
def login():
    # Get revenue table's last modified time (BigQuery)
    try:
        revenue_table_last_modified_time = client.get_table(REVENUE_TABLE).modified
        revenue_table_last_modified_time_local = revenue_table_last_modified_time.astimezone(aest)
        formatted_time = revenue_table_last_modified_time_local.strftime("%d/%m/%Y %-I:%M%p").lower()
    except Exception as e:
        return jsonify({"success": False, "error": f"BigQuery error: {str(e)}"}), 500

    # Get login payload
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({
            "success": False,
            "error": "Username and password are required."
        }), 400

    try:
        users = db.collection("users").where("username", "==", username).limit(1).stream()
        user_doc = next(users, None)
        if user_doc is None:
            return jsonify({"success": False, "error": "Invalid username or password."}), 401
        user = user_doc.to_dict()
        if user.get("password") != password:
            return jsonify({"success": False, "error": "Invalid username or password."}), 401

        # ✅ Create JWT token
        payload = {
            "username": username,
            "role": user.get("role"),
            "name": user.get("name"),
            "exp": datetime.now(timezone.utc) + timedelta(hours=2)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

        return jsonify({
            "success": True,
            "token": token,
            "role": user.get("role"),
            "name": user.get("name"),
            "revenue_table_last_modified_time": formatted_time
        })

    except Exception as e:
        return jsonify({"success": False, "error": f"Firestore error: {str(e)}"}), 500


@app.route("/change-password", methods=["POST"])
def change_password():
    data = request.get_json()
    username = data.get("username")
    old_password = data.get("oldPassword")
    new_password = data.get("newPassword")

    if not username or not old_password or not new_password:
        return jsonify({
            "success": False,
            "error": "Username, old password, and new password are required."
        }), 400

    try:
        users = db.collection("users").where("username", "==", username).limit(1).stream()
        user_doc = next(users, None)

        if user_doc is None:
            return jsonify({"success": False, "error": "User not found."}), 404

        user = user_doc.to_dict()

        if user.get("password") != old_password:
            return jsonify({"success": False, "error": "Old password is incorrect."}), 403

        db.collection("users").document(user_doc.id).update({
            "password": new_password
        })

        return jsonify({
            "success": True,
            "message": "Password changed successfully."
        })

    except Exception as e:
        return jsonify({"success": False, "error": f"Server error: {str(e)}"}), 500

    
def get_token_payload(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Get token from Authorization header: Bearer <token>
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        if not token:
            return jsonify({"error": "Token is missing!"}), 401

        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.user = data  # Attach user info to request context
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired!"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token!"}), 401

        return f(*args, **kwargs)

    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            if data.get("role") != "admin":
                return jsonify({"error": "Admins only."}), 403
        except:
            return jsonify({"error": "Invalid or missing token."}), 401
        return f(*args, **kwargs)
    return decorated

    
@app.route("/forecasts", methods=["POST"])
@token_required
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
@token_required
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
@token_required
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
@token_required
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
@token_required
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
@token_required
@admin_required
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
@token_required
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
    
    
@app.route("/legends", methods=["GET"])
@token_required
def get_consultant_margins():
    fy = request.args.get("fy")
    if not fy:
        return jsonify({"error": "Missing 'fy'"}), 400

    # Query 1: Consultant totals
    query1 = """
    SELECT 
      Consultant,
      SUM(Margin) AS TotalMargin,
      Quarter
    FROM `futureyou-458212.InvoiceData.InvoiceEnquiry`
    WHERE FinancialYear = @fy
    GROUP BY Consultant, Quarter
    ORDER BY TotalMargin DESC
    """

    # Query 2: Consultant + Type totals
    query2 = """
    SELECT 
      Consultant,
      Type,
      SUM(Margin) AS TotalMargin,
      Quarter
    FROM `futureyou-458212.InvoiceData.InvoiceEnquiry`
    WHERE FinancialYear = @fy
    GROUP BY Consultant, Type, Quarter
    ORDER BY Consultant, Type, Quarter
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("fy", "STRING", fy)]
    )

    try:
        # Run both queries
        results1 = client.query(query1, job_config=job_config).result()
        results2 = client.query(query2, job_config=job_config).result()

        # Build the response
        response = {
            "consultantTotals": [dict(row) for row in results1],
            "consultantTypeTotals": [dict(row) for row in results2],
        }

        return jsonify(response)

    except Exception as e:
        print("❌ BigQuery error:", e)
        return jsonify({"error": str(e)}), 500

    
# ============ FIRESTORE FUNCTIONS ==================
@app.route("/recruiters", methods=["GET"])
@token_required
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
@token_required
@admin_required
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
@token_required
@admin_required
def delete_recruiter(id):
    try:
        db.collection("recruiters").document(id).delete()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/areas", methods=["GET"])
@token_required
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
@token_required
@admin_required
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
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
    
