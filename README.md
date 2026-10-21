<div align="center">
  <img src="assets/branding/icon.png" width="112" alt="Eggheist Tracker icon">
  <h1>Aniimo Eggheist Tracker</h1>
  <p>Track your runs. Plan your Emperor egg goal. Find your way through Lost Sanctum.</p>
  <p>
    <a href="https://github.com/CoreosG/aniimo-tracker/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/CoreosG/aniimo-tracker?style=flat-square&color=79dcc8"></a>
    <img alt="Windows 10 and 11" src="https://img.shields.io/badge/platform-Windows_10_%2F_11-8fbaff?style=flat-square">
    <img alt="English and Brazilian Portuguese" src="https://img.shields.io/badge/languages-EN_%2F_PT--BR-b6a0f4?style=flat-square">
  </p>
  <p><b><a href="https://github.com/CoreosG/aniimo-tracker/releases/latest">Download for Windows</a></b> · <a href="docs/USER_GUIDE.md">User guide</a> · <a href="server/README.md">Self-host a party server</a> · <a href="https://github.com/CoreosG/aniimo-tracker/issues">Report an issue</a></p>
</div>

---

## Get started

1. Download **AniimoTracker.exe** from the [latest release](https://github.com/CoreosG/aniimo-tracker/releases/latest) and open it. **No Python required.**
2. Use the tutorial's **Set current stats** button to enter your **total Egg Heist points**, tickets and balance. Capture follows the Aniimo window automatically by default; choose another target in **Settings → General → Game capture** if needed. You can set stats without starting a run. Reopen the tutorial anytime with **?**.
3. Click **Download map pack** in the tutorial or **Map & routes** once. Maps download directly from AniimoTools and MOANIIMO in the background.

**Updating from 0.3.1 or earlier?** Download **0.3.2** once from the latest release, close the older tracker, and open the new executable. Older versions only open the download in your browser. Your history and settings stay in `%LOCALAPPDATA%/AniimoTracker`.

**From 0.3.2 onward**, an update banner offers **Update & restart**: it downloads and verifies the release, closes the tracker, replaces the executable with a `.previous` backup, and reopens it. Checks run at startup and every 30 minutes; turn them off in **Settings → Storage & updates** if preferred.

## One shortcut, the right reading

| In the game | Press | What happens |
| :--- | :---: | :--- |
| Any screen | **Ctrl + Shift + F7** | Use Start run; balance is optional |
| Inventory, after shopping | **Ctrl + Shift + F8** | Start a run and read your balance |
| Loot result | **Ctrl + Shift + F8** | Record the extracted loot value |
| Egg Heist result | **Ctrl + Shift + F8** | Read points gained or lost |
| Results ready | **Ctrl + Shift + F9** | Save the run; loot is optional |
| During navigation | **M** | Identify the map from the game’s full map |
| During navigation | **;** | Show or hide the overlay |

All shortcuts are customizable. You can also start without a balance, enter a run manually, record only points, or use **map-only tracking**.

Already using map-only tracking? Capturing Inventory starts a run with the observed balance. Capturing a result switches to result entry. You can save points-only results repeatedly without starting a run first.

<details>
<summary><b>See the capture screens</b></summary>
<br>
<p align="center">
  <img src="assets/tutorial/inventory.png" width="30%" alt="Inventory: capture your starting balance">
  <img src="assets/tutorial/loot.png" width="30%" alt="Loot result: capture the run’s loot value">
  <img src="assets/tutorial/points.png" width="30%" alt="Points result: capture the award, then save">
</p>
These are anonymized tutorial examples. Original player screenshots are not distributed.
</details>

## What you can do

| Track and plan | Navigate and play together |
| :--- | :--- |
| Editable runs, failures, paid and free tickets | All 21 layouts across four difficulties |
| Total points, Emperor eggs, tickets and remaining-playtime forecasts | Routes from both entrances; preferred exits |
| Key, gear and daily ticket break-even budgets | Key doors, eggs, rich rooms or trials |
| Loot, wallet, points and ticket graphs | Optional room icons, monsters and legend |
| Estimated loot/hour, sortable run details and filtered CSV export | Low CPU position updates and cached minimap detection |
| Edit historical balance checkpoints to fix outliers | Three-player parties with shared layouts and positions |
| Keep screenshots for the latest 30 runs, or choose a limit | Movable, click-through overlay with live display previews |

**Loot value and wallet balance are separate.** Unsold items do not add cash. Inventory captures record your wallet after sales and shopping. Failed runs affect progression but stay out of the successful-run points average.

### New in 0.3.2

Update directly from the tracker with **Update & restart**, available in the top banner and **Settings → Storage & updates**. Downloads and replacement require your click. Automatic checks run at startup and every 30 minutes; source runs keep the browser-download option.

Capture follows the Aniimo window's game area as it moves or resizes, and the overlay stays inside it. **Settings → General → Game capture** offers automatic or explicit game-window selection and a manual entire-monitor fallback. Default portal recognition covers tested 720p, 1080p and 4K cases; keep the game visible and recalibrate custom markers after resolution changes when needed. See [capture setup and limits](docs/USER_GUIDE.md#game-window-capture).

### Added in 0.3.1

**Total points come first**, including before Egg Emperor. Egg counts are derived automatically; optional calibration uses the total, eggs and progress shown on the same screen. The tutorial now includes setup buttons and annotated examples distinguishing total points from a run's award. Map-only captures switch into run tracking or result entry when needed.

Want a compact status bar even while idle or paused? Enable **Persistent status bar** at the top of **Map & routes**, beside the tracking controls. It is off by default and still follows the master **Show overlay** switch. Its hints use your customized start/capture/save shortcuts.

### The 0.3 interface

The break-even card shows one sales target per run, with a colored ticket/key/gear breakdown. Assumptions stay collapsed until you need them. Analytics adds Today and 90-day filters, per-run comparisons, editing and CSV export. Map controls are grouped into **Route**, **Icons**, **Overlay** and **Tools**.

**Using a slower PC?** Choose **Map & routes → Overlay → Position updates → Low CPU (1.5s)**. Map identification and OCR work locally in background workers. Position tracking reuses the detected minimap area, while keeping the same geometric checks. See [performance notes](docs/PERFORMANCE.md) for measurements and limits.

[Release notes →](docs/CHANGELOG.md)

<details>
<summary><b>See the new analytics and budget</b></summary>
<p>These previews use invented demo data.</p>
<img src="assets/previews/goal.png" width="900" alt="Total points, Emperor eggs and remaining-playtime goal estimate">
<img src="assets/previews/analytics.png" width="900" alt="Analytics with estimated loot per hour, budget comparison and history charts">
<img src="assets/previews/budget.png" width="900" alt="Compact break-even target with ticket, key and gear costs">
</details>

## Party navigation

Open **Party**, choose a username, then create a party or join an eight-character code. Up to three players share map identification and circular position markers through the default relay at **eggheist.banneret.app**. A custom server can be selected instead.

Any member can start a **New shared run**; the host controls difficulty. A confirmed map in a new shared run can warn about an unfinished local run, even when the layout repeats. **Warn about unfinished runs** is optional, and map-only users do not receive ledger warnings. Navigation advances without saving or discarding anyone’s unfinished results.

The relay forwards bounded navigation fields, not arbitrary commands, files or download links. It checks message size, rate, numeric ranges and packet structure. A teammate can still provide inaccurate map evidence or coordinates; share invite codes with intended teammates.

[Party usage and privacy →](docs/USER_GUIDE.md#party-navigation) · [Self-hosting →](server/README.md) · [Capacity measurements →](server/CAPACITY.md)

## Your data stays yours

Screenshots, OCR, balances and run history stay on your PC. A party relay receives only the chosen username, shared-run/map information and map coordinates. Its party state is held in memory.

Back up `%LOCALAPPDATA%/AniimoTracker` to preserve your data. The public executable excludes downloaded map art/data and personal databases. See the [user guide](docs/USER_GUIDE.md#local-data-and-privacy) for details.

## Inside the repository

```text
assets/       Recognition references, branding and anonymized tutorial examples
src/          Desktop app, ledger, OCR, map recognition and party communication
tests/        Ledger, vision, navigation and desktop regression tests
docs/         User guide, development and architecture notes
packaging/    Windows executable specification
scripts/      Source setup, launch and build helpers
server/       Lightweight relay deployment and load-test tooling
```

[Run from source, test and build →](docs/DEVELOPMENT.md) · [Architecture →](docs/ARCHITECTURE.md) · [Contributing →](CONTRIBUTING.md)

## Credits

The map features use resources downloaded directly from **[AniimoTools — Lost Sanctum](https://aniimotools.dev/map/lost-sanctum/)** and **[MOANIIMO — Sanctum finder](https://aniimo.kr/en/palace-finder)**. Please visit and support the original projects. Aniimo and its game content belong to **Pawprint Studio / FunPlus**.

This is an unofficial fan project. Third-party content retains its owners’ rights; credit does not grant redistribution rights. See [third-party notices](THIRD_PARTY_NOTICES.md). The original tracker source is public for inspection and feedback; an open-source license has not yet been selected.
