#!/usr/bin/env python3
import os
import sys
import json
import time
import urllib.parse
from urllib.parse import urlsplit, parse_qs
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ.get("FUTUREYOU_BULLHORN_CLIENT_ID")
CLIENT_SECRET = os.environ.get("FUTUREYOU_BULLHORN_CLIENT_SECRET")
USERNAME = "futureyou.restapi"
PASSWORD = "FutureYou2025!"
REDIRECT_URI = "https://welcome.bullhornstaffing.com"


TOKEN_CACHE_PATH = os.environ.get("FUTUREYOU_BULLHORN_TOKEN_CACHE", "./tokens.json")

session = requests.Session()
session.headers["User-Agent"] = "futureyou-bh-oauth/1.1"
session.headers["Accept"] = "application/json"
TIMEOUT = 30

ZAPIER_HOOK_URL = "https://hooks.zapier.com/hooks/catch/2393707/urpxb6h/"

def notify_zapier(payload):
    try:
        r = session.post(ZAPIER_HOOK_URL, json=payload, timeout=15)
        print(f"Posted to Zapier: {payload['placementId']}, {r.status_code}")
    except Exception as e:
        print("Zapier post failed:", e)
        
        
def pretty(obj):
    print(json.dumps(obj, indent=2, sort_keys=True))

def _load_cache():
    if not os.path.exists(TOKEN_CACHE_PATH):
        return {}
    with open(TOKEN_CACHE_PATH, "r") as f:
        try:
            return json.load(f)
        except Exception:
            return {}

def _save_cache(data):
    tmp = TOKEN_CACHE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp, TOKEN_CACHE_PATH)

def _discover_swimlane(username: str):
    # Finds oauthUrl + restUrl base for your user
    r = session.get(
        "https://rest.bullhornstaffing.com/rest-services/loginInfo",
        params={"username": username},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    info = r.json()
    if "oauthUrl" not in info or "restUrl" not in info:
        raise SystemExit(f"loginInfo missing fields: {info}")
    # Normalize bases
    oauth_parts = urlsplit(info["oauthUrl"])
    oauth_base = f"{oauth_parts.scheme}://{oauth_parts.netloc}"
    rest_parts = urlsplit(info["restUrl"])
    rest_base = f"{rest_parts.scheme}://{rest_parts.netloc}"
    return oauth_base, rest_base

def _interactive_authorize(oauth_base: str):
    # One-time manual step to mint the initial code
    authorize_url = f"{oauth_base}/oauth/authorize"
    auth_params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "action": "Login",
        "username": USERNAME,
        "password": PASSWORD,
        "redirect_uri": REDIRECT_URI,
        "state": "xyz-123",
    }
    auth_url = f"{authorize_url}?{urllib.parse.urlencode(auth_params)}"

    print("\n=== ACTION REQUIRED (first-time only) ===")
    print("Open this URL in a browser, login/consent, then paste the FULL redirect URL:\n")
    print(auth_url, "\n")

    redirected = input("Paste redirect URL: ").strip()
    qs = parse_qs(urlsplit(redirected).query)
    code = (qs.get("code") or [None])[0]
    if not code:
        raise SystemExit("No 'code' found in redirect URL.")
    return code

