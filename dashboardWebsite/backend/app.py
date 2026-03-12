import os
import base64
import logging
import time
import requests
from dotenv import load_dotenv

# Must load .env BEFORE any Google/user_database imports so env vars are available
load_dotenv()

from flask import Flask, jsonify, request, g
from flask_cors import CORS
from urllib.parse import quote
from user_database import get_user
from google.cloud import firestore

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App & Firestore
# ---------------------------------------------------------------------------
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
db = firestore.Client(project=GCP_PROJECT_ID)

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GITHUB_TOKEN  = os.getenv("GH_PAT")
GITHUB_OWNER  = "Trihalo"
GITHUB_REPO   = "XeroAPI"
BRANCH        = "main"
UPLOAD_FOLDER = "uploads"

WORKFLOWS = {
    "test-email":                        "sendEmail.yml",
    "futureyou-reports":                 "futureYouReports.yml",
    "h2coco-supplier-payment":           "h2cocoSupplierPayment.yml",
    "h2coco-invoice-approver":           "h2cocoDraftInvoices.yml",
    "futureyou-revenue-database":        "futureYouInvoiceRevenue.yml",
    "futureyou-atb-database":            "futureYouATB.yml",
    "flight-risk-invoice-approver":      "flightRiskDraftInvoices.yml",
    "flight-risk-prepayment-allocator":  "flightRiskPrepaymentAllocator.yml",
    "flight-risk-atb":                   "flightRiskAtb.yml",
}

# Workflows that pass name/email as inputs to GitHub Actions
WORKFLOWS_WITH_INPUTS = {
    "sendEmail.yml",
    "futureYouReports.yml",
    "tradeFinance.yml",
    "flightRiskPrepaymentAllocator.yml",
}

BACKEND_API_KEY = os.getenv("BACKEND_API_KEY")

# ---------------------------------------------------------------------------
# Request lifecycle — log every incoming request and its response time
# ---------------------------------------------------------------------------
@app.before_request
def _start_timer():
    g.start_time = time.perf_counter()

