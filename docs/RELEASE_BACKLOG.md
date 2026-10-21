# Next-version feedback

Collected during live testing on 2026-10-21. These are pending changes, not
released fixes.

- **Capture stays in the background.** The user reports that the main tracker
  window appears on the second monitor after using the capture shortcut.
  Investigate capture completion, automatic tab changes and window restoration.
  A shortcut must preserve the game's foreground focus and the tracker's
  minimized/background state on both single- and multi-monitor setups. Keep
  button-initiated capture restoration separate. Report capture progress in the
  overlay without bringing up the main window.
- **Explain paused map tracking.** An active run with paused navigation currently
  shows the misleading overlay combination "Ready / Run active / waiting for
  map." Show that map tracking is paused and how to resume it. Avoid suggesting
  that recognition is running while it is paused. Keep EN/PT-BR consistent.
- **Explain party prerequisites.** Live test confirmed that the detected Chaos
  layout reached the shared party. The teammate's map and position both appeared
  after resuming map tracking. Make this dependency visible in Party controls;
  preserve the user's explicit pause rather than silently restarting navigation.
- **Investigate the earlier missing-overlay session if it recurs.** Restarting
  restored visibility. The original stall was not reproduced or attributed to
  an exception; do not describe it as fixed by the status-wording release.

Before release, verify shortcut capture from inventory and result screens with
the tracker minimized and behind the game; confirm game focus is retained and
the compact overlay receives capture/save feedback. Verify party layout and
position exchange after explicitly resuming navigation.
