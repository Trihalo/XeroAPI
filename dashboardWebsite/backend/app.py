import os
import requests
from flask import Flask, jsonify
from dotenv import load_dotenv
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app)

GITHUB_TOKEN = os.getenv("GH_PAT") 
GITHUB_OWNER = "Trihalo"
GITHUB_REPO = "XeroAPI"
BRANCH = "website"

@app.route("/")
def home():
    return jsonify({"message": "Hello from Flask!"})


@app.route("/test-api", methods=["GET"])
def test_api():
    """Returns a test message for debugging."""
    return jsonify({"success": True, "message": "✅ Test API is working!"})


@app.route("/test-email", methods=["POST"])
def trigger_test_email():
    WORKFLOW_ID = "sendEmail.yml"
    
    try:
        # Construct the API URL for triggering the workflow
        url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{WORKFLOW_ID}/dispatches"

        # Set the headers with the GitHub token
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }

        # Define the payload for the workflow dispatch event
        payload = {
            "ref": BRANCH,
            "inputs": {}
        }

        # Make the POST request to trigger the workflow
        response = requests.post(url, headers=headers, json=payload)

        # Check if the request was successful
        if response.status_code == 200:
            print("helloworld")
            return jsonify({"success": True, "message": "GitHub Action triggered successfully!"})
        else:
            return jsonify({"success": False, "error": response.json().get("message", "Unknown error")}), response.status_code

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))  # Cloud Run uses dynamic ports
    app.run(host="0.0.0.0", port=port)
