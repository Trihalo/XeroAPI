import os
import subprocess
from dotenv import load_dotenv, set_key

load_dotenv()

# List of refresh tokens
refresh_token_names = [
    "XERO_REFRESH_TOKEN_COSMOPOLITAN_CORPORATION",
    "XERO_REFRESH_TOKEN_FUTUREYOU_CONTRACTING",
    "XERO_REFRESH_TOKEN_FUTUREYOU_RECRUITMENT",
    "XERO_REFRESH_TOKEN_FUTUREYOU_RECRUITMENT_PERTH",
    "XERO_REFRESH_TOKEN_H2COCO"
]

env_file = ".env"

# Fetch latest tokens from GitHub Variables and update .env
for token_name in refresh_token_names:
    try:
        result = subprocess.run(["gh", "variable", "get", token_name], capture_output=True, text=True)
        if result.returncode == 0:
            new_token = result.stdout.strip()
            set_key(env_file, token_name, new_token)
            print(f"✅ Updated {token_name} in .env")
        else:
            print(f"⚠️ Failed to fetch {token_name}: {result.stderr}")
    except Exception as e:
        print(f"❌ Error fetching {token_name}: {e}")

print("🚀 All refresh tokens are up-to-date!")
