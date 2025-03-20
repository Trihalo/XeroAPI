import os
import base64
import requests
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app)

# GitHub Configuration
GITHUB_TOKEN = os.getenv("GH_PAT") 
GITHUB_OWNER = "Trihalo"
GITHUB_REPO = "XeroAPI"
BRANCH = "website"

# Workflow Mapping (Name -> GitHub Workflow File)
WORKFLOWS = {
    "test-email": "sendEmail.yml",
    "futureyou-reports": "futureYouReports",
    "h2coco-trade-finance": "tradeFinanceAllocator.yml",
    "cosmo-bills-approver": "cosmoBillsApprover.yml",
}

# 🔹 Reusable function to trigger GitHub Actions
def trigger_github_action(workflow_id):
    try:
        url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{workflow_id}/dispatches"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        payload = {
            "ref": BRANCH,
            "inputs": {}
        }

        response = requests.post(url, headers=headers, json=payload)

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
@app.route("/test-api", methods=["GET"])
def test_api():
    return jsonify({"success": True, "message": "✅ Test API is working!"})


# 🔹 Unified API for triggering workflows dynamically
@app.route("/trigger/<workflow_key>", methods=["POST"])
def trigger_workflow(workflow_key):
    workflow_id = WORKFLOWS.get(workflow_key)

    if not workflow_id:
        return jsonify({"success": False, "error": f"Workflow '{workflow_key}' not found"}), 400

    return trigger_github_action(workflow_id)


@app.route("/upload-file", methods=["POST"])
def upload_file():
    upload_folder = "uploads"
    if "file" not in request.files: return jsonify({"success": False, "message": "No file uploaded"}), 400
    file = request.files["file"]
    if file.filename == "": return jsonify({"success": False, "message": "No selected file"}), 400

    file_path = os.path.join(upload_folder, file.filename)
    file.save(file_path)

    # Read file in base64 format for GitHub API
    with open(file_path, "rb") as f:
        file_content = base64.b64encode(f.read()).decode("utf-8")

    # GitHub API URL to create/update a file
    github_api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/uploads/{file.filename}"

    # Check if file already exists in GitHub
    existing_file_response = requests.get(
        github_api_url, headers={"Authorization": f"token {GITHUB_TOKEN}"}
    )

    sha = None  # SHA is required if updating an existing file
    if existing_file_response.status_code == 200: sha = existing_file_response.json().get("sha")

    # Prepare payload for GitHub API
    payload = {
        "message": f"Replacing {file.filename}",
        "content": file_content,
        "branch": BRANCH,
    }

    if sha: payload["sha"] = sha
    response = requests.put(github_api_url, json=payload, headers={"Authorization": f"token {GITHUB_TOKEN}"})

    if response.status_code in [200, 201]:
        return jsonify({"success": True, "message": f"File {file.filename} replaced on GitHub"})
    else:
        return jsonify({"success": False, "message": response.json()}), 500



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
