from datetime import datetime
import pytz
import re
from datetime import timezone

def getSydneyDate(dateString):
    utcTimezone = pytz.utc
    sydneyTimezone = pytz.timezone("Australia/Sydney")

    utcDatetime = utcTimezone.localize(datetime.strptime(dateString, "%Y-%m-%dT%H:%M:%S"))

    # Convert to Sydney timezone
    return(utcDatetime.astimezone(sydneyTimezone))

def parse_xero_date(xero_date_str):
    match = re.search(r"/Date\((\d+)", xero_date_str)
    if match:
        timestamp_ms = int(match.group(1))
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).date()
    return None