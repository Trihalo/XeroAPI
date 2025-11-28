#!/usr/bin/env python3
import os
import json
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional, List
from zoneinfo import ZoneInfo
from calendar import monthrange

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials as UserCredentials

import dotenv
dotenv.load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar"]


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


def _rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _ms_to_local_date(ms: int, cal_tz: str) -> date:
    tz = ZoneInfo(cal_tz)
    dt = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).astimezone(tz)
    return dt.date()


def _add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    last_day = monthrange(y, m)[1]
    new_date = date(y, m, min(d.day, last_day))
    if new_date.weekday() == 5: new_date += timedelta(days=2)
    elif new_date.weekday() == 6: new_date += timedelta(days=1)
    return new_date

def _today_local(cal_tz: str) -> date:
    return datetime.now(ZoneInfo(cal_tz)).date()

def _norm_employment_type(s: Optional[str]) -> str:
    return (s or "").strip().lower()

def _is_allowed_employment_type(etype: Optional[str]) -> bool:
    et = _norm_employment_type(etype)
    return et in {"permanent", "ftc", "temporary"}

def _is_contract_like(etype: Optional[str]) -> bool:
    et = _norm_employment_type(etype)
    return et in {"ftc", "temporary"}


def build_event_body(payload: dict, cal_tz: str = "Australia/Sydney") -> dict:
    placement_id = str(payload.get("placementId", ""))
    candidate = payload.get("candidateName", "Candidate")
    client = payload.get("clientName", "")
    owner = payload.get("ownerName", "")
    owner_email = payload.get("ownerEmail")
    job_title = payload.get("jobTitle") or payload.get("job") or ""

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

    description_lines = [
        f"Hi {owner},",
        "",
        f"Your candidate, {candidate}, was recently placed at {client} with Placement reference no. {placement_id}.",
    ]
    if job_title:
        description_lines.append(f"Role: {job_title}")
    description_lines += [
        "",
        f"{candidate} is projected to start on {start_date.strftime('%A, %d %B %Y')}.",
        "",
        f"Please give {candidate} a follow-up call at the end of their first day!",
        "",
        "More info:",
        placement_link,
    ]
    description = "\n".join(description_lines)

    body = {
        "summary": summary,
        "description": description,
        "start": {"date": start_date.isoformat()},
        "end": {"date": end_date.isoformat()},
        "reminders": {"useDefault": False, "overrides": []},
        "extendedProperties": {
            "private": {"placementId": placement_id, "source": "bullhorn", "kind": "primary"}
        },
    }
    if owner_email:
        body["attendees"] = [{"email": owner_email}]
    return body


def _all_day_body_from_date(
    payload: dict,
    event_date: date,
    summary: str,
    cal_tz: str,
    extra_desc: Optional[str] = None,
) -> dict:
    placement_id = str(payload.get("placementId", ""))
    candidate = payload.get("candidateName", "Candidate")
    client = payload.get("clientName", "")
    owner = payload.get("ownerName", "")
    owner_email = payload.get("ownerEmail")
    # owner_email = "leoshi@future-you.com.au"  # TEMPORARY OVERRIDE
    job_title = payload.get("jobTitle") or payload.get("job") or ""

    placement_link = (
        "https://cls60.bullhornstaffing.com/BullhornSTAFFING/"
        f"OpenWindow.cfm?Entity=Placement&id={placement_id}"
    )
    description_lines = [
        f"Hi {owner},",
        "",
        f"Candidate: {candidate}",
        f"Client: {client}",
    ]
    if job_title:
        description_lines.append(f"Role: {job_title}")
    description_lines += [
        "",
        f"This is an automated follow-up touchpoint scheduled for {event_date.strftime('%A, %d %B %Y')}.",
    ]
    if extra_desc:
        description_lines += ["", extra_desc]
    description_lines += [
        "",
        f"Placement ref: {placement_id}",
        placement_link,
    ]
    description = "\n".join(description_lines)

    body = {
        "summary": summary,
        "description": description,
        "start": {"date": event_date.isoformat()},
        "end": {"date": (event_date + timedelta(days=1)).isoformat()},
        "reminders": {"useDefault": False, "overrides": []},
        "extendedProperties": {
            "private": {"placementId": placement_id, "source": "bullhorn", "kind": "followup"}
        },
    }
    if owner_email:
        body["attendees"] = [{"email": owner_email}]
    return body


