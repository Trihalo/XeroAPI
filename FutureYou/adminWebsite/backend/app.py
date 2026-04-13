import sys
import os
import tempfile
import importlib.util
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from functools import wraps

import jwt
import pytz
from flask import Flask, jsonify, request, send_file, after_this_request
from flask_cors import CORS
from dotenv import load_dotenv
from google.cloud import bigquery, firestore

load_dotenv()

# ── Path setup ───────────────────────────────────────────────────────────────
REPO_ROOT       = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
FUTUREYOU_DIR   = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TALENT_MAP_DIR  = os.path.join(REPO_ROOT, "FutureYou", "bullhorn", "talentMapping")

for p in [REPO_ROOT, FUTUREYOU_DIR, TALENT_MAP_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ── Flask setup ──────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# ── Forecasting — FutureYou GCP project ──────────────────────────────────────
FORECAST_PROJECT_ID = "futureyou-458212"
FORECAST_SECRET_KEY = os.getenv("FUTUREYOU_FORECAST_SECRET_KEY")
AEST = pytz.timezone("Australia/Sydney")

FIRESTORE_KEY_PATH = os.getenv("FUTUREYOU_FIRESTOREACCESS")
BQACCESS_KEY_PATH  = os.getenv("FUTUREYOU_BQACCESS")

if FIRESTORE_KEY_PATH and os.path.exists(FIRESTORE_KEY_PATH):
    forecast_db = firestore.Client.from_service_account_json(
        FIRESTORE_KEY_PATH, project=FORECAST_PROJECT_ID, database="futureyou"
    )
else:
    forecast_db = firestore.Client(project=FORECAST_PROJECT_ID, database="futureyou")

if BQACCESS_KEY_PATH and os.path.exists(BQACCESS_KEY_PATH):
    from google.oauth2 import service_account as _sa
    _creds = _sa.Credentials.from_service_account_file(
        BQACCESS_KEY_PATH, scopes=["https://www.googleapis.com/auth/bigquery"]
    )
    forecast_bq = bigquery.Client(credentials=_creds, project=FORECAST_PROJECT_ID)
else:
    forecast_bq = bigquery.Client(project=FORECAST_PROJECT_ID)

# BQ table references
_RF  = f"{FORECAST_PROJECT_ID}.RecruiterForecasts"
FC_STAGING = f"{_RF}.StagingTable"
FC_MAIN    = f"{_RF}.RecruiterForecasts"
FC_REVENUE = f"{FORECAST_PROJECT_ID}.InvoiceData.InvoiceEnquiry"
FC_TARGETS = f"{_RF}.MonthlyTargets"


# ── Forecasting auth helpers ──────────────────────────────────────────────────
def fc_token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ").strip()
        if not token:
            return jsonify({"error": "Token is missing"}), 401
        try:
            data = jwt.decode(token, FORECAST_SECRET_KEY, algorithms=["HS256"])
            request.fc_user = data
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated


def fc_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ").strip()
        try:
            data = jwt.decode(token, FORECAST_SECRET_KEY, algorithms=["HS256"])
            if data.get("role") != "admin":
                return jsonify({"error": "Admins only"}), 403
        except Exception:
            return jsonify({"error": "Invalid or missing token"}), 401
        return f(*args, **kwargs)
    return decorated


# ── Annual Leave ─────────────────────────────────────────────────────────────
@app.route("/annual-leave/generate", methods=["POST"])
def generate_annual_leave():
    try:
        from xeroAuthHelper import getXeroAccessToken
        from xeroAuth import XeroTenants
        from fetchFYAnnualLeave import (
            fetchEmployeeList,
            fetchAllEmployeeAnnualLeave,
            fetchLeaveApplications,
            build_leave_email,
        )

        access_token = getXeroAccessToken("FUTUREYOU_RECRUITMENT")
        tenant_id    = XeroTenants(access_token)
        employees    = fetchEmployeeList(access_token, tenant_id)

        if not employees:
            return jsonify({"error": "No employees returned from Xero"}), 500

        annual_leave_df      = fetchAllEmployeeAnnualLeave(access_token, tenant_id, employees)
        leave_applications_df = fetchLeaveApplications(access_token, tenant_id, employees)
        html                 = build_leave_email(annual_leave_df, leave_applications_df)

        return jsonify({"html": html})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Talent Map ────────────────────────────────────────────────────────────────
@app.route("/talent-map/generate", methods=["POST"])
def generate_talent_map():
    try:
        from generateTalentMapWord import read_excel, build_word

        if "file" not in request.files:
            return jsonify({"error": "No Excel file uploaded"}), 400

        file      = request.files["file"]
        client    = request.form.get("client", "").strip()
        job_title = request.form.get("jobTitle", "").strip()

        if not file.filename or not file.filename.endswith(".xlsx"):
            return jsonify({"error": "Please upload a .xlsx file"}), 400
        if not client:
            return jsonify({"error": "Client name is required"}), 400
        if not job_title:
            return jsonify({"error": "Job title is required"}), 400

        # Save uploaded Excel to a temp file
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_xlsx:
            file.save(tmp_xlsx.name)
            excel_path = tmp_xlsx.name

        # Build the Word doc into a temp file
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_docx:
            docx_path = tmp_docx.name

        logo_path = os.path.join(
            FUTUREYOU_DIR, "forecastingWebsite", "frontend", "public", "fy.png"
        )
        if not os.path.exists(logo_path):
            logo_path = None

        you_logo_path = os.path.join(
            FUTUREYOU_DIR, "forecastingWebsite", "frontend", "public", "fy_you.png"
        )
        if not os.path.exists(you_logo_path):
            you_logo_path = None

        candidates = read_excel(excel_path)
        doc        = build_word(candidates, client, job_title, logo_path, you_logo_path)
        doc.save(docx_path)
        os.unlink(excel_path)

        # Build a descriptive filename
        date_str   = datetime.today().strftime("%b%y")
        safe_corp  = client.replace("/", "-").replace(" ", "")
        safe_title = (
            "".join(c for c in job_title if c.isalnum() or c in " -")[:30]
            .strip()
            .replace(" ", "")
        )
        download_name = f"FYTalentMap_{safe_corp}_{safe_title}_{date_str}.docx"

        @after_this_request
        def cleanup(response):
            try:
                os.unlink(docx_path)
            except OSError:
                pass
            return response

        return send_file(
            docx_path,
            as_attachment=True,
            download_name=download_name,
            mimetype=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Forecasting endpoints ─────────────────────────────────────────────────────

@app.route("/forecasting/login", methods=["POST"])
def fc_login():
    try:
        rev_table = forecast_bq.get_table(FC_REVENUE)
        last_mod  = rev_table.modified.astimezone(AEST)
        fmt_time  = last_mod.strftime("%d/%m/%Y %-I:%M%p").lower()
    except Exception as e:
        return jsonify({"success": False, "error": f"BigQuery error: {str(e)}"}), 500

    data     = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"success": False, "error": "Username and password are required."}), 400

    try:
        users    = forecast_db.collection("users").where("username", "==", username).limit(1).stream()
        user_doc = next(users, None)
        if user_doc is None or user_doc.to_dict().get("password") != password:
            return jsonify({"success": False, "error": "Invalid username or password."}), 401

        user = user_doc.to_dict()
        payload = {
            "username": username,
            "role": user.get("role"),
            "name": user.get("name"),
            "exp": datetime.now(timezone.utc) + timedelta(hours=2),
        }
        token = jwt.encode(payload, FORECAST_SECRET_KEY, algorithm="HS256")
        return jsonify({
            "success": True,
            "token": token,
            "role": user.get("role"),
            "name": user.get("name"),
            "revenue_table_last_modified_time": fmt_time,
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Firestore error: {str(e)}"}), 500


@app.route("/forecasting/change-password", methods=["POST"])
def fc_change_password():
    data         = request.get_json()
    username     = data.get("username")
    old_password = data.get("oldPassword")
    new_password = data.get("newPassword")

    if not username or not old_password or not new_password:
        return jsonify({"success": False, "error": "All fields are required."}), 400

    try:
        users    = forecast_db.collection("users").where("username", "==", username).limit(1).stream()
        user_doc = next(users, None)
        if user_doc is None:
            return jsonify({"success": False, "error": "User not found."}), 404
        if user_doc.to_dict().get("password") != old_password:
            return jsonify({"success": False, "error": "Old password is incorrect."}), 403
        forecast_db.collection("users").document(user_doc.id).update({"password": new_password})
        return jsonify({"success": True, "message": "Password changed successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/forecasting/forecasts", methods=["POST"])
@fc_token_required
def fc_upload_forecasts():
    try:
        forecast_bq.query(f"TRUNCATE TABLE `{FC_STAGING}`").result()
        data         = request.get_json()
        forecasts    = data.get("forecasts", [])
        recruiter    = forecasts[0]["name"] if forecasts else "Unknown"
        upload_user  = getattr(request, "fc_user", {}).get("name", "Unknown User")

        for entry in forecasts:
            entry["key"]            = f"{entry['fy']}:{entry['month']}:{entry['week']}:{entry['name']}"
            entry["revenue"]        = int(entry.get("revenue", 0) or 0)
            entry["tempRevenue"]    = int(entry.get("tempRevenue", 0) or 0)
            entry["uploadMonth"]    = entry.get("uploadMonth", "")
            entry["uploadWeek"]     = int(entry.get("uploadWeek", 0) or 0)
            entry["uploadYear"]     = entry.get("uploadYear", 0) or 0
            entry["uploadTimestamp"] = datetime.now(AEST).strftime("%-I:%M%p %-d/%-m/%Y").lower()
            entry["uploadUser"]     = upload_user

        errors = forecast_bq.insert_rows_json(FC_STAGING, forecasts)
        if errors:
            return jsonify({"error": errors}), 400

        merge_sql = f"""
            MERGE `{FC_MAIN}` T USING `{FC_STAGING}` S
            ON T.key = S.key AND T.uploadMonth = S.uploadMonth
               AND T.uploadWeek = S.uploadWeek AND T.uploadYear = S.uploadYear
            WHEN MATCHED THEN UPDATE SET
                fy=S.fy, month=S.month, week=S.week, `range`=S.`range`,
                revenue=S.revenue, tempRevenue=S.tempRevenue, notes=S.notes,
                name=S.name, uploadMonth=S.uploadMonth, uploadWeek=S.uploadWeek,
                uploadYear=S.uploadYear, uploadTimestamp=S.uploadTimestamp, uploadUser=S.uploadUser
            WHEN NOT MATCHED THEN INSERT
                (`key`,fy,month,week,`range`,revenue,tempRevenue,notes,name,
                 uploadMonth,uploadWeek,uploadYear,uploadTimestamp,uploadUser)
            VALUES (S.`key`,S.fy,S.month,S.week,S.`range`,S.revenue,S.tempRevenue,S.notes,S.name,
                    S.uploadMonth,S.uploadWeek,S.uploadYear,S.uploadTimestamp,S.uploadUser)
        """
        forecast_bq.query(merge_sql).result()
        return jsonify({"success": True, "message": f"Updated forecast for {recruiter}."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/forecasting/forecasts/view", methods=["GET"])
@fc_token_required
def fc_forecast_view():
    fy    = request.args.get("fy")
    month = request.args.get("month")
    if not fy or not month:
        return jsonify({"error": "Missing 'fy' or 'month'"}), 400

    sql = f"""
        SELECT name, week, SUM(IFNULL(revenue,0)+IFNULL(tempRevenue,0)) AS total_revenue, uploadWeek
        FROM `{FC_MAIN}` WHERE fy=@fy AND month=@month GROUP BY name, week, uploadWeek
    """
    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("fy", "STRING", fy),
        bigquery.ScalarQueryParameter("month", "STRING", month),
    ])
    try:
        return jsonify([dict(r) for r in forecast_bq.query(sql, job_config=cfg).result()])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/forecasting/forecasts/weekly", methods=["GET"])
@fc_token_required
def fc_forecast_weekly():
    fy         = request.args.get("fy")
    month      = request.args.get("month")
    upload_week = request.args.get("uploadWeek")
    if not fy or not month:
        return jsonify({"error": "Missing 'fy' or 'month'"}), 400

    sql = f"""
        SELECT name, week, SUM(IFNULL(revenue,0)+IFNULL(tempRevenue,0)) AS total_revenue, uploadWeek
        FROM `{FC_MAIN}` WHERE fy=@fy AND month=@month AND uploadWeek=@uploadWeek
        GROUP BY name, week, uploadWeek
    """
    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("fy", "STRING", fy),
        bigquery.ScalarQueryParameter("month", "STRING", month),
        bigquery.ScalarQueryParameter("uploadWeek", "STRING", upload_week),
    ])
    try:
        return jsonify([dict(r) for r in forecast_bq.query(sql, job_config=cfg).result()])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/forecasting/forecasts/<recruiter_name>", methods=["GET"])
@fc_token_required
def fc_forecast_for_recruiter(recruiter_name):
    fy    = request.args.get("fy")
    month = request.args.get("month")
    if not fy or not month:
        return jsonify({"error": "Missing 'fy' or 'month'"}), 400

    sql = f"""
        SELECT fy, month, week, `range`, revenue, tempRevenue, notes, name,
               uploadMonth, uploadWeek, uploadYear, uploadTimestamp, uploadUser
        FROM `{FC_MAIN}`
        WHERE name=@name AND fy=@fy AND month=@month
        ORDER BY week ASC, uploadWeek DESC, uploadTimestamp DESC
    """
    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("name", "STRING", recruiter_name),
        bigquery.ScalarQueryParameter("fy", "STRING", fy),
        bigquery.ScalarQueryParameter("month", "STRING", month),
    ])
    try:
        results   = list(forecast_bq.query(sql, job_config=cfg).result())
        week_map  = defaultdict(list)
        for row in results:
            week_map[row.week].append(dict(row))

        final = []
        for week in sorted(week_map.keys()):
            if week_map[week]:
                final.append(week_map[week][0])
            else:
                fallback = next(
                    (week_map[w][0] for w in range(week - 1, 0, -1) if week_map[w]), None
                )
                if fallback:
                    entry = {**fallback, "week": week, "range": ""}
                else:
                    entry = {"fy": fy, "month": month, "week": week, "range": "",
                             "revenue": 0, "tempRevenue": 0, "notes": "",
                             "name": recruiter_name, "uploadMonth": "",
                             "uploadWeek": 0, "uploadYear": 0, "uploadTimestamp": "", "uploadUser": ""}
                final.append(entry)
        return jsonify(final)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/forecasting/invoices", methods=["GET"])
