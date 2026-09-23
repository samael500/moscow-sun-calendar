"""Generate a finite, subscribable Moscow sunrise/sunset calendar."""

import argparse
import calendar
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from astral import Observer
from astral.sun import sunrise, sunset
from icalendar import Calendar, Event

MOSCOW = ZoneInfo("Europe/Moscow")
OBSERVER = Observer(latitude=55.7558, longitude=37.6173, elevation=0)
BASE_URL = "https://maks.live/moscow-sun-calendar"


def add_months(day: date, months: int) -> date:
    year, month = divmod(day.year * 12 + day.month - 1 + months, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def build_calendar(start: date, months: int = 6) -> Calendar:
    if not 1 <= months <= 12:
        raise ValueError("months must be between 1 and 12")
    result = Calendar()
    result.add("prodid", "-//Moscow Sun Calendar//RU")
    result.add("version", "2.0")
    result.add("calscale", "GREGORIAN")
    result.add("method", "PUBLISH")
    result.add("x-wr-calname", "Москва — восходы и закаты")
    result.add("x-wr-timezone", "Europe/Moscow")
    result.add("x-wr-caldesc", "Восходы и закаты Москвы на ближайшие 6 месяцев. События по 10 минут.")
    result.add("refresh-interval", timedelta(days=1))
    result.add("x-published-ttl", "P1D")
    result.add("url", f"{BASE_URL}/moscow.ics")
    day = start
    while day < add_months(start, months):
        for kind, title, calculate in (
            ("sunrise", "Восход солнца · Москва", sunrise),
            ("sunset", "Закат · Москва", sunset),
        ):
            instant = calculate(OBSERVER, date=day, tzinfo=MOSCOW)
            # Round to the nearest minute; calendar entries do not imply second precision.
            instant = (instant + timedelta(seconds=30)).replace(second=0, microsecond=0)
            event = Event()
            event.add("uid", f"moscow-{kind}-{day.isoformat()}@samael500.github.io")
            # Stable timestamp: unchanged dates serialize identically across refreshes.
            event.add("dtstamp", datetime(2026, 1, 1, tzinfo=timezone.utc))
            event.add("sequence", 0)
            event.add("dtstart", instant.astimezone(timezone.utc))
            event.add("dtend", (instant + timedelta(minutes=10)).astimezone(timezone.utc))
            event.add("summary", title)
            event.add("location", "Москва, Россия")
            event.add("geo", (OBSERVER.latitude, OBSERVER.longitude))
            event.add("description", "Расчёт для центра Москвы (55.7558, 37.6173), открытый горизонт. "
                      "Начало события — момент восхода или заката; продолжительность 10 минут. "
                      "Рельеф, здания и фактическая погода не учитываются. Время округлено до минуты.")
            event.add("status", "CONFIRMED")
            event.add("transp", "TRANSPARENT")
            result.add_component(event)
        day += timedelta(days=1)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=None)
    parser.add_argument("--months", type=int, default=6)
    parser.add_argument("--output", type=Path, default=Path("docs/moscow.ics"))
    args = parser.parse_args()
    start = args.start or datetime.now(MOSCOW).date()
    result = build_calendar(start, args.months)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result.to_ical())
    metadata = {
        "from": start.isoformat(), "until_exclusive": add_months(start, args.months).isoformat(),
        "events": len(result.subcomponents), "timezone": "Europe/Moscow",
    }
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata))


if __name__ == "__main__":
    main()
