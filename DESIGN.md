---
name: Imperial Anti-Piracy Network
description: An Imperial pilot's glance-and-go ledger for stacked massacre missions, in Apple Stocks/Weather dark grammar.
colors:
  ground-top: "#140e1f"
  ground: "#0b0a0f"
  surface: "#16131d"
  surface-2: "#1e1a27"
  surface-3: "#2a2436"
  hairline: "rgba(255, 255, 255, .07)"
  hairline-strong: "rgba(255, 255, 255, .12)"
  fill: "rgba(255, 255, 255, .08)"
  label: "#f4f2f8"
  label-2: "rgba(236, 232, 246, .64)"
  label-3: "rgba(236, 232, 246, .52)"
  imperial: "#b890ff"
  imperial-deep: "#7a4ddc"
  imperial-wash: "rgba(184, 144, 255, .14)"
  green: "#34d15a"
  amber: "#ffb340"
  gold: "#f0cc70"
  red: "#ff6b61"
  switch-track: "rgba(120, 120, 128, .38)"
typography:
  display:
    fontFamily: "Saira, -apple-system, BlinkMacSystemFont, SF Pro Display, Segoe UI Variable Display, Segoe UI, system-ui, sans-serif"
    fontSize: "96px"
    fontWeight: 300
    lineHeight: 1
    letterSpacing: "-.04em"
    fontFeature: "tnum"
  display-narrow:
    fontFamily: "Saira, -apple-system, BlinkMacSystemFont, SF Pro Display, Segoe UI Variable Display, Segoe UI, system-ui, sans-serif"
    fontSize: "80px"
    fontWeight: 300
    lineHeight: 1
    letterSpacing: "-.04em"
    fontFeature: "tnum"
  headline:
    fontFamily: "Saira, -apple-system, BlinkMacSystemFont, SF Pro Display, Segoe UI Variable Display, Segoe UI, system-ui, sans-serif"
    fontSize: "50px"
    fontWeight: 300
    lineHeight: 1
    letterSpacing: "-.035em"
    fontFeature: "tnum"
  title:
    fontFamily: "Saira, -apple-system, BlinkMacSystemFont, SF Pro Display, Segoe UI Variable Display, Segoe UI, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-.01em"
  title-sm:
    fontFamily: "Saira, -apple-system, BlinkMacSystemFont, SF Pro Display, Segoe UI Variable Display, Segoe UI, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: "Saira, -apple-system, BlinkMacSystemFont, SF Pro Text, Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "tnum"
  sentence:
    fontFamily: "Saira, -apple-system, BlinkMacSystemFont, SF Pro Text, Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "13.5px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Saira, -apple-system, BlinkMacSystemFont, SF Pro Text, Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.45
  caption:
    fontFamily: "Saira, -apple-system, BlinkMacSystemFont, SF Pro Text, Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.45
  wordmark:
    fontFamily: "Saira, -apple-system, BlinkMacSystemFont, SF Pro Display, Segoe UI Variable Display, Segoe UI, system-ui, sans-serif"
    fontSize: "13.5px"
    fontWeight: 500
    lineHeight: 1
    letterSpacing: ".16em"
  eyebrow:
    fontFamily: "Saira, -apple-system, BlinkMacSystemFont, SF Pro Display, Segoe UI Variable Display, Segoe UI, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: ".3em"
  welcome:
    fontFamily: "Saira, -apple-system, BlinkMacSystemFont, SF Pro Display, Segoe UI Variable Display, Segoe UI, system-ui, sans-serif"
    fontSize: "26px"
    fontWeight: 600
    lineHeight: 1.15
rounded:
  link: "6px"
  control: "8px"
  inset: "10px"
  banner: "12px"
  popover: "14px"
  card: "18px"
  pill: "99px"
spacing:
  row-y: "10px"
  card-x: "22px"
  card-x-narrow: "16px"
  stack-gap: "22px"
  side-gap: "34px"
  column-gap: "36px"