@fc_token_required
def fc_invoices():
    fy    = request.args.get("fy")
    month = request.args.get("month")
    if not fy or not month:
        return jsonify({"error": "Missing 'fy' or 'month'"}), 400

    sql = f"SELECT * FROM `{FC_REVENUE}` WHERE FutureYouMonth=@month AND FinancialYear=@fy"
    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("month", "STRING", month),
        bigquery.ScalarQueryParameter("fy", "STRING", fy),
    ])
    try:
        return jsonify([dict(r) for r in forecast_bq.query(sql, job_config=cfg).result()])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/forecasting/monthly-targets", methods=["GET"])
@fc_token_required
def fc_get_targets():
    fy = request.args.get("fy")
    if not fy:
        return jsonify({"error": "Missing 'fy'"}), 400

    sql = f"""
        SELECT Month, Target, uploadTimestamp, uploadTimeRaw, uploadUser
        FROM `{FC_TARGETS}` WHERE FinancialYear=@fy
        QUALIFY ROW_NUMBER() OVER (PARTITION BY Month ORDER BY uploadTimeRaw DESC) = 1
        ORDER BY CASE Month
            WHEN 'Jan' THEN 1 WHEN 'Feb' THEN 2 WHEN 'Mar' THEN 3 WHEN 'Apr' THEN 4
            WHEN 'May' THEN 5 WHEN 'Jun' THEN 6 WHEN 'Jul' THEN 7 WHEN 'Aug' THEN 8
            WHEN 'Sep' THEN 9 WHEN 'Oct' THEN 10 WHEN 'Nov' THEN 11 WHEN 'Dec' THEN 12
        END
    """
    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("fy", "STRING", fy),
    ])
    try:
        return jsonify([dict(r) for r in forecast_bq.query(sql, job_config=cfg).result()])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/forecasting/monthly-targets", methods=["POST"])
