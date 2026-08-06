# TACPE CLI

CLI that adds TA work entries into the CPE TA site, single or in bulk from a CSV

## Prerequisite

- Python >=3.14
- [uv](https://docs.astral.sh/uv/) (provides `uvx`)
- [Playwright](https://playwright.dev/python/) (optional for browser login )
`uvx playwright install chromium`

## One-time (Without install)
```bash
uvx --from git+https://github.com/sriv95/TACPE-cli tacpe
```

## Installation

Using [uv](https://docs.astral.sh/uv/)
```bash
uv tool install git+https://github.com/sriv95/TACPE-cli
```

Force Update: `uv tool upgrade tacpe`

Uninstall: `uv tool uninstall tacpe`.

## Usage

```bash
tacpe
```

1. **Login** - on first run, choose how to authenticate:
   - **Browser login**: opens a real browser window, log in with your CMU account (incl. MFA), the session cookie is captured automatically.
   - **Manual paste**: log into the site yourself, open DevTools → Network tab, copy the `Cookie` header from any request, paste it in.

   The cookie is cached in `.cache/.cookie` (gitignored) and reused on future runs until it expires.

2. **Select course** - pick course/section you're a TA for from academic term/year

3. **Works menu**:
   - View existing work entries for the course.
   - **Add works**:
     - **Add a work** - enter a date, then task/start/end time. At the summary,
       choose Submit, or **Add more dates** to extend the same task/time to more
       dates before submitting
     - **Add bulk works (.csv)** - import a CSV file
     - **Auto Find Slot** - given a date, work hours, and task, finds start times, then lets you pick one.
     - **Auto Find Slot (bulk .csv)** - same, from a CSV of multiple entries.

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

### Auto Find Slot (bulk) CSV format

Required columns (extra columns are ignored):

| column      | format                                              |
|-------------|------------------------------------------------------|
| `date`      | `YYYY-MM-DD`                                          |
| `workHour`  | hours as a number, multiple of `0.5` (e.g. `2`, `2.5`) |
| `work`      | task description                                      |
| `startTime` | (optional) minimum start time, `HH:MM`/`HHMM`/`H`/`H.mm` - blank to skip |

Example:

```csv
date,workHour,work,startTime
2026-07-04,3,Grading Assignment 1,
```

### Enrolled Course Time Table

First run of Auto Find Slot offers to edit your weekly course schedule (`.cache/.timetable`, gitignored) - name, day of week, start/end time - used to avoid scheduling TA work over your classes.

## Development

See more [src/README.md](src/README.md)
