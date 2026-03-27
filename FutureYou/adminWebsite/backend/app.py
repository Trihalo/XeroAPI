import sys
import os
import tempfile
import importlib.util
from datetime import datetime

from flask import Flask, jsonify, request, send_file, after_this_request
from flask_cors import CORS
from dotenv import load_dotenv

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


# ── Dev server ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081, debug=True)
