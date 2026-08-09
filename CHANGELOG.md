<!-- markdownlint-disable -->

# Changelog

All notable changes to this project will be documented in this file.

## [0.1.6] - 2026-08-09
### Fixed
- Guarded optional control platform registration so the integration does not
	fail setup on Home Assistant builds that do not expose newer Platform enum
	members.

### Result
- Control entities can load again instead of showing only stale unavailable
	sensors after setup failure.

## [0.1.5] - 2026-08-09
### Added
- Native dashboard form entities (datetime, number, select, switch, text)
	for bottle, diaper, activity, and sleep logging.
- Native one-tap write controls for form submission without external
	input helpers or scripts.
- Native delete and correction controls for latest sleep, bottle, and diaper
	events.
- Native restore control for the latest retained deleted interval.

### Changed
- CI and local configuration updated for Python 3.14 compatibility.

## [0.1.0] - 2026-08-08
### Added
- Initial repository scaffold.
- Home Assistant custom integration skeleton for Huckleberry.
- Quality tooling, CI, tests scaffold, and licensing documentation.
