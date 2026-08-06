# Changelog

## [v1.1.0] - 2026-08-06

### Added
- Standalone CLI with argument parsing, per-command help descriptions, and a version command.
- `list` command for courses and works with term/year resolution.
- `submit` command for work entries, supporting single and bulk uploads.
- Login check and cookie validation before running commands; logout command for standalone CLI.

### Changed
- Simplified browser opening logic, removed Playwright integration.
- Refactored time handling with shared `split_time` function.
- Refactored work submission into shared `run_batch` utility.
- Renamed repository to TACPE-cli, updated URL references.
- Moved source files into a submodule.

### Fixed
- Browser subprocess stderr suppressed and process closed only when connected.

### Tests
- Added unit tests for time handling, CSV reading, and batch processing.

## [v1.0.1] - 2026-08-05

### Added
- Timetable view with loop for browsing and editing entries.
- Overlap checking for courses against the timetable.
- Browser launching for work report pages.
- Logout option that removes the saved cookie.

## [1.0.0] - 2026-08-05
First Release

[v1.1.0]: https://github.com/sriv95/TACPE-cli/compare/v1.0.1...v1.1.0
[v1.0.1]: https://github.com/sriv95/TACPE-cli/compare/v1.0.0...v1.0.1
