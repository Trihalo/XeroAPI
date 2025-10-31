#!/usr/bin/env python3
import os
import json
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials as UserCredentials

SCOPES = ["https://www.googleapis.com/auth/calendar"]


# ---------------- Token / Service ----------------
def _load_token_from_env(env_var: str = "FUTUREYOU_CALENDAR_OAUTH_ACCESS") -> dict:
    val = os.environ.get(env_var)
    if not val:
        raise RuntimeError(f"Missing {env_var} environment variable.")

    val = val.strip()
    if os.path.exists(val):
        with open(val, "r", encoding="utf-8") as f:
            return json.load(f)
    try:
        return json.loads(val)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{env_var} is not valid JSON or a valid file path: {e}")



def _calendar_service():
    t = _load_token_from_env()
    creds = UserCredentials(
        token=t.get("access_token"),
        refresh_token=t.get("refresh_token"),
        token_uri=t.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=t.get("client_id"),
        client_secret=t.get("client_secret"),
        scopes=t.get("scopes", SCOPES),
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


# ---------------- Build Event (All-day) ----------------
def build_event_body(payload: dict, cal_tz: str = "Australia/Sydney") -> dict:
    placement_id = str(payload.get("placementId", ""))
    candidate = payload.get("candidateName", "Candidate")
    client = payload.get("clientName", "")
    owner = payload.get("ownerName", "")
    owner_email = payload.get("ownerEmail")
    date_begin_ms = int(payload["dateBegin"])
    start_utc = datetime.fromtimestamp(date_begin_ms / 1000, tz=timezone.utc)
    local_tz = ZoneInfo(cal_tz)
    start_date = start_utc.astimezone(local_tz).date()
    end_date = start_date + timedelta(days=1)

    summary = f"Placement {placement_id}: {candidate}'s First Day at {client}"

    placement_link = (
        "https://cls60.bullhornstaffing.com/BullhornSTAFFING/"
        f"OpenWindow.cfm?Entity=Placement&id={placement_id}"
    )
    description = (
        f"Hi {owner},\n\n"
        f"Your candidate, {candidate}, was recently placed at {client} "
        f"with Placement reference no.{placement_id}.\n\n"
        f"{candidate} is projected to start on {start_date.strftime('%A, %d %B %Y')}.\n\n"
        f"Please give {candidate} a follow-up call at the end of their first day!\n\n"
        f"For more information, please click on this link:\n{placement_link}\n"
    )

    body = {
        "summary": summary,
        "description": description,
        "start": {"date": start_date.isoformat()},
        "end": {"date": end_date.isoformat()},
        "reminders": {"useDefault": False, "overrides": []},
        "extendedProperties": {"private": {"placementId": placement_id, "source": "bullhorn"}},
    }
    if owner_email:
        body["attendees"] = [{"email": owner_email}]
    return body


# ---------------- Dup Checker ----------------
def _rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _find_existing_event(
    calendar_id: str,
    body: dict,
    cal_tz: str = "Australia/Sydney",
    search_margin_hours: int = 12,
) -> Optional[dict]:
    """Find an existing event by placementId (extendedProperties) or exact summary within a time window."""
    svc = _calendar_service()

    placement_id = body.get("extendedProperties", {}).get("private", {}).get("placementId")
    summary = body.get("summary", "")
    start_str = body.get("start", {}).get("date")
    if not start_str:
        return None  # only all-day bodies supported here

    local_tz = ZoneInfo(cal_tz)
    start_date = date.fromisoformat(start_str)
    window_start_local = datetime.combine(start_date, datetime.min.time(), tzinfo=local_tz) - timedelta(hours=search_margin_hours)
    window_end_local = datetime.combine(start_date + timedelta(days=1), datetime.min.time(), tzinfo=local_tz) + timedelta(hours=search_margin_hours)

    time_min = _rfc3339(window_start_local)
    time_max = _rfc3339(window_end_local)
    q = str(placement_id) if placement_id else summary

    page_token = None
    while True:
        resp = svc.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            q=q,
            singleEvents=True,
            maxResults=50,
            orderBy="startTime",
            pageToken=page_token,
        ).execute()

        for ev in resp.get("items", []):
            ev_pid = ev.get("extendedProperties", {}).get("private", {}).get("placementId")
            if placement_id and ev_pid == placement_id:
                return ev
            if ev.get("summary", "") == summary:
                return ev

        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return None


# ---------------- Public API ----------------
def upsert_followup_event(payload: dict) -> Dict:
    """
    Builds the all-day follow-up event from the Bullhorn payload,
    checks for duplicates, and inserts only if missing.
    """
    cal_id = os.environ.get("FUTUREYOU_GOOGLE_CALENDAR_ID")
    if not cal_id:
        raise RuntimeError("Missing FUTUREYOU_GOOGLE_CALENDAR_ID.")
    cal_tz = os.environ.get("CAL_TZ", "Australia/Sydney")

    body = build_event_body(payload, cal_tz=cal_tz)

    # Check for existing
    existing = _find_existing_event(cal_id, body, cal_tz=cal_tz)
    if existing:
        return {
            "ok": True,
            "skipped": True,
            "reason": "duplicate-detected",
            "eventId": existing.get("id"),
            "htmlLink": existing.get("htmlLink"),
        }

    # Insert new
    svc = _calendar_service()
    try:
        created = svc.events().insert(calendarId=cal_id, body=body, sendUpdates="none").execute()
        return {"ok": True, "skipped": False, "eventId": created.get("id"), "htmlLink": created.get("htmlLink")}
    except HttpError as e:
        return {"ok": False, "error": getattr(e, "content", b"").decode(errors="ignore")}
