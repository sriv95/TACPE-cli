import os
import tempfile
import unittest

from src.cli.work.bulk_works import REQUIRED_COLUMNS, _validate_row, read_csv_rows


class ReadCsvRowsTest(unittest.TestCase):
    def _write(self, content: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        self.addCleanup(os.remove, path)
        return path

    def test_reads_rows_with_all_columns(self):
        path = self._write("date,startTime,endTime,work\n2026-08-06,09:00,17:00,Grading\n")
        rows = read_csv_rows(path, REQUIRED_COLUMNS)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["work"], "Grading")

    def test_missing_column_returns_none(self):
        path = self._write("date,startTime,work\n2026-08-06,09:00,Grading\n")
        self.assertIsNone(read_csv_rows(path, REQUIRED_COLUMNS))

    def test_empty_file_no_header(self):
        path = self._write("")
        self.assertIsNone(read_csv_rows(path, REQUIRED_COLUMNS))

    def test_header_only_no_rows(self):
        path = self._write("date,startTime,endTime,work\n")
        self.assertEqual(read_csv_rows(path, REQUIRED_COLUMNS), [])

    def test_task_column_aliases_work(self):
        path = self._write("date,startTime,endTime,task\n2026-08-06,09:00,17:00,Grading\n")
        rows = read_csv_rows(path, REQUIRED_COLUMNS)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["work"], "Grading")

    def test_work_column_wins_over_task(self):
        path = self._write("date,startTime,endTime,work,task\n2026-08-06,09:00,17:00,Real,Alias\n")
        rows = read_csv_rows(path, REQUIRED_COLUMNS)
        self.assertEqual(rows[0]["work"], "Real")

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            read_csv_rows("/no/such/file.csv", REQUIRED_COLUMNS)


class ValidateRowTest(unittest.TestCase):
    def test_valid_row(self):
        row = {"date": "2026-08-06", "startTime": "09:00", "endTime": "17:00", "work": "Grading"}
        entry = _validate_row(row, 2)
        self.assertEqual(entry["hours"], 8)
        self.assertEqual(entry["time_start"], "09:00")

    def test_blank_row_returns_none_silently(self):
        row = {"date": "", "startTime": "", "endTime": "", "work": ""}
        self.assertIsNone(_validate_row(row, 2))

    def test_invalid_date_rejected(self):
        row = {"date": "not-a-date", "startTime": "09:00", "endTime": "17:00", "work": "Grading"}
        self.assertIsNone(_validate_row(row, 2))

    def test_invalid_time_rejected(self):
        row = {"date": "2026-08-06", "startTime": "garbage", "endTime": "17:00", "work": "Grading"}
        self.assertIsNone(_validate_row(row, 2))

    def test_empty_work_rejected(self):
        row = {"date": "2026-08-06", "startTime": "09:00", "endTime": "17:00", "work": "  "}
        self.assertIsNone(_validate_row(row, 2))

    def test_duration_under_one_hour_rejected(self):
        row = {"date": "2026-08-06", "startTime": "09:00", "endTime": "09:30", "work": "Grading"}
        self.assertIsNone(_validate_row(row, 2))

    def test_duration_exactly_one_hour_accepted(self):
        row = {"date": "2026-08-06", "startTime": "09:00", "endTime": "10:00", "work": "Grading"}
        entry = _validate_row(row, 2)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["hours"], 1)

    def test_end_before_start_rejected(self):
        row = {"date": "2026-08-06", "startTime": "17:00", "endTime": "09:00", "work": "Grading"}
        self.assertIsNone(_validate_row(row, 2))


if __name__ == "__main__":
    unittest.main()
