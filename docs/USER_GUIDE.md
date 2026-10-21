# Aniimo Eggheist Tracker

A Windows desktop companion for tracking Eggheist runs, planning an Egg Emperor
rank goal, and displaying a local Lost Sanctum route overlay. English and
Português (Brasil) are available in Settings.

## Features

- Capture the game screen with one customizable shortcut. OCR recognizes coin
  balances, loot results and points; review or correct readings before saving.
- Start with an optional balance, record points-only runs, mark losses, edit
  saved runs, and log paid or free tickets.
- Forecast remaining runs, tickets, playtime and the per-run break-even budget,
  including keys and gear costs. Skipped play days retain your ticket stock.
- Explore loot, spending, wallet checkpoints, points and tickets on graphs.
- Recognize Lost Sanctum layouts from the full game map and follow the player
  through screen-based minimap matching. Plan routes from both entrances for
  keys, eggs, both, rich rooms or trials; choose a preferred exit while keeping
  both entrance routes visible. Toggle room icons, monsters and the legend
  independently; click a room in the app preview for details.
- Move and lock the overlay, toggle it with `;`, and keep a compact status bar
  while the game map is open. Opacity, size and zoom controls automatically
  show a live overlay preview while the app is focused; leave the Map tab or
  turn off **Live overlay preview** to finish adjusting.
- Keep screenshots from the latest **30 saved runs** by default, configurable
  in Settings. Older run records and statistics remain available.
- Create or join a **three-player party** with a random invite code and your own
  username. Share circular player markers and the strongest map identification.
  The host controls party difficulty; any member can start a new shared run.

## Download for Windows

