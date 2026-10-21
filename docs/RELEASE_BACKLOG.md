# Release follow-ups

Last updated 2026-10-21.

## Pending investigation

The earlier missing-overlay session recovered after restarting. Its original
stall was not reproduced or attributed to an exception. If it recurs, capture
bounded local diagnostics; do not describe it as fixed by the status updates.

## Addressed in 0.3.7

- Captured results keep the selected page. Native Windows focus and minimized
  state checks cover result capture, inventory starts and overlay refreshes;
  button-initiated window restoration is tested separately.
- The persistent overlay explicitly identifies paused map tracking rather than
  saying Ready or waiting for map.
- The Party page exposes Start / Resume map tracking and explains that local
  minimap readings are required for positions. A real isolated relay test covers
  shared layout adoption and bidirectional positions after resuming, without
  altering the run ledger. Explicit pauses remain respected.
