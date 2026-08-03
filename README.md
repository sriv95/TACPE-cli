# TACPE CSV to Works

CLI that adds TA work entries into the CPE TA site, single or in bulk from a CSV

## Prerequisite

- Python >=3.14
- [uv](https://docs.astral.sh/uv/)

## Installation

```bash
git clone https://github.com/sriv95/TACPE-csv-to-works
cd TACPE-csv-to-works
uv sync                              # install dependencies
uv run playwright install chromium   # browser for the Browser login method
```

## Usage

```bash
uv run python -m src.main
```

1. **Login** - on first run, choose how to authenticate:
   - **Browser login**: opens a real browser window, log in with your CMU account (incl. MFA), the session cookie is captured automatically.
   - **Manual paste**: log into the site yourself, open DevTools → Network tab, copy the `Cookie` header from any request, paste it in.

   The cookie is cached in `.cache/.cookie` (gitignored) and reused on future runs until it expires.

2. **Select course** - pick course/section you're a TA for from academic term/year

3. **Works menu**:
   - View existing work entries for the course.
   - **Add works**:
     - **Add a work** - enter date, task, start/end time for a single entry.
     - **Add bulk works (.csv)** - import a CSV file

### Bulk CSV format

Required columns (extra columns are ignored):

| column      | format                                              |
|-------------|------------------------------------------------------|
| `date`      | `YYYY-MM-DD`                                          |
| `startTime` | `HH:MM`, `HHMM`, `H`, or `H.mm` (minutes must be `00` or `30`) |
| `endTime`   | same as `startTime`, at least 1 hour after `startTime` |
| `work`      | task description                                      |

Example:

```csv
date,startTime,endTime,work
2026-07-04,10:00,14:00,Grading Assignment 1
```

## Development

See more [src/README.md](src/README.md)