Download **[AniimoTracker.exe from the latest release](https://github.com/CoreosG/aniimo-tracker/releases/latest)** and open it. No Python or administrator access is required. In **Map & routes**, click **Download map pack** once. The map files download directly from AniimoTools and MOANIIMO and stay on your PC.

The first-run tutorial explains capture, points, saving, overlays and parties. Reopen it anytime with **?** at the top. Its example screenshots are anonymized; original player captures are not distributed. All shortcuts shown in the guide follow your current settings.

**Settings → Storage & updates** checks GitHub at launch, at most once a day and offers a manual check. New versions download when you click the button; nothing is installed or executed automatically. Replace the old executable after closing it. Your history and settings remain in `%LOCALAPPDATA%/AniimoTracker`.

## Run from source

Requires **64-bit Windows 10/11**, **Python 3.13** with Tkinter, and Windows OCR
language support for the game's text. Install Python from
[python.org](https://www.python.org/downloads/windows/) if needed.

Clone or download this repository, open PowerShell in its folder, and run:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src/setup_maps.py
.\.venv\Scripts\python.exe src/app.py
```

Or run `scripts/setup.ps1` followed by `scripts/run.ps1`. Neither script needs administrator
access. The setup downloads map data and artwork directly from **AniimoTools**
and floor-texture references from **MOANIIMO**, onto your own PC. It parses data
literals without executing downloaded JavaScript. It does not download or run
their website application, ads, account scripts or community scripts.

**The map features need this setup step.** After it finishes, the native map
preview, routes and overlay work locally without the website being open. The
downloaded files are deliberately excluded from Git. If an upstream page
changes, setup reports an error; it does not alter your run history. Retry after
updating the setup tool. The optional original website simulator is opened at
its source unless a separate local copy is already installed.

Settings are grouped into **General**, **Goals & budget**, **Shortcuts**, and
**Storage & updates**. Map route targets and icon visibility are separate controls.

Map controls use four sections: **Route**, **Icons**, **Overlay** and **Tools**.
Overlay contains live opacity, size and zoom previews, a position reset, and
**Low CPU (1.5s)** position updates. Tools contains minimap calibration and imports.
**Stop map-only session** is beside the tracking controls at the top. The overlay
shows a compact status even before map setup; it tells you when a map pack is needed.

## Budget and analytics

The overview's **Break-even estimate** shows the coins you need to sell per run,
split into tickets, keys and replacement gear. Expand **Planning assumptions** for
the weekly totals, or choose **Adjust budget** to change the ticket target,
solo/party key count, gear costs and play schedule. It never deducts modeled costs
from your wallet automatically.

Analytics filters **Today**, **7/30/90 days**, or **All time** using the game's
configured reset hour. **Run details** supports sorting, direct editing and
**Export this period**. Unknown loot remains blank in the CSV; recorded zero
remains zero. Exports from Analytics exclude screenshot paths and notes.

**Estimated loot/hour** uses the average known loot from ticket-consuming runs
and your configured run time plus extra minutes. **Loot minus planned cost**
compares the same sample with the current budget. These are item-value estimates,
not measured playtime or cash profit. Failed runs remain in overall results and
known-loot calculations, but do not lower the successful-run points average.

## First use

1. Set your current rank, rank progress, tickets and coin balance with **Correct
   stats**. Configure the target, deadline, ticket budget and costs in Settings.
   The initial rank/tickets are example values; replace them with your own.
2. Choose the game monitor. Start a run, with or without a balance, or start
   map-only tracking from **Map & routes**.
3. Open the full game map with `M` during a run to identify the layout. Recognition
   and OCR can be wrong; review the displayed result and calibrate if needed.
4. Capture the loot and points result screens, then save the run.

Default shortcuts (all customizable):

| Action | Shortcut |
| --- | --- |
| Capture screen | `Ctrl+Shift+F8` |
| Save captured run | `Ctrl+Shift+F9` |
| Toggle overlay | `;` |
| Observe game map key | `M` |

The loot valuation is **separate from actual cash**: unsold items do not add to
the wallet. A starting balance is a wallet checkpoint after sales and shopping.
Failed runs affect rank and tickets but are excluded from the successful-run
points average.

## Party navigation

Open **Party**, save a username, and create a party or enter a teammate's
8-character code. The default server is `eggheist.banneret.app`; select
**Custom / self-hosted server** to use another instance. Everyone in a party
must use the same server. Joining does not start a tracked run or alter stats;
start your run or map-only tracking to display party navigation.

The first confident full-map identification is shared. A strictly higher
evidence score replaces it for everyone. Each player continues recognizing their
own minimap locally. Circles show names and distinct colors; a dim center and
"last known" label indicate a stale position, which disappears after 30 seconds.

The host controls **Party difficulty**. Any member can choose **New shared run**. Starting the next tracked run also announces a new shared session after completing the current session. Finishing an older ledger run and catching up does not reset the newer map again.

A new shared run clears navigation. Its first confirmed map can display an unfinished-run warning, even if the same layout repeats. Turn **Party → Warn about unfinished runs** off to hide it. Map-only tracking never displays this ledger warning. Map sharing continues without saving, discarding, or changing the unfinished run.

The relay is self-hostable with Docker or Python and needs only `websockets`.
See [server/README.md](../server/README.md) for ports, TLS, limits and deployment;
see [capacity measurements](../server/CAPACITY.md) for the initial load test.

## Correct a balance outlier

Open **Analytics → Balance history / edit**, select the observation, and choose **Edit balance**. You can also double-click a row. Enter full coins or a K/M amount; the preview shows the grouped number and compact value.

Saving edits the original checkpoint and refreshes the graph. Older checkpoint edits preserve newer authoritative balances. Editing the latest checkpoint recalculates the current wallet using spending recorded after it. Run points, loot, tickets and drafts are not changed. **Correct stats** also shows a formatted balance preview.

## Local data and privacy

Run history, settings, screenshots and calibrations are stored under
`%LOCALAPPDATA%\AniimoTracker`. Back up that folder to keep your history.
Screenshot capture and OCR run locally. While connected to a party, the chosen
server receives your username, layout evidence and map coordinates and relays
them to your party. It keeps this state in memory; it receives no screenshots,
loot values, coin balances or run history. Leaving disconnects the session;
temporary reconnect reservations expire after 60 seconds. Invite codes grant
access to a party's navigation, so share them only with intended teammates.
Map setup makes requests to the credited source sites; opening the optional
external simulator uses your browser.

This repository contains no player's database, run screenshots, credentials or
compiled application. The small marker crops in `assets/` are game-interface
recognition references, not full screenshots.

## Development and tests

After installing dependencies and map assets:

```powershell
.\.venv\Scripts\python.exe -m unittest discover
```

To build an executable for local use:

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm "packaging/Aniimo Tracker.spec"
```

The public build excludes downloaded map art and route data. It bundles only the small recognition templates, factual portal coordinates and anonymized tutorial examples. Map assets are downloaded directly from their sources through the in-app setup. Third-party content retains its original owners’ rights.

## Credits

- **[AniimoTools — Lost Sanctum](https://aniimotools.dev/map/lost-sanctum/):**
  the layout catalog, room information, map renders and route graph data used by
  the native overlay. Please visit and support the original project.
- **[MOANIIMO — Sanctum finder](https://aniimo.kr/en/palace-finder):**
  unannotated floor-map references and portal alignment coordinates used for
  screen matching.
- **Pawprint Studio / FunPlus:** Aniimo and its game content, including the
  interface icons used as recognition references.
- **Pillow, OpenCV, Python/WinRT, pywebview, websockets, and Python/Tk:** the libraries used
  by this application; their respective licenses apply.

This is an unofficial fan project, with no affiliation or endorsement implied.
Credits do not transfer ownership or grant a license to third-party content.
See [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

## Source terms

This repository is public for inspection and feedback. No open-source license
has been selected for the original tracker code yet. Third-party content always
remains subject to its owners' terms.