components:
  button:
    backgroundColor: "{colors.fill}"
    textColor: "{colors.imperial}"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "30px"
  button-prime:
    backgroundColor: "{colors.imperial-deep}"
    textColor: "#ffffff"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "28px"
  link:
    backgroundColor: "transparent"
    textColor: "{colors.imperial}"
    rounded: "{rounded.link}"
    padding: "4px 7px"
  link-hover:
    backgroundColor: "{colors.imperial-wash}"
  link-quiet:
    textColor: "{colors.label-2}"
  segmented:
    backgroundColor: "{colors.fill}"
    rounded: "{rounded.control}"
    padding: "2px"
  segmented-item:
    textColor: "{colors.label-2}"
    rounded: "{rounded.link}"
    padding: "0 14px"
    height: "26px"
  segmented-item-selected:
    backgroundColor: "rgba(255, 255, 255, .16)"
    textColor: "{colors.label}"
  switch:
    backgroundColor: "{colors.switch-track}"
    rounded: "{rounded.pill}"
    width: "40px"
    height: "24px"
  switch-on:
    backgroundColor: "{colors.imperial-deep}"
  option-row:
    rounded: "{rounded.control}"
    padding: "11px 12px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.label}"
    rounded: "{rounded.card}"
    padding: "20px 22px 14px"
  input:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.label}"
    rounded: "{rounded.control}"
    padding: "0 8px"
    height: "28px"
  track:
    backgroundColor: "rgba(255, 255, 255, .045)"
    rounded: "{rounded.pill}"
    height: "6px"
---

# Design System: Imperial Anti-Piracy Network

Product truth, audience and brand commitments live in [PRODUCT.md](PRODUCT.md); this file is strictly visual. Everything below is recorded from the shipped `dashboard.html` (inline CSS on `:root`), not from the plan. Where the direction comment at the top of `<body>` and the build differ, the build is recorded.

## Overview

**Creative North Star: "The Imperial Stocks App"**

Apple's Stocks and Weather, dark, issued to Arissa Lavigny-Duval's pilots. The page reads like a first-party utility: a violet-black ground, plum-neutral cards lifted a step above it, thin numerals at weather-app scale, hairline key-value grids, and one imperial violet that carries progress, the emblem and every control. Empire enters through the purple, the commander's own eagle emblem (user raster at `/emblem`; an original inline-SVG eagle only if that file is missing) and one typeface, Saira, whose squared letters echo the lettering on Elite's own cockpit panels. The type is in-universe; the chrome stays Apple's, and there is no sci-fi HUD chrome.

It is built for a few seconds of attention between fights. One huge kill count answers the first question; every mission is drawn as a segment on its stack's shared kill axis, so the queue that sets the pace can be seen rather than worked out; state is written as a plain sentence with a small line icon, never as a badge. Density is Stocks-like: many rows, 13px labels, hairlines instead of boxes, and tabular figures everywhere so columns never shimmer as the page polls every second.

Rejected by the direction and absent from the build: the gaming-HUD dashboard of orange stat tiles, and badge clutter.

**Key Characteristics:**
- Violet-black ground gradient under plum-neutral surfaces; depth by tone, with one soft card shadow.
- One accent (imperial violet); green, amber and red appear only as state.
- Saira throughout, one family at every size; thin 300-weight numerals for the two headline counts; letterspaced capitals for the wordmark alone.
- Range rows on a shared axis; dashed segments mean queued or pending.
- States as sentences; amber reserved for real uncertainty and warnings.
- Authored 1.75-stroke line icons at 14 to 17px.
- Two authored motions: the welcome card on launch, and a landed kill ticking the hero number and growing the bars.

## Colors

A near-monochrome plum-dark system with a single violet voice and three state colors held in reserve.

### Primary
- **Imperial Violet** (`imperial`): progress fills (as the light end of the fill gradient), the emblem, button and link text, icons that mark place, the provider queue order, the "corrected by hand" note, the in-progress journal run, focus rings, caret, and the tick flash on the hero count.
- **Deep Imperial** (`imperial-deep`): the dark start of every progress fill gradient, the filled primary button (white text), and a switch that is on.
- **Imperial Wash** (`imperial-wash`): hover ground for text links. Queued-segment dashes and the pending rank gain use the same violet at .38 and .6 alpha.

