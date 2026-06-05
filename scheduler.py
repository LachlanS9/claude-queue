import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BRISBANE_TZ = ZoneInfo("Australia/Brisbane")


def parse_brisbane_time(hhmm: str) -> float:
    h, m = map(int, hhmm.split(":"))
    now = datetime.now(BRISBANE_TZ)
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target.timestamp()


def minutes_until(timestamp: float) -> int:
    return max(0, int((timestamp - time.time()) / 60))