@fc_token_required
@fc_admin_required
def fc_submit_target():
    data       = request.get_json()
    fy         = data.get("FinancialYear")
    month      = data.get("Month")
    target     = data.get("Target")
    upload_user = data.get("uploadUser")
    raw_ts     = data.get("uploadTimestamp")

    if not fy or not month or target is None or not upload_user or not raw_ts:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        utc_dt    = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        local_dt  = utc_dt.astimezone(AEST)
        fmt_ts    = local_dt.strftime("%-I:%M%p %-d/%-m/%Y").lower()
        table_ref = forecast_bq.dataset("RecruiterForecasts").table("MonthlyTargets")
        table     = forecast_bq.get_table(table_ref)
        row = {"FinancialYear": fy, "Month": month, "Target": target,
               "uploadUser": upload_user, "uploadTimestamp": fmt_ts, "uploadTimeRaw": raw_ts}
        errors = forecast_bq.insert_rows_json(table, [row])
        if errors:
            return jsonify({"success": False, "error": str(errors)}), 500
        return jsonify({"success": True, "message": "Monthly target submitted."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/forecasting/legends", methods=["GET"])
@fc_token_required
def fc_legends():
    fy = request.args.get("fy")
    if not fy:
        return jsonify({"error": "Missing 'fy'"}), 400

    sql1 = """
        SELECT Consultant, Area, SUM(Margin) AS TotalMargin, Quarter
        FROM `futureyou-458212.InvoiceData.InvoiceEnquiry`
        WHERE FinancialYear=@fy GROUP BY Consultant, Quarter, Area ORDER BY TotalMargin DESC
    """
    sql2 = """
        SELECT Consultant, Area, Type, SUM(Margin) AS TotalMargin, Quarter,
               FutureYouMonth AS MonthName,
               CASE FutureYouMonth
                 WHEN 'Jan' THEN 1 WHEN 'Feb' THEN 2 WHEN 'Mar' THEN 3 WHEN 'Apr' THEN 4
                 WHEN 'May' THEN 5 WHEN 'Jun' THEN 6 WHEN 'Jul' THEN 7 WHEN 'Aug' THEN 8
                 WHEN 'Sep' THEN 9 WHEN 'Oct' THEN 10 WHEN 'Nov' THEN 11 WHEN 'Dec' THEN 12
                 ELSE NULL END AS Month
        FROM `futureyou-458212.InvoiceData.InvoiceEnquiry`
        WHERE FinancialYear=@fy
        GROUP BY Consultant, Area, Type, Quarter, MonthName, Month
        ORDER BY Consultant, Type, Quarter, Month
    """
    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("fy", "STRING", fy),
    ])
    try:
        r1 = forecast_bq.query(sql1, job_config=cfg).result()
        r2 = forecast_bq.query(sql2, job_config=cfg).result()
        return jsonify({
            "consultantTotals":    [dict(r) for r in r1],
            "consultantTypeTotals": [dict(r) for r in r2],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Forecasting Firestore endpoints ───────────────────────────────────────────

@app.route("/forecasting/recruiters", methods=["GET"])
@fc_token_required
def fc_get_recruiters():
    try:
        docs = forecast_db.collection("recruiters").stream()
        return jsonify([{"id": d.id, **d.to_dict()} for d in docs])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/forecasting/recruiters", methods=["POST"])
@fc_token_required
@fc_admin_required
def fc_add_recruiter():
    data = request.get_json()
    name = data.get("name")
    area = data.get("area")
    if not name or not area:
        return jsonify({"error": "Missing name or area"}), 400
    try:
        ref = forecast_db.collection("recruiters").add({"name": name, "area": area})
        return jsonify({"success": True, "id": ref[1].id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/forecasting/recruiters/<doc_id>", methods=["DELETE"])
@fc_token_required
@fc_admin_required
def fc_delete_recruiter(doc_id):
    try:
        forecast_db.collection("recruiters").document(doc_id).delete()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/forecasting/areas", methods=["GET"])
@fc_token_required
def fc_get_areas():
    try:
        docs = forecast_db.collection("areas").stream()
        return jsonify([{"id": d.id, **d.to_dict()} for d in docs])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/forecasting/areas/<doc_id>", methods=["PATCH"])
@fc_token_required
@fc_admin_required
def fc_update_area(doc_id):
    data      = request.get_json()
    headcount = data.get("headcount")
    if headcount is None:
        return jsonify({"error": "Missing 'headcount'"}), 400
    try:
        forecast_db.collection("areas").document(doc_id).update({"headcount": float(headcount)})
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Dev server ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081, debug=True)
