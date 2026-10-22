# Eggheist tracking and party navigation

## Language

**Total points**: A player's cumulative Egg Heist points across earlier tiers and Egg Emperor. A known total is distinct from an unknown legacy total; known zero is a valid observation. Each subsequent recorded award changes the known total in order, with a floor of zero after each award.

**Run award**: The actual signed points gained or lost in one run, including any daily bonus. It is separate from the cumulative total and stays unchanged in history even if a loss reaches the zero floor.

**Emperor eggs**: Progress within Egg Emperor, derived from the cumulative total above the Emperor threshold. The default threshold is 14,550 total points, with 180 additional points per egg. Before that threshold, progression is expressed as total points rather than an Emperor egg count.

**Progress calibration**: An explicit pairing of a cumulative total, Emperor egg count and within-egg progress observed together. It establishes the Emperor threshold without replacing the observed total or run history.

**Update check**: Discovery of a newer tracker release. It can run automatically at startup and every 30 minutes unless disabled, without downloading or installing the executable.

**Update and restart**: A user-requested replacement of the packaged tracker with a verified release executable. It preserves the prior executable as a `.previous` backup and reopens the new version while keeping the player's data separate.

**Map-only tracking**: Navigation without an active ledger run. Explicit result entry or Start run / capture can switch the player into recording results; an observed starting balance is optional for recorded runs.

**Capture target**: The chosen game window or explicit entire-monitor fallback. Automatic selection requires one unambiguous game window belonging to an Aniimo process; window capture uses the visible client area rather than the desktop's full monitor bounds.

**Client area**: The game content inside its window borders. Window-mode screenshot reading areas, minimap coordinates and overlay placement refer to this area and follow its movement and resizing. Hidden or unavailable game content is not an observation.

**Party**: Up to three people sharing navigation through one invite code. Membership is independent of each person's run ledger.

**Party restart recovery**: A brief reservation of party membership and shared layout across a relay restart. Members reconnect with their existing identities and code; locations must be observed again. It is not a permanent party or player history.

**Username**: A player's chosen display name, not a game account or authentication credential.

**Shared run**: One party navigation session. A new shared run discards the previous layout and all player locations without changing anyone's saved runs.

**Layout evidence**: A local full-map portal reading or repeated, unambiguous minimap corridor observations identifying one layout. Receiving someone else's evidence does not create new evidence of your own.

**Evidence score**: The weaker portal-template match, reduced when a portal is partly covered, or a capped score for confirmed minimap observations. Higher scores replace weaker shared layout evidence; equal scores keep the current choice. This is a comparison score, not a probability.

**Outdoor observation**: Local evidence that the player is outside a dungeon. It suppresses dungeon navigation without ending, saving or starting a ledger run. Returning to a dungeon requires fresh layout evidence.

**Local dungeon presence**: A fresh local dungeon-map or confirmed minimap observation showing that this player is inside. A shared layout identifies the party's dungeon but does not establish local presence. Until local presence is known, only the shared-layout status is shown. An outdoor observation withdraws the player's shared location.

**Player trail**: A bounded, optional history of observed locations within one navigation session and layout revision. It uses that player's marker color, breaks at missing locations or implausible jumps, and is separate from planned routes. Trails are reconstructed locally from position messages; they are not uploaded as history.

**Party location**: A player's last observed coordinates on the shared layout. A location belongs to one shared run and layout revision; old or incompatible locations cannot move a marker on a new layout.

**Modeled margin**: Known extracted item value minus the current planned per-run cost. It is a comparison against today's budget settings, not realized cash profit or historical spending.

**Estimated rate**: A rate based on ticket-consuming runs and configured run minutes plus extra minutes. It is not measured playtime. Unknown loot is excluded from loot averages and rates, while known zero loot is included.

## Map and distribution invariants

Map settings sections use visible buttons rather than a dropdown. Persistent
status visibility is a top-level map control, independent of the selected
settings page. One Start run / capture shortcut reads Inventory balance or result
values when recognized and otherwise starts without a balance. The manual Start
run button also accepts an optional balance. Retiring a shortcut preserves other
custom bindings.

Route targets and icon visibility are independent. Rich-room and trial goals use the downloaded route graph. Exit preference applies separately to routes from both entrances; the default remains the nearest exit. A navigation preference never changes the run ledger.

A changed capture target invalidates custom reading areas and prior map confirmation. Monitor-relative areas cannot be silently reused as client-relative areas. Default portal recognition scales independently of native custom marker calibration; a resolution change can require recalibrating custom markers.

The public executable excludes downloaded map art/data. The in-app installer retrieves them directly from their sources into a separate local cache. Tutorial assets are anonymized examples with metadata removed; original captures must not enter Git or releases. The update feed points only to versioned executable assets in this repository. Downloading and replacing the executable requires an explicit Update & restart action; background checks alone never install or restart. Source runs use a browser download instead of replacing the interpreter or source files.

Settings uses a section selector with shared save controls rather than another notebook: it reduces the visible fields and preserves the existing scroll container and setting bindings.

A shared run advances by an explicit member announcement or the next tracked start after completing that shared session. Only the host changes difficulty. Shared epochs distinguish repeated layouts. A local ledger run keeps its original epoch when navigation advances, so late ledger completion cannot reset a newer party map. Optional unfinished-run notices require both a new shared epoch and a confirmed map; map-only sessions never display them.

Historical balance edits replace the original wallet checkpoint amount while preserving its timestamp, progression fields and cutoffs. Newer authoritative wallet observations still win. Editing the latest checkpoint recalculates the wallet from its original cutoffs; drafts and run results are not changed.
