from __future__ import annotations

from datetime import datetime, timedelta


DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
HTML_DATETIME_FORMAT = "%Y-%m-%dT%H:%M"


def now_local() -> datetime:
    return datetime.now().replace(microsecond=0)


def to_db(dt: datetime) -> str:
    return dt.replace(microsecond=0).strftime(DATETIME_FORMAT)


def from_db(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, DATETIME_FORMAT)


def html_to_db(value: str) -> str:
    return datetime.strptime(value, HTML_DATETIME_FORMAT).strftime(DATETIME_FORMAT)


def date_time_to_db(date_value: str, time_value: str) -> str:
    return datetime.strptime(f"{date_value}T{time_value}", HTML_DATETIME_FORMAT).strftime(DATETIME_FORMAT)


def display_time(value: str | datetime | None) -> str:
    dt = from_db(value) if isinstance(value, str) else value
    return dt.strftime("%H:%M") if dt else ""


def duration_hours(start: str | datetime, end: str | datetime) -> float:
    start_dt = from_db(start) if isinstance(start, str) else start
    end_dt = from_db(end) if isinstance(end, str) else end
    if start_dt is None or end_dt is None:
        return 0.0
    return round((end_dt - start_dt).total_seconds() / 3600, 2)


def week_bounds(reference: datetime | None = None) -> tuple[str, str]:
    ref = reference or now_local()
    start = ref - timedelta(days=ref.weekday())
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    return to_db(start), to_db(end)
