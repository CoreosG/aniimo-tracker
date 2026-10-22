# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.3.8] - 2026-10-22

### Fixed

- Keep background refresh and map-key polling scheduled after callback errors,
  so a transient map failure cannot permanently freeze later party joins.
- Reject minimap positions from cached/manual rectangles when the circular HUD
  rim is absent, including menus that contain map-like pixels.
- Ignore bright party/waypoint icons when comparing the outdoor island reference.

### Added

- Rate-limited local callback diagnostics with two bounded log files.
- Portuguese manual-balance start/join regressions in both operation orders.

## [0.3.7] - 2026-10-21

### Added

- Party navigation guidance with direct Start map tracker / Resume map buttons,
  map-pack setup guidance and local-position requirements in English and PT-BR.

### Fixed

- Keep the selected page when processing shortcut captures instead of switching
  automatically to Overview. Verify foreground focus and minimized state across
  result captures, inventory starts and overlay refreshes.
- Say Map tracking paused in the persistent overlay instead of Ready, and
  suppress waiting-for-map messages while navigation is paused.

## [0.3.6] - 2026-10-21

### Fixed

- Show one navigation status outside a dungeon instead of repeating
  “waiting for minimap” and “waiting for map” in the overlay. Keep run status
  and capture/save hints visible in English and PT-BR.

## [0.3.5] - 2026-10-21

### Added

- Automatic minimap layout identification using compact corridor masks,
  repeated evidence, layout/position ambiguity rejection and outdoor references.
- Identify from minimap toggle and a small map-pack upgrade for older installs.
- Reference maps and player alignment for all supported difficulty pools.

### Changed

- Keep M as confirmation/correction and retain feature-based position tracking.
- Share confirmed minimap evidence with parties below strong portal evidence.
- Hide dungeon navigation after outdoor detection without changing run records.
- Credit MOANIIMO for the detection approach; update English/PT-BR help.

### Fixed

- Retain local recognition for parties joined after identification, without
  reusing evidence for another layout or echoing received party evidence.

## [0.3.4] - 2026-10-21

### Added

- A dated changelog with categories and version comparison links.

### Changed

- Use **Start run / capture** (**Ctrl+Shift+F8**) as one action: Inventory reads
  the starting balance, results read loot or points, and other gameplay starts
  a run without a balance. The persistent bar shows the same shortcut.

### Fixed

- Allow capture to start a run without a balance during a map-only session.
- Preserve custom capture and overlay shortcuts when loading older settings.

### Removed

- The redundant separate **Ctrl+Shift+F7** Start run shortcut.

## [0.3.3] - 2026-10-21

### Added

- Visible Route, Icons, Overlay and Tools buttons in English and Brazilian Portuguese.
- A customizable Start run shortcut, Ctrl+Shift+F7, with optional balance.

### Changed

- Move Persistent status bar to the main map controls, showing start/capture/save hints.

## [0.3.2] - 2026-10-21

### Added

- An update banner and verified **Update & restart** for Windows executables,
  preserving history and settings and keeping a `.previous` executable backup.
- Update checks at startup and every 30 minutes, with an automatic-check setting.
- Aniimo client-area capture, explicit window selection and monitor fallback.

### Changed

- Follow the selected game window when it moves or resizes.
- Normalize default portal recognition across 720p, 1080p and 4K.
- Keep browser downloads for source runs and older clients.

### Fixed

- Reject unavailable, minimized, background, ambiguous or off-screen capture targets.
- Reset incompatible reading areas when migrating or changing capture targets.

## [0.3.1] - 2026-10-21

### Added

- Total Egg Heist points before Emperor, Emperor egg counts and optional calibration.
- Expanded English/PT-BR tutorial with map-pack download and current-stat setup.
- Optional persistent status bar between runs, respecting game focus and overlay visibility.
- Party packet validation, bounded message rates and malformed-value rejection on server and client.

### Fixed

- Inventory and result captures during map-only tracking, including queued capture bursts.
- Zero-point results and total-point floors after losses.

## [0.3.0] - 2026-10-21

### Added

- Compact per-run budget target with ticket/key/gear breakdown and collapsed assumptions.
- Today/90-day analytics, estimated loot/hour, planned-cost comparisons,
  sortable run details, direct editing and period CSV exports.
- Grouped map controls, live slider values, position reset and Low CPU updates.

### Changed

- Simplify goal/playtime summaries and reflow stats on narrow windows.
- Keep overlay headers to two lines and fit maps within the monitor.
- Cache minimap bounds, skip hidden previews and coalesce slider writes.
- Recognize portal fragments around overlapping 1P/2P/3P badges.

### Fixed

- Missing-map-pack overlay feedback, Auto layout recognition reset and disconnected displays.
- Forecast background and rank progress labels in the corrected release build.
- Retained screenshot dialogs and unbounded map/route caches.

## [0.2.1] - 2026-10-21

### Added

- Historical balance editing, optional unfinished-run party notices, map-only status,
  application icon and repository documentation.

## [0.2.0] - 2026-10-21

### Added

- Initial public release with run tracking, local map-pack setup, party navigation,
  tutorial, update checks and map controls.

[Unreleased]: https://github.com/CoreosG/aniimo-tracker/compare/v0.3.8...HEAD
[0.3.8]: https://github.com/CoreosG/aniimo-tracker/compare/v0.3.7...v0.3.8
[0.3.7]: https://github.com/CoreosG/aniimo-tracker/compare/v0.3.6...v0.3.7
[0.3.6]: https://github.com/CoreosG/aniimo-tracker/compare/v0.3.5...v0.3.6
[0.3.5]: https://github.com/CoreosG/aniimo-tracker/compare/v0.3.4...v0.3.5
[0.3.4]: https://github.com/CoreosG/aniimo-tracker/compare/v0.3.3...v0.3.4
[0.3.3]: https://github.com/CoreosG/aniimo-tracker/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/CoreosG/aniimo-tracker/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/CoreosG/aniimo-tracker/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/CoreosG/aniimo-tracker/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/CoreosG/aniimo-tracker/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/CoreosG/aniimo-tracker/tree/v0.2.0