def _find_existing_event(
    calendar_id: str,
    body: dict,
    cal_tz: str = "Australia/Sydney",
    search_margin_hours: int = 1,
) -> Optional[dict]:
    svc = _calendar_service()
    placement_id = body.get("extendedProperties", {}).get("private", {}).get("placementId")
    summary = body.get("summary", "")
    start_str = body.get("start", {}).get("date")
    if not start_str:
        return None

    local_tz = ZoneInfo(cal_tz)
    start_date = date.fromisoformat(start_str)
    window_start_local = datetime.combine(
        start_date, datetime.min.time(), tzinfo=local_tz
    ) - timedelta(hours=search_margin_hours)
    window_end_local = datetime.combine(
        start_date + timedelta(days=1), datetime.min.time(), tzinfo=local_tz
    ) + timedelta(hours=search_margin_hours)

    time_min = _rfc3339(window_start_local)
    time_max = _rfc3339(window_end_local)

    q = summary if not placement_id else str(placement_id)

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
            ev_sum = ev.get("summary", "")
            if placement_id:
                if ev_pid == placement_id and ev_sum == summary:
                    return ev
            else:
                if ev_sum == summary:
                    return ev

        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return None



def upsert_followup_event(payload: dict) -> Dict:
    cal_id = os.environ.get("FUTUREYOU_GOOGLE_CALENDAR_ID")
    if not cal_id:
        raise RuntimeError("Missing FUTUREYOU_GOOGLE_CALENDAR_ID.")
    cal_tz = os.environ.get("CAL_TZ", "Australia/Sydney")
    cand_name = (payload.get("candidateName") or "").strip().lower()
    if cand_name == "retainer commencement":
        return {"ok": True, "skipped": True, "reason": "retainer-commencement-skip"}
    if not _is_allowed_employment_type(payload.get("employmentType")):
        return {"ok": True, "skipped": True, "reason": "employmentType-not-eligible"}

    body = build_event_body(payload, cal_tz=cal_tz)

    # Check if the event is in the past
    start_str = body.get("start", {}).get("date")
    if start_str:
        event_date = date.fromisoformat(start_str)
        if event_date < _today_local(cal_tz):
            return {"ok": True, "skipped": True, "reason": "event-in-past"}

    existing = _find_existing_event(cal_id, body, cal_tz=cal_tz)
    if existing:
        return {
            "ok": True,
            "skipped": True,
            "reason": "duplicate-detected",
            "eventId": existing.get("id"),
            "htmlLink": existing.get("htmlLink"),
        }
    svc = _calendar_service()
    try:
        created = svc.events().insert(calendarId=cal_id, body=body, sendUpdates="all").execute()
        return {"ok": True, "skipped": False, "eventId": created.get("id"), "htmlLink": created.get("htmlLink")}
    except HttpError as e:
        return {"ok": False, "error": getattr(e, "content", b"").decode(errors="ignore")}


def build_followup_bodies(payload: dict, cal_tz: str = "Australia/Sydney") -> List[dict]:
    if not payload.get("dateBegin"):
        return []
    if not _is_allowed_employment_type(payload.get("employmentType")):
        return []

    start_date = _ms_to_local_date(int(payload["dateBegin"]), cal_tz)
    end_date: Optional[date] = None
    if payload.get("dateEnd"):
        end_date = _ms_to_local_date(int(payload["dateEnd"]), cal_tz)

    candidate = (payload.get("candidateName") or "Candidate").strip()
    client = (payload.get("clientName") or "").strip()
    job_title = (payload.get("jobTitle") or payload.get("job") or "").strip()

    role_text = f" ({job_title})" if job_title else ""
    at_text = f" at {client}" if client else ""

    today = _today_local(cal_tz)
    bodies: List[dict] = []
    planned_dates: set[date] = set()

    def add_if_new(d: date, summary: str):
        if d not in planned_dates:
            bodies.append(_all_day_body_from_date(payload, d, summary, cal_tz))
            planned_dates.add(d)

    one_week_before = start_date - timedelta(weeks=1)
    one_day_before  = start_date - timedelta(days=1)

    if one_week_before > today:
        add_if_new(one_week_before, f"{candidate}{role_text} 1 week till start{at_text}")
    if one_day_before > today:
        add_if_new(one_day_before, f"{candidate}{role_text} starts tomorrow{at_text}")

    monthly_points = [
        (1,  f"{candidate}{role_text} 1 month in role{at_text}"),
        (2,  f"{candidate}{role_text} 2 months in role{at_text}"),
        (5,  f"{candidate}{role_text} 5 months in role{at_text}"),
        ("11.5", f"{candidate}{role_text} 11.5 months in role{at_text}"),
    ]

    is_contract = _is_contract_like(payload.get("employmentType"))

    for months, summary in monthly_points:
        if months == "11.5": d = _add_months(start_date, 11) + timedelta(days=15)
        else: d = _add_months(start_date, months)
        if d < today: continue
        if is_contract and end_date is not None and d > end_date: continue
        add_if_new(d, summary)

    if is_contract and end_date is not None:
        one_month_before_end = _add_months(end_date, -1)
        if one_month_before_end >= start_date and one_month_before_end >= today and one_month_before_end not in planned_dates:
            end_date_str = end_date.strftime('%A, %d %B %Y')
            extra_desc = f"Contract scheduled to end on {end_date_str}."
            bodies.append(
                _all_day_body_from_date(
                    payload,
                    one_month_before_end,
                    f"{candidate}{role_text} 1 month until contract end{at_text}",
                    cal_tz,
                    extra_desc=extra_desc,
                )
            )
            planned_dates.add(one_month_before_end)

    return bodies



