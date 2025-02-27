from datetime import datetime
import pytz

def getSydneyDate(dateString):
    utcTimezone = pytz.utc
    sydneyTimezone = pytz.timezone("Australia/Sydney")

    utcDatetime = utcTimezone.localize(datetime.strptime(dateString, "%Y-%m-%dT%H:%M:%S"))

    # Convert to Sydney timezone
    return(utcDatetime.astimezone(sydneyTimezone))
