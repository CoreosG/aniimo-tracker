# Architecture

[← Project home](../README.md)

The desktop program is a standalone Python application under `src/`. Keeping its existing module imports avoids a packaging refactor while separating executable code from tests, documentation and release tooling.

| Area | Main files | Responsibility |
| --- | --- | --- |
| Desktop | `app.py`, `*_panel.py`, `tutorial.py` | Tk interface and local workflows |
| Run ledger | `tracker_core.py`, `analytics.py`, `balance_history.py` | SQLite history, authoritative wallet checkpoints, forecasts and chart data |
| Capture | `windows_capture.py`, `readings.py`, `screen_kind.py` | Monitor capture, local Windows OCR and conservative reading classification |
| Navigation | `sanctum.py`, `map_engine.py`, `map_overlay.py` | Full-map identification, minimap registration, route calculation and overlay |
| Party | `party_client.py`, `party_panel.py`, `party_server.py` | Ephemeral shared navigation, positions and run boundaries |
| Distribution | `asset_paths.py`, `setup_maps.py`, `update_checker.py` | Local map installation and user-initiated release downloads |

A saved run and a shared navigation session are separate concepts. Shared sessions have an increasing epoch, even when the layout repeats. A local ledger run retains the epoch it started in, so finishing an old run cannot accidentally reset a newer party map. Unfinished-run notices wait for a confirmed map, are optional, and never alter the ledger.

Only the host can change shared difficulty. Any member can explicitly announce a new shared run. Epoch and layout revisions reject stale position packets; stronger client-reported evidence replaces weaker layout evidence. Screenshots, OCR and financial calculations never go through the relay.

The default public relay runs separately from the desktop program. See [deployment](../server/README.md), [capacity notes](../server/CAPACITY.md), and the [domain vocabulary](../CONTEXT.md).