### Tertiary (state only)
- **System Green** (`green`): the live dot, money that is ready to collect, "you are here now", Allied/Friendly standing, and the target icon on a good target sentence.
- **Signal Amber** (`amber`): the "+" on a count the game has not yet confirmed, capped missions, deadlines that will pass before a queued mission's turn, Unfriendly standing, a full mission-slot count, lost contact, an unpaid fine in the current system, and warning sentences.
- **Bounty Gold** (`gold`): a bounty figure that includes a Powerplay cash-in bonus (session strip, side grid, stack figures). Softer and yellower than Signal Amber so it never reads as a warning.
- **Alert Red** (`red`): expired deadlines, Hostile standing, the sentence that says a locked target is clean (attacking it is a crime), and the sentence that says you're wanted in the current system.

### Neutral
- **Violet-Black Ground** (`ground-top` fading to `ground` over the first 560px): the page itself.
- **Plum Surface** (`surface`): stack cards, the empty state. **Plum Surface 2** (`surface-2`): inset panels inside a card (the sync form). **Plum Surface 3** (`surface-3`): scrollbar thumb.
- **Hairline** (`hairline`) and **Hairline Strong** (`hairline-strong`): every row divider and card border; the strong one for the popover edge and input stroke.
- **Fill** (`fill`): the ground of tinted buttons and the segmented control; hover and press step it to .13 and .18 white.
- **Switch Track** (`switch-track`): Apple's native off-state switch fill, a neutral grey that is not tinted plum; used only for the switch track.
- **Label** (`label`), **Label 2** (`label-2`), **Label 3** (`label-3`): primary text, secondary text and captions, the iOS label ladder. Label 3 is the floor; it clears 4.5:1 on `surface` and nothing dimmer is used for text.

### Named Rules
**The One Violet Rule.** Imperial violet is the only hue that is not state. It marks progress, identity and what can be pressed; it is never a section color, a card tint or a heading color.

**The Colour Is State Rule.** Green, amber and red appear only when they mean something about the data. Amber is reserved for real uncertainty and warnings; if nothing is uncertain or at risk, no amber is on screen.

## Typography

**Typeface:** Saira, every role (bundled `fonts/saira.woff2`, variable 100 to 900, SIL OFL; licence in `fonts/OFL.txt`)
**Fallback:** SF Pro Display / SF Pro Text, then Segoe UI Variable Display / Text, Segoe UI, system-ui, used only if the file is missing

**Character:** Apple's weather-app contrast in the squared, Eurostile-like lettering of Elite's own cockpit panels: numerals hairline-thin and huge, everything else small, semibold where it needs weight. Chosen by the commander over Space Grotesk, Outfit and Sora; serif faces were rejected because the type must be one family everywhere and stay crisp at 12px.

### Hierarchy
- **Display** (300, 96px, 1, -.04em): the total kills left in the summary column. Only one per view.
- **Display, narrow step** (`display-narrow`: 300, 80px, 1, -.04em): the same numeral at 720px and below; nothing else changes.
- **Headline** (300, 50px, 1, -.035em): the kills-to-go count on each stack card. An unconfirmed count carries an amber "+" sized in proportion to its numeral rather than on a ramp step: .46em beside the display count (so it follows the 96px and 80px steps) and .52em beside this one.
- **Title** (600, 22px, 1.2, -.01em): stack names and the empty-state heading. The current-system line in the hero is its 20px sibling with a violet pin icon.
- **Title Small** (600, 17px, 1.3): side-column and journal section heads (ready to hand in, Ranks, best stacks). The hero condition sentence is 17px at 500.
- **Body** (400, 15px, 1.45): page default; row names in lists at 600.
- **Sentence** (400, 13.5px, 1.45, max 78ch): state sentences under a stack head.
- **Label** (13px): key-value grids, meta lines, buttons (500), table cells. Values are 600 in `label`, keys 400 in `label-2`.
- **Caption** (12 to 12.5px, `label-3` or `label-2`): hand-in lines, footnotes, ticker keys, column heads.
- **Wordmark** (500, 13.5px, .16em tracking, uppercase; .12em at 720px and below): "Anti-Piracy Network" in the toolbar, with "Imperial" set above it as an eyebrow (600, 11px, .3em tracking, `label-3`), so the two-line lockup stays narrow enough for a phone-width toolbar.

