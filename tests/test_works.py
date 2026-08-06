import unittest

from src.cli.work.works import (
    _daily_dates,
    _month_range,
    _to_utc_date,
    _weekly_dates,
    _work_payload,
    format_date,
    format_entry_line,
    format_time,
    minutes,
    overlaps_lunch,
    parse_time,
    split_time,
    validate_date,
    validate_work,
)


class SplitTimeTest(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(split_time("0930-1730"), ("09:30", "17:30"))

    def test_midnight_and_end_of_day(self):
        self.assertEqual(split_time("0000-2359"), ("00:00", "23:59"))


class MinutesTest(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(minutes("09:30"), 570)

    def test_midnight(self):
        self.assertEqual(minutes("00:00"), 0)


class OverlapsLunchTest(unittest.TestCase):
    def test_fully_inside(self):
        self.assertTrue(overlaps_lunch("12:15", "12:45"))

    def test_no_overlap_before(self):
        self.assertFalse(overlaps_lunch("10:00", "12:00"))

    def test_no_overlap_after(self):
        self.assertFalse(overlaps_lunch("13:00", "15:00"))

    def test_touches_start_boundary_only(self):
        # ends exactly at 12:00 -> not > 12:00, so no overlap
        self.assertFalse(overlaps_lunch("11:00", "12:00"))

    def test_touches_end_boundary_only(self):
        # starts exactly at 13:00 -> not < 13:00, so no overlap
        self.assertFalse(overlaps_lunch("13:00", "14:00"))

    def test_spans_whole_lunch(self):
        self.assertTrue(overlaps_lunch("11:00", "14:00"))


class ValidateDateTest(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(validate_date("2026-08-06"))

    def test_invalid_format(self):
        self.assertNotEqual(validate_date("08-06-2026"), True)

    def test_empty_string(self):
        self.assertNotEqual(validate_date(""), True)


class ValidateWorkTest(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(validate_work("Grading"))

    def test_empty(self):
        self.assertNotEqual(validate_work(""), True)

    def test_whitespace_only(self):
        self.assertNotEqual(validate_work("   "), True)


class ParseTimeTest(unittest.TestCase):
    def test_colon_format(self):
        self.assertEqual(parse_time("17:30"), "17:30")

    def test_digits_four(self):
        self.assertEqual(parse_time("1730"), "17:30")

    def test_digits_short_hour_only(self):
        self.assertEqual(parse_time("17"), "17:00")

    def test_dotted_format(self):
        self.assertEqual(parse_time("17.5"), "17:30")

    def test_strips_whitespace(self):
        self.assertEqual(parse_time(" 17:30 "), "17:30")

    def test_strict_rejects_non_half_hour_minutes(self):
        self.assertIsNone(parse_time("17:15"))

    def test_non_strict_allows_any_minute(self):
        self.assertEqual(parse_time("17:15", strict=False), "17:15")

    def test_hour_out_of_range(self):
        self.assertIsNone(parse_time("24:00"))

    def test_minute_out_of_range(self):
        self.assertIsNone(parse_time("17:75"))

    def test_garbage(self):
        self.assertIsNone(parse_time("not a time"))

    def test_empty_string(self):
        self.assertIsNone(parse_time(""))

    def test_midnight_edge(self):
        self.assertEqual(parse_time("00:00"), "00:00")

    def test_last_valid_hour(self):
        self.assertEqual(parse_time("23:30"), "23:30")


class FormatTimeTest(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(format_time("0900-1700"), "09:00 - 17:00 (8 hrs)")

    def test_fractional_hours(self):
        self.assertEqual(format_time("0900-1230"), "09:00 - 12:30 (3.5 hrs)")


class FormatDateTest(unittest.TestCase):
    def test_utc_to_bangkok_shifts_date_forward(self):
        # 2026-08-05 23:00 UTC -> 2026-08-06 06:00 Bangkok (+7)
        self.assertEqual(format_date("2026-08-05T23:00:00.000Z"), "2026-08-06")

    def test_no_shift_needed(self):
        self.assertEqual(format_date("2026-08-06T01:00:00.000Z"), "2026-08-06")


class ToUtcDateTest(unittest.TestCase):
    def test_bangkok_midnight_is_previous_day_utc(self):
        self.assertEqual(_to_utc_date("2026-08-06"), "2026-08-05T17:00:00.000Z")


class MonthRangeTest(unittest.TestCase):
    def test_january_anchor_wraps_to_prior_december(self):
        min_date, _ = _month_range("2026-01-15")
        self.assertEqual(min_date, "2025-12-01")

    def test_mid_year_anchor(self):
        min_date, _ = _month_range("2026-08-06")
        self.assertEqual(min_date, "2026-07-01")


class WeeklyDatesTest(unittest.TestCase):
    def test_includes_selected_date_and_steps_by_seven(self):
        dates = _weekly_dates("2026-08-06", "2026-07-01", "2026-08-06")
        self.assertIn("2026-08-06", dates)
        self.assertTrue(all((d1 > d2) for d1, d2 in zip(dates, dates[1:])))

    def test_newest_first(self):
        dates = _weekly_dates("2026-08-06", "2026-07-01", "2026-08-06")
        self.assertEqual(dates[0], max(dates))


class DailyDatesTest(unittest.TestCase):
    def test_inclusive_bounds(self):
        dates = _daily_dates("2026-08-04", "2026-08-06")
        self.assertEqual(dates, ["2026-08-06", "2026-08-05", "2026-08-04"])

    def test_single_day_range(self):
        self.assertEqual(_daily_dates("2026-08-06", "2026-08-06"), ["2026-08-06"])


class FormatEntryLineTest(unittest.TestCase):
    def test_with_hours(self):
        entry = {"date": "2026-08-06", "time_start": "09:00", "time_end": "17:00", "work": "Grading", "hours": 8}
        self.assertEqual(format_entry_line(entry), "2026-08-06 | 09:00 - 17:00 (8 hrs) | Grading")

    def test_without_hours(self):
        entry = {"date": "2026-08-06", "time_start": "09:00", "time_end": "17:00", "work": "Grading"}
        self.assertEqual(format_entry_line(entry, with_hours=False), "2026-08-06 | 09:00 - 17:00 | Grading")


class WorkPayloadTest(unittest.TestCase):
    def test_builds_expected_shape(self):
        entry = {"date": "2026-08-06", "work": "Grading", "time_start": "09:00", "time_end": "17:00"}
        payload = _work_payload(1, entry)
        self.assertEqual(
            payload,
            {
                "courseId": 1,
                "work": "Grading",
                "date": "2026-08-05T17:00:00.000Z",
                "time": "0900-1700",
            },
        )


if __name__ == "__main__":
    unittest.main()