@app.after_request
def _log_request(response):
    duration_ms = (time.perf_counter() - g.start_time) * 1000
    log.info(
        "%s %s → %d  (%.0f ms)",
        request.method,
        request.path,
        response.status_code,
        duration_ms,
    )
    return response

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def trigger_github_action(workflow_id: str):
    """Dispatch a GitHub Actions workflow."""
    auth_user = request.json.get("user")
    if not auth_user:
        log.warning("Trigger '%s' rejected — no user data in request", workflow_id)
        return jsonify({"success": False, "message": "No user data provided."}), 400

    user_label = auth_user.get("name", auth_user.get("username", "unknown"))
    log.info("Trigger | '%s' requested by %s (%s)", workflow_id, user_label, auth_user.get("email", "-"))

    url = (
        f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
        f"/actions/workflows/{workflow_id}/dispatches"
    )
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {"ref": BRANCH}
    if workflow_id in WORKFLOWS_WITH_INPUTS:
        payload["inputs"] = {
            "name":  auth_user.get("name"),
            "email": auth_user.get("email"),
        }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
    except requests.Timeout:
        log.error("Trigger | GitHub API timed out for '%s'", workflow_id)
        return jsonify({"success": False, "error": "GitHub API timed out."}), 504
    except requests.RequestException as exc:
        log.error("Trigger | GitHub API request failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500

    if response.status_code in (200, 204):
        log.info("Trigger | '%s' dispatched successfully (HTTP %d)", workflow_id, response.status_code)
        return jsonify({"success": True, "message": f"GitHub Action '{workflow_id}' triggered successfully!"})

    log.error(
        "Trigger | '%s' failed (HTTP %d): %s",
        workflow_id, response.status_code, response.text[:300],
    )
    return jsonify({"success": False, "error": response.json()}), response.status_code

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def home():
    return jsonify({"message": "Trihalo backend is running."})


@app.route("/trigger/<workflow_key>", methods=["POST"])
def trigger_workflow(workflow_key):
    workflow_id = WORKFLOWS.get(workflow_key)
    if not workflow_id:
        log.warning("Trigger | unknown workflow key '%s'", workflow_key)
        return jsonify({"success": False, "error": f"Workflow '{workflow_key}' not found"}), 400
    return trigger_github_action(workflow_id)


@app.route("/test-api", methods=["POST"])
def test_api():
    return jsonify({"success": True, "message": "Test API is working!"})


@app.route("/authenticate", methods=["POST"])
def authenticate():
    try:
        data = request.json or {}
        username = data.get("username", "").strip()
        password = data.get("password", "")

        if not username or not password:
            return jsonify({"success": False, "message": "Missing username or password"}), 400

        log.info("Auth | login attempt for '%s'", username)
        user = get_user(username)

        if user is None:
            log.warning("Auth | user '%s' not found in Firestore", username)
            return jsonify({"success": False, "message": "Invalid username or password"}), 401

        if user.get("password") == password:
            user_data = {k: v for k, v in user.items() if k != "password"}
            log.info("Auth | '%s' authenticated successfully", username)
            return jsonify({"success": True, "message": "Authentication successful", "user": user_data})

        log.warning("Auth | wrong password for '%s'", username)
        return jsonify({"success": False, "message": "Invalid username or password"}), 401

    except Exception as exc:
        log.exception("Auth | unexpected error")
        return jsonify({"success": False, "message": f"Server error: {exc}"}), 500


def _push_file_to_github(file_bytes: bytes, repo_path: str, commit_message: str) -> tuple[bool, str]:
    """Push raw file bytes to a specific path in the GitHub repo. Returns (success, message)."""
    auth_header = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    github_api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{repo_path}"

    # Fetch existing SHA if the file already exists (required for updates)
    existing = requests.get(github_api_url, headers=auth_header, params={"ref": BRANCH}, timeout=15)
    log.info("GitHub GET %s → HTTP %d", repo_path, existing.status_code)

    if existing.status_code == 200:
        sha = existing.json().get("sha")
        log.info("Existing blob SHA: %s", sha)
    elif existing.status_code == 404:
        sha = None
        log.info("File does not exist yet — will create")
    else:
        log.warning("Unexpected GET status %d: %s", existing.status_code, existing.text[:200])
        sha = None

    payload = {
        "message": commit_message,
        "content": base64.b64encode(file_bytes).decode("utf-8"),
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha

    response = requests.put(github_api_url, json=payload, headers=auth_header, timeout=30)
    log.info("GitHub PUT %s → HTTP %d", repo_path, response.status_code)

    if response.status_code in (200, 201):
        resp_data = response.json()
        commit_sha = resp_data.get("commit", {}).get("sha", "unknown")
        commit_url = resp_data.get("commit", {}).get("html_url", "")
        log.info("Commit created: %s  %s", commit_sha[:12], commit_url)
        return True, "OK"

    log.error("GitHub rejected upload (HTTP %d): %s", response.status_code, response.text[:400])
    return False, response.text[:300]


@app.route("/upload-file", methods=["POST"])
def upload_file():
    """
    Upload a file to GitHub.
    Form fields:
      file        — the file itself (required)
      target_path — repo-relative path, e.g. "H2coco/PO.xlsx"
                    Defaults to "uploads/<filename>" if omitted.
    """
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"success": False, "message": "No file selected"}), 400

    target_path = request.form.get("target_path", "").strip()
    if not target_path:
        target_path = f"uploads/{file.filename}"

    log.info("Upload | '%s' → repo path '%s'", file.filename, target_path)

    file_bytes = file.read()
    success, msg = _push_file_to_github(
        file_bytes,
        target_path,
        commit_message=f"Dashboard upload: {target_path}",
    )

    if success:
        log.info("Upload | '%s' pushed successfully", target_path)
        return jsonify({"success": True, "message": f"'{file.filename}' uploaded successfully."})

    log.error("Upload | GitHub rejected '%s': %s", target_path, msg)
    return jsonify({"success": False, "message": f"GitHub upload failed: {msg}"}), 500


@app.route("/file-info", methods=["GET"])
def file_info():
    """
    Return last-commit metadata for a file in the repo.
    Query param: path=H2coco/PO.xlsx
    """
    repo_path = request.args.get("path", "").strip()
    if not repo_path:
        return jsonify({"error": "Missing path param"}), 400

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/commits"
    try:
        resp = requests.get(url, headers=headers, params={"path": repo_path, "per_page": 1}, timeout=10)
    except requests.RequestException as exc:
        log.error("FileInfo | GitHub API error: %s", exc)
        return jsonify({"error": str(exc)}), 500

    if resp.status_code != 200 or not resp.json():
        log.warning("FileInfo | no commits found for '%s' (HTTP %d)", repo_path, resp.status_code)
        return jsonify({"path": repo_path, "last_updated_at": None, "last_updated_by": None})

    commit = resp.json()[0]
    author = commit.get("commit", {}).get("author", {})
    log.info("FileInfo | '%s' last updated %s by %s", repo_path, author.get("date"), author.get("name"))
    return jsonify({
        "path":            repo_path,
        "last_updated_at": author.get("date"),
        "last_updated_by": author.get("name"),
    })


