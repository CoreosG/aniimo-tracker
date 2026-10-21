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
  keys, eggs, or both; toggle room icons independently.
- Move and lock the overlay, toggle it with `;`, and keep a compact status bar
  while the game map is open.
- Keep screenshots from the latest **30 saved runs** by default, configurable
  in Settings. Older run records and statistics remain available.

## Windows setup

Requires **64-bit Windows 10/11**, **Python 3.13** with Tkinter, and Windows OCR
language support for the game's text. Install Python from
[python.org](https://www.python.org/downloads/windows/) if needed.

Clone or download this repository, open PowerShell in its folder, and run:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe setup_maps.py
.\.venv\Scripts\python.exe app.py
```

Or run `setup.ps1` followed by `run.ps1`. Neither script needs administrator
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

## Local data and privacy

Run history, settings, screenshots and calibrations are stored under
`%LOCALAPPDATA%\AniimoTracker`. Back up that folder to keep your history.
Screenshot capture and OCR run locally. Map setup makes requests to the credited
source sites; opening the optional external simulator uses your browser.

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
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm "Aniimo Tracker.spec"
```

The local build bundles your downloaded assets. They retain their original
owners' rights; this repository does not grant permission to redistribute those
assets or a bundle containing them. No bundled executable is published here.

## Credits

- **[AniimoTools — Lost Sanctum](https://aniimotools.dev/map/lost-sanctum/):**
  the layout catalog, room information, map renders and route graph data used by
  the native overlay. Please visit and support the original project.
- **[MOANIIMO — Sanctum finder](https://aniimo.kr/en/palace-finder):**
  unannotated floor-map references and portal alignment coordinates used for
  screen matching.
- **Pawprint Studio / FunPlus:** Aniimo and its game content, including the
  interface icons used as recognition references.
- **Pillow, OpenCV, Python/WinRT, pywebview, and Python/Tk:** the libraries used
  by this application; their respective licenses apply.

This is an unofficial fan project, with no affiliation or endorsement implied.
Credits do not transfer ownership or grant a license to third-party content.
See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Source terms

This repository is public for inspection and feedback. No open-source license
has been selected for the original tracker code yet. Third-party content always
remains subject to its owners' terms.
