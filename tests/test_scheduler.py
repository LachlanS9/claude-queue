import time
import pytest
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo
from scheduler import parse_brisbane_time, minutes_until

BRISBANE = ZoneInfo("Australia/Brisbane")


def test_parse_brisbane_time_returns_future_timestamp():
    ts = parse_brisbane_time("23:59")
    assert ts > time.time()


def test_parse_brisbane_time_advances_to_tomorrow_if_past():
    now_brisbane = datetime.now(BRISBANE)
    past_time = f"{now_brisbane.hour - 1:02d}:00" if now_brisbane.hour > 0 else "23:00"
    ts = parse_brisbane_time(past_time)
    assert ts > time.time()


def test_minutes_until_future():
    future = time.time() + 3600
    assert 59 <= minutes_until(future) <= 60


def test_minutes_until_past_returns_zero():
    past = time.time() - 60
    assert minutes_until(past) == 0
