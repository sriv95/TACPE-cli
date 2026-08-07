---
name: tacpe-cli
description: Use when adding, listing, editing, or deleting TA work-hour entries on the CPE TA site, checking or editing the saved weekly class timetable, checking for schedule conflicts across courses, or logging into/out of the site via the `tacpe` CLI.
---

# tacpe CLI

## Overview

`tacpe` reports TA work hours to the CPE TA site. Besides its interactive menu, it has non-interactive subcommands built for scripting/agents: no prompts, `--json` on read commands, exit code non-zero on failure.

## Setup (once per machine)

```bash
uv tool install git+https://github.com/sriv95/TACPE-cli   # or: uvx --from git+https://github.com/sriv95/TACPE-cli tacpe
tacpe login browser   # or: tacpe login cookie (paste a Cookie header manually)
```

Session cookie caches in `.cache/.cookie`; re-login only after it expires (commands print `Not logged in. Run 'tacpe login' first.` when it has).

## Quick reference

| Command | Purpose |
|---|---|
| `tacpe login [browser\|cookie]` / `tacpe logout` | Auth |
| `tacpe courses [--term N] [--year Y] [--json]` | List courses you TA for |
| `tacpe list <target> [--term] [--year] [--sec] [--json]` | List work entries (includes `workId`) |
| `tacpe add <target> --date --startTime --endTime --work [--force]` | Add one entry |
| `tacpe add <target> --bulk file.csv [--force]` | Add many, from CSV |
| `tacpe edit <target> --workId ID --date --startTime --endTime --work [--force]` | Full replace of one entry |
| `tacpe delete <target> --workId ID` | Delete one entry |
| `tacpe auto <target> --date --workHour --work [--startTime] [--force]` | Find a free slot and add it |
| `tacpe auto <target> --bulk file.csv [--force]` | Same, bulk from CSV |
| `tacpe timetable [list\|add\|edit\|delete] ...` | Manage the saved weekly class schedule (no login needed) |
| `tacpe check [--term] [--year] [--json]` | Report overlapping work entries across all courses |

Run `tacpe <command> --help` for exact flags; `tacpe help` for the full list.

## Conventions

- `<target>` — courseNo (e.g. `21-259`) or numeric courseId, from `tacpe courses`. Add `--sec N` if a courseNo has multiple sections.
- Times — `HH:MM`, `HHMM`, `H`, or `H.mm`; work entries require minutes `00`/`30`.
- `--term`/`--year` default to the current term; `--year` also accepts combined `term/year` (e.g. `1/2026`).
- `--json` on `courses`, `list`, `timetable list`, `check` for structured output — prefer this over parsing table text.
- `add`/`edit`/`auto` validate input and soft-check for overlaps/hour limits by default; add `--force` (alias `--no-check`) to skip.
- `--workId` values come from `tacpe list <target> --json`.
- `timetable` days: `Mon Tue Wed Thu Fri Sat Sun`. `timetable edit`/`delete` need `--index` from `tacpe timetable list --json`.

## Examples

```bash
tacpe courses --json
tacpe list 21-259 --json
tacpe add 21-259 --date 2026-08-10 --startTime 10:00 --endTime 12:00 --work "Grading HW3"
tacpe auto 21-259 --date 2026-08-10 --workHour 2 --work "Office hours"
tacpe edit 21-259 --workId abc123 --date 2026-08-11 --startTime 13:00 --endTime 15:00 --work "Grading HW3"
tacpe delete 21-259 --workId abc123
tacpe timetable add --name "Compiler Design" --day Mon --startTime 9:00 --endTime 10:30
tacpe check --json
```

## CSV bulk formats

- `add --bulk`: columns `date,startTime,endTime,work`.
- `auto --bulk`: columns `date,workHour,work,startTime` (startTime optional, minimum start).

## Common mistakes

- Forgetting `tacpe login` first — every course/work command needs it (`timetable` and `login`/`logout` don't).
- Passing a courseId as `<target>` when the account has multiple sections of that courseNo without `--sec` — resolves to the first match, may be the wrong section.
- Using `--force` by default — it skips the overlap/hour-limit check; only use when the soft-check is a known false positive.