def upsert_batch_followups(payload: dict) -> Dict:
    cal_id = os.environ.get("FUTUREYOU_GOOGLE_CALENDAR_ID")
    if not cal_id:
        raise RuntimeError("Missing FUTUREYOU_GOOGLE_CALENDAR_ID.")
    cal_tz = os.environ.get("CAL_TZ", "Australia/Sydney")

    cand_name = (payload.get("candidateName") or "").strip().lower()
    if cand_name == "retainer commencement":
        return {"ok": True, "count": 0, "results": [], "reason": "retainer-commencement-skip"}
    if not _is_allowed_employment_type(payload.get("employmentType")):
        return {"ok": True, "count": 0, "results": [], "reason": "employmentType-not-eligible"}

    if payload.get("dateBegin"):
        start_date = _ms_to_local_date(int(payload["dateBegin"]), cal_tz)
        if start_date < _today_local(cal_tz):
            return {"ok": True, "count": 0, "results": [], "reason": "event-in-past"}

    svc = _calendar_service()
    results = []

    for body in build_followup_bodies(payload, cal_tz=cal_tz):
        existing = _find_existing_event(cal_id, body, cal_tz=cal_tz)
        if existing:
            results.append({
                "summary": body.get("summary"),
                "date": body.get("start", {}).get("date"),
                "ok": True,
                "skipped": True,
                "reason": "duplicate-detected",
                "eventId": existing.get("id"),
                "htmlLink": existing.get("htmlLink"),
            })
            continue

        try:
            created = svc.events().insert(calendarId=cal_id, body=body, sendUpdates="all").execute()
            results.append({
                "summary": body.get("summary"),
                "date": body.get("start", {}).get("date"),
                "ok": True,
                "skipped": False,
                "eventId": created.get("id"),
                "htmlLink": created.get("htmlLink"),
            })
        except HttpError as e:
            results.append({
                "summary": body.get("summary"),
                "date": body.get("start", {}).get("date"),
                "ok": False,
                "error": getattr(e, "content", b"").decode(errors="ignore"),
            })

    return {"ok": True, "count": len(results), "results": results}

if __name__ == "__main__":
    sample_start_ms = int(datetime(2025, 11, 19, tzinfo=timezone.utc).timestamp() * 1000)

    payload = {
        "placementId": 987654,
        "status": "Approved",
        "employmentType": "Permanent",
        "dateBegin": sample_start_ms,
        "dateEnd": None,
        "ownerName": "Leo Shee",
        "ownerEmail": "leoshi@future-you.com.au",
        "candidateName": "clavicle wang",
        "clientName": "duohalo",
        "jobTitle": "money debt Manager",
    }
    
    temp_payload = {
    "placementId": 246810,
    "status": "Approved",
    "employmentType": "Temporary",
    "dateBegin": int(datetime(2025, 11, 12, tzinfo=timezone.utc).timestamp() * 1000),
    "dateEnd": int(datetime(2026, 3, 12, tzinfo=timezone.utc).timestamp() * 1000),  # ~3 months
    "ownerName": "Leo Shee",
    "ownerEmail": "leoshi@future-you.com.au",
    "candidateName": "patrick kim",
    "clientName": "jeans chilli chicken Pty Ltd",
    "jobTitle": "chef Officer",
}

    print("Creating primary 'first day' event…")
    res1 = upsert_followup_event(payload)
    print(json.dumps(res1, indent=2))

    print("\nCreating batch follow-up events…")
    res2 = upsert_batch_followups(payload)
    print(json.dumps(res2, indent=2))
