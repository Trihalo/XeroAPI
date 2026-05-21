# Placements Approval Event Subscription

This system listens for placement changes in Bullhorn CRM and automatically creates Google Calendar events for the job owner (recruiter) when a placement is approved.

---

## Files

### `eventSubscriptionAuth.py` — The Main Runner

This is the entry point. It:

1. **Authenticates with Bullhorn** via `get_session_creds()` — fetches a stored refresh token from GitHub Variables, exchanges it for an access token, and performs a REST login to get a `BhRestToken`.

2. **Registers an event subscription** (`ensure_event_subscription`) — creates or reuses a Bullhorn event subscription named `"placementsApprovedFlow"` that listens for `INSERTED` or `UPDATED` events on `Placement` entities.

3. **Polls for events** (`poll_events`) — fetches up to 50 pending events from the subscription queue.

4. **Filters and processes each event**:
   - Skips non-`Placement` entities
   - Skips events where `status` wasn't in the updated properties (i.e., nothing status-related changed)
   - Fetches full placement details from Bullhorn
   - Skips placements that aren't `"Approved"`
   - Looks up the job owner's email/name via `get_corporate_user()`
   - Calls `upsert_followup_event()` and `upsert_batch_followups()` to create calendar events

### `googleCalendarCreation.py` — Calendar Event Logic

Handles all Google Calendar creation. Authenticates via OAuth credentials stored in the `FUTUREYOU_CALENDAR_OAUTH_ACCESS` environment variable.

### `bootstrap_oauth.py` — One-time OAuth Setup

A one-time script to bootstrap Google OAuth credentials. Opens the browser, catches the callback, and prints the token JSON to copy into environment variables.

---

## How Google Calendar Events Are Created

Two types of events are created per placement:

### 1. Primary "First Day" Event (`upsert_followup_event`)

A single all-day calendar event on the candidate's `dateBegin` date.

**Title format:** `Placement {id}: {Candidate}'s First Day at {Client}`

**Description:** Addressed to the job owner, shows candidate name, client, role, start date, and a Bullhorn link.

**Attendee:** The job order owner's email is added so they get an invite.

---

### 2. Batch Follow-up Events (`upsert_batch_followups`)

Multiple milestone reminder events scheduled across the placement lifecycle.

**Schedule of events created:**

| Event | Timing |
|---|---|
| "1 week till start" | 1 week before `dateBegin` |
| "starts tomorrow" | 1 day before `dateBegin` |
| "1 month in role" | 1 month after `dateBegin` |
| "2 months in role" | 2 months after `dateBegin` |
| "5 months in role" | 5 months after `dateBegin` |
| "11.5 months in role" | 11 months + 15 days after `dateBegin` |
| "1 month until contract end" | 1 month before `dateEnd` *(contract types only)* |

If a milestone falls on a weekend, it's bumped to Monday.

---

## Criteria That Must Be Met for Events to Be Created

All of the following must be true:

| Check | Requirement |
|---|---|
| **Entity type** | Must be a `Placement` entity |
| **Changed field** | `status` must be in the updated properties (or it's a new insert) |
| **Placement status** | Must be `"Approved"` |
| **Candidate name** | Must NOT be `"Retainer Commencement"` or `"Retainer Shortlist"` (internal placeholders) |
| **Employment type** | Must be one of: `Permanent`, `FTC`, `Temporary`, or `Retained` |
| **Start date** | `dateBegin` must be today or in the future (not in the past) |
| **No duplicate** | No existing calendar event with the same placement ID, summary, and date already exists |

For the contract-end follow-up event specifically, `employmentType` must also be `FTC` or `Temporary`, and the milestone date must fall before the contract's `dateEnd`.
