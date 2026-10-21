# Aniimo Eggheist Tracker

A Windows desktop companion for tracking Eggheist runs, planning an Egg Emperor
egg goal, and displaying a local Lost Sanctum route overlay. English and
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

The first-run tutorial includes **Download map pack** and **Set current stats** buttons, with live setup status. You can install maps in the background and set stats without starting a run. It explains capture, points, saving, overlays and parties; the points example labels the cumulative total, run award and Emperor eggs separately. Reopen it anytime with **?** at the top. Its example screenshots are anonymized; original player captures are not distributed. All shortcuts shown in the guide follow your current settings.

### Updating the tracker

**Using 0.3.1 or earlier?** Download **0.3.2** manually once from the latest release,
close the older tracker, and open the new executable. The older updater only
opens a browser download; it cannot replace itself. Your history and settings
remain in `%LOCALAPPDATA%/AniimoTracker`.

Starting with **0.3.2**, the tracker checks at startup and every **30 minutes** while
open. An available update appears in a top banner and in
**Settings → Storage & updates**. Disable **Check on startup and every 30 minutes**
to opt out; **Check for updates** remains available for manual checks.

Click **Update & restart** when you are ready. The tracker downloads and verifies
the release executable from the project's GitHub release, waits for the current
tracker process to exit, then replaces the executable and opens the new version.
The previous executable is retained alongside it with a **`.previous`** suffix.
Your data folder stays separate from the executable. Checking alone does not
download an executable, replace it, or restart the app.

When running from Python source, updates use the **browser-download** fallback;
the updater does not replace your Python interpreter or source checkout.

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

Map controls use four visible section buttons: **Route**, **Icons**, **Overlay** and **Tools**.
Overlay contains live opacity, size and zoom previews, a position reset, and
**Low CPU (1.5s)** position updates. Tools contains minimap calibration and imports.
**Stop map-only session** is beside the tracking controls at the top. The overlay
shows a compact status even before map setup; it tells you when a map pack is needed.

**Map & routes → Persistent status bar** (at the top, below the tracking controls) keeps a compact in-game
status header visible even while idle or paused. It is **off by default**. The master
**Show overlay** switch still hides it; enabling the header does not start a run.

The bar shows your configured shortcuts. **Ctrl+Shift+F7** calls the same
**Start run** action as the button: an entered balance is optional, and a blank
balance starts the run anyway. This also switches map-only tracking into a
recorded run. Change or disable the shortcut in Settings. If an older custom
shortcut already uses that combination, it is preserved and the new start
shortcut stays blank until you choose a free combination.

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

1. Use **Correct stats** or the tutorial's **Set current stats** button to enter
   **total Egg Heist points**, tickets and coin balance. Configure the egg target,
   deadline, ticket budget and costs in Settings. Initial ticket values are
   examples; replace them with your own. An unknown total stays blank until set.
2. Use automatic game-window capture, or select the intended window in
   **Settings → General → Game capture**. Start a run, with or without a balance,
   or start map-only tracking from **Map & routes**.
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

### Game-window capture

Open **Settings → General → Game capture**. **Capture target** defaults to
**Aniimo window (automatic)**. With one Aniimo game window available, the app
follows its client area—the game content inside the window borders—as it moves
or resizes. Screenshots, OCR reading areas and minimap coordinates use that same
game area. The overlay follows the window and is kept inside it.

Use **Refresh windows** to list the available Aniimo game processes and choose
an explicit window if more than one is running. If you need monitor capture,
select **Entire monitor (manual fallback)** and choose **Fallback monitor**;
that monitor selection is used only in this fallback mode.

Window capture stops rather than guessing when the target is missing, minimized,
in the background, ambiguous or partly off-screen. Keep the whole game area
visible on your displays and bring the game to the foreground before capturing.
Capture crops the visible desktop; it does **not** reconstruct game pixels hidden
behind another window.

Changing the capture target clears custom OCR/minimap reading areas and requires
a fresh full-map confirmation. When older monitor-based settings are first
migrated to client-area capture, their custom reading areas are reset too.

Default portal matching normalizes to a 1080p reference, with regression fixtures
covering the same layout at **720p, 1080p and 4K**. Custom marker calibrations stay
at their native resolution and may need to be redone after a resolution change.
These checks do not guarantee every resolution, aspect ratio or in-game UI scale;
review recognition and use calibration when your setup differs.

### Total points and Emperor eggs

Use the cumulative number **before the slash** on the points-result screen, not
the **+points** awarded for that run. For example, **52,530 / 52,710** with
**+370** means a current total of **52,530** and an award of **370**.

The app tracks total points before and after Egg Emperor. Its default Emperor
threshold is **14,550 total points**, followed by **180 points per egg**. It derives
the egg count and progress automatically: **52,530 total → 211 eggs, 0/180**.
Before the threshold, it shows points remaining to Egg Emperor. A target of
**1,000 eggs** therefore requires **194,550 total points** with these defaults.

If you are already Emperor and the game's egg count differs, open
**Correct stats → Advanced · calibrate eggs**, enable **Calibrate using the eggs
shown in game**, and enter the total, egg count and within-egg progress from the
same screen. Calibration is optional and changes the threshold used to derive
eggs. It preserves your observed total and saved runs. Existing calibrated data
keeps its threshold during updates.

Known zero points and an unknown total are different. Enter **0** for a real zero;
older histories with no confirmed total keep their records and ask you to set it.
Losses reduce progression; the known total floors at zero after each result.
Actual signed awards remain unchanged in run history and analytics.

### Switching from map-only tracking

While map-only tracking is running, the same capture shortcut still recognizes
Inventory, loot and points. **Inventory** exits map-only mode and starts a run
with the observed balance. **Loot or points results** exit map-only mode and open
result entry; a starting balance is optional. Captures queued in that same burst
stay together through an automatic start.

You can also type points and choose **Save run** directly from map-only mode.
After saving, enter or capture the next result and save again: no start button or
balance is required for points-only logging. Saving consumes a ticket when
**Uses 1 Chaos ticket** is enabled. Starting a run alone does not consume one.

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

The relay accepts only typed navigation updates and rebuilds outgoing state from
known fields. Messages are limited to **2 KB**, JSON nesting to **16 levels**,
positions to finite **0–100** coordinates, and layout evidence to the selected
difficulty's presets. Updates have a **3/second** allowance with an initial
**8-message burst**. Malformed updates are rejected before changing shared state;
oversized or flooding connections are closed. Peers cannot supply another
member's identity to move their marker or send arbitrary files, commands or URLs
for the app to open.

These checks do not verify the truth of valid-looking map evidence or positions.
A party member can deliberately report incorrect navigation or start a new shared
run, so invite codes should be shared with people you intend to play with.

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
