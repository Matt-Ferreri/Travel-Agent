"""Resolve relative and explicit trip dates before weather/tool calls."""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any


_ISO_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_ISO_RANGE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2})\s*(?:to|-|–|—|/)\s*(\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE,
)
_US_DATE = re.compile(
    r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b"
)
_US_RANGE = re.compile(
    r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\s*(?:to|-|–|—)\s*(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b",
    re.IGNORECASE,
)
_MONTH_NAMES = {
    name.lower(): idx
    for idx, name in enumerate(calendar.month_name)
    if name
} | {
    name.lower(): idx
    for idx, name in enumerate(calendar.month_abbr)
    if name
}
_MONTH_DATE = re.compile(
    r"\b("
    + "|".join(sorted(_MONTH_NAMES, key=len, reverse=True))
    + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(\d{4}))?\b",
    re.IGNORECASE,
)
_MONTH_RANGE = re.compile(
    r"\b("
    + "|".join(sorted(_MONTH_NAMES, key=len, reverse=True))
    + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?"
    r"(?:\s*(?:to|-|–|—|/|and)\s*)"
    r"(?:("
    + "|".join(sorted(_MONTH_NAMES, key=len, reverse=True))
    + r")\.?\s+)?"
    r"(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(\d{4}))?\b",
    re.IGNORECASE,
)

_PLANNING_HINTS = (
    "plan",
    "trip",
    "itinerary",
    "weekend",
    "visit",
    "getaway",
    "vacation",
)


@dataclass(frozen=True)
class TripDateResolution:
    status: str  # resolved | needs_clarification | not_applicable
    start_date: date | None = None
    end_date: date | None = None
    label: str = ""
    reason: str = ""
    source: str = ""  # explicit | weekend | default

    @property
    def trip_dates(self) -> list[str]:
        if not self.start_date or not self.end_date:
            return []
        days: list[str] = []
        cur = self.start_date
        while cur <= self.end_date:
            days.append(cur.isoformat())
            cur += timedelta(days=1)
        return days

    def forecast_days_from(self, today: date | None = None) -> int:
        """Days of forecast needed from `today` to cover end_date (1-7)."""
        if not self.end_date:
            return 3
        today = today or date.today()
        span = (self.end_date - today).days + 1
        return max(1, min(7, span))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "trip_dates": self.trip_dates,
            "label": self.label,
            "reason": self.reason,
            "source": self.source,
            "forecast_days": self.forecast_days_from() if self.status == "resolved" else None,
        }


def _parse_year(raw: str | None, today: date) -> int:
    if not raw:
        return today.year
    year = int(raw)
    if year < 100:
        year += 2000
    return year


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _extract_explicit_dates(text: str, today: date) -> tuple[date, date] | None:
    """Return (start, end) when the user named specific dates; else None."""
    range_match = _ISO_RANGE.search(text)
    if range_match:
        start = date.fromisoformat(range_match.group(1))
        end = date.fromisoformat(range_match.group(2))
        if end < start:
            start, end = end, start
        return start, end

    us_range = _US_RANGE.search(text)
    if us_range:
        y1 = _parse_year(us_range.group(3), today)
        y2 = _parse_year(us_range.group(6), today)
        start = _safe_date(y1, int(us_range.group(1)), int(us_range.group(2)))
        end = _safe_date(y2, int(us_range.group(4)), int(us_range.group(5)))
        if start and end:
            if end < start and not us_range.group(6):
                # Cross-year range like 12/30-1/2 without years.
                end = _safe_date(y2 + 1, int(us_range.group(4)), int(us_range.group(5))) or end
            if end < start:
                start, end = end, start
            return start, end

    month_range = _MONTH_RANGE.search(text)
    if month_range:
        m1 = _MONTH_NAMES[month_range.group(1).lower()]
        d1 = int(month_range.group(2))
        m2_raw = month_range.group(3)
        m2 = _MONTH_NAMES[m2_raw.lower()] if m2_raw else m1
        d2 = int(month_range.group(4))
        year = _parse_year(month_range.group(5), today)
        start = _safe_date(year, m1, d1)
        end = _safe_date(year, m2, d2)
        if start and end:
            if end < start:
                end = _safe_date(year + 1, m2, d2) or end
            if end < start:
                start, end = end, start
            # If the whole window is in the past this year and no year given, roll forward.
            if not month_range.group(5) and end < today:
                start = _safe_date(year + 1, m1, d1) or start
                end = _safe_date(year + 1, m2, d2) or end
            return start, end

    iso_dates = [date.fromisoformat(m.group(1)) for m in _ISO_DATE.finditer(text)]
    if len(iso_dates) >= 2:
        start, end = min(iso_dates[0], iso_dates[1]), max(iso_dates[0], iso_dates[1])
        return start, end
    if len(iso_dates) == 1:
        return iso_dates[0], iso_dates[0]

    us_dates: list[date] = []
    for m in _US_DATE.finditer(text):
        parsed = _safe_date(_parse_year(m.group(3), today), int(m.group(1)), int(m.group(2)))
        if parsed:
            us_dates.append(parsed)
    if len(us_dates) >= 2:
        return min(us_dates[0], us_dates[1]), max(us_dates[0], us_dates[1])
    if len(us_dates) == 1:
        return us_dates[0], us_dates[0]

    month_dates: list[date] = []
    for m in _MONTH_DATE.finditer(text):
        month = _MONTH_NAMES[m.group(1).lower()]
        day = int(m.group(2))
        year = _parse_year(m.group(3), today)
        parsed = _safe_date(year, month, day)
        if parsed and not m.group(3) and parsed < today:
            parsed = _safe_date(year + 1, month, day)
        if parsed:
            month_dates.append(parsed)
    if len(month_dates) >= 2:
        return min(month_dates[0], month_dates[1]), max(month_dates[0], month_dates[1])
    if len(month_dates) == 1:
        return month_dates[0], month_dates[0]

    return None