### Named Rules
**The Thin Numeral Rule.** Only the two kill counts are set at 300 weight and large; no other number competes with them. Every other figure is 13 to 15px at 600.

**The One Face Rule.** Saira is the only typeface, at every size and role. It ships as the variable file `fonts/saira.woff2` (weights 100 to 900) and is loaded only from there: a `local()` source would let an installed static Saira stand in for every weight. Letterspaced capitals belong to the wordmark; headings, labels and figures are sentence case.

**The Tabular Rule.** `font-variant-numeric: tabular-nums` is set on body and on inputs; figures in a column must not shift width as they update.

## Layout

A two-column desktop grid, max 1440px wide, padded 32px 28px 72px: a summary column of 300 to 360px and a fluid main column, 36px apart. The summary column is sticky under the toolbar (top 90px) and scrolls on its own when taller than the window; its blocks are 34px apart. The main column stacks the this-session ticker strip and the stack cards 22px apart, largest stack first. The Journal view uses the same grid with a static side column.

Inside cards, content sits 22px from the edges (16px at 720px and below) and rows are separated by hairlines with 9 to 11px vertical padding. Desktop mission rows are a fixed five-column grid (range, left, reward, due, action) and stay one line tall; the hand-in station truncates rather than wraps.

Responsive steps, all observed:
- **1100px and below:** the stack-history table drops its per-hour column.
- **960px and below:** one column; the summary loses its stickiness and sits above the stacks; the commander name leaves the toolbar.
- **720px and below:** the toolbar becomes two rows (iOS narrow-bar pattern): brand and buttons on the first, the Stacks | Journal control full width beneath; button text labels, the edition line and the current system leave. Journal rows become three-column cells, each value with its label on the line above it, so a figure sits in the same place on every row. Mission rows reflow so the range bar spans the full width with its figures below.

### Named Rules
**The Glance Column Rule.** On desktop the answer (kills left, pay, standing, where to hand in) never scrolls away; it lives in the sticky left column.

## Elevation & Depth

Depth is mostly tonal: ground, then plum surface, then surface-2 insets, each a step lighter, bounded by white hairlines. Stack cards add one quiet lift, a 1px inner top highlight plus a long soft drop shadow. Vibrancy (blur plus saturation) is used only where content scrolls beneath: the sticky toolbar and the view-options popover.

### Shadow Vocabulary
- **Card lift** (`box-shadow: 0 1px 0 rgba(255, 255, 255, .035) inset, 0 16px 36px -18px rgba(0, 0, 0, .7)`): stack cards only.
- **Popover float** (`box-shadow: 0 20px 50px -10px rgba(0, 0, 0, .6)`): the view-options popover.
- **Control knob** (`box-shadow: 0 2px 5px rgba(0, 0, 0, .35)` on switch knobs; `0 1px 2px rgba(0, 0, 0, .35)` on the selected segment): the small lift Apple gives to a thumb.

### Named Rules
**The Vibrancy Earns Its Keep Rule.** Blur only surfaces that float over scrolling content (toolbar `rgba(15, 11, 21, .74)`, popover `color-mix(in srgb, var(--surface-3) 94%, transparent)`, a material derived from the surface-3 token). Cards are opaque.

## Shapes

Soft, continuous Apple corners that scale with the object: 18px cards, 14px popover, 12px banner, 10px inset panels, 8px buttons, option rows, number fields and the segmented control, whose 6px segments sit concentric inside its 2px padding, 6px link hover grounds and focus rings. Every bar, track, switch and status dot is fully round. There are no sharp corners and no borders heavier than 1px. Icons are authored inline SVG line symbols on a 24px grid, stroked at 1.75 with round caps and joins, drawn at 14 to 17px in `currentColor`.