@app.route("/run-status", methods=["GET"])
def get_run_status():
    """
    Poll for the latest run of a workflow dispatched after a given timestamp.
    Query params:
      workflow=<filename.yml>
      after=<ISO timestamp>  (e.g. 2026-03-08T10:00:00Z)
    """
    workflow_file    = request.args.get("workflow", "")
    dispatched_after = request.args.get("after", "")

    if not workflow_file:
        return jsonify({"status": "error", "steps": [], "message": "Missing workflow param"}), 400

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    # Fetch the most recent runs for this workflow, filtered by creation time
    runs_url = (
        f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
        f"/actions/workflows/{workflow_file}/runs"
    )
    params = {"per_page": 5, "branch": BRANCH}
    if dispatched_after:
        # GitHub's created filter doesn't accept milliseconds — strip them
        clean_after = dispatched_after.split(".")[0] + "Z" if "." in dispatched_after else dispatched_after
        params["created"] = f">={clean_after}"
        log.info("RunStatus | querying '%s' created>=%s", workflow_file, clean_after)

    try:
        runs_resp = requests.get(runs_url, headers=headers, params=params, timeout=10)
    except requests.RequestException as exc:
        log.error("RunStatus | GitHub API error fetching runs: %s", exc)
        return jsonify({"status": "error", "steps": []}), 500

    if runs_resp.status_code != 200:
        log.warning("RunStatus | GitHub returned %d: %s", runs_resp.status_code, runs_resp.text[:200])
        return jsonify({"status": "not_found", "steps": []})

    runs = runs_resp.json().get("workflow_runs", [])
    log.info("RunStatus | GitHub returned %d run(s) for '%s'", len(runs), workflow_file)
    if not runs:
        return jsonify({"status": "not_found", "steps": []})

    run = runs[0]
    run_id = run["id"]

    # Fetch jobs and their steps for this run
    jobs_url = (
        f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
        f"/actions/runs/{run_id}/jobs"
    )
    try:
        jobs_resp = requests.get(jobs_url, headers=headers, timeout=10)
        jobs = jobs_resp.json().get("jobs", []) if jobs_resp.status_code == 200 else []
    except requests.RequestException:
        jobs = []

    steps = [
        {
            "name":       step["name"],
            "status":     step["status"],
            "conclusion": step.get("conclusion"),
        }
        for step in (jobs[0].get("steps", []) if jobs else [])
    ]

    log.info(
        "RunStatus | '%s' run #%d  status=%s  conclusion=%s  steps=%d",
        workflow_file, run_id, run["status"], run.get("conclusion"), len(steps),
    )

    return jsonify({
        "run_id":     run_id,
        "status":     run["status"],       # queued | in_progress | completed
        "conclusion": run.get("conclusion"),  # success | failure | cancelled | None
        "html_url":   run["html_url"],
        "steps":      steps,
    })


@app.route("/debug-users", methods=["GET"])
def debug_users():
    """Diagnostic endpoint — lists usernames only (no passwords). Remove after debugging."""
    try:
        usernames = [doc.id for doc in db.collection("users").stream()]
        log.info("Debug | found %d user(s) in Firestore", len(usernames))
        return jsonify({"users_found": len(usernames), "usernames": usernames})
    except Exception as exc:
        log.exception("Debug | error listing users")
        return jsonify({"error": str(exc)}), 500


@app.route("/store-summary", methods=["POST"])
def store_summary():
    api_key = request.headers.get("X-API-Key", "")
    if not BACKEND_API_KEY or api_key != BACKEND_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json or {}
    run_id = data.get("run_id")
    run_number = data.get("run_number")
    workflow_file = data.get("workflow_file", "")
    summary = data.get("summary", "").strip()

    if not summary or not workflow_file:
        return jsonify({"error": "Missing summary or workflow_file"}), 400

    doc_ref = db.collection("summaries").document()
    doc_ref.set({
        "run_id":        run_id,
        "run_number":    run_number,
        "workflow_file": workflow_file,
        "summary":       summary,
        "stored_at":     firestore.SERVER_TIMESTAMP,
    })
    log.info("Summary | stored for '%s' run #%s", workflow_file, run_number)
    return jsonify({"success": True})


@app.route("/summaries", methods=["GET"])
def get_summaries():
    docs = (
        db.collection("summaries")
        .order_by("stored_at", direction=firestore.Query.DESCENDING)
        .limit(30)
        .stream()
    )
    result = [doc.to_dict() for doc in docs]
    log.info("Summaries | returned %d records", len(result))
    return jsonify(result)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    log.info("Starting Trihalo backend on port %d", port)
    app.run(host="0.0.0.0", port=port, debug=False)
