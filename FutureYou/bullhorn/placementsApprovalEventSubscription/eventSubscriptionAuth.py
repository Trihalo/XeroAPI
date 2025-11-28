#!/usr/bin/env python3
import os
import json
import sys
import time
from urllib.parse import urlsplit
import requests
from googleCalendarCreation import upsert_followup_event, upsert_batch_followups

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from xeroAuthHelper import get_github_variable, update_github_variable 

CLIENT_ID  = os.environ.get("FUTUREYOU_BULLHORN_CLIENT_ID")
CLIENT_SECRET = os.environ.get("FUTUREYOU_BULLHORN_CLIENT_SECRET")
USERNAME   = "futureyou.restapi"
PASSWORD   = os.environ.get("FUTUREYOU_BULLHORN_PASSWORD")
REDIRECT_URI = "https://welcome.bullhornstaffing.com"

session = requests.Session()
session.headers["User-Agent"] = "futureyou-bh-oauth/2.0"
session.headers["Accept"] = "application/json"
TIMEOUT = 30

def _discover_swimlane(username: str):
    r = session.get(
        "https://rest.bullhornstaffing.com/rest-services/loginInfo",
        params={"username": username},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    info = r.json()
    if "oauthUrl" not in info or "restUrl" not in info:
        raise SystemExit(f"loginInfo missing fields: {info}")
    oauth_parts = urlsplit(info["oauthUrl"])
    oauth_base = f"{oauth_parts.scheme}://{oauth_parts.netloc}"
    rest_parts = urlsplit(info["restUrl"])
    rest_base = f"{rest_parts.scheme}://{rest_parts.netloc}"
    return oauth_base, rest_base

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
        raise RuntimeError(f"Refresh failed (likely invalid_grant/rotated): {resp.text}")
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
    return j

def get_session_creds():
    refresh_token = get_github_variable("BULLHORN_REFRESH_TOKEN_FUTUREYOU")
    if not refresh_token:
        raise SystemExit("No refresh token found in GitHub variable 'BULLHORN_REFRESH_TOKEN_FUTUREYOU'.")

    oauth_base, rest_base = _discover_swimlane(USERNAME)
    tokens = refresh_access_token(oauth_base, refresh_token)
    access_token = tokens["access_token"]
    latest_refresh = tokens.get("refresh_token") or refresh_token

    rl = rest_login(rest_base, access_token)
    BhRestToken = rl["BhRestToken"]
    restUrl = rl["restUrl"]

    if latest_refresh != refresh_token: update_github_variable("BULLHORN_REFRESH_TOKEN_FUTUREYOU", latest_refresh)

    return {
        "access_token": access_token,
        "refresh_token": latest_refresh,
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
    if r.status_code == 400 and "already exists" in r.text.lower():
        if not force:
            return {"subscriptionId": name, "status": "exists"}
        d = session.delete(url, params={"BhRestToken": bh_token}, timeout=TIMEOUT)
        d.raise_for_status()
        r = session.put(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    r.raise_for_status()
    return {"subscriptionId": name, "status": "ok"}

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
    params = {"BhRestToken": bh_token}
    fields_primary = ",".join([
        "id",
        "status",
        "employmentType",
        "dateBegin",
        "dateEnd",
        "jobOrder(id,owner(id),title)",
        "candidate(id,firstName,lastName)",
        "clientCorporation(id,name)",
    ])
    r = session.get(base, params={**params, "fields": fields_primary}, timeout=TIMEOUT)
    if r.status_code == 401:
        raise PermissionError("BhRestToken expired")
    try:
        payload = r.json()
    except ValueError:
        payload = {"_raw": r.text}
    if r.status_code == 200 and isinstance(payload, dict) and payload.get("data"):
        return payload["data"]
    return None

def get_corporate_user(rest_url: str, bh_token: str, user_id: int):
    url = f"{rest_url}entity/CorporateUser/{user_id}"
    params = {"fields": "id,firstName,lastName,email", "BhRestToken": bh_token}
    r = session.get(url, params=params, timeout=TIMEOUT)
    if r.status_code == 401:
        raise PermissionError("BhRestToken expired")
    r.raise_for_status()
    return r.json().get("data")

# ---------------- Main ----------------
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

        try:
            p = get_placement(restUrl, BhRestToken, pid)
        except PermissionError:
            fresh = rest_login(creds["rest_base"], creds["access_token"])
            BhRestToken = fresh["BhRestToken"]
            restUrl = fresh["restUrl"]
            p = get_placement(restUrl, BhRestToken, pid)

        if not p or p.get("status") != "Approved":
            continue

        owner = (p.get("jobOrder") or {}).get("owner") or {}
        job_title = ((p.get("jobOrder") or {}).get("title")) or ""
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
                cu = get_corporate_user(restUrl, BhRestToken, owner_id)
            owner_email = (cu or {}).get("email")
            owner_name = f"{(cu or {}).get('firstName','')} {(cu or {}).get('lastName','')}".strip()
            
        print("Placement approved event:", i)
        payload = {
            "placementId": pid,
            "status": p.get("status"),
            "employmentType": p.get("employmentType"),
            "dateBegin": p.get("dateBegin"),
            "dateEnd": p.get("dateEnd"),
            "ownerName": owner_name,
            "ownerEmail": owner_email,
            "candidateName": f"{cand.get('firstName')} {cand.get('lastName')}" if (cand := p.get("candidate")) else "",
            "clientName": (p.get("clientCorporation") or {}).get("name"),
            "jobTitle": job_title,
        }

        # --- Skip if this is an internal “Retainer Commencement” placeholder
        if payload.get("candidateName", "").strip().lower() == "retainer commencement":
            print(f"⏭️  Skipping placement {pid} — candidate marked 'Retainer Commencement'")
            continue

        # print("Payload:", json.dumps(payload, indent=2))
        
        try:
            result = upsert_followup_event(payload)
            if result.get("ok"):
                if result.get("skipped") == True:
                    reason = result.get("reason")
                    print("\n🟢 Calendar Update")
                    print("──────────────────────────────")
                    print(f"Candidate:  {payload.get('candidateName')}")
                    print(f"Placement:  {payload.get('placementId')}")
                    
                    if reason == "event-in-past":
                        print("Status:     Skipped (Event date is in the past)")
                    elif reason == "duplicate-detected":
                        print("Status:     Skipped (Duplicate event detected)")
                    elif reason == "retainer-commencement-skip":
                        print("Status:     Skipped (Retainer Commencement)")
                    elif reason == "employmentType-not-eligible":
                        print(f"Status:     Skipped (Employment Type '{payload.get('employmentType')}' not eligible)")
                    else:
                        print(f"Status:     Skipped ({reason})")
                    print("==============================")
                else:
                    print("\n📅 Calendar Event Created")
                    print("──────────────────────────────")
                    print(f"Candidate:  {payload.get('candidateName')}")
                    print(f"Placement:  {payload.get('placementId')}")
                    print(f"Status:     Success ✅")
                    print(f"Event ID:   {result.get('eventId')}")
                    print("==============================")
            else:
                print("\n❌ Calendar Error")
                print("──────────────────────────────")
                print(f"Candidate:  {payload.get('candidateName')}")
                print(f"Placement:  {payload.get('placementId')}")
                print(f"Error:      {result.get('error', 'Unknown error')}\n")
                print("==============================")
            
            if result.get("skipped") and result.get("reason") == "event-in-past":
                print(f"Batch follow-ups: Skipped (Start date in past)")
            else:
                result2 = upsert_batch_followups(payload)
                if result2.get("ok"):
                    print(f"Batch follow-ups: {result2.get('count')} processed for {payload.get('candidateName')} (Placement {payload.get('placementId')})")
                else:
                    print(f"Batch follow-up error for Placement {payload.get('placementId')}: {result2.get('error', 'Unknown error')}")

        except Exception as ex:
            print("Calendar error:", ex)

if __name__ == "__main__":
    main()