def _exchange_code_for_tokens(oauth_base: str, code: str):
    token_url = f"{oauth_base}/oauth/token"
    resp = session.post(
        token_url,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    t = resp.json()
    if "access_token" not in t:
        raise SystemExit(f"Token exchange failed: {t}")
    t["_obtained_at"] = int(time.time())
    return t

def refresh_access_token(oauth_base: str, refresh_token: str):
    token_url = f"{oauth_base}/oauth/token"
    resp = session.post(
        token_url,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=TIMEOUT,
    )
    if resp.status_code == 400:
        # Usually invalid_grant (refresh revoked/expired) -> need re-auth
        raise RuntimeError(f"Refresh failed (likely invalid_grant): {resp.text}")
    resp.raise_for_status()
    t = resp.json()
    if "access_token" not in t:
        raise RuntimeError(f"Refresh returned no access_token: {t}")
    t["_obtained_at"] = int(time.time())
    return t

def rest_login(rest_base: str, access_token: str):
    r = session.get(
        f"{rest_base}/rest-services/login",
        params={"version": "2.0", "access_token": access_token},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    j = r.json()
    if "BhRestToken" not in j or "restUrl" not in j:
        raise RuntimeError(f"REST login failed: {j}")
    return j  # { BhRestToken, restUrl }

def get_session_creds():
    cache = _load_cache()

    oauth_base = cache.get("oauth_base")
    rest_base = cache.get("rest_base")
    if not oauth_base or not rest_base:
        oauth_base, rest_base = _discover_swimlane(USERNAME)
        cache["oauth_base"] = oauth_base
        cache["rest_base"] = rest_base

    access_token = cache.get("access_token")
    refresh_token = cache.get("refresh_token")
    BhRestToken = cache.get("BhRestToken")
    restUrl = cache.get("restUrl")

    def _store_tokens(token_dict):
        cache["access_token"] = token_dict["access_token"]
        if "refresh_token" in token_dict and token_dict["refresh_token"]:
            cache["refresh_token"] = token_dict["refresh_token"]
        cache["_obtained_at"] = token_dict.get("_obtained_at", int(time.time()))
        _save_cache(cache)

    # If we have nothing, do one-time interactive auth
    if not access_token or not refresh_token:
        code = _interactive_authorize(oauth_base)
        tokens = _exchange_code_for_tokens(oauth_base, code)
        _store_tokens(tokens)
        access_token = tokens["access_token"]
        refresh_token = tokens.get("refresh_token")

    # Ensure we have a current BhRestToken (do REST login if missing)
    if not BhRestToken or not restUrl:
        rl = rest_login(rest_base, access_token)
        cache["BhRestToken"] = rl["BhRestToken"]
        cache["restUrl"] = rl["restUrl"]
        _save_cache(cache)
        BhRestToken = rl["BhRestToken"]
        restUrl = rl["restUrl"]

    # Test the token quickly by calling a cheap endpoint; on 401, refresh & relogin
    test = session.get(
        f"{restUrl}settings/applicationMeta",  # low-cost GET
        params={"BhRestToken": BhRestToken},
        timeout=TIMEOUT,
    )
    if test.status_code == 401:
        # Access token may be expired OR BhRestToken expired -> refresh access, relogin
        try:
            tokens = refresh_access_token(oauth_base, refresh_token)
        except RuntimeError:
            # refresh_token invalid -> force interactive re-auth
            print("Refresh token invalid/expired. Re-authorizing once…")
            code = _interactive_authorize(oauth_base)
            tokens = _exchange_code_for_tokens(oauth_base, code)
        _store_tokens(tokens)
        access_token = tokens["access_token"]
        refresh_token = tokens.get("refresh_token")

        rl = rest_login(rest_base, access_token)
        cache["BhRestToken"] = rl["BhRestToken"]
        cache["restUrl"] = rl["restUrl"]
        _save_cache(cache)
        BhRestToken = rl["BhRestToken"]
        restUrl = rl["restUrl"]

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "rest_base": rest_base,
        "restUrl": restUrl,
        "BhRestToken": BhRestToken,
        "oauth_base": oauth_base,
    }


def ensure_event_subscription(rest_url: str, bh_token: str, name: str = "placementsApprovedFlow", force=False):
    url = f"{rest_url}event/subscription/{name}"
    params = {
        "type": "entity",
        "names": "Placement",
        "eventTypes": "INSERTED,UPDATED",
        "BhRestToken": bh_token,
    }
    r = session.put(url, params=params, timeout=TIMEOUT)
    if r.status_code == 200:
        return r.json()

    # If it already exists, either no-op or force recreate
    if r.status_code == 400 and "already exists" in r.text.lower():
        if not force:
            # No-op: treat as success and continue
            return {"subscriptionId": name, "status": "exists"}
        else:
            # Recreate with same params
            d = session.delete(url, params={"BhRestToken": bh_token}, timeout=TIMEOUT)
            d.raise_for_status()
            r = session.put(url, params=params, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()

    # Any other error: raise
    try:
        r.raise_for_status()
    except Exception:
        raise SystemExit(f"Failed to create subscription: {r.status_code} {r.text}")


def poll_events(rest_url: str, bh_token: str, name: str = "placementsApprovedFlow", max_events: int = 100):
    url = f"{rest_url}event/subscription/{name}"
    params = {"maxEvents": max_events, "BhRestToken": bh_token}
    r = session.get(url, params=params, timeout=TIMEOUT)
    if r.status_code == 204 or not r.text.strip():
        return {"requestId": None, "events": []}
    try:
        data = r.json()
    except ValueError:
        raise SystemExit(f"Poll returned non-JSON (status {r.status_code}): {r.text[:300]}")
    if isinstance(data, dict):
        data.setdefault("events", [])
        return data
    elif isinstance(data, list):
        return {"requestId": None, "events": data}
    else:
        return {"requestId": None, "events": []}

def get_placement(rest_url: str, bh_token: str, placement_id: int):
    base = f"{rest_url}entity/Placement/{placement_id}"
    common = {"BhRestToken": bh_token}

    def _req(fields_csv: str):
        r = session.get(base, params={**common, "fields": fields_csv}, timeout=TIMEOUT)
        # If unauthorized, bubble up so caller can re-login
        if r.status_code == 401:
            raise PermissionError("BhRestToken expired")
        # Try to parse JSON (even on 400) so we can print errorMessage
        try:
            payload = r.json()
        except ValueError:
            payload = {"_raw": r.text}
        return r.status_code, payload

    # 1) conservative primary field set
    fields_primary = ",".join([
        "id",
        "status",
        "dateBegin",
        "jobOrder(id,owner(id))",
        "candidate(id,firstName,lastName)",
        "clientCorporation(id,name)",
    ])
    code, body = _req(fields_primary)
    if code == 200 and isinstance(body, dict) and body.get("data"):
        data = body["data"]
        return data


def get_corporate_user(rest_url: str, bh_token: str, user_id: int):
    url = f"{rest_url}entity/CorporateUser/{user_id}"
    params = {"fields": "id,firstName,lastName,email", "BhRestToken": bh_token}
    r = session.get(url, params=params, timeout=TIMEOUT)
    if r.status_code == 401:
        raise PermissionError("BhRestToken expired")
    r.raise_for_status()
    return r.json().get("data")

# ---------------- Main (headless after first run) ----------------

def main():
    creds = get_session_creds()
    BhRestToken = creds["BhRestToken"]
    restUrl = creds["restUrl"]

    print("Ensuring event subscription…")
    info = ensure_event_subscription(restUrl, BhRestToken, name="placementsApprovedFlow")
    print("Subscription:", json.dumps(info, indent=2))

    print("Polling events…")
    try:
        data = poll_events(restUrl, BhRestToken, name="placementsApprovedFlow", max_events=50)
    except SystemExit as e:
        # Non-JSON or other edge -> bubble up
        raise
    except Exception as e:
        print("Poll error:", e)
        return

    events = data.get("events", [])
    print(f"Got {len(events)} events")

    for i, ev in enumerate(events, start=1):
        if ev.get("entityName") != "Placement":
            continue
        pid = ev.get("entityId")
        
        updated_props = ev.get("updatedProperties", [])
        if updated_props and "status" not in updated_props:
            continue

        # If BhRestToken did expire mid-loop, recover once:
        try:
            p = get_placement(restUrl, BhRestToken, pid)
        except PermissionError:
            # refresh BhRestToken via rest_login with cached access_token
            fresh = rest_login(creds["rest_base"], creds["access_token"])
            BhRestToken = fresh["BhRestToken"]
            restUrl = fresh["restUrl"]
            # Update cache so next run is good
            cache = _load_cache()
            cache["BhRestToken"] = BhRestToken
            cache["restUrl"] = restUrl
            _save_cache(cache)
            p = get_placement(restUrl, BhRestToken, pid)

        if not p or p.get("status") != "Approved":
            continue

        owner = (p.get("jobOrder") or {}).get("owner") or {}
        owner_id = owner.get("id")
        owner_email = None
        owner_name = None
        if owner_id:
            try:
                cu = get_corporate_user(restUrl, BhRestToken, owner_id)
            except PermissionError:
                fresh = rest_login(creds["rest_base"], creds["access_token"])
                BhRestToken = fresh["BhRestToken"]
                restUrl = fresh["restUrl"]
                cache = _load_cache()
                cache["BhRestToken"] = BhRestToken
                cache["restUrl"] = restUrl
                _save_cache(cache)
                cu = get_corporate_user(restUrl, BhRestToken, owner_id)
            owner_email = (cu or {}).get("email")
            owner_name = f"{(cu or {}).get('firstName','')} {(cu or {}).get('lastName','')}".strip()
        print("Placement approved event: ", i)
        payload = {
            "placementId": pid,
            "status": p.get("status"),
            "dateBegin": p.get("dateBegin"),
            "ownerName": owner_name,
            "ownerEmail": owner_email,
            "candidateName": f"{cand.get('firstName')} {cand.get('lastName')}" if (cand := p.get("candidate")) else "",
            "clientName": (p.get("clientCorporation") or {}).get("name"),
        }
        notify_zapier(payload)
        

if __name__ == "__main__":
    main()