def upcoming_weekend(today: date | None = None) -> tuple[date, date]:
    """Next Sat–Sun that has not fully ended; on Sunday, use next week's weekend."""
    today = today or date.today()
    weekday = today.weekday()  # Mon=0 ... Sun=6
    if weekday == 6:  # Sunday → next Saturday
        saturday = today + timedelta(days=6)
    else:
        saturday = today + timedelta(days=(5 - weekday))
    sunday = saturday + timedelta(days=1)
    return saturday, sunday


def planning_needs_dates(text: str) -> bool:
    lowered = (text or "").lower()
    return any(hint in lowered for hint in _PLANNING_HINTS)


def resolve_trip_dates(text: str, today: date | None = None) -> TripDateResolution:
    """
    Resolve trip dates from user text.

    Priority:
    1. Explicit dates in the prompt
    2. "weekend" → upcoming Saturday–Sunday
    3. Planning request with neither → needs_clarification
    4. Otherwise not_applicable (e.g. hello / out of scope)
    """
    today = today or date.today()
    text = text or ""

    explicit = _extract_explicit_dates(text, today)
    if explicit:
        start, end = explicit
        if (end - start).days > 6:
            return TripDateResolution(
                status="needs_clarification",
                reason=(
                    f"Requested window {start.isoformat()} to {end.isoformat()} is longer than "
                    "the 7-day forecast. Please pick a shorter range."
                ),
                source="explicit",
            )
        if start > today + timedelta(days=6):
            return TripDateResolution(
                status="needs_clarification",
                reason=(
                    f"{start.isoformat()} is beyond the 7-day weather forecast window. "
                    "Please choose dates within the next week, or say 'weekend' for the upcoming Saturday–Sunday."
                ),
                source="explicit",
            )
        return TripDateResolution(
            status="resolved",
            start_date=start,
            end_date=end,
            label=f"{start.isoformat()} to {end.isoformat()}",
            reason="Using the specific dates from your request.",
            source="explicit",
        )

    if re.search(r"\bweekends?\b", text, re.IGNORECASE):
        start, end = upcoming_weekend(today)
        return TripDateResolution(
            status="resolved",
            start_date=start,
            end_date=end,
            label=f"upcoming weekend ({start.isoformat()} to {end.isoformat()})",
            reason="Interpreted 'weekend' as the upcoming Saturday–Sunday.",
            source="weekend",
        )

    if planning_needs_dates(text):
        return TripDateResolution(
            status="needs_clarification",
            reason=(
                "I need trip dates before checking weather. "
                "Say 'weekend' for the upcoming Saturday–Sunday, or give specific dates "
                "(e.g. 2026-11-28 to 2026-11-29)."
            ),
            source="",
        )

    return TripDateResolution(
        status="not_applicable",
        reason="No trip-date resolution needed for this request.",
    )


def filter_daily_to_window(daily: dict[str, Any] | None, start: date, end: date) -> dict[str, Any]:
    """Keep only forecast rows whose date falls in [start, end]."""
    daily = daily or {}
    times = list(daily.get("time") or [])
    if not times:
        return dict(daily)

    keep: list[int] = []
    for i, raw in enumerate(times):
        try:
            day = date.fromisoformat(str(raw)[:10])
        except ValueError:
            continue
        if start <= day <= end:
            keep.append(i)

    out: dict[str, Any] = {}
    for key, values in daily.items():
        if isinstance(values, list) and len(values) == len(times):
            out[key] = [values[i] for i in keep]
        else:
            out[key] = values
    return out


def align_fixture_daily_to_window(
    daily: dict[str, Any] | None,
    start: date,
    end: date,
) -> dict[str, Any]:
    """
    Remap fixture series onto the resolved trip dates so offline demos show the
    correct weekend/explicit window instead of the fixture's sample calendar days.
    """
    daily = daily or {}
    trip_days = []
    cur = start
    while cur <= end:
        trip_days.append(cur.isoformat())
        cur += timedelta(days=1)
    if not trip_days:
        return dict(daily)

    source_len = len(daily.get("time") or []) or 1
    out: dict[str, Any] = {"time": trip_days}
    for key, values in daily.items():
        if key == "time":
            continue
        if isinstance(values, list) and values:
            out[key] = [values[i % len(values)] for i in range(len(trip_days))]
        else:
            out[key] = values
    # Preserve length alignment when source had matching parallel arrays.
    if source_len and not any(isinstance(v, list) for k, v in daily.items() if k != "time"):
        return out
    return out


def clarification_message(resolution: TripDateResolution) -> str:
    return resolution.reason or (
        "Please provide trip dates (or say 'weekend') before I call the weather tool."
    )
