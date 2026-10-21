# Eggheist tracking and party navigation

## Language

**Total points**: A player's cumulative Egg Heist points across earlier tiers and Egg Emperor. A known total is distinct from an unknown legacy total; known zero is a valid observation. Each subsequent recorded award changes the known total in order, with a floor of zero after each award.

**Run award**: The actual signed points gained or lost in one run, including any daily bonus. It is separate from the cumulative total and stays unchanged in history even if a loss reaches the zero floor.

**Emperor eggs**: Progress within Egg Emperor, derived from the cumulative total above the Emperor threshold. The default threshold is 14,550 total points, with 180 additional points per egg. Before that threshold, progression is expressed as total points rather than an Emperor egg count.

**Progress calibration**: An explicit pairing of a cumulative total, Emperor egg count and within-egg progress observed together. It establishes the Emperor threshold without replacing the observed total or run history.

**Map-only tracking**: Navigation without an active ledger run. Explicit result entry or a recognized Inventory/result capture can switch the player into recording results; an observed starting balance is optional for recorded runs.

**Party**: Up to three people sharing navigation through one invite code. Membership is independent of each person's run ledger.

**Username**: A player's chosen display name, not a game account or authentication credential.

**Shared run**: One party navigation session. A new shared run discards the previous layout and all player locations without changing anyone's saved runs.

**Layout evidence**: A local full-map recognition result for a single layout, with an evidence score. Receiving someone else's evidence does not create new evidence of your own.

**Evidence score**: The weaker portal-template match, reduced when a portal is partly covered. Higher scores replace weaker shared layout evidence; equal scores keep the current choice. This is a comparison score, not a probability.

**Party location**: A player's last observed coordinates on the shared layout. A location belongs to one shared run and layout revision; old or incompatible locations cannot move a marker on a new layout.

**Modeled margin**: Known extracted item value minus the current planned per-run cost. It is a comparison against today's budget settings, not realized cash profit or historical spending.

**Estimated rate**: A rate based on ticket-consuming runs and configured run minutes plus extra minutes. It is not measured playtime. Unknown loot is excluded from loot averages and rates, while known zero loot is included.

## Map and distribution invariants

Route targets and icon visibility are independent. Rich-room and trial goals use the downloaded route graph. Exit preference applies separately to routes from both entrances; the default remains the nearest exit. A navigation preference never changes the run ledger.

The public executable excludes downloaded map art/data. The in-app installer retrieves them directly from their sources into a separate local cache. Tutorial assets are anonymized examples with metadata removed; original captures must not enter Git or releases. The update feed points only to versioned executable assets in this repository, and updates require a user download action.

Settings uses a section selector with shared save controls rather than another notebook: it reduces the visible fields and preserves the existing scroll container and setting bindings.

A shared run advances by an explicit member announcement or the next tracked start after completing that shared session. Only the host changes difficulty. Shared epochs distinguish repeated layouts. A local ledger run keeps its original epoch when navigation advances, so late ledger completion cannot reset a newer party map. Optional unfinished-run notices require both a new shared epoch and a confirmed map; map-only sessions never display them.

Historical balance edits replace the original wallet checkpoint amount while preserving its timestamp, progression fields and cutoffs. Newer authoritative wallet observations still win. Editing the latest checkpoint recalculates the wallet from its original cutoffs; drafts and run results are not changed.
