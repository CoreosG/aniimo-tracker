# Changes

## 0.3.1

- Capture Inventory while map-only tracking is active to start a recorded run.
  Capture or enter points and save directly; rapid captures stay queued together.
- Show total Egg Heist points before Emperor, then also show Emperor eggs.
  Preserve existing calibration and offer optional calibration from a single
  result screen. Recognize earlier-tier point results too.
- Expand the tutorial with map-pack download and current-stat setup buttons,
  annotated examples and English/Brazilian Portuguese instructions.
- Add **Keep status bar between runs** in Map & routes > Overlay, off by default.
  The compact, click-through bar respects game focus and the overlay toggle.
- Validate party packets on both the relay and client, bound message/event rates
  and reject malformed values before updating shared state. Navigation packets
  cannot supply executable commands, files or update URLs.
- Preserve known total points at zero after losses and handle zero-point results
  without breaking the forecast, save flow or next startup.

## 0.3.0

The release download was rebuilt with a matching-background forecast panel,
labeled rank progress and three-line assumptions. This corrected build also
releases closed screenshot dialogs and caps map/route caches to avoid retaining
all visited maps. Download 0.3.0 again if you obtained the initial build.

- Replace the long budget paragraph with a per-run sales target, proportional
  ticket/key/gear breakdown, collapsed assumptions and a budget settings shortcut.
- Simplify goal/playtime summaries and reflow overview stats on narrower windows.
- Add Today/90-day analytics filters, estimated loot/hour, comparisons against
  current planned costs, sortable per-run details, direct editing and period CSV.
- Group map controls into Route, Icons, Overlay and Tools. Show live slider
  values, add overlay position reset, and move map-only stop to the toolbar.
- Keep overlay headers to two lines and fit the map within the monitor.
- Cache detected minimap bounds, skip hidden preview renders, coalesce slider
  writes and offer Low CPU position updates.
- Recognize visible portal fragments around stacked 1P/2P/3P badges, including
  overlap on both entrances, while retaining the full-map and ambiguity checks.
- Show an explanatory overlay before the map pack is downloaded. Resetting a
  layout to Auto rearms recognition; disconnected displays no longer stop map
  polling with an indexing error.
- Preserve existing run history, settings, editable balance checkpoints,
  screenshot retention, party navigation and English/PT-BR support.

## 0.2.1

- Add historical balance editing, optional unfinished-run party notices,
  map-only status, the application icon and repository documentation.