## Components

### Buttons
Tinted, quiet, and violet-lettered, like toolbar buttons in a first-party Mac app.
- **Shape:** gently rounded (8px), 30px tall (28px small).
- **Default:** `fill` ground, imperial text at 500 13px, optional 16px line icon 7px before the label. Hover .13 white, press .18 white.
- **Primary (prime):** deep imperial ground, white text; used for the one committing action (Set in the sync form). Hover keeps the token and lifts it with `filter: brightness(1.14)`; there is no separate hover colour.
- **Link:** no ground, imperial text, 6px corner; hover shows `imperial-wash`. The quiet variant is `label-2` and hovers to `label` on a faint white ground (Cancel).
- **Busy:** the refresh icon spins while the journal is re-read.
- **Focus:** a 2px imperial outline, 2px offset, across every focusable element.

### Segmented Control
- **Style:** a `fill` track with 2px padding and 8px corners; segments 26px tall with 6px corners, concentric with the track, `label-2` text. The selected segment is .16 white with `label` text and the small knob shadow. Tabs are Stacks and Journal.
- **Mobile:** stretches full width on the toolbar's second row, segments sharing the width.

### Switch
- iOS switch: 40 by 24px, `switch-track` grey when off, white 20px knob with a soft shadow, deep imperial when on; the knob slides 16px on the site's ease-out curve. Lives in option rows (8px corners, .04 white on hover; title at 600 14px, `label-2` explanation beneath).

### Cards / Containers
- **Corner Style:** 18px.
- **Background:** `surface`, 1px `hairline` border, card-lift shadow, content clipped.
- **Internal Padding:** head 20px 22px 14px; sections below are divided by hairlines.
- **Use:** one card per stack; the Journal reuses the same card for its every-stack and hunting-session tables.

### Inputs / Fields
- **Style:** 28px tall, 76px wide numeric field on the ground color inside a `surface-2` inset panel, 1px `hairline-strong` stroke, 8px corner (`control`), 600 14px tabular figures, violet caret.
- **Focus:** 2px imperial outline flush to the edge.

### Navigation
- **Toolbar:** sticky, 58px, vibrancy ground with a hairline beneath. Left to right: 30px emblem, wordmark lockup, live state (7px green dot and "Live"; amber when contact is lost), commander, current system, then the segmented control and mission slots (`label-2`, the count amber when full), then View and Refresh buttons.

### Range Row (signature)
Weather's temperature-range bar, turned into a kill axis. Each mission is a segment on its stack's one shared axis: a provider's queue lays its missions end to end from 0, and all queues in a stack share the scale, so the pace-setting queue reaches the end.
- **Track:** 6px, fully round, .045 white. **Segment:** .14 white. **Fill:** a deep-imperial-to-imperial gradient revealed by a `clip-path` inset driven by `--p`, transitioning 0.7s on ease-out; minimum 12px so a new mission is visible.
- **Queued:** the segment is dashed violet (4px on, 4px off, .38 alpha) and its start figure drops to `label-3` at 400; a "Starts in N kills" note sits beneath.
- **Capped:** the fill and the remaining count turn amber (the journal ran past a mission the game still lists).
- **Figures:** 30px columns either side, done count at 600 on the left, axis end in `label-2` on the right.
- **Reuse:** the Imperial Navy and Powerplay rank bars use the same track, with the expected gain from hand-ins drawn as a dashed violet (.6) span ahead of the fill.

