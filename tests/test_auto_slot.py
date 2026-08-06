import unittest

from src.cli.work.auto_slot import (
    _filter_by_min_start,
    _validate_duration,
    default_pick,
    find_free_slots,
    slots_with_overlap,
)


class SlotsWithOverlapTest(unittest.TestCase):
    def test_free_slot_has_no_reasons(self):
        slots = dict(slots_with_overlap("2026-08-06", 1, [], []))
        self.assertEqual(slots["09:00"], [])

    def test_lunch_blocks_overlapping_start(self):
        slots = dict(slots_with_overlap("2026-08-06", 1, [], []))
        self.assertIn("lunch break", slots["12:00"][0])

    def test_last_slot_start_is_thirty_min_before_day_end(self):
        # 30-min duration's latest start is 23:00, ending exactly at the 23:30 day boundary.
        slots = dict(slots_with_overlap("2026-08-06", 0.5, [], []))
        self.assertIn("23:00", slots)
        self.assertNotIn("23:30", slots)

    def test_duration_too_long_for_day_yields_no_slots(self):
        slots = slots_with_overlap("2026-08-06", 25, [], [])
        self.assertEqual(slots, [])

    def test_extra_busy_blocks_slot(self):
        slots = dict(slots_with_overlap("2026-08-06", 1, [], [], extra_busy=[(600, 660)]))
        self.assertTrue(slots["10:00"])

    def test_existing_work_on_other_date_ignored(self):
        works = [{"date": "2026-08-05T00:00:00.000Z", "time": "0900-1000", "work": "Other day"}]
        slots = dict(slots_with_overlap("2026-08-06", 1, [], works))
        self.assertEqual(slots["09:00"], [])


class FindFreeSlotsTest(unittest.TestCase):
    def test_excludes_busy_slots(self):
        free = find_free_slots("2026-08-06", 1, [], [])
        self.assertNotIn("12:00", free)
        self.assertIn("09:00", free)


class DefaultPickTest(unittest.TestCase):
    def test_prefers_eight_am(self):
        self.assertEqual(default_pick(["07:00", "08:00", "13:00"]), "08:00")

    def test_falls_back_to_one_pm(self):
        self.assertEqual(default_pick(["07:00", "13:00"]), "13:00")

    def test_falls_back_to_latest(self):
        self.assertEqual(default_pick(["07:00", "07:30"]), "07:30")

    def test_empty_returns_none(self):
        self.assertIsNone(default_pick([]))


class ValidateDurationTest(unittest.TestCase):
    def test_valid_half_hour_multiple(self):
        self.assertTrue(_validate_duration("2.5"))

    def test_non_numeric_rejected(self):
        self.assertNotEqual(_validate_duration("abc"), True)

    def test_below_minimum_rejected(self):
        self.assertNotEqual(_validate_duration("0.5"), True)

    def test_not_half_hour_multiple_rejected(self):
        self.assertNotEqual(_validate_duration("1.3"), True)

    def test_exactly_minimum_accepted(self):
        self.assertTrue(_validate_duration("1"))


class FilterByMinStartTest(unittest.TestCase):
    def test_filters_below_min(self):
        result = _filter_by_min_start(["08:00", "09:00", "10:00"], "09:00")
        self.assertEqual(result, ["09:00", "10:00"])

    def test_none_min_returns_all(self):
        items = ["08:00", "09:00"]
        self.assertEqual(_filter_by_min_start(items, None), items)

    def test_falls_back_to_full_list_when_filter_empties_it(self):
        items = ["08:00", "09:00"]
        self.assertEqual(_filter_by_min_start(items, "23:00"), items)


if __name__ == "__main__":
    unittest.main()
