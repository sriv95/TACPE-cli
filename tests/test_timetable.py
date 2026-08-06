import unittest

from src.cli.work.timetable import entries_for_weekday


class EntriesForWeekdayTest(unittest.TestCase):
    def setUp(self):
        self.entries = [
            {"name": "A", "weekday": 0, "start": "09:00", "end": "10:15"},
            {"name": "B", "weekday": 2, "start": "14:00", "end": "15:00"},
            {"name": "C", "weekday": 0, "start": "13:00", "end": "14:00"},
        ]

    def test_matches_multiple_entries_same_weekday(self):
        result = entries_for_weekday(self.entries, 0)
        self.assertEqual(result, [self.entries[0], self.entries[2]])

    def test_no_matches_returns_empty_list(self):
        self.assertEqual(entries_for_weekday(self.entries, 6), [])

    def test_empty_entries(self):
        self.assertEqual(entries_for_weekday([], 0), [])


if __name__ == "__main__":
    unittest.main()
