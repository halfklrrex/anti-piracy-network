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

- Local: `stacker.py` (Python standard library) tails the journal folder
  and serves `dashboard.html` at http://127.0.0.1:8765, polled once a second.
  The one exception is Recon (`recon.py`), which asks INTRA and EDSM about
  systems (a position and system names only; never the commander's name or
  standing). It is on by default and switched off under Settings (the
  commander's choice: opt-out).
- Viewed by alt-tab on the same monitor as the game, usually mid-session, in a
  window of its own: a frameless WebView2 window (`appwindow.py`, pywebview)
  whose title bar is the dashboard's toolbar, with macOS-style red, yellow and
  green buttons at its left (the commander's choice, over Windows' conventions).
  Dragging empty toolbar and top-edge resizing are done by Python following the
  mouse (WebView2 holds it); the other edges resize natively; its size and place
  are remembered. Without pywebview or WebView2 it falls back to an Edge app
  window. Closing the window quits the app. The packaged .exe has no console
  window.
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
- Next deadline: the soonest among the missions still needing kills, queued ones
  included, in the side column and the mini window; amber under two hours, as
  the missions' own countdowns. Finished missions don't count (the game keeps
  them payable past it).
- Free kills: for every giver behind the pace-setting queue, how many kills a
  further mission from them could need and still add nothing to the stack's
  cost (shown only while a mission slot is free).
- Target check: whether the locked ship counts toward a stack, is the right
  faction in the wrong system, or is clean (attacking it is a crime).
- Wanted alert: whether the game flags the commander as wanted, or owing a
  fine, in the current system (the `Wanted` / `ActiveFine` flags on the last
  jump in), with the amounts from `CommitCrime` events logged there. Cleared by
  `PayBounties` / `PayFines` or a clean jump back in.
- Standing with each mission provider (last reading on a jump into its space,
  plus the "+" from missions handed in since, at the commander's measured rate),
  mission slots against the cap of 20, and a "this session" strip.
- Session earnings (Hunt's strip, Commander, the mini window's credits an
  hour, History, the Statistics chart) count missions as their kills are made,
  not at hand-in (`mission_shares`): a kill counts for the mission at the front
  of each giver's queue against its faction in its system, and earns that
  mission's reward over the kills it took (over its kill count while it's
  still being worked). Counting at hand-in showed a stacking session at about
  a seventh of what it earned (14M against 107M an hour on 2026-09-30), since a
  stack's money is paid sessions after it's earned. Missions that fail, are
  abandoned, run out or that the game drops unclaimed (gone from its list at
  log-in) earn nothing. What was handed in stays on hover. Stacks keep what
  they actually paid.
- Ranks: combat rank with this session's estimated gain and kills to the next
  rank (progress is logged only at log-in; the gain uses the commander's own
  kills-per-percent at this rank), Imperial Navy rank with an estimate of what handing in
  current Imperial missions adds (measured from the commander's own history,
  about 0.30% per reputation "+" at Duke), and Powerplay rank with merits.
- Five pages: Hunt (the live stacks), Commander (this session in full with crew
  share and a copyable summary, ranks with time to the next at this session's
  pace, mission providers and targets with standing and faction state),
  Statistics (lifetime earnings, an earnings-per-hour chart, kills by faction,
  ship type, system and own ship, favourites, missions, crew wages, deaths,
  every stack), History (every session as a link to its own statistics) and
  Recon (where to stack next). A relog within 30 minutes continues the session.
- Recon: target systems (one pirate faction's home) whose sources in reach
  have exactly that one target (INTRA's pairs), ranked by distinct givers
  (non-Anarchy factions, each counted once across sources, as same-giver
  missions queue) divided by the pirate factions there; givers weighed by
  state (Elections count for nothing: 0 of 28 in the commander's journal;
  states measured from the journal at 15+ samples, defaults otherwise) and
  left out when Unfriendly or Hostile. The commander's standing (full-history
  ledger) is highlighted and breaks ties; "Best pay" ranks by it. Reference
  system defaults to the current one; the ship, picked from the fleet, sets
  the pad size; Refine prioritises giver allegiance and the power holding the
  target, and sets radius and sort. States older than 3 days are ignored,
  systems not reported for 7 days dropped. Deserters and Infected missions
  target the same factions, so there is no separate control. Sources with two
  or more pirate systems in reach are not shown (INTRA leaves them out).
- Settings is a page of its own (the toolbar button, Back or Esc returns): style,
  the Hunt toggles (hand-in station on every mission; count kills only in the
  target system), the mini window, Recon's online switch, and where the app keeps
  its files. Everything is saved in `config.json`.
- The app's own files (settings, hand corrections, Recon's cache, an emblem of
  the commander's own) live in `Anti-Piracy Network` inside the journal folder,
  whichever folder the app runs from; older copies beside the app, and the cache
  in AppData, are moved there on first start. Only a `journal_dir` override stays
  beside the app. The window's Edge profile stays in `%LOCALAPPDATA%` (about 1 GB,
  a full browser profile: not for a folder OneDrive or backups may sync).
- Mini window: a native window (`miniwin.py`, tkinter, Python's own) in a corner
  of the screen (top-left by default; any of the four under Settings) showing
  only the rounded info panel: everything around it is a see-through colour, so
  the game shows (the commander's ask: "just the info box and nothing else"). An
  Edge window was tried first and dropped: Edge draws with DirectComposition,
  which window regions don't clip, so its white frame always showed. Kills to
  go, stack progress (along the pace-setting queue, finished missions included),
  next deadline, target check and wanted alert by default; next payout (and how
  many missions are counting kills), credits an hour and missions left in the
  stack (grouped as History groups stacks; "Missions complete" in green at the
  end) on request. Drawn in Saira from `fonts/saira.ttf`, loaded privately
  (Windows can't read WOFF2). Always on top, click-through, out of the taskbar
  and Alt-Tab, never takes the focus from the game or the dashboard (Tk
  activates a window as it makes it, so the app makes it at start-up, before
  the dashboard's window; showing and hiding it later activates nothing); size,
  corner and opacity are settings. It
  keeps 12px in from the screen's work area, clear of the taskbar; in a bottom
  corner it grows upwards. Off by default. It needs the game in Borderless or
  Windowed mode (exclusive fullscreen can't be overlaid), which Settings detects
  from `DisplaySettings.xml`. It reads the tracker directly, so it has no
  bearing on when the app quits, and it closes with the app.
- Stack report cards: every stack has its own page under Statistics (givers,
  ships killed and flown, materials, bounty merits) with a 1600×900 PNG export
  sharing the session card's drawing (`drawCard`). Finished stacks link to it
  from Ready to hand in.
- To cash in: bounties earned and not cashed in (per issuing faction; a cash-in
  naming "" clears them all, dying clears them), from the full history plus live
  events, with the nearest docked station where a Powerplay bonus applies.
  Merits for bounty hunting are awarded at the kill (the commander's journal: all
  of them within seconds of a kill, none after any of 12 cash-ins; the wiki's
  Powerplay 2.0 table and INTRA agree), so the Power Contact adds none; bounty
  merits are counted per stack and session.
- Materials, on Statistics and History only (the commander's choice, not Hunt):
  inventory from each log-in's `Materials` list moved by every event that adds or
  spends (91% of log-ins predicted exactly on replay; each log-in resets it),
  earned by source and grade, and full-or-nearly materials (90% of the grade's
  cap: 300/250/200/150/100).
- Declined by the commander: a mission-board calculator, sounds, hunting-ground
  statistics, and a phone/LAN view.
- The journal cannot see the mission board and writes no event when a finished
  mission is dropped. It logs a Deserter kill and a Pirate kill alike; the app
  sorts them by the NPCs' radio chatter (silent fights count as deserters while
  a Deserters mission against that faction is running there).

## Brand Commitments

- Apple-grade product feel, specifically alongside Apple's **Stocks** and
  **Weather** apps (user's choice).
- Presented as an in-universe device of the commander's Powerplay power: one
  style per power (emblem from `styles/`, accent in its colours, its own name),
  chosen under Settings or, by default, Automatic from the pledge in the
  journal. The commander flies for **Arissa Lavigny-Duval**, whose purple eagle
  and violet are the original look. Archon Delaine has no style; unpledged
  commanders get Interstellar.
- Bounties are shown as accumulated income, never framed as "at risk".
- The app is named "Anti-Piracy Network" (the commander's choice, after
  "Massacre Stack", "Imperial Anti-Piracy Network" and "Her Imperial Majesty's
  Anti-Piracy Network"); each style prefixes it ("Her Imperial Highness' Anti-Piracy
  Network", "Utopian Anti-Piracy Collective"...). The exe is "Anti-Piracy
  Network.exe", its icon the Interstellar mark. Each launch opens with a short "Welcome,
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
