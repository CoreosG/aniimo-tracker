# Eggheist party navigation

## Language

**Party**: Up to three people sharing navigation through one invite code. Membership is independent of each person's run ledger.

**Username**: A player's chosen display name, not a game account or authentication credential.

**Shared run**: One party navigation session. A new shared run discards the previous layout and all player locations without changing anyone's saved runs.

**Layout evidence**: A local full-map recognition result for a single layout, with an evidence score. Receiving someone else's evidence does not create new evidence of your own.

**Evidence score**: The weaker portal-template match, reduced when a portal is partly covered. Higher scores replace weaker shared layout evidence; equal scores keep the current choice. This is a comparison score, not a probability.

**Party location**: A player's last observed coordinates on the shared layout. A location belongs to one shared run and layout revision; old or incompatible locations cannot move a marker on a new layout.

## Map and distribution invariants

Route targets and icon visibility are independent. Rich-room and trial goals use the downloaded route graph. Exit preference applies separately to routes from both entrances; the default remains the nearest exit. A navigation preference never changes the run ledger.

The public executable excludes downloaded map art/data. The in-app installer retrieves them directly from their sources into a separate local cache. Tutorial assets are anonymized examples with metadata removed; original captures must not enter Git or releases. The update feed points only to versioned executable assets in this repository, and updates require a user download action.

Settings uses a section selector with shared save controls rather than another notebook: it reduces the visible fields and preserves the existing scroll container and setting bindings.
