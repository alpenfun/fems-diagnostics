# Changelog

## 1.1.0 — 2026-11-14

First stable release of the 1.1 series.

### Added
- Automatically discover available FEMS charger/MPP tracker components instead of assuming only Charger 0 and 1.
- Create sensors for additional detected charger channels, including Charger 2 and beyond where available.

### Fixed
- Replace deprecated Home Assistant device registry `via_device` references with `via_device_id` (issue #12).
- Preserve the FEMS System → Battery → Diagnostics/Cells and System → Charger/Energy Management device topology.

### Compatibility
- Minimum Home Assistant version in HACS: **2026.10.0**, matching the oldest version covered by the current test environment.
- Existing sensor unique IDs are retained.

### Verification
- GitHub Actions: **25 tests passed**, HACS and Hassfest checks passed.
- Manually tested with current sensor readings and no FEMS warnings on Home Assistant 2026.11.1 in separate test and production instances.
