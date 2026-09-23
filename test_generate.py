import unittest
from datetime import date, timedelta

from icalendar import Calendar

from generate import MOSCOW, add_months, build_calendar


class CalendarTests(unittest.TestCase):
    def test_month_boundaries(self):
        self.assertEqual(add_months(date(2027, 8, 31), 6), date(2028, 2, 29))
        self.assertEqual(add_months(date(2026, 8, 31), 6), date(2027, 2, 28))

    def test_finite_valid_calendar(self):
        start = date(2026, 9, 23)
        raw = build_calendar(start).to_ical()
        self.assertIn(b"REFRESH-INTERVAL;VALUE=DURATION:P1D\r\n", raw)
        events = Calendar.from_ical(raw).walk("VEVENT")
        self.assertEqual(len(events), (date(2027, 3, 23) - start).days * 2)
        self.assertEqual(len({str(e["uid"]) for e in events}), len(events))
        for event in events:
            instant = event.decoded("dtstart")
            self.assertTrue(start <= instant.astimezone(MOSCOW).date() < date(2027, 3, 23))
            self.assertEqual(event.decoded("dtend") - instant, timedelta(minutes=10))
            self.assertNotIn("rrule", event)
            self.assertIsNotNone(instant.tzinfo)
        self.assertTrue(all(len(line) <= 75 for line in raw.split(b"\r\n")))
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))

    def test_refresh_preserves_overlapping_events(self):
        def events(day):
            return {str(e["uid"]): e.to_ical() for e in build_calendar(day).subcomponents}
        before, after = events(date(2026, 9, 23)), events(date(2026, 9, 24))
        for uid in before.keys() & after.keys():
            self.assertEqual(before[uid], after[uid])
        self.assertEqual(len(before.keys() - after.keys()), 2)

    def test_moscow_seasons_and_leap_day(self):
        for day, rise_hour, set_hour in ((date(2027, 6, 21), 3, 21), (date(2026, 12, 21), 8, 15)):
            events = build_calendar(day, 1).subcomponents
            self.assertEqual(events[0].decoded("dtstart").astimezone(MOSCOW).hour, rise_hour)
            self.assertEqual(events[1].decoded("dtstart").astimezone(MOSCOW).hour, set_hour)
        events = build_calendar(date(2028, 2, 28), 1).subcomponents
        self.assertEqual(sum(e.decoded("dtstart").date() == date(2028, 2, 29) for e in events), 2)


if __name__ == "__main__":
    unittest.main()
