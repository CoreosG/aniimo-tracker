# Architecture

[← Project home](../README.md)

The desktop program is a standalone Python application under `src/`. Keeping its existing module imports avoids a packaging refactor while separating executable code from tests, documentation and release tooling.

| Area | Main files | Responsibility |
| --- | --- | --- |
| Desktop | `app.py`, `*_panel.py`, `tutorial.py` | Tk interface and local workflows |
| Run ledger | `tracker_core.py`, `analytics.py`, `balance_history.py` | SQLite history, authoritative wallet checkpoints, forecasts and chart data |
| Capture | `windows_capture.py`, `readings.py`, `screen_kind.py` | Monitor capture, local Windows OCR and conservative reading classification |
| Navigation | `sanctum.py`, `minimap_recognition.py`, `map_engine.py`, `map_overlay.py` | Portal/corridor identification, minimap registration, route calculation and overlay |
| Party | `party_client.py`, `party_panel.py`, `party_server.py` | Ephemeral shared navigation, positions and run boundaries |
| Distribution | `asset_paths.py`, `setup_maps.py`, `update_checker.py` | Local map installation and user-initiated release downloads |

A saved run and a shared navigation session are separate concepts. Shared sessions have an increasing epoch, even when the layout repeats. A local ledger run retains the epoch it started in, so finishing an old run cannot accidentally reset a newer party map. Unfinished-run notices wait for a confirmed map, are optional, and never alter the ledger.

Only the host can change shared difficulty. Any member can explicitly announce a new shared run. Epoch and layout revisions reject stale position packets; stronger client-reported evidence replaces weaker layout evidence. Screenshots, OCR and financial calculations never go through the relay.

The default public relay runs separately from the desktop program. See [deployment](../server/README.md), [capacity notes](../server/CAPACITY.md), and the [domain vocabulary](../CONTEXT.md).

`budget_panel.py` owns the compact budget presentation while `tracker_core.break_even`
remains the calculation interface. `analytics.build_report` returns both chart data
and filtered run comparisons; CSV export consumes that same report. Historical
wallet observations and modeled item-value margins remain separate.

Each map model caches accepted minimap bounds, not accepted positions. A new
frame must still satisfy the original registration checks. Manual bounds take
priority; resolution changes and repeated misses trigger discovery again.
UI preview rendering is deferred while hidden and refreshed on return. Overlay
slider previews are coalesced separately from persistence, and ephemeral
positions do not cause a configuration-file write on every frame.

Shared layout knowledge and local dungeon presence are independent. Only local
observations authorize dungeon navigation and outgoing positions. An outdoor
observation clears local presence and publishes a null location. Player trails
are bounded client-side paths, with no trail history or extra calculation on the
relay. Explicit update restarts use a single-use DPAPI-protected resume handoff
and disconnect without sending Leave; ordinary closes retain Leave behavior.
Authenticated reconnects replace the seat's prior transport even when it remains
half-open. Each handler keeps its own outgoing queue, and incoming updates and
cleanup require current socket ownership. The retired socket receives a fixed
terminal error before closure, so a live old client cannot fight the replacement.
The relay advertises its periodic full-state interval in the welcome message.
The desktop validates the optional capability and tracks full-state receipt
separately from position deltas, control pings and the incoming flood budget.
Missing full states trigger reconnect after the greater of 45 seconds or three
advertised intervals. Legacy relays without that capability retain idle behavior.
Each network-to-UI snapshot carries the validated connection identity, so a busy
UI can restore connected state even if its bounded queue displaced the welcome.
The reconnect token remains private to the worker and never enters UI events.

The relay optionally checkpoints membership and shared layout through `party_cache.py`.
An atomic private file holds at most the configured room limit, no coordinates,
and SHA-256 hashes of high-entropy resume tokens. Writes run off the event loop
after membership/layout changes and every ten seconds while active. A cached
member expires at most sixty seconds after its last online checkpoint; offline
reservations keep their original expiry. Restore marks everyone offline and clears
positions. This is restart recovery for one relay process, not multi-replica routing.

Map libraries retain two recently used models each. Route results live in each
model's bounded cache, so global cache keys cannot prolong an evicted model's
lifetime. Active callers may keep their current model even after library eviction.
Localization removes per-widget references, variable traces and Tcl commands on
widget destruction; closed image canvases must not remain reachable through it.

Automatic layout recognition owns compact floor masks and temporal evidence for
one navigation context. Outdoor RGB-reference matching precedes dungeon acceptance.
Repeated rooms, weak observations and missing HUDs cannot select a layout. Context,
difficulty and capture-target changes discard prior recognition state; scan results
still pass the generation check before affecting the UI. M portal readings retain
authority within a dungeon. Confirmed feature registration remains the preferred
position reading, with an unambiguous corridor position as fallback.
