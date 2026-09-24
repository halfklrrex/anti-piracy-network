# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

One Elite Dangerous commander (CMDR Arkadius Rex) who farms pirate massacre
missions by stacking them, and bounty-hunts alongside. Pledged to Arissa
Lavigny-Duval in Powerplay. Checks the stacker by alt-tabbing out of the game
on the same screen, between fights: a few seconds of full attention, then back
to flying.

## Product Purpose

Reads the Elite Dangerous journal live and answers, at a glance, the questions
a massacre stacker actually has: how many kills are left, what the stack pays
per kill, which mission each kill is feeding, where to hand in, and what is
already done. Success is never having to open the in-game transactions panel
to know where a stack stands, and never having to correct the numbers by hand.

## Positioning

It models how the game really credits kills, verified against this
commander's own journal rather than folklore: missions from different giving
factions share kills; missions from the same giving faction queue one after
another; Pirates and Deserters of one faction are separate kill streams; the
log-in `Missions` list is the authority on what still exists. Every claim on
screen is traceable to a journal event.

## Operating Context

- Local only: `stacker.py` (Python standard library) tails the journal folder
  and serves `dashboard.html` at http://127.0.0.1:8765, polled once a second.
- Viewed by alt-tab on the same monitor as the game, usually mid-session, in a
  window of its own (an Edge app window with a dedicated profile); closing the
  window quits the app. The packaged .exe has no console window.
- Journal folder: `%USERPROFILE%\Saved Games\Frontier Developments\Elite Dangerous`.

## Capabilities and Constraints

- Active massacre missions grouped by target faction, target type and system;
  kills needed = max over giving factions of that faction's queued total.
- Per-mission provider, target system and hand-in station; queue order. Progress
  is rebuilt from bounties and corrected by every completion in the stack (the game
  doesn't count every kill it pays a bounty for); a mission is never shown finished
  before the game says so, and a stack whose logged kills run past an unconfirmed
  mission is held there and says how many kills didn't count. Per-mission manual
  sync (rarely needed).
- Ready-to-hand-in list, grouped by station in nearest-first route order with
  light years per leg; its deadline is informational (the game keeps finished
  missions payable past expiry, then silently drops them some days later).
- Bounties per stack (bounties only; combat bonds are kept separate), time to
  finish at this session's or the usual pace, and amber warnings for queued
  missions that will expire before their turn.
- Free kills: for every giver behind the pace-setting queue, how many kills a
  further mission from them could need and still add nothing to the stack's
  cost (shown only while a mission slot is free).
- Target check: whether the locked ship counts toward a stack, is the right
  faction in the wrong system, or is clean (attacking it is a crime).
- Wanted alert: whether the game flags the commander as wanted, or owing a
  fine, in the current system (the `Wanted` / `ActiveFine` flags on the last
  jump in), with the amounts from `CommitCrime` events logged there. Cleared by
  `PayBounties` / `PayFines` or a clean jump back in.
- Standing with each mission provider (as of the last jump into its space),
  mission slots against the cap of 20, and a "this session" strip.
- Ranks: combat rank with this session's estimated gain and kills to the next
  rank (progress is logged only at log-in; the gain uses the commander's own
  kills-per-percent at this rank), Imperial Navy rank with an estimate of what handing in
  current Imperial missions adds (measured from the commander's own history,
  about 0.30% per reputation "+" at Duke), and Powerplay rank with merits.
- Journal view: lifetime mission pay and bounties, every stack and hunting
  session, best stacks, places and providers, and finished missions that were
  never handed in. Time played counts gaps between events, any over 10 minutes
  treated as a break.
- Toggles: hand-in station on every mission; count kills only in the target system.
- Declined by the commander: a mission-board calculator, sounds, hunting-ground
  statistics, and a phone/LAN view.
- The journal cannot see the mission board, cannot tell a Deserter kill from a
  Pirate kill of the same faction, and writes no event when a finished mission
  is dropped.

## Brand Commitments

- Apple-grade product feel, specifically alongside Apple's **Stocks** and
  **Weather** apps (user's choice).
- Presented as an in-universe Imperial device used by pilots of **Arissa
  Lavigny-Duval**; her purple eagle is the emblem. The commander supplied it
  (`emblem.png` beside `stacker.py`, transparent, origin embedded); it is the
  toolbar mark and the browser-tab icon. An original eagle mark stands in only
  if that file is removed.
- Bounties are shown as accumulated income, never framed as "at risk".
- The app is named "Imperial Anti-Piracy Network" (the commander's choice; it
  replaced "Massacre Stack"), and each launch opens with a short "Welcome,
  Commander" card around the Arissa Lavigny-Duval emblem.
- One typeface everywhere, Saira (the commander's pick over Space Grotesk, Outfit
  and Sora; serif faces were rejected as too fussy at small sizes). Bundled, never
  fetched online.

## Evidence on Hand

Real journal data only (this commander's logs). No invented lore claims,
factions, statistics or quotes. The one piece of Frontier's artwork, the
Arissa Lavigny-Duval emblem, ships in the repository at the commander's choice,
credited to Frontier in the README.

## Product Principles

1. The journal is the source of truth; say plainly when it cannot know.
2. The first glance answers "how many kills left, for how much".
3. Never claim a mission is finished before the game does.
4. Quiet by default; colour means state, not decoration.
