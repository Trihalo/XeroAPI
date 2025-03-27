import os
import base64
import requests
import json
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from flask_cors import CORS
from urllib.parse import quote
from user_database import get_user
from google.cloud import firestore
import time

load_dotenv()
db = firestore.Client()

app = Flask(__name__)
CORS(app)

# GitHub Configuration
GITHUB_TOKEN = os.getenv("GH_PAT") 
GITHUB_OWNER = "Trihalo"
GITHUB_REPO = "XeroAPI"
BRANCH = "main"
UPLOAD_FOLDER = "uploads"

# Workflow Mapping (Name -> GitHub Workflow File)
WORKFLOWS = {
    "test-email": "sendEmail.yml",
    "futureyou-reports": "futureYouReports.yml",
    "h2coco-trade-finance": "tradeFinance.yml",
    "cosmo-bills-approver": "cosmoBillsApprover.yml",
}

def log_api_call(workflow_id, auth_user, status_code):
    doc_ref = db.collection("api_call_history").document()
    now = firestore.SERVER_TIMESTAMP

    history_entry = {
        "workflow": workflow_id,
        "name": auth_user,
        "called_at": now,
        "success": "Success" if status_code in (200, 204) else "Fail"
    }
    print("logging")
    doc_ref.set(history_entry)

# 🔹 Reusable function to trigger GitHub Actions
def trigger_github_action(workflow_id):
    try:
        auth_user = request.json.get("user")
        if not auth_user: return jsonify({"success": False, "message": "❌ No user data provided."}), 400
        
        url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{workflow_id}/dispatches"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        payload = {
            "ref": BRANCH,
            "inputs": {
                "name": auth_user.get("name"),
                "email": auth_user.get("email")
            }
        }

        response = requests.post(url, headers=headers, json=payload)
        
        print(response.status_code)
        log_api_call(workflow_id, auth_user, response.status_code)

        if response.status_code in [200, 204]:
            return jsonify({"success": True, "message": f"GitHub Action '{workflow_id}' triggered successfully!"})
        else:
            error_message = response.json().get("message", "Unknown error")
            return jsonify({"success": False, "error": error_message}), response.status_code

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# 🔹 Home Route
@app.route("/")
def home():
    return jsonify({"message": "Hello from Flask!"})


# 🔹 Test API Route
@app.route("/test-api", methods=["POST"])
def test_api():
    try:
        try:
            json_data = request.get_json(force=True)
        except Exception:
            json_data = {}

        auth_user = json_data.get("user", "anonymous")
        workflow_id = "test"
        status_code = 200

        log_api_call(workflow_id, auth_user, status_code)

        return jsonify({"success": True, "message": "✅ Test API is working!"})
    except Exception as e:
        print("❌ Error in test_api:", str(e))
        return jsonify({"success": False, "error": str(e)}), 500




# 🔹 Unified API for triggering workflows dynamically
@app.route("/trigger/<workflow_key>", methods=["POST"])
def trigger_workflow(workflow_key):
    workflow_id = WORKFLOWS.get(workflow_key)

    if not workflow_id:
        return jsonify({"success": False, "error": f"Workflow '{workflow_key}' not found"}), 400

    return trigger_github_action(workflow_id)

@app.route("/upload-file", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "message": "No selected file"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    file.save(file_path)
    
    # Read file in base64 format for GitHub API
    with open(file_path, "rb") as f:
        file_content = base64.b64encode(f.read()).decode("utf-8")

    # GitHub API URL
    file_name_encoded = quote(file.filename)
    github_api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/uploads/{file_name_encoded}"

    # Check if file exists in GitHub
    sha = None
    existing_file_response = requests.get(
        github_api_url, headers={"Authorization": f"token {GITHUB_TOKEN}"}, params={"ref":BRANCH}
    )
    print(existing_file_response)
    if existing_file_response.status_code == 200:
        sha = existing_file_response.json().get("sha")
    
    # **Check if SHA was successfully retrieved**
    if existing_file_response.status_code == 200 and not sha:
        return jsonify({"success": False, "message": "❌ Unable to fetch file SHA from GitHub."}), 500


    # Prepare payload for GitHub API
    payload = {
        "message": f"Replacing {file.filename}",
        "content": file_content,
        "branch": BRANCH,
    }
    if sha: payload["sha"] = sha

    # Push file to GitHub
    response = requests.put(github_api_url, json=payload, headers={"Authorization": f"token {GITHUB_TOKEN}"})

    # **DEBUG: Log response from GitHub**
    # print("GitHub API Response Status Code:", response.status_code)
    # print("GitHub API Response JSON:", response.json())

    if response.status_code in [200, 201]:
        return jsonify({"success": True, "message": f"File {file.filename} replaced on GitHub"})
    else:
        return jsonify({"success": False, "message": response.json()}), 500


@app.route("/authenticate", methods=["POST"])
def authenticate():
    try:
        data = request.json
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify({"success": False, "message": "Missing username or password"}), 400

        user = get_user(username)  # Fetch user data

        if user and user["password"] == password:
            # Return user data excluding password
            user_data = {key: value for key, value in user.items() if key != "password"}
            return jsonify({"success": True, "message": "Authentication successful", "user": user_data})
        else:
            return jsonify({"success": False, "message": "Invalid username or password"}), 401


    except Exception as e:
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500
    
    
@app.route("/history", methods=["GET"])
def get_history():
    docs = db.collection("api_call_history") \
             .order_by("called_at", direction=firestore.Query.DESCENDING) \
             .limit(100).stream()

    history = []
    for doc in docs:
        entry = doc.to_dict()
        if entry.get("called_at"):
            entry["called_at"] = entry["called_at"].astimezone().strftime("%H:%M | %d-%m-%Y")
        history.append(entry)

    return jsonify(history)



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
