import os
import tempfile
import unittest
from unittest import mock

from src.cli.work import timetable
from src.cli.work.timetable import entries_for_weekday, export_timetable, import_timetable


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


class ImportExportTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.csv = os.path.join(self.dir.name, "t.csv")
        patch = mock.patch.object(timetable, "TIMETABLE_FILE", __import__("pathlib").Path(self.dir.name) / ".timetable")
        patch.start()
        self.addCleanup(patch.stop)

    def write(self, text):
        with open(self.csv, "w") as f:
            f.write(text)

    def test_round_trip(self):
        entries = [{"name": "A, B", "weekday": 0, "start": "09:00", "end": "10:15"}]
        export_timetable(entries, self.csv)
        self.assertEqual(import_timetable(self.csv, replace=True), (1, []))
        self.assertEqual(timetable.load_timetable(), entries)

    def test_merge_skips_duplicates(self):
        self.write("name,day,startTime,endTime\nA,mon,9,10\n")
        self.assertEqual(import_timetable(self.csv)[0], 1)
        self.assertEqual(import_timetable(self.csv)[0], 0)
        self.assertEqual(len(timetable.load_timetable()), 1)

    def test_bad_row_imports_nothing(self):
        self.write("name,day,startTime,endTime\nA,Mon,9,10\nB,Xyz,11,10\n")
        added, errors = import_timetable(self.csv)
        self.assertEqual(added, 0)
        self.assertEqual(len(errors), 1)
        self.assertEqual(timetable.load_timetable(), [])


if __name__ == "__main__":
    unittest.main()