### Key-Value Grid
Stocks' statistics grid: two columns 22px apart, each pair a hairline-topped row 9px tall-padded, key in `label-2` on the left, value at 600 on the right, 13px. The Journal's single-column variant allows a 12px `label-3` note under a value. The ready-to-hand-in list follows the same hairline grammar as a Stocks watchlist grouped by station, with a rotating chevron disclosure and green money on the right. The this-session ticker is its horizontal cousin: key over value, 30px apart, ruled off below. Each stack card carries the same grammar under its name (next payout, time to finish, rewards, per kill, bounties; 28px apart, no rule): money there is rounded (41.3M, 608K) and every figure keeps its full amount and source in a hover title, so the card reads as figures, not prose. Explanations that are not state (how an estimate was measured, why a queue sets the pace, when finished missions drop) live in hover titles; visible sentences are reserved for state that changes what to do next.

### State Sentence
Every state is written, not badged: a 15px line icon, then a 13.5px sentence in `label-2` with the key figure in `label` at 600. Warning sentences turn wholly amber; a clean target turns red; a good target keeps grey text with a green icon. The pace reads as "N kills an hour of hunting". Provider standing prints as a coloured word after the name, not a chip. Being wanted, or owing a fine, where you are prints as a red or amber sentence under the this-session ticker, above the locked-target line.

### Giver Head
Each giver's queue opens with its name and standing on the left and, on the right, its kill total in `label-2` 13px. The pace-setting queue follows it with "sets the pace" in imperial violet; every other queue, while a mission slot is free, with "N free" in the same violet at the same place: the kills a further mission from that giver could need and still cost nothing. Both explain themselves on hover.

### Hero and Motion
The summary column opens like Weather: the current system at 20px with a violet pin, the 96px thin kill count, a 17px condition line, a `label-2` sub line and a narrow note. When a kill lands, the count replays a 0.55s tick (rises 10px from .25 opacity through imperial violet to `label`) and the range fills grow from their previous value to the new one. The other authored motion is the welcome card, once per launch (a fresh browser tab): the dashboard blurs behind a card (a .45s veil, backdrop blur 16px); a 1.5px imperial reticle ring draws itself around the emblem in 1s with four cardinal ticks; a violet radial glow blooms behind it and a white sheen sweeps across the emblem, masked to its shape; the "Imperial Anti-Piracy Network" eyebrow tightens its tracking from .55em to .3em; "Welcome," and "Commander" come into focus from an 8px blur, 120ms apart; the CMDR name and a violet hairline follow. At 2.75s it dissolves (.42s, scale .97 and blur 6px) into the sharpening dashboard; any click or key skips it, and with reduced motion it simply shows for 1.6s and goes. Other transitions are functional (hover grounds .15s, switch .25s, chevron .2s, stale-data fade to .7 opacity). `prefers-reduced-motion: reduce` removes all animation and transition.

## Do's and Don'ts

### Do:
- **Do** keep imperial violet the only non-state hue: progress, emblem, controls, focus.
- **Do** write state as a sentence with a 1.75-stroke line icon, and color the sentence only when it is a warning or a danger.
- **Do** mark anything the game has not confirmed with an amber "+" or amber text, and use amber for nothing else.
- **Do** put every mission on its stack's shared kill axis; dash what is queued or pending.
- **Do** set the headline counts at 300 weight and everything else at 13 to 15px, with tabular figures.
- **Do** separate rows with 1px hairlines rather than boxes, in the Stocks key-value manner.
- **Do** keep the summary column sticky on desktop and collapse to the two-row toolbar and label-above-value cells below 720px.
- **Do** use the commander's emblem raster as the mark and tab icon, with the original inline eagle only as a fallback.

### Don't:
- **Don't** render state as badge chips or colored pills, and don't build orange stat tiles or other gaming-HUD chrome.
- **Don't** add a second accent hue, or tint cards, headings or sections violet.
- **Don't** add a second typeface, or use letterspaced capitals anywhere but the wordmark.
- **Don't** give a mission bar its own 0-to-N scale; that hides which queue sets the pace.
- **Don't** blur or frost surfaces that do not float over scrolling content.
- **Don't** add motion beyond the welcome card, the kill tick and bar growth, and never ignore reduced motion.
- **Don't** set text dimmer than `label-3`.
- **Don't** bundle Frontier artwork or icon fonts; icons are authored inline SVG.
