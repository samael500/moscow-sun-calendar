"""Generate finite sunrise/sunset calendars for Russian cities."""

import argparse
import calendar
import json
import shutil
from html import escape
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from astral import Observer
from astral.sun import sunrise, sunset
from icalendar import Calendar, Event, vDuration

MOSCOW = ZoneInfo("Europe/Moscow")
OBSERVER = Observer(latitude=55.7558, longitude=37.6173, elevation=0)
BASE_URL = "https://brodov.net/sun-calendar"
ROOT = Path(__file__).resolve().parent

def cities():
    return json.loads((ROOT / "data/cities.json").read_text())


def add_months(day: date, months: int) -> date:
    year, month = divmod(day.year * 12 + day.month - 1 + months, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def build_calendar(start: date, months: int = 6, history_months: int = 6, city: dict | None = None) -> Calendar:
    if not 1 <= months <= 12:
        raise ValueError("months must be between 1 and 12")
    if not 0 <= history_months <= 12:
        raise ValueError("history_months must be between 0 and 12")
    city = city or next(c for c in cities() if c["id"] == "moscow")
    observer = Observer(city["latitude"], city["longitude"], 0)
    tz = ZoneInfo(city["timezone"])
    result = Calendar()
    result.add("prodid", "-//Moscow Sun Calendar//RU")
    result.add("version", "2.0")
    result.add("calscale", "GREGORIAN")
    result.add("method", "PUBLISH")
    result.add("x-wr-calname", f"{city['name']} — восходы и закаты")
    result.add("x-wr-timezone", city["timezone"])
    result.add("x-wr-caldesc", f"Восходы и закаты ({city['name']}): {history_months} месяцев назад и {months} вперёд. События по 10 минут.")
    result.add("refresh-interval", vDuration(timedelta(days=1)), parameters={"VALUE": "DURATION"})
    result.add("x-published-ttl", "P1D")
    result.add("url", f"{BASE_URL}/{city['id']}.ics")
    day = add_months(start, -history_months)
    while day < add_months(start, months):
        for kind, title, calculate in (
            ("sunrise", f"Восход солнца · {city['name']}", sunrise),
            ("sunset", f"Закат · {city['name']}", sunset),
        ):
            try:
                instant = calculate(observer, date=day, tzinfo=tz)
            except ValueError as error:
                if any(message in str(error) for message in ("Sun is always above", "Sun is always below", "Unable to find a sunrise", "Unable to find a sunset")):
                    continue
                raise
            # Round to the nearest minute; calendar entries do not imply second precision.
            instant = (instant + timedelta(seconds=30)).replace(second=0, microsecond=0)
            event = Event()
            event.add("uid", f"{city['id']}-{kind}-{day.isoformat()}@samael500.github.io")
            # Stable timestamp: unchanged dates serialize identically across refreshes.
            event.add("dtstamp", datetime(2026, 1, 1, tzinfo=timezone.utc))
            event.add("sequence", 0)
            event.add("dtstart", instant.astimezone(timezone.utc))
            event.add("dtend", (instant + timedelta(minutes=10)).astimezone(timezone.utc))
            event.add("summary", title)
            event.add("location", f"{city['name']}, Россия")
            event.add("geo", (observer.latitude, observer.longitude))
            event.add("description", ("Расчёт для центра Москвы (55.7558, 37.6173), открытый горизонт. " if city["id"] == "moscow" else f"Расчёт для центра города ({observer.latitude}, {observer.longitude}), открытый горизонт. ") +
                      "Начало события — момент восхода или заката; продолжительность 10 минут. "
                      "Рельеф, здания и фактическая погода не учитываются. Время округлено до минуты.")
            event.add("status", "CONFIRMED")
            event.add("transp", "TRANSPARENT")
            result.add_component(event)
        day += timedelta(days=1)
    return result


def generate_site(output: Path, anchor: date | None = None, months: int = 6, history_months: int = 6):
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "web", output, dirs_exist_ok=True)
    catalog = []
    now = datetime.now(timezone.utc)
    for city in cities():
        start = anchor or now.astimezone(ZoneInfo(city["timezone"])).date()
        cal = build_calendar(start, months, history_months, city)
        (output / f"{city['id']}.ics").write_bytes(cal.to_ical())
        today = [event for event in cal.subcomponents if event.decoded("dtstart").astimezone(ZoneInfo(city["timezone"])).date() == start]
        daily = {}
        for event in today:
            kind = "sunrise" if "-sunrise-" in str(event["uid"]) else "sunset"
            daily[kind] = event.decoded("dtstart").astimezone(ZoneInfo(city["timezone"])).strftime("%H:%M")
        catalog.append({**city, "from": add_months(start, -history_months).isoformat(),
            "until_exclusive": add_months(start, months).isoformat(), "today": start.isoformat(),
            "events": len(cal.subcomponents), "times": daily})
    data = {"updated": now.isoformat(), "cities": catalog}
    (output / "cities.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    template = (ROOT / "web/index.html").read_text()
    links = "\n".join(f'<li><a href="{c["id"]}.ics">{escape(c["name"])}</a></li>' for c in catalog)
    (output / "index.html").write_text(template.replace("<!-- CITY_LINKS -->", links).replace("{{CITY_COUNT}}", str(len(catalog))))
    print(f"Generated {len(catalog)} calendars in {output}")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--months", type=int, default=6)
    parser.add_argument("--history-months", type=int, default=6)
    parser.add_argument("--output-dir", type=Path, default=Path("docs"))
    args = parser.parse_args()
    generate_site(args.output_dir, args.start, args.months, args.history_months)


if __name__ == "__main__":
    main()
