#!/usr/bin/env python3
"""Anti-Piracy Network: a massacre-stacking dashboard for Elite Dangerous.

Reads your Elite Dangerous journal, finds every active massacre mission, groups
them by target faction, target type and system, and works out how many kills
you ACTUALLY need: missions from different givers share every kill, while a
giver's own missions complete one after another, so a stack costs its biggest
giver's total.

Usage:
    python stacker.py            live dashboard at http://127.0.0.1:8765
    python stacker.py --console  one-shot text summary, no server
    python stacker.py --verify   replay history to sanity-check kill counting
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from bisect import bisect_left, bisect_right
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Where your own files live (config.json, offsets.json, an emblem of your own):
# beside stacker.py, or beside the .exe when running the packaged app.
FROZEN = getattr(sys, "frozen", False)
APP_DIR = Path(sys.executable if FROZEN else __file__).resolve().parent
# Where the files that ship with the app live (dashboard.html, fonts/, the
# emblem). The packaged .exe unpacks them to a temporary folder at start.
RES_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
APP_NAME = "Anti-Piracy Network"
APP_FILE = APP_NAME           # the .exe, and the window's own browser profile folder
PROG = f'"{APP_FILE}.exe"' if FROZEN else "python stacker.py"
DEFAULT_PORT = 8765
MASSACRE_PREFIX = "Mission_Massacre"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        pass
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


# --------------------------------------------------------------------------
# Locating the journal folder
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Game constants
# --------------------------------------------------------------------------

MISSION_CAP = 20

IMPERIAL_RANKS = ["None", "Outsider", "Serf", "Master", "Squire", "Knight", "Lord",
                  "Baron", "Viscount", "Count", "Earl", "Marquis", "Duke", "Prince", "King"]

# Bounty vouchers pay more when cashed in a system held by these powers,
# whoever you're pledged to. Read off this journal's cash-ins: paid / logged was
# 1.4 in A. Lavigny-Duval and Yuri Grom strongholds, 1.2 where they exploit,
# and 1.0 everywhere else (Aisling Duval, Archer, Mahon, Torval, Patreus, none).
# Fortified sits between the two measured states.
BOUNTY_BONUS_POWERS = {"A. Lavigny-Duval", "Yuri Grom"}
BOUNTY_BONUS_BY_STATE = {"Exploited": 0.2, "Fortified": 0.3, "Stronghold": 0.4}

# Who a kill was. The journal writes a pirate's kill and a deserter's alike,
# but the NPCs say who they are on the radio ($Pirate_..., $Deserter_...), and
# a fight is one group. Checked against the game's own completions when Pirates
# and Deserters (Irukama) or Pirates and Infected (Melcior) missions ran at
# once: the talking pirates matched the Pirates count, and the fights where
# nobody talked (all Master or Dangerous ships) matched the Deserters count.
CHATTER_KIND = {"Pirate": "pirate", "PirateLord": "pirate", "Deserter": "deserter",
                "InfectedShip": "infected", "Smuggler": "smuggler"}
MISSION_KIND = {"Pirate": "pirate", "Deserter": "deserter", "Infected": "infected",
                "Smuggler": "smuggler"}
FIGHT_BREAKS = {"SupercruiseExit", "SupercruiseEntry", "FSDJump", "CarrierJump",
                "Location", "LoadGame", "Died"}


def mission_kind(target_type):
    """'$MissionUtil_FactionTag_Deserter;' -> 'deserter' (the code, not the
    translated name, so it works in every game language)."""
    for key, kind in MISSION_KIND.items():
        if f"FactionTag_{key};" in str(target_type or ""):
            return kind
    return None


# Each Powerplay power's dress for the app: its name (a small line over the
# main one in the toolbar), its emblem in styles/, and an accent in its colours.
# Accents that would read as a state colour are shifted: the greens away from
# "ready" green, Grom's orange away from warning amber. Where the accent is
# gold or yellow, bounties boosted by a Powerplay bonus are marked with an
# underline instead of gold text. Archon Delaine, a pirate, has no style.
STYLES = {
    "ald": ("A. Lavigny-Duval", "Her Imperial Majesty’s", "Anti-Piracy Network",
            "#b890ff", "#7a4ddc", "#140e1f", "#ffffff", "gold"),
    "aisling": ("Aisling Duval", "Her Highness’", "Anti-Piracy Network",
                "#6cc6f2", "#1f7fb4", "#0b1620", "#ffffff", "gold"),
    "torval": ("Zemina Torval", "Torval Mining Ltd’s", "Anti-Piracy Network",
               "#88a8ff", "#3a61d4", "#0d1224", "#ffffff", "gold"),
    "patreus": ("Denton Patreus", "Imperial Admiralty’s", "Anti-Piracy Network",
                "#52d3c8", "#177f78", "#081a19", "#ffffff", "gold"),
    "winters": ("Felicia Winters", "Federal", "Anti-Piracy Network",
                "#f2c14e", "#b8871c", "#1a1408", "#0b0a0f", "underline"),
    "archer": ("Jerome Archer", "Federal Security Service", "Anti-Piracy Network",
               "#e27ce3", "#a13aa3", "#1b0d1c", "#ffffff", "gold"),
    "mahon": ("Edmund Mahon", "Alliance Defence Force", "Anti-Piracy Network",
              "#2ec6a2", "#127c66", "#081a15", "#ffffff", "gold"),
    "kaine": ("Nakato Kaine", "Free Alliance", "Anti-Piracy Network",
              "#c4de50", "#7f9b18", "#121a06", "#0b0a0f", "gold"),
    "yongrui": ("Li Yong-Rui", "Sirius Corporation", "Anti-Piracy Network",
                "#63dccb", "#168e80", "#07191a", "#ffffff", "gold"),
    "antal": ("Pranav Antal", "Utopian", "Anti-Piracy Collective",
              "#f0d84a", "#a99212", "#191707", "#0b0a0f", "underline"),
    "grom": ("Yuri Grom", "EG Union", "Anti-Piracy Network",
             "#ec8a55", "#b35020", "#1c0f09", "#ffffff", "gold"),
    "interstellar": (None, "Interstellar", "Anti-Piracy Network",
                     "#f0823a", "#ad4a12", "#1b0f07", "#ffffff", "gold"),
}
POWER_STYLE = {v[0]: k for k, v in STYLES.items() if v[0]}


def load_config():
    try:
        return json.loads((APP_DIR / "config.json").read_text(encoding="utf-8")) or {}
    except (OSError, ValueError, TypeError):
        return {}


def save_config(**changes):
    cfg = load_config()
    cfg.update(changes)
    try:
        (APP_DIR / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except OSError:
        pass


def style_info(slug, choice):
    power, small, main, accent, deep, ground, on, bounty = STYLES[slug]
    return {"slug": slug, "choice": choice, "power": power, "small": small, "main": main,
            "name": f"{small} {main}", "accent": accent, "deep": deep, "ground": ground,
            "on_accent": on, "bounty": bounty}


COMBAT_RANKS = ["Harmless", "Mostly Harmless", "Novice", "Competent", "Expert", "Master",
                "Dangerous", "Deadly", "Elite", "Elite I", "Elite II", "Elite III",
                "Elite IV", "Elite V"]


def ship_kill(ev):
    """A kill that moves the Pilots' Federation combat rank: a ship, not a
    soldier or skimmer on foot (those Bounty events name a suit or citizen)."""
    if ev.get("event") == "FactionKillBond":
        return True
    target = str(ev.get("Target") or "").lower()
    return not any(k in target for k in ("suitai", "citizen", "skimmer"))


def powerplay_threshold(rank):
    """Merits needed to reach a Powerplay rank. Checked against this journal's
    own rank-ups: rank 6 by 23 935, rank 9 at 47 005, rank 10 at 55 035."""
    early = {0: 0, 1: 0, 2: 2000, 3: 5000, 4: 9000, 5: 15000}
    return early.get(rank, 15000 + 8000 * (rank - 5))


def active_hours(times, gap_cap=timedelta(minutes=10)):
    """Time actually spent hunting: the gaps between consecutive kills, with any
    gap longer than `gap_cap` counted as a break. Measuring first kill to last
    instead counts every pause, and every night of a multi-day stack."""
    times = sorted(t for t in times if t)
    return sum(min(b - a, gap_cap).total_seconds() for a, b in zip(times, times[1:])) / 3600


def standing(rep):
    """The game's reputation bands for a faction (MyReputation, -100..100)."""
    if rep is None:
        return None
    for limit, label in ((-90, "Hostile"), (-35, "Unfriendly"), (4, "Neutral"),
                         (35, "Cordial"), (90, "Friendly")):
        if rep < limit:
            return label
    return "Allied"


def find_journal_dir(explicit=None):
    candidates = []
    if explicit:
        candidates.append(Path(explicit))

    cfg = APP_DIR / "config.json"
    if cfg.is_file():
        try:
            value = json.loads(cfg.read_text(encoding="utf-8")).get("journal_dir")
            if value:
                candidates.append(Path(value))
        except (OSError, ValueError):
            pass

    home = Path(os.environ.get("USERPROFILE") or os.path.expanduser("~"))
    tail = "Saved Games/Frontier Developments/Elite Dangerous"
    candidates.append(home / tail)
    candidates.append(home / "OneDrive" / tail)
    onedrive = os.environ.get("OneDrive")
    if onedrive:
        candidates.append(Path(onedrive) / tail)

    for path in candidates:
        try:
            if path.is_dir() and any(path.glob("Journal.*.log")):
                return path
        except OSError:
            continue
    return None


class CreditFrame:
    """How many of the kills logged on one stream the game has really counted.

    The journal writes a bounty for every kill, but it has no per-mission
    counter, and the game does not move massacre missions for every kill it
    pays a bounty on -- nor does every counted kill make a bounty. Replayed
    against this journal, the logged kills and the game's completions often
    disagree by a few (see `python stacker.py --verify`).
    Completions are the one thing the game does say. Each pins the count at
    that moment -- this many of the kills logged since the mission started
    earning were counted -- and every mission on the same stream is measured
    from those pins, logged kills filling in between.
    """

    def __init__(self, times):
        self.times = times            # kill timestamps, oldest first
        self.n = len(times)
        self.pins = [(0, 0)]          # (kills logged, kills counted), by position

    def start(self, mission, anchor):
        """Position where a mission starts earning. A predecessor's last kill
        belongs to the predecessor, so after a redirect the count is strict."""
        if anchor is None:
            return 0
        if anchor != mission["accepted"]:
            return bisect_right(self.times, anchor)
        return bisect_left(self.times, anchor)

    def upto(self, when):
        return bisect_right(self.times, when)

    def at(self, pos):
        """Kills counted by the time `pos` kills were logged: the latest pin
        plus every kill logged since, never past a later pin."""
        value = None
        for p, v in self.pins:
            if p <= pos:
                value = v + (pos - p)
            elif value is not None:
                value = min(value, v)
        return value

    def pin(self, pos, counted):
        self.pins = sorted([p for p in self.pins if p[0] != pos] + [(pos, counted)])


# --------------------------------------------------------------------------
# Journal tracker
# --------------------------------------------------------------------------

class Tracker:
    """Parses journal files and keeps a live picture of massacre missions."""

    def __init__(self, journal_dir, days=30, require_system=True):
        self.dir = Path(journal_dir)
        self.days = days
        self.require_system = require_system

        self.lock = threading.RLock()
        self.missions = {}        # MissionID -> accepted details
        self.ended = {}           # MissionID -> (reason, timestamp)
        self.redirected = {}      # MissionID -> timestamp (objective complete)
        self.turn_in = {}         # MissionID -> {system, station}
        self.kills = []           # (timestamp, victim_faction, star_system)
        self.kill_fight = []      # the fight each kill was in, index for index
        self.fight = 0            # a new one at every drop, jump or log-in
        self.fight_talk = {}      # fight -> what its NPCs said they were ({"pirate", ...})
        self.snapshot = None      # latest "Missions" event
        self.last_dock = {}       # where we were standing when a mission was taken
        self.current_system = None
        self.commander = None
        self.last_event = None

        # Beyond the stack itself: what else the journal says about the hunt.
        self.bounties = []        # (timestamp, star_system, credits, "bounty" | "bond"), every kill paid
        self.paid = []            # (timestamp, credits): mission rewards actually paid out
        self.merits = []          # (timestamp, merits gained)
        self.accepts = {}         # every MissionID accepted, any type -> timestamp (mission slots)
        self.system_pos = {}      # star system -> (x, y, z) in light years (hand-in route)
        self.system_power = {}    # star system -> (controlling power, powerplay state)
        self.factions = {}        # faction -> {"allegiance", "rep"} from the latest jump into its space
        # The journal only states reputation on a jump into (or log-in in) a
        # faction's space, so hand-ins since then are counted in "+" marks and
        # converted at the rate this commander's own history shows.
        self.rep_pending = {}     # faction -> net "+" marks from hand-ins since that reading
        self.rep_samples = []     # reputation points per "+", measured between readings
        self.session_start = None # the latest LoadGame
        self.session_active = 0.0 # seconds actually playing since then
        self.power = {}           # Powerplay pledge: {"name", "rank", "merits"}
        self.empire = {}          # Imperial Navy: {"rank", "progress"}
        self.combat = {}          # Pilots' Federation combat: {"rank", "progress", "kills" since then}
        self.target = None        # the ship currently locked, as far as it has been scanned
        self.legal = {}           # star system -> {"wanted", "fine"}: the game's word on the latest jump in
        self.crimes = []          # (timestamp, star_system, faction, "bounty" | "fine", credits) still owed
        self.history = {}         # summary from the full-history scan (usual pace, rank rates)
        self._history_full, self._history_at = None, 0.0

        self.current_file = None
        self.pos = 0
        self.buf = b""

        # Manual corrections, keyed by mission id. The journal has no per-mission
        # kill counter, and the game does not always credit a kill to every
        # stacked mission, so each mission is corrected on its own.
        self.offsets = {}
        self._load_offsets()

    # -- manual calibration ------------------------------------------------

    @property
    def offsets_path(self):
        return APP_DIR / "offsets.json"

    def _load_offsets(self):
        self.offsets = {}
        try:
            data = json.loads(self.offsets_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return
        dropped = False
        for key, value in (data or {}).items():
            # Older versions stored a bare number measured from the wrong
            # starting point. Those corrections are meaningless now, so they
            # are dropped rather than carried forward.
            if isinstance(value, dict) and "delta" in value:
                self.offsets[key] = {"delta": int(value["delta"]),
                                     "anchor": value.get("anchor")}
            else:
                dropped = True
        if dropped:
            self._save_offsets()   # clear them off disk too, not just in memory

    def _save_offsets(self):
        try:
            self.offsets_path.write_text(json.dumps(self.offsets, indent=2), encoding="utf-8")
        except OSError:
            pass

    def offset_for(self, mission_id, anchor):
        """A hand-typed correction is only meaningful while the mission is
        still counting from the same starting point. The moment the chain
        moves on -- the previous mission from that faction finishes, and this
        one starts counting from there -- the old number describes a different
        measurement, so it is thrown away instead of poisoning the estimate.
        """
        entry = self.offsets.get(str(mission_id))
        if not entry:
            return 0
        if entry.get("anchor") != iso(anchor):
            self.offsets.pop(str(mission_id), None)
            self._save_offsets()
            return 0
        return entry["delta"]

    def sync(self, mission_id, actual_done):
        """Record what the in-game mission panel really shows for one mission.
        Corrections are per mission, not per faction: the game does not always
        credit one kill to every stacked mission."""
        with self.lock:
            m = self.missions.get(mission_id)
            if not m:
                return False
            # Must measure from exactly the same point report() does, or the
            # correction is applied to a different number than it was made against.
            anchor = self.chain_anchor(m)
            self.offsets[str(mission_id)] = {
                "delta": int(actual_done) - self.kills_for(m, since=anchor),
                "anchor": iso(anchor),
            }
            self._save_offsets()
            return True

    def clear_sync(self, mission_id):
        with self.lock:
            self.offsets.pop(str(mission_id), None)
            self._save_offsets()
            return mission_id in self.missions

    # -- file discovery ----------------------------------------------------

    def journal_files(self):
        try:
            files = sorted(self.dir.glob("Journal.*.log"), key=lambda p: p.name)
        except OSError:
            return []
        if self.days:
            cutoff = time.time() - self.days * 86400
            recent = []
            for f in files:
                try:
                    if f.stat().st_mtime >= cutoff:
                        recent.append(f)
                except OSError:
                    continue
            if recent:
                return recent
        return files[-5:]

    # -- ingestion ---------------------------------------------------------

    def load_history(self):
        files = self.journal_files()
        with self.lock:
            for path in files:
                try:
                    data = path.read_bytes()
                except OSError:
                    continue
                for line in data.split(b"\n"):
                    self._feed(line)
                self.current_file = path
                self.pos = len(data)
                self.buf = b""

    def poll(self):
        """Read anything new, including a fresh journal file after a restart."""
        files = self.journal_files()
        if not files:
            return
        newest = files[-1]
        with self.lock:
            if self.current_file != newest:
                self.current_file = newest
                self.pos = 0
                self.buf = b""
            try:
                with newest.open("rb") as fh:
                    fh.seek(self.pos)
                    data = fh.read()
                    self.pos = fh.tell()
            except OSError:
                return
            if not data:
                return
            self.buf += data
            chunks = self.buf.split(b"\n")
            self.buf = chunks.pop()
            for line in chunks:
                self._feed(line)

    def _feed(self, raw):
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        raw = raw.strip()
        if not raw:
            return
        try:
            ev = json.loads(raw)
        except ValueError:
            return

        name = ev.get("event")
        ts = parse_ts(ev.get("timestamp"))
        if name in FIGHT_BREAKS:
            self.fight += 1
        if ts:
            # Session time counts gaps between events, any gap over 10 minutes
            # as a break -- a game left open overnight isn't a 19-hour session.
            if self.last_event and self.session_start and ts >= self.session_start:
                self.session_active += min((ts - self.last_event).total_seconds(), 600)
            self.last_event = ts

        if name in ("Location", "FSDJump", "CarrierJump"):
            self.current_system = ev.get("StarSystem") or self.current_system
            if name == "Location" and ev.get("Docked") and ev.get("StationName"):
                self.last_dock = {"system": ev.get("StarSystem"),
                                  "station": ev.get("StationName")}
            if self.current_system and "PowerplayState" in ev:
                self.system_power[self.current_system] = (ev.get("ControllingPower"),
                                                          ev.get("PowerplayState"))
            if self.current_system:
                self._legal_status(self.current_system, bool(ev.get("Wanted")),
                                   bool(ev.get("ActiveFine")))
            pos = ev.get("StarPos")
            if self.current_system and isinstance(pos, list) and len(pos) == 3:
                self.system_pos[self.current_system] = tuple(pos)
            for fa in ev.get("Factions") or []:
                if fa.get("Name"):
                    self._rep_reading(fa["Name"], fa.get("MyReputation"))
                    self.factions[fa["Name"]] = {"allegiance": fa.get("Allegiance"),
                                                 "rep": fa.get("MyReputation")}

        elif name == "LoadGame":
            self.commander = ev.get("Name") or self.commander
            self.session_start, self.session_active = ts, 0.0

        elif name == "Powerplay":
            self.power = {"name": ev.get("Power"), "rank": ev.get("Rank"), "merits": ev.get("Merits")}

        elif name == "PowerplayMerits":
            self.merits.append((ts, ev.get("MeritsGained") or 0))
            self.power.update(name=ev.get("Power"), merits=ev.get("TotalMerits"))

        elif name == "PowerplayRank":
            self.power.update(name=ev.get("Power"), rank=ev.get("Rank"))

        elif name == "Rank":
            self.empire["rank"] = ev.get("Empire")
            self.combat["rank"] = ev.get("Combat")

        elif name == "Progress":
            # Written only at log-in: kills since then are counted below.
            self.empire["progress"] = ev.get("Empire")
            self.combat.update(progress=ev.get("Combat"), kills=0)

        elif name == "Promotion":
            if "Empire" in ev:
                self.empire.update(rank=ev["Empire"], progress=0)
            if "Combat" in ev:
                self.combat.update(rank=ev["Combat"], progress=0, kills=0)

        elif name == "ShipTargeted":
            self._target(ev, ts)

        elif name == "ReceiveText" and ev.get("Channel") == "npc":
            family = str(ev.get("Message") or "").lstrip("$").split("_", 1)[0]
            if family in CHATTER_KIND:
                self.fight_talk.setdefault(self.fight, set()).add(CHATTER_KIND[family])

        elif name == "CommitCrime":
            kind = "bounty" if ev.get("Bounty") else "fine" if ev.get("Fine") else None
            if kind and self.current_system:
                self.crimes.append((ts, self.current_system, ev.get("Faction"), kind,
                                    ev.get("Bounty") or ev.get("Fine") or 0))
                self.legal.setdefault(self.current_system, {"wanted": False, "fine": False})
                self.legal[self.current_system]["wanted" if kind == "bounty" else "fine"] = True

        elif name in ("PayBounties", "PayFines"):
            self._paid_off("bounty" if name == "PayBounties" else "fine",
                           ev.get("Faction"), bool(ev.get("AllFines")))

        elif name == "Docked":
            # Missions are taken at a station, so this is where a mission
            # accepted next came from -- and where it has to be handed back in.
            self.last_dock = {"system": ev.get("StarSystem"),
                              "station": ev.get("StationName")}

        elif name == "Commander":
            self.commander = ev.get("Name") or self.commander

        elif name == "Missions":
            self.snapshot = {
                "ts": ts,
                "active": [m.get("MissionID") for m in (ev.get("Active") or [])],
                "complete": [m.get("MissionID") for m in (ev.get("Complete") or [])],
            }

        elif name == "MissionAccepted":
            mid = ev.get("MissionID")
            if mid is None:
                return
            self.accepts[mid] = ts          # every type counts toward the 20-mission cap
            if not str(ev.get("Name") or "").startswith(MASSACRE_PREFIX):
                return
            self.missions[mid] = {
                "id": mid,
                "accepted": ts,
                "title": ev.get("LocalisedName") or ev.get("Name"),
                "giver": ev.get("Faction"),
                "target_faction": ev.get("TargetFaction"),
                "target_type": ev.get("TargetType_Localised") or "Ships",
                "target_kind": mission_kind(ev.get("TargetType")),
                "kill_count": ev.get("KillCount") or 0,
                "system": ev.get("DestinationSystem"),
                "station": ev.get("DestinationStation"),
                "expiry": parse_ts(ev.get("Expiry")),
                "reward": ev.get("Reward") or 0,
                "wing": bool(ev.get("Wing")),
                "origin_system": self.last_dock.get("system"),
                "origin_station": self.last_dock.get("station"),
                # "++" = reputation reward; also what moves the Imperial Navy rank
                "rep_plus": len(str(ev.get("Reputation") or "")),
            }

        elif name in ("MissionCompleted", "MissionFailed", "MissionAbandoned"):
            mid = ev.get("MissionID")
            if mid is not None:
                self.ended[mid] = (name.replace("Mission", ""), ts)
            if name == "MissionCompleted":
                self.paid.append((ts, ev.get("Reward") or 0))
                for fe in ev.get("FactionEffects") or []:
                    marks = len(str(fe.get("Reputation") or ""))
                    if fe.get("Faction") and marks:
                        down = "Down" in str(fe.get("ReputationTrend") or "")
                        self.rep_pending[fe["Faction"]] = (self.rep_pending.get(fe["Faction"], 0)
                                                           + (-marks if down else marks))

        elif name == "MissionRedirected":
            mid = ev.get("MissionID")
            if mid is not None:
                self.redirected[mid] = ts
                self.turn_in[mid] = {
                    "system": ev.get("NewDestinationSystem"),
                    "station": ev.get("NewDestinationStation"),
                }

        elif name in ("Bounty", "FactionKillBond"):
            if ship_kill(ev):
                self.combat["kills"] = self.combat.get("kills", 0) + 1
            # Bounty = bounty-hunting kills, FactionKillBond = combat-zone kills.
            # Massacre missions count both, so we do too.
            self.kills.append((ts, ev.get("VictimFaction"), self.current_system))
            self.kill_fight.append(self.fight)
            # Income is kept apart by kind: bounties from wanted ships, combat
            # bonds from conflict zones. They pay at different places.
            if name == "Bounty":
                self.bounties.append((ts, self.current_system, ev.get("TotalReward") or 0, "bounty"))
            else:
                self.bounties.append((ts, self.current_system, ev.get("Reward") or 0, "bond"))

    # -- mission state -----------------------------------------------------

    def classify(self):
        """Split the massacre missions the game still holds into active and
        ready-to-hand-in.

        The `Missions` event written at every log-in is the game's own list of
        what is in the transactions panel, so it decides what still exists: a
        mission accepted before it and missing from it is gone. That matters
        because the game drops finished-but-unclaimed missions without writing
        any event at all -- two LP 932-12 missions sat in every log-in list from
        09-05 to 09-11, then simply stopped appearing.
        """
        snap = self.snapshot
        if snap and snap["ts"]:
            live = {i for i in snap["active"] + snap["complete"] if i in self.missions}
            # Anything taken since that log-in is too new to be listed yet.
            live |= {mid for mid, m in self.missions.items()
                     if m["accepted"] and m["accepted"] >= snap["ts"]}
        else:
            live = set(self.missions)
        live -= set(self.ended)

        # Among what is still live, a redirect is permanent: once the game says
        # the objective is met, the mission never goes back to being worked.
        # Elite lists such missions under Active (not Complete) at log-in, so
        # this cannot be read off the snapshot -- otherwise a finished mission
        # comes back to life after a relog, takes over its faction's queue and
        # parks the mission actually being worked at zero progress.
        complete = {mid for mid in live if mid in self.redirected}
        return live - complete, complete

    def chain_anchor(self, mission):
        """When this mission actually started earning kills.

        Missions from one giving faction are worked ONE AT A TIME, in the order
        they were accepted -- so a mission only starts counting when the
        previous mission from that same faction finished. Confirmed by the
        journal: four Cemiess Commodities missions needing 15/4/9/15 completed
        at cumulative kills 15, 19, 28 and 43, while a fifth from a different
        faction ran alongside them.
        """
        start = mission["accepted"]
        for mid, when in self.redirected.items():
            other = self.missions.get(mid)
            if not other or not when or mid == mission["id"]:
                continue
            if (other["giver"] != mission["giver"]
                    or other["target_faction"] != mission["target_faction"]
                    or other["target_type"] != mission["target_type"]
                    or other["system"] != mission["system"]):
                continue
            if (other["accepted"] and mission["accepted"]
                    and (other["accepted"], mid) > (mission["accepted"], mission["id"])):
                continue                      # that one is queued behind us
            if start is None or when > start:
                start = when
        return start

    def kills_for(self, mission, since=None):
        """Kills that count toward this mission: right faction, right system,
        landed after the mission started earning."""
        faction = mission["target_faction"]
        system = mission["system"]
        start = since or mission["accepted"]
        # A predecessor's last kill belongs to the predecessor, so when the
        # anchor is another mission finishing, that kill is excluded.
        strict = since is not None and since != mission["accepted"]
        kind = mission.get("target_kind")
        total = 0
        for i, (ts, victim, where) in enumerate(self.kills):
            if victim != faction:
                continue
            if not self.kill_fits(i, kind, faction, system):
                continue
            if start and ts and (ts <= start if strict else ts < start):
                continue
            if self.require_system and system and where and where != system:
                continue
            total += 1
        return total

    def kill_fits(self, i, kind, faction, system):
        """Could kill i count for a mission against `kind` ships of this
        faction? Only the kinds the radio tells apart are sorted; a fight where
        nobody said who they were is deserters while a Deserters mission
        against them is running here, and pirates otherwise."""
        if kind not in CHATTER_KIND.values():
            return True
        said = self.fight_talk.get(self.kill_fight[i]) if i < len(self.kill_fight) else None
        if said:
            return kind in said
        ts = self.kills[i][0]
        hunting_deserters = any(
            m["target_kind"] == "deserter" and m["target_faction"] == faction
            and m["system"] == system and m["accepted"] and ts and m["accepted"] <= ts
            and not (mid in self.ended and self.ended[mid][1] and self.ended[mid][1] < ts)
            for mid, m in self.missions.items())
        return kind == ("deserter" if hunting_deserters else "pirate")

    def credit_frame(self, faction, target_type, system):
        """The kill stream behind one stack, pinned by every completion of a
        mission on it. Pirates and Deserters of one faction share the logged
        kills but not the counting, so each target type gets its own stream
        (see kill_fits) and its own pins."""
        key = (faction, target_type, system)
        kind = next((m.get("target_kind") for m in self.missions.values()
                     if (m["target_faction"], m["target_type"], m["system"]) == key), None)
        times = sorted(ts for i, (ts, victim, where) in enumerate(self.kills)
                       if ts and victim == faction
                       and not (self.require_system and system and where and where != system)
                       and self.kill_fits(i, kind, faction, system))
        frame = CreditFrame(times)
        finished = sorted((when, mid) for mid, when in self.redirected.items()
                          if when and mid in self.missions
                          and (self.missions[mid]["target_faction"], self.missions[mid]["target_type"],
                               self.missions[mid]["system"]) == key)
        for when, mid in finished:
            m = self.missions[mid]
            lo, hi = frame.start(m, self.chain_anchor(m)), frame.upto(when)
            if hi >= lo:
                frame.pin(hi, frame.at(lo) + m["kill_count"])
        return frame

    # -- the rest of the hunt ----------------------------------------------

    def history_report(self, max_age=20):
        """The stats journal, rebuilt from every journal file at most every
        `max_age` seconds. It also feeds the live view its usual pace and the
        Imperial rank rate."""
        if self._history_full and time.time() - self._history_at < max_age:
            return self._history_full
        full = build_history(self.dir)
        with self.lock:
            self._history_full, self._history_at = full, time.time()
            self.history = {"usual_pace": full["usual_pace"], "empire_rate": full["empire_rate"],
                            "combat_rate": full["combat_rate"]}
        return full

    def _target(self, ev, ts):
        """The locked ship. Scans arrive in stages, and only the last one
        names its faction, so details carry over while the same ship stays
        locked."""
        if not ev.get("TargetLocked"):
            self.target = None
            return
        pilot = ev.get("PilotName_Localised") or ev.get("PilotName")
        ship = ev.get("Ship_Localised") or str(ev.get("Ship") or "").replace("_", " ").title()
        same = self.target if (self.target and self.target.get("pilot") == pilot
                               and self.target.get("ship") == ship) else {}
        self.target = {
            "ts": ts, "ship": ship, "pilot": pilot,
            "rank": ev.get("PilotRank") or same.get("rank"),
            "scan": ev.get("ScanStage", 0),
            "faction": ev.get("Faction") or same.get("faction"),
            "legal": ev.get("LegalStatus") or same.get("legal"),
            "bounty": ev.get("Bounty") or same.get("bounty"),
        }

    def _legal_status(self, system, wanted, fine):
        """Location and FSDJump say whether you're wanted, or owe a fine, in
        the system you're in. Once the game says you aren't, the crimes logged
        there are settled, however that happened."""
        self.legal[system] = {"wanted": wanted, "fine": fine}
        cleared = {k for k, owed in (("bounty", wanted), ("fine", fine)) if not owed}
        self.crimes = [c for c in self.crimes if not (c[1] == system and c[3] in cleared)]

    def _paid_off(self, kind, faction, everything):
        """Bounties or fines paid at a station or Interstellar Factors: to one
        faction, or all of them at once."""
        flag = "wanted" if kind == "bounty" else "fine"
        paid = [c for c in self.crimes if c[3] == kind and (everything or c[2] == faction)]
        self.crimes = [c for c in self.crimes if c not in paid]
        still = {c[1] for c in self.crimes if c[3] == kind}
        # A flag set by the game on a jump, with no crime logged behind it, is
        # left alone unless everything was paid; the next jump says for sure.
        for system in ({c[1] for c in paid} - still) | (set(self.legal) if everything else set()):
            if system in self.legal:
                self.legal[system][flag] = False

    def legal_summary(self):
        """Whether you're wanted, or owe a fine, where you are right now."""
        system = self.current_system
        status = self.legal.get(system) or {}
        if not (status.get("wanted") or status.get("fine")):
            return None
        owed = {}
        for ts, where, faction, kind, credits in self.crimes:
            if where == system and status.get("wanted" if kind == "bounty" else "fine"):
                entry = owed.setdefault(kind, {"credits": 0, "factions": []})
                entry["credits"] += credits
                if faction and faction not in entry["factions"]:
                    entry["factions"].append(faction)
        return {
            "system": system,
            "wanted": bool(status.get("wanted")),
            "fine": bool(status.get("fine")),
            # Amounts only for crimes logged in the scanned window; an older
            # one still flags you, with no figure to show.
            "bounty": owed.get("bounty", {}).get("credits", 0),
            "bounty_factions": owed.get("bounty", {}).get("factions", []),
            "fines": owed.get("fine", {}).get("credits", 0),
            "fine_factions": owed.get("fine", {}).get("factions", []),
        }

    def target_summary(self, groups):
        t = self.target
        if not t:
            return None
        mine = [g for g in groups if g["target_faction"] == t.get("faction")]
        here = [g for g in mine if g["system"] == self.current_system]
        if here:
            verdict = "counts"
        elif mine:
            verdict = "wrong_system"
        elif t.get("legal") == "Clean":
            verdict = "clean"
        elif not t.get("faction"):
            verdict = "unscanned"
        else:
            verdict = "other"
        return {
            **{k: t.get(k) for k in ("ship", "pilot", "rank", "scan", "faction", "legal", "bounty")},
            "at": iso(t["ts"]),
            "verdict": verdict,
            # one kill moves the head of every giver's queue in the stack forward
            "missions": sum(len(g["chains"]) for g in here),
        }

    def slots_used(self):
        """Missions of every kind held right now, against the game's cap of 20."""
        snap = self.snapshot
        if snap and snap["ts"]:
            live = set(snap["active"]) | set(snap["complete"])
            live |= {mid for mid, ts in self.accepts.items() if ts and ts >= snap["ts"]}
        else:
            live = set(self.accepts)
        return len(live - set(self.ended))

    def _rep_reading(self, faction, rep):
        """A fresh reputation reading. If hand-ins moved it since the last one,
        it measures how much a "+" is worth (not at the 100 ceiling, where
        they add nothing)."""
        marks = self.rep_pending.pop(faction, 0)
        old = (self.factions.get(faction) or {}).get("rep")
        if marks and rep is not None and old is not None and max(old, rep) < 99.5:
            per = (rep - old) / marks
            if 0 < per < 15:
                self.rep_samples.append(per)

    def rep_per_mark(self):
        # The latest stretches: what a "+" is worth drifts over time.
        s = sorted(self.rep_samples[-15:])
        return s[len(s) // 2] if len(s) >= 5 else 4.0    # 4: the typical value in real journals

    def provider(self, name):
        info = self.factions.get(name) or {}
        logged = info.get("rep")
        marks = self.rep_pending.get(name, 0)
        rep = logged
        if logged is not None and marks:
            rep = max(-100.0, min(100.0, logged + marks * self.rep_per_mark()))
        return {"standing": standing(rep), "rep": rep, "logged_rep": logged,
                "since_marks": marks, "allegiance": info.get("allegiance")}

    def bounty_bonus(self, system):
        """What cashing bounties in this system adds: (rate, power, state)."""
        power, state = self.system_power.get(system, (None, None))
        rate = BOUNTY_BONUS_BY_STATE.get(state, 0) if power in BOUNTY_BONUS_POWERS else 0
        return rate, power, state

    def bounties_since(self, system, start):
        hits = [(c, kind) for ts, where, c, kind in self.bounties
                if where == system and ts and start and ts >= start]
        logged = sum(c for c, kind in hits if kind == "bounty")
        rate, power, state = self.bounty_bonus(system)
        return {"bounties": logged,
                # Worth this much cashed in the system they were earned in.
                "bounties_paid": round(logged * (1 + rate)),
                "bonus_rate": rate, "bonus_power": power if rate else None,
                "bonus_state": state if rate else None,
                "bonds": sum(c for c, kind in hits if kind == "bond"),
                "kills": len(hits)}

    def pace_for(self, faction, system):
        """Kills an hour against this faction here, from this session's own
        kills once there are enough of them; otherwise the commander's usual
        stacking pace from the full history."""
        start = self.session_start
        times = [ts for ts, victim, where in self.kills
                 if victim == faction and where == system and ts and start and ts >= start]
        hours = active_hours(times)
        # A handful of kills in one fight says nothing about an hour's pace.
        if len(times) >= 10 and hours >= 0.2:
            return {"per_hour": round((len(times) - 1) / hours, 1), "source": "session"}
        usual = self.history.get("usual_pace")
        return {"per_hour": usual, "source": "usual"} if usual else None

    def session_summary(self):
        start = self.session_start
        if not start:
            return None
        hours = max(self.session_active / 3600, 1 / 60)
        hunt = [(c, kind, where) for ts, where, c, kind in self.bounties if ts and ts >= start]
        bounty = sum(c for c, kind, _ in hunt if kind == "bounty")
        bounty_paid = round(sum(c * (1 + self.bounty_bonus(where)[0])
                                for c, kind, where in hunt if kind == "bounty"))
        bonds = sum(c for c, kind, _ in hunt if kind == "bond")
        paid = sum(c for ts, c in self.paid if ts and ts >= start)
        return {
            "started": iso(start),
            "hours": round(hours, 3),
            "kills": len(hunt),
            "kills_per_hour": round(len(hunt) / hours, 1),
            "bounties": bounty,
            "bounties_paid": bounty_paid,
            "bonds": bonds,
            "mission_credits": paid,
            "credits_per_hour": int((bounty_paid + bonds + paid) / hours),
            "merits": sum(m for ts, m in self.merits if ts and ts >= start),
        }

    def powerplay(self):
        p = self.power
        if not p.get("name") or p.get("rank") is None:
            return None
        rank, merits = p["rank"], p.get("merits") or 0
        start = self.session_start
        # Switching powers makes the journal report rank 0 for a while, even
        # with thousands of merits. When the rank contradicts the merits, show
        # the merits alone rather than invent a rank the journal didn't state.
        known = rank >= 1 and merits < powerplay_threshold(rank + 1)
        return {
            "power": p["name"],
            "rank": rank if known else None,
            "merits": merits,
            "rank_floor": powerplay_threshold(rank) if known else None,
            "next_rank_at": powerplay_threshold(rank + 1) if known else None,
            "to_next": max(0, powerplay_threshold(rank + 1) - merits) if known else None,
            "session": sum(m for ts, m in self.merits if ts and start and ts >= start),
        }

    def imperial(self, missions):
        """Imperial Navy rank, and what handing in these missions should add to
        it -- measured from this commander's own history at this rank."""
        rank = self.empire.get("rank")
        if rank is None:
            return None
        rate = self.history.get("empire_rate") or {}
        per_plus = rate.get("per_plus") if rate.get("rank") == rank else None
        imperial = [m for m in missions
                    if (self.factions.get(m["giver"]) or {}).get("allegiance") == "Empire"]
        pluses = sum(m["rep_plus"] for m in imperial)
        return {
            "rank": rank,
            "title": IMPERIAL_RANKS[rank] if 0 <= rank < len(IMPERIAL_RANKS) else str(rank),
            "next": IMPERIAL_RANKS[rank + 1] if rank + 1 < len(IMPERIAL_RANKS) else None,
            "progress": self.empire.get("progress"),
            "imperial_missions": len(imperial),
            "pending_gain": round(pluses * per_plus, 1) if per_plus and pluses else None,
            "per_plus": per_plus,
            "basis_missions": rate.get("missions"),
        }

    def style(self):
        """The style in use: the one chosen in Settings, or with "auto" the one
        for the power you're pledged to (Interstellar if none has a style)."""
        choice = load_config().get("style") or "auto"
        slug = choice if choice in STYLES else POWER_STYLE.get(self.power.get("name"), "interstellar")
        return style_info(slug, choice if choice in STYLES else "auto")

    def combat_rank(self):
        """Combat rank, and how far the ship kills since the journal last
        recorded it (at log-in) should have moved it -- at the rate this
        commander's own kills have moved it at this rank."""
        rank, progress = self.combat.get("rank"), self.combat.get("progress")
        if rank is None or progress is None:
            return None
        kills = self.combat.get("kills", 0)
        rate = self.history.get("combat_rate") or {}
        per_pct = rate.get("kills_per_pct") if rate.get("rank") == rank else None
        top = rank + 1 >= len(COMBAT_RANKS)
        gain = min(kills / per_pct, 99.9 - progress) if per_pct and kills and not top else None
        return {
            "rank": rank,
            "title": COMBAT_RANKS[rank] if 0 <= rank < len(COMBAT_RANKS) else str(rank),
            "next": None if top else COMBAT_RANKS[rank + 1],
            "progress": progress,
            "kills": kills,
            "gain": round(gain, 1) if gain else None,
            "kills_to_next": (max(0, round((100 - progress) * per_pct - kills))
                              if per_pct and not top else None),
            "kills_per_pct": per_pct,
            "basis_kills": rate.get("kills"),
        }

    def hand_in_route(self, ready):
        """Hand-in stations, nearest first from where you are, then nearest from
        each stop, using the coordinates of systems you've been to."""
        stops = {}
        for r in ready:
            s = stops.setdefault((r["station"], r["system"]), {
                "station": r["station"], "system": r["system"], "missions": 0, "credits": 0})
            s["missions"] += 1
            s["credits"] += r["reward"]
        todo, route, total = list(stops.values()), [], 0.0
        here = self.system_pos.get(self.current_system)
        while todo:
            known = [s for s in todo if s["system"] in self.system_pos]
            if not here or not known:
                route.extend(dict(s, leg_ly=None) for s in todo)
                break
            nxt = min(known, key=lambda s: math.dist(here, self.system_pos[s["system"]]))
            leg = math.dist(here, self.system_pos[nxt["system"]])
            total += leg
            route.append(dict(nxt, leg_ly=round(leg, 1)))
            here = self.system_pos[nxt["system"]]
            todo.remove(nxt)
        return {"stops": route, "total_ly": round(total, 1)}

    # -- the actual stacking maths ----------------------------------------

    def report(self):
        with self.lock:
            active, complete = self.classify()
            now = utcnow()

            # Corrections only make sense for missions still being worked.
            live_keys = {str(i) for i in active}
            stale = [k for k in self.offsets if k not in live_keys]
            if stale:
                for key in stale:
                    self.offsets.pop(key, None)
                self._save_offsets()

            # Pirates and Deserters of one faction are different ships, so they
            # are separate kill streams -- a deserter mission never waits behind
            # a pirate one (confirmed: a 15-deserter mission from Guuguyni Front
            # finished before the 18-pirate mission accepted ahead of it).
            buckets = {}
            for mid in active:
                m = self.missions[mid]
                key = (m["target_faction"] or "Unknown", m["target_type"] or "Ships",
                       m["system"] or "Unknown")
                buckets.setdefault(key, []).append((mid, m))
            # The journal writes both kinds of kill alike; the NPCs' radio
            # chatter sorts pirates, deserters and infected ships (kill_fits).
            # Only kinds it can't sort still share one uncertain count.
            by_faction = {}
            for (faction, ttype, system), members in buckets.items():
                by_faction.setdefault((faction, system), set()).add(members[0][1].get("target_kind"))
            sortable = set(CHATTER_KIND.values())

            groups = []
            for (faction, target_type, system), members in buckets.items():
                kinds = by_faction[(faction, system)]
                mixed = len(kinds) > 1 and not kinds <= sortable
                # Every mission here shares one kill stream. But missions from
                # the SAME giving faction queue up behind each other, so a stack
                # costs the biggest single giver's total -- not the biggest
                # single mission, and not the sum of everything.
                chains = {}
                for mid, m in members:
                    chains.setdefault(m["giver"] or "Unknown", []).append((mid, m))

                # What the game has confirmed about these kills (see CreditFrame).
                frame = self.credit_frame(faction, target_type, system)
                logged = frame.at(frame.n)

                # The mission each giver is working right now: its first one
                # that hasn't expired.
                working = {}
                for giver, chain in chains.items():
                    chain.sort(key=lambda pair: (pair[1]["accepted"] or now, pair[0]))
                    for mid, m in chain:
                        if not (m["expiry"] and m["expiry"] <= now):
                            anchor = self.chain_anchor(m)
                            # offset_for drops a correction made against a
                            # different starting point, so ask before checking.
                            working[mid] = {"start": frame.start(m, anchor),
                                          "offset": self.offset_for(mid, anchor),
                                          "synced": str(mid) in self.offsets}
                            break

                # A mission the game still lists as active has NOT had its last
                # kill counted, whatever the journal says. If the kills logged
                # since it started earning already cover it, the surplus didn't
                # count -- and because every mission here earns from the same
                # kills, none of them can be further on than that allows.
                held, holder = logged, None
                for mid, h in working.items():
                    m = self.missions[mid]
                    ceiling = frame.at(h["start"]) + m["kill_count"] - 1
                    if not h["synced"] and ceiling < held:
                        held, holder = ceiling, m["giver"]

                entries, chain_info = [], []
                for giver, chain in chains.items():
                    cost, head_taken = 0, False

                    for position, (mid, m) in enumerate(chain):
                        required = m["kill_count"]
                        expired = bool(m["expiry"] and m["expiry"] <= now)
                        synced = capped = False
                        queued = head_taken and not expired
                        done = 0

                        if mid in working:
                            head_taken = True
                            h = working[mid]
                            synced = h["synced"]
                            if synced:
                                # A number typed in by hand is trusted as-is.
                                done = max(0, min(frame.n - h["start"] + h["offset"], required))
                            else:
                                base = frame.at(h["start"])
                                capped = logged - base >= required
                                done = max(0, min(held - min(base, held), required - 1))

                        remaining = max(0, required - done)
                        if not expired:
                            cost += remaining
                        entries.append({
                            "id": mid,
                            "title": m["title"],
                            "giver": giver,
                            "position": position,          # place in this giver's queue
                            "accepted": iso(m["accepted"]),
                            "target_type": m["target_type"],
                            "required": required,
                            "done": done,
                            "remaining": remaining,
                            "queued": queued,
                            "capped": capped,                 # its own logged kills cover it
                            "held": mid in working and not synced and held < logged,
                            "synced": synced,
                            "reward": m["reward"],
                            "wing": m["wing"],
                            "system": m["system"],
                            "station": m["station"],
                            "origin_system": m["origin_system"],
                            "origin_station": m["origin_station"],
                            "expiry": iso(m["expiry"]),
                            "expires_in": (m["expiry"] - now).total_seconds() if m["expiry"] else None,
                            "expired": expired,
                        })

                    live_here = sum(1 for _, m in chain
                                    if not (m["expiry"] and m["expiry"] <= now))
                    if live_here:
                        chain_info.append({"giver": giver, "missions": live_here,
                                           "kills": cost, **self.provider(giver)})

                live = [e for e in entries if not e["expired"]]
                heads = [e for e in live if not e["queued"]]
                needed = max((c["kills"] for c in chain_info), default=0)
                # Every queue shorter than the pace has room: a mission of up
                # to that many kills from this giver adds nothing to the cost.
                for c in chain_info:
                    c["free"] = needed - c["kills"]
                naive = sum(e["remaining"] for e in live)
                reward = sum(e["reward"] for e in live)
                entries.sort(key=lambda e: (e["queued"], e["remaining"], -e["reward"]))
                chain_info.sort(key=lambda c: -c["kills"])

                # What the hunt here has paid on top of the missions: every
                # bounty and bond in this system since the stack began. Mission
                # credits aren't guaranteed -- materials or reputation are often
                # the reward taken -- so this is the stack's other income.
                began = min((self.missions[e["id"]]["accepted"] for e in live
                             if self.missions[e["id"]]["accepted"]), default=None)
                earned = self.bounties_since(system, began)
                pace = self.pace_for(faction, system)
                # Kills logged since the earliest current mission started earning
                # that the game's completions show it did not count (negative:
                # it counted more than were logged).
                earliest = min((h["start"] for h in working.values()), default=frame.n)
                uncounted = (frame.n - earliest) - (logged - frame.at(earliest))
                groups.append({
                    "target_faction": faction,
                    "target_type": target_type,
                    "system": system,
                    "mixed_types": mixed,
                    "uncertain": mixed or held < logged,
                    "uncounted": uncounted,
                    "held_back": logged - held,          # more that can't have counted
                    "held_by": holder if held < logged else None,
                    "synced": sum(1 for e in live if e["synced"]),
                    "in_position": bool(self.current_system and self.current_system == system),
                    "missions": entries,
                    "mission_count": len(live),
                    "chains": chain_info,
                    "queued_count": sum(1 for e in live if e["queued"]),
                    "kills_needed": needed,
                    "kills_naive": naive,
                    "reward": reward,
                    "cr_per_kill": int(reward / needed) if needed else 0,
                    "next_payout": self._next_payout(heads),
                    "began": iso(began),
                    "bounties": earned["bounties"],
                    "bounties_paid": earned["bounties_paid"],
                    "bonus_rate": earned["bonus_rate"],
                    "bonus_power": earned["bonus_power"],
                    "bonus_state": earned["bonus_state"],
                    "bonds": earned["bonds"],
                    "bounty_kills": earned["kills"],
                    "pace": pace,
                    "eta_hours": round(needed / pace["per_hour"], 2)
                                 if pace and pace["per_hour"] and needed else None,
                })
            groups.sort(key=lambda g: (-g["kills_needed"], g["target_faction"]))

            ready = []
            for mid in complete:
                m = self.missions[mid]
                dest = self.turn_in.get(mid, {})
                ready.append({
                    "id": mid,
                    "title": m["title"],
                    "giver": m["giver"],
                    "reward": m["reward"],
                    "required": m["kill_count"],
                    "system": dest.get("system") or m["origin_system"] or m["system"],
                    "station": dest.get("station") or m["origin_station"] or m["station"],
                    "target_system": m["system"],
                    "expiry": iso(m["expiry"]),
                    "expires_in": (m["expiry"] - now).total_seconds() if m["expiry"] else None,
                    **self.provider(m["giver"]),
                })
            ready.sort(key=lambda r: -r["reward"])

            kills_needed = sum(g["kills_needed"] for g in groups)
            kills_naive = sum(g["kills_naive"] for g in groups)
            reward = sum(g["reward"] for g in groups)
            live_missions = [self.missions[i] for i in active | complete]

            # Stacks in one system share one stream of kills (Pirates and
            # Deserters of a faction, say), so income is counted once per
            # system, from its earliest stack's start -- never per stack.
            first = {}
            for g in groups:
                b = parse_ts(g["began"])
                if b and (g["system"] not in first or b < first[g["system"]]):
                    first[g["system"]] = b
            shared = [self.bounties_since(s, b) for s, b in first.items()]

            return {
                "commander": self.commander,
                "current_system": self.current_system,
                "journal_file": self.current_file.name if self.current_file else None,
                "last_event": iso(self.last_event),
                "generated": iso(now),
                "require_system": self.require_system,
                "slots": {"used": self.slots_used(), "cap": MISSION_CAP},
                "session": self.session_summary(),
                "imperial": self.imperial(live_missions),
                "powerplay": self.powerplay(),
                "combat": self.combat_rank(),
                "style": self.style(),
                "styles": [{"slug": k, "power": v[0], "name": f"{v[1]} {v[2]}"}
                           for k, v in STYLES.items()],
                "target": self.target_summary(groups),
                "legal": self.legal_summary(),
                "route": self.hand_in_route(ready),
                "totals": {
                    "missions": sum(g["mission_count"] for g in groups),
                    "kills_needed": kills_needed,
                    "kills_naive": kills_naive,
                    "kills_saved": max(0, kills_naive - kills_needed),
                    "reward": reward,
                    "cr_per_kill": int(reward / kills_needed) if kills_needed else 0,
                    "ready_reward": sum(r["reward"] for r in ready),
                    "bounties": sum(x["bounties"] for x in shared),
                    "bounties_paid": sum(x["bounties_paid"] for x in shared),
                    "bonds": sum(x["bonds"] for x in shared),
                },
                "groups": groups,
                "ready": ready,
            }

    @staticmethod
    def _next_payout(live):
        """The nearest milestone: kills until the next mission(s) tick over."""
        pending = [e for e in live if e["remaining"] > 0]
        if not pending:
            return None
        step = min(e["remaining"] for e in pending)
        finishing = [e for e in pending if e["remaining"] == step]
        return {
            "kills": step,
            "missions": len(finishing),
            "reward": sum(e["reward"] for e in finishing),
        }


# --------------------------------------------------------------------------
# Stats journal: everything the whole journal history can tell us
# --------------------------------------------------------------------------

HISTORY_EVENTS = {b'"MissionAccepted"', b'"MissionCompleted"', b'"MissionFailed"',
                  b'"MissionAbandoned"', b'"MissionRedirected"', b'"Bounty"',
                  b'"FactionKillBond"', b'"FSDJump"', b'"Location"', b'"CarrierJump"',
                  b'"LoadGame"', b'"PowerplayMerits"', b'"Rank"', b'"Progress"',
                  b'"Promotion"'}


def fast_ts(raw):
    """'YYYY-MM-DDTHH:MM:SSZ' bytes to a datetime, without strptime's cost --
    this runs once for every line of every journal."""
    try:
        return datetime(int(raw[0:4]), int(raw[5:7]), int(raw[8:10]), int(raw[11:13]),
                        int(raw[14:16]), int(raw[17:19]), tzinfo=timezone.utc)
    except (ValueError, IndexError):
        return None


def iter_history(journal_dir):
    """(timestamp, event or None) for every line of every journal file. Only
    the events the stats journal uses are JSON-parsed; for every other line the
    timestamp alone is read, because time played is measured from all of them --
    the same lines the live tracker sees, so both give a session one length."""
    for path in sorted(Path(journal_dir).glob("Journal.*.log"), key=lambda p: p.name):
        try:
            data = path.read_bytes()
        except OSError:
            continue
        for line in data.split(b"\n"):
            i = line.find(b'"timestamp":"')
            if i < 0:
                continue
            ev = None
            j = line.find(b'"event":')
            if j >= 0 and line[j + 8:line.find(b'"', j + 9) + 1] in HISTORY_EVENTS:
                try:
                    ev = json.loads(line)
                except ValueError:
                    ev = None
            yield fast_ts(line[i + 13:i + 33]), ev


def build_history(journal_dir):
    system, rank, session, since = None, None, None, None
    kills, merits, sessions = [], [], []
    accepted, completed, failed, redirected, allegiance = {}, {}, {}, {}, {}
    segments, prev_progress, done_since = [], None, []   # Imperial rank measurements
    combat_rank, combat_prev, ship_kills, combat_segments = None, None, 0, []

    for ts, e in iter_history(journal_dir):
        if ts is None:
            continue
        since = since or ts
        if e is not None and e.get("event") == "LoadGame":
            session = {"start": ts, "end": ts, "active": 0.0, "kills": 0, "bounties": 0,
                       "bonds": 0, "bond_kills": 0, "paid": 0, "merits": 0, "massacres": 0}
            sessions.append(session)
        elif session:
            # Same rule as the live tracker: gaps over 10 minutes are breaks.
            session["active"] += min(max((ts - session["end"]).total_seconds(), 0), 600)
            session["end"] = ts
        if e is None:
            continue

        ev, mid = e.get("event"), e.get("MissionID")
        if ev in ("FSDJump", "Location", "CarrierJump"):
            system = e.get("StarSystem") or system
            for fa in e.get("Factions") or []:
                if fa.get("Name"):
                    allegiance[fa["Name"]] = fa.get("Allegiance")
        elif ev in ("Bounty", "FactionKillBond"):
            kind = "bounty" if ev == "Bounty" else "bond"
            credits = (e.get("TotalReward") if ev == "Bounty" else e.get("Reward")) or 0
            kills.append((ts, e.get("VictimFaction"), system, credits, kind))
            ship_kills += ship_kill(e)
            if session:
                session["kills"] += 1
                session["bounties" if kind == "bounty" else "bonds"] += credits
                session["bond_kills"] += kind == "bond"
        elif ev == "PowerplayMerits":
            gained = e.get("MeritsGained") or 0
            merits.append((ts, gained))
            if session:
                session["merits"] += gained
        elif ev == "MissionAccepted" and mid is not None:
            accepted[mid] = e
        elif ev == "MissionCompleted" and mid is not None:
            completed[mid] = e
            done_since.append(mid)
            if session:
                session["paid"] += e.get("Reward") or 0
                if str(e.get("Name") or "").startswith(MASSACRE_PREFIX):
                    session["massacres"] += 1
        elif ev in ("MissionFailed", "MissionAbandoned") and mid is not None:
            failed[mid] = ts
        elif ev == "MissionRedirected" and mid is not None:
            redirected.setdefault(mid, ts)
        elif ev == "Rank":
            rank, combat_rank = e.get("Empire"), e.get("Combat")
        elif ev == "Progress":
            if prev_progress and prev_progress[1] == rank:
                segments.append((rank, e.get("Empire", 0) - prev_progress[0], list(done_since)))
            prev_progress, done_since = (e.get("Empire", 0), rank), []
            if combat_prev and combat_prev[1] == combat_rank and e.get("Combat") is not None:
                combat_segments.append((combat_rank, e["Combat"] - combat_prev[0],
                                        ship_kills - combat_prev[2]))
            combat_prev = (e.get("Combat") or 0, combat_rank, ship_kills)
        elif ev == "Promotion":
            if "Empire" in e:
                rank, prev_progress, done_since = e["Empire"], None, []
            if "Combat" in e:
                # A new rank starts at 0% here, so kills from now on count toward it.
                combat_rank, combat_prev = e["Combat"], (0, e["Combat"], ship_kills)

    def pluses(m):
        return len(str(accepted.get(m, {}).get("Reputation") or ""))

    # Imperial Navy: how far each reputation "+" on an Imperial mission has
    # moved the rank bar, measured between log-ins at the current rank.
    gained = plus_total = counted = 0
    for seg_rank, delta, done in segments:
        imp = [m for m in done if allegiance.get(completed[m].get("Faction")) == "Empire"]
        if seg_rank == rank and imp and delta >= 0:
            gained += delta
            plus_total += sum(pluses(m) for m in imp)
            counted += len(imp)
    empire_rate = ({"rank": rank, "per_plus": round(gained / plus_total, 4), "missions": counted}
                   if plus_total else {"rank": rank})

    # Combat rank: ship kills per 1% at the current rank, measured between
    # log-ins. The journal rounds progress down to whole percents, so single
    # stretches are noisy; summed over the whole rank they aren't.
    per = [(d, k) for r, d, k in combat_segments if r == combat_rank and d >= 0 and k >= 0]
    pct, shot = sum(d for d, _ in per), sum(k for _, k in per)
    combat_rate = ({"rank": combat_rank, "kills_per_pct": round(shot / pct, 2), "kills": shot}
                   if pct >= 5 else {"rank": combat_rank})

    # Stacks: massacre missions against one faction in one system, taken
    # within half a day of the previous one finishing, form one run.
    runs = []
    for key in sorted({(a.get("TargetFaction"), a.get("DestinationSystem"))
                       for a in accepted.values()
                       if str(a.get("Name") or "").startswith(MASSACRE_PREFIX)}, key=str):
        mids = sorted((m for m, a in accepted.items()
                       if str(a.get("Name") or "").startswith(MASSACRE_PREFIX)
                       and (a.get("TargetFaction"), a.get("DestinationSystem")) == key),
                      key=lambda m: accepted[m]["timestamp"])
        run = None
        for m in mids:
            t0 = parse_ts(accepted[m]["timestamp"])
            ends = [t for t in (t0, redirected.get(m), failed.get(m),
                                parse_ts(completed.get(m, {}).get("timestamp"))) if t]
            if run and t0 and t0 <= run["end"] + timedelta(hours=12):
                run["mids"].append(m)
                run["end"] = max(run["end"], *ends)
            else:
                run = {"faction": key[0], "system": key[1], "start": t0, "end": max(ends), "mids": [m]}
                runs.append(run)

    stacks, now = [], utcnow()
    for run in runs:
        mids, faction, where = run["mids"], run["faction"], run["system"]
        # A stack still being worked runs until now; one the game quietly dropped
        # (never redirected, long expired) must not soak up later kills here.
        working = [m for m in mids if m not in redirected and m not in completed
                   and m not in failed and (parse_ts(accepted[m].get("Expiry")) or now) > now]
        hunt_end = now if working else max((redirected[m] for m in mids if m in redirected),
                                           default=run["end"])
        window = [k for k in kills if k[2] == where and k[0] and run["start"] <= k[0] <= hunt_end]
        targets = [k for k in window if k[1] == faction]
        bounties = sum(k[3] for k in window if k[4] == "bounty")
        bonds = sum(k[3] for k in window if k[4] == "bond")
        paid = sum(completed[m].get("Reward") or 0 for m in mids if m in completed)
        per_giver = {}
        for m in mids:
            giver = accepted[m].get("Faction")
            per_giver[giver] = per_giver.get(giver, 0) + (accepted[m].get("KillCount") or 0)
        hours = active_hours([k[0] for k in window])
        t_hours = active_hours([k[0] for k in targets])
        income = paid + bounties + bonds          # "all-in": everything the stack paid
        stacks.append({
            "target_faction": faction,
            "system": where,
            "start": iso(run["start"]),
            "end": iso(hunt_end),
            "missions": len(mids),
            "completed": sum(1 for m in mids if m in completed),
            "failed": sum(1 for m in mids if m in failed),
            "open": sum(1 for m in mids if m not in completed and m not in failed),
            "in_progress": bool(working),
            "providers": len(per_giver),
            "kill_cost": max(per_giver.values(), default=0),
            "kills": len(window),
            "target_kills": len(targets),
            "quoted": sum(accepted[m].get("Reward") or 0 for m in mids),
            "paid": paid,
            "bounties": bounties,
            "bonds": bonds,
            "income": income,
            "merits": sum(g for t, g in merits if t and run["start"] <= t <= hunt_end),
            "hours": round(hours, 2),
            "per_kill": int(income / len(window)) if window else None,
            "per_hour": int(income / hours) if hours >= 0.25 else None,
            "target_rate": round((len(targets) - 1) / t_hours, 1) if t_hours >= 0.25 else None,
        })
    stacks.sort(key=lambda s: s["start"] or "", reverse=True)

    rates = sorted(s["target_rate"] for s in stacks if s["target_rate"] and s["target_kills"] >= 10)
    usual_pace = rates[len(rates) // 2] if rates else None
    ranked = [s for s in stacks if s["kills"] >= 10 and s["completed"]]

    providers = {}
    for m, c in completed.items():
        if str(c.get("Name") or "").startswith(MASSACRE_PREFIX):
            p = providers.setdefault(c.get("Faction"), {"name": c.get("Faction"), "missions": 0, "paid": 0})
            p["missions"] += 1
            p["paid"] += c.get("Reward") or 0
    places = {}
    for s in stacks:
        p = places.setdefault(s["system"], {"system": s["system"], "stacks": 0, "income": 0})
        p["stacks"] += 1
        p["income"] += s["income"]

    massacres_done = [c for c in completed.values()
                      if str(c.get("Name") or "").startswith(MASSACRE_PREFIX)]
    hunts = [s for s in sessions if s["kills"] or s["massacres"]]
    return {
        "generated": iso(utcnow()),
        "since": iso(since),
        "totals": {
            "massacres_completed": len(massacres_done),
            "massacre_credits": sum(c.get("Reward") or 0 for c in massacres_done),
            "kills": len(kills),
            "bounties": sum(k[3] for k in kills if k[4] == "bounty"),
            "bonds": sum(k[3] for k in kills if k[4] == "bond"),
            "merits": sum(g for _, g in merits),
            "stacks": sum(1 for s in stacks if s["completed"]),
            "hunting_hours": round(sum(s["hours"] for s in stacks), 1),
        },
        "best_per_kill": max(ranked, key=lambda s: s["per_kill"] or 0, default=None),
        "best_per_hour": max((s for s in ranked if s["per_hour"]),
                             key=lambda s: s["per_hour"], default=None),
        "top_systems": sorted(places.values(), key=lambda p: -p["income"])[:5],
        "top_providers": sorted(providers.values(), key=lambda p: -p["missions"])[:5],
        "stacks": stacks,
        "sessions": [{
            "start": iso(s["start"]), "hours": round(s["active"] / 3600, 2),
            "kills": s["kills"], "bounties": s["bounties"], "bonds": s["bonds"],
            "bond_kills": s["bond_kills"], "paid": s["paid"],
            "merits": s["merits"], "massacres": s["massacres"],
        } for s in reversed(hunts[-30:]) if s["start"] and s["end"]],
        "usual_pace": usual_pace,
        "empire_rate": empire_rate,
        "combat_rate": combat_rate,
    }


# --------------------------------------------------------------------------
# Console output
# --------------------------------------------------------------------------

def fmt_cr(value):
    return f"{value:,}".replace(",", " ")


def fmt_span(seconds):
    if seconds is None:
        return "no expiry"
    if seconds <= 0:
        return "EXPIRED"
    hours, rem = divmod(int(seconds), 3600)
    days, hours = divmod(hours, 24)
    if days:
        return f"{days}d {hours}h"
    return f"{hours}h {rem // 60}m"


def print_report(state):
    t = state["totals"]
    print()
    print("=" * 68)
    print(f" {APP_NAME.upper()}")
    print("=" * 68)
    print(f" CMDR {state['commander'] or '?'}   |   in system: {state['current_system'] or '?'}")
    legal = state.get("legal")
    if legal and legal["wanted"]:
        owed = f": {fmt_cr(legal['bounty'])} Cr bounty" if legal["bounty"] else ""
        print(f" !! WANTED in {legal['system']}{owed}")
    if legal and legal["fine"]:
        owed = f": {fmt_cr(legal['fines'])} Cr" if legal["fines"] else ""
        print(f" !  Unpaid fine in {legal['system']}{owed}")
    print()
    if not state["groups"] and not state["ready"]:
        print(" No active massacre missions found.")
        print()
        return

    for g in state["groups"]:
        flag = "   <-- you are here" if g["in_position"] else ""
        print("-" * 68)
        print(f" {g['target_faction']}  in  {g['system']}{flag}")
        needed = f"{g['kills_needed']}+" if g["uncertain"] else str(g["kills_needed"])
        print(f" {g['mission_count']} missions | {needed} kills needed "
              f"| {fmt_cr(g['reward'])} Cr | {fmt_cr(g['cr_per_kill'])} Cr/kill")
        for c in g["chains"]:
            queue = f" ({c['missions']} queued one after another)" if c["missions"] > 1 else ""
            free = f"  ({c['free']} free)" if c["free"] and state["slots"]["used"] < state["slots"]["cap"] else ""
            print(f"   {c['kills']:>3} kills from {c['giver']}{queue}{free}")
        print("-" * 68)
        for m in g["missions"]:
            width = 22
            filled = int(width * m["done"] / m["required"]) if m["required"] else 0
            bar = "#" * filled + "." * (width - filled)
            tag = "WING" if m["wing"] else "    "
            note = ""
            if m["expired"]:
                note = "  !EXPIRED"
            elif m["queued"]:
                note = "  (waits for the one above from the same faction)"
            elif m["capped"]:
                note = "  ? estimate ran out - check the panel and sync"
            elif m["synced"]:
                note = "  (synced)"
            print(f"  {tag} [{bar}] {m['done']:>3}/{m['required']:<3} "
                  f"{fmt_cr(m['reward']):>12} Cr  {fmt_span(m['expires_in']):>9}{note}")
            where = f"{m['origin_station']} ({m['origin_system']})" \
                if m["origin_station"] else "origin unknown"
            print(f"       {m['giver']}  -  kill in {m['system']}, hand in at {where}")
        nxt = g["next_payout"]
        if nxt:
            print(f"   next: {nxt['kills']} more kill(s) -> {nxt['missions']} mission(s), "
                  f"{fmt_cr(nxt['reward'])} Cr")
        print()

    if state["ready"]:
        print("-" * 68)
        print(" READY TO HAND IN")
        print("-" * 68)
        for r in state["ready"]:
            print(f"  {fmt_cr(r['reward']):>12} Cr  {r['station']} ({r['system']})  - {r['giver']}")
        print()

    print("=" * 68)
    unsure = any(g["uncertain"] for g in state["groups"])
    total_kills = f"{t['kills_needed']}+" if unsure else str(t["kills_needed"])
    print(f" TOTAL: {total_kills} kills for {fmt_cr(t['reward'])} Cr "
          f"= {fmt_cr(t['cr_per_kill'])} Cr/kill")
    if unsure:
        print(" (+ = the journal estimate ran past a mission the game still"
              " lists as active)")
    if t["kills_saved"]:
        print(f" Stacking saves you {t['kills_saved']} kills "
              f"(would be {t['kills_naive']} one at a time)")
    if any(c["missions"] > 1 for g in state["groups"] for c in g["chains"]):
        print(" Tip: missions from the SAME giving faction do not stack with"
              " each other -")
        print("      they complete one after another. Spread them across"
              " different factions.")
    if t["ready_reward"]:
        print(f" Waiting to be collected: {fmt_cr(t['ready_reward'])} Cr")
    print("=" * 68)
    print()


# --------------------------------------------------------------------------
# Verification: replay history and check counting against MissionRedirected
# --------------------------------------------------------------------------

def verify(tracker):
    """Every completion the game recorded, against two predictions: the kills
    logged since the mission started earning, and the same corrected by the
    completions that came before it on that stream (what the dashboard shows)."""
    print()
    print("Each completion the game recorded (the moment a mission's last kill counted),")
    print("against the kills the journal logged for that mission.")
    print()
    streams = {}
    for mid, when in tracker.redirected.items():
        m = tracker.missions.get(mid)
        if m and when:
            key = (m["target_faction"], m["target_type"], m["system"])
            streams.setdefault(key, []).append((when, mid))
    if not streams:
        print("  No completed massacre missions in the scanned window.")
        print("  Try a wider window:  python stacker.py --verify --days 90")
        print()
        return

    rows = []
    for key, finished in streams.items():
        frame = CreditFrame(tracker.credit_frame(*key).times)   # pinned as we go
        for when, mid in sorted(finished):
            m = tracker.missions[mid]
            lo, hi = frame.start(m, tracker.chain_anchor(m)), frame.upto(when)
            predicted = frame.at(hi) - frame.at(lo)
            rows.append((when, m, hi - lo, predicted))
            frame.pin(hi, frame.at(lo) + m["kill_count"])

    alone = corrected = 0
    for when, m, logged, predicted in sorted(rows, key=lambda r: r[0]):
        need = m["kill_count"]
        alone += logged == need
        corrected += predicted == need
        mark = lambda n: "OK" if n == need else f"{n - need:+d}"
        print(f"  {when:%m-%d}  needed {need:>3}  logged {mark(logged):>4}  corrected {mark(predicted):>4}  "
              f"{m['target_faction']} ({m['target_type']}) in {m['system']}, from {m['giver']}")
    print()
    print(f"  {alone}/{len(rows)} matched by the logged kills alone,")
    print(f"  {corrected}/{len(rows)} once the completions before them are used.")
    print("  + means the game counted fewer kills than were logged; - that it counted more.")
    print()


# --------------------------------------------------------------------------
# Web server
# --------------------------------------------------------------------------

def dress(html, style):
    """Put the style into the page before it's sent, so its first frame (and
    the welcome card) already wears the right name, emblem and colours."""
    def text(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    colours = (f":root {{ --imperial: {style['accent']}; --imperial-deep: {style['deep']}; "
               f"--ground-top: {style['ground']}; --on-accent: {style['on_accent']}; }}")
    for token, value in (("%%STYLE_VARS%%", colours), ("%%NAME%%", text(style["name"])),
                         ("%%SMALL%%", text(style["small"])), ("%%MAIN%%", text(style["main"])),
                         ("%%POWER%%", text(style["power"] or style["name"])),
                         ("%%SLUG%%", style["slug"]), ("%%BOUNTY%%", style["bounty"])):
        html = html.replace(token, value)
    return html


class Server(ThreadingHTTPServer):
    # With SO_REUSEADDR set, Windows lets a second socket bind a port that is
    # already listening, so a second copy of the app would start silently
    # beside the first. Refuse there; elsewhere the flag only skips the wait
    # after a restart.
    allow_reuse_address = os.name != "nt"


def already_running(port):
    """Is the app already answering on this port?"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state", timeout=2) as reply:
            return "groups" in json.loads(reply.read())
    except (OSError, ValueError):
        return False


class Handler(BaseHTTPRequestHandler):
    tracker = None
    last_seen = 0.0       # when a dashboard last asked for data
    bye_at = 0.0          # when a dashboard said it was closing

    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _style_image(self, slug):
        path = RES_DIR / "styles" / f"{slug}.png"
        if slug in STYLES and path.is_file():
            self._send(200, path.read_bytes(), "image/png")
        else:
            self._send(404, "no emblem", "text/plain; charset=utf-8")

    def do_POST(self):
        # The dashboard says goodbye as its window closes (or reloads).
        if urlparse(self.path).path == "/api/bye":
            Handler.bye_at = time.time()
            self._send(204, b"", "text/plain")
        else:
            self._send(404, "not found", "text/plain; charset=utf-8")

    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path

        if route in ("/", "/index.html"):
            page = RES_DIR / "dashboard.html"
            if not page.is_file():
                self._send(500, "dashboard.html is missing", "text/plain; charset=utf-8")
                return
            self._send(200, dress(page.read_text(encoding="utf-8"), self.tracker.style()),
                       "text/html; charset=utf-8")

        elif route == "/api/history":
            body = json.dumps(self.tracker.history_report())
            self._send(200, body, "application/json; charset=utf-8")

        elif route == "/emblem":
            # The style's emblem, unless you've put an emblem image of your
            # own beside stacker.py (or the .exe).
            types = {".svg": "image/svg+xml", ".png": "image/png",
                     ".webp": "image/webp", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
            for suffix, ctype in types.items():
                path = APP_DIR / f"emblem{suffix}"
                if path.is_file():
                    self._send(200, path.read_bytes(), ctype)
                    return
            self._style_image(self.tracker.style()["slug"])

        elif route.startswith("/styles/") and route.endswith(".png"):
            self._style_image(route[len("/styles/"):-len(".png")])

        elif route.startswith("/fonts/"):
            # The display typeface ships in fonts/ so the dashboard never
            # reaches the internet. Without it the page falls back to the system font.
            name = route[len("/fonts/"):]
            path = RES_DIR / "fonts" / name
            if name.endswith(".woff2") and "/" not in name and "\\" not in name and path.is_file():
                self._send(200, path.read_bytes(), "font/woff2")
            else:
                self._send(404, "no such font", "text/plain; charset=utf-8")

        elif route in ("/api/state", "/api/refresh"):
            Handler.last_seen = time.time()
            if route == "/api/refresh":
                # Re-read the journal right now instead of waiting for the
                # background poll, so the button does something real.
                try:
                    self.tracker.poll()
                except Exception:
                    pass
            body = json.dumps(self.tracker.report())
            self._send(200, body, "application/json; charset=utf-8")

        elif route == "/api/sync":
            params = parse_qs(parsed.query)
            try:
                mission_id = int(params.get("mission", [""])[0])
            except ValueError:
                self._send(400, "bad mission id", "text/plain; charset=utf-8")
                return
            if "reset" in params:
                ok = self.tracker.clear_sync(mission_id)
            else:
                try:
                    ok = self.tracker.sync(mission_id, int(params.get("done", ["0"])[0]))
                except ValueError:
                    ok = False
            self._send(200 if ok else 404, json.dumps({"ok": ok}),
                       "application/json; charset=utf-8")

        elif route == "/api/config":
            params = parse_qs(parsed.query)
            if "require_system" in params:
                self.tracker.require_system = params["require_system"][0] not in ("0", "false")
            if "style" in params:
                choice = params["style"][0]
                save_config(style=choice if choice in STYLES else "auto")
            self._send(200, json.dumps({"require_system": self.tracker.require_system,
                                        "style": self.tracker.style()}),
                       "application/json; charset=utf-8")
        else:
            self._send(404, "not found", "text/plain; charset=utf-8")


def watcher(tracker, interval=1.0):
    while True:
        try:
            tracker.poll()
        except Exception as exc:                      # keep the loop alive
            print(f"[watch] {exc}", file=sys.stderr)
        time.sleep(interval)


# --------------------------------------------------------------------------

def fail(*lines):
    """Explain why we're stopping: in a dialog when there's no console to
    print to (the packaged app has none), otherwise on the console."""
    if sys.stdout is None and os.name == "nt":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, "\n".join(lines), APP_NAME, 0x10)
    else:
        for line in lines:
            print(line)
    return 1


def borrow_console():
    """The packaged app has no console window. For the text commands
    (--console, --verify, --help) it borrows the terminal it was started
    from, or opens one of its own. Returns True when it opened its own."""
    if sys.stdout is not None or os.name != "nt":
        return False
    import ctypes
    kernel = ctypes.windll.kernel32
    attached = bool(kernel.AttachConsole(-1))       # the terminal we were run from
    if not attached:
        kernel.AllocConsole()
    sys.stdout = sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace")
    sys.stdin = open("CONIN$", encoding="utf-8")
    return not attached


def app_browser():
    """Edge or Chrome: they can show a page as a window of its own, with no
    tabs or address bar. Edge ships with every copy of Windows."""
    if os.name == "nt":
        import winreg
        for exe in ("msedge.exe", "chrome.exe"):
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    key = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}"
                    with winreg.OpenKey(hive, key) as handle:
                        path = winreg.QueryValue(handle, None)
                    if path and Path(path).is_file():
                        return path
                except OSError:
                    continue
        for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
                     os.environ.get("LOCALAPPDATA")):
            for rel in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"):
                if base and Path(base, rel).is_file():
                    return str(Path(base, rel))
        return None
    for mac in ("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if Path(mac).is_file():
            return mac
    for name in ("microsoft-edge", "google-chrome", "chromium", "chromium-browser"):
        if shutil.which(name):
            return shutil.which(name)
    return None


def open_window(url, tab=False):
    """Show the dashboard as its own app window, or as a browser tab when
    asked to or when no suitable browser is installed. Returns the window's
    browser process when there is one to watch."""
    browser = None if tab else app_browser()
    if browser:
        # A profile of its own keeps the window separate from your browsing
        # (and remembers its size and place), and makes the browser process
        # ours, so we can tell when the window has been closed.
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
        profile = Path(base) / APP_FILE / "window"
        old = Path(base) / "Imperial Anti-Piracy Network" / "window"    # before the rename
        try:
            if old.is_dir() and not profile.exists():
                profile.parent.mkdir(parents=True, exist_ok=True)
                old.rename(profile)
            profile.mkdir(parents=True, exist_ok=True)
            return subprocess.Popen(
                [browser, f"--app={url}", f"--user-data-dir={profile}", "--window-size=1440,900",
                 "--no-first-run", "--no-default-browser-check"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass
    webbrowser.open(url)
    return None


def close_with_window(server, window):
    """Stop when the dashboard is closed, like any other app: when the page
    says goodbye and nothing asks for data again (a reload asks at once), or
    when the window's own browser process ends."""
    opened = time.time()
    while True:
        time.sleep(1)
        now = time.time()
        quiet = now - Handler.last_seen > 4
        said_bye = Handler.bye_at and now - Handler.bye_at > 4 and Handler.last_seen < Handler.bye_at
        # A process that ends within seconds only handed the window to a
        # browser that was already running; that isn't the window closing.
        closed = window is not None and window.poll() is not None and now - opened > 10
        if said_bye or (closed and quiet):
            break
    server.shutdown()


def main():
    own_console = False
    if any(flag in sys.argv for flag in ("-h", "--help", "--console", "--verify")):
        own_console = borrow_console()
    try:
        return run()
    finally:
        if own_console:
            input("\nPress Enter to close.")


def run():
    ap = argparse.ArgumentParser(prog=PROG, description=f"{APP_NAME}: Elite Dangerous massacre stacking")
    ap.add_argument("--journal-dir", help="path to the Elite Dangerous journal folder")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--days", type=int, default=30, help="how far back to scan (default 30)")
    ap.add_argument("--console", action="store_true", help="print a summary and exit")
    ap.add_argument("--verify", action="store_true", help="check kill counting against history")
    ap.add_argument("--any-system", action="store_true",
                    help="count kills regardless of which system they happened in")
    ap.add_argument("--tab", action="store_true",
                    help="open in your usual browser as a tab, not in a window of its own")
    ap.add_argument("--no-browser", action="store_true",
                    help="don't open anything; keep serving until stopped")
    args = ap.parse_args()
    url = f"http://127.0.0.1:{args.port}/"

    # Started twice (a second double-click, say): show the one that's running.
    if not (args.verify or args.console) and already_running(args.port):
        print(f"{APP_NAME} is already running at {url}")
        if not args.no_browser:
            open_window(url, tab=args.tab)
        return 0

    journal_dir = find_journal_dir(args.journal_dir)
    if not journal_dir:
        return fail("Could not find your Elite Dangerous journal folder.",
                    r"Expected: %USERPROFILE%\Saved Games\Frontier Developments\Elite Dangerous",
                    f'Pass it explicitly:  {PROG} --journal-dir "D:\\path\\to\\folder"',
                    f"or put its path in config.json beside {'the .exe' if FROZEN else 'stacker.py'}.")

    tracker = Tracker(journal_dir, days=args.days, require_system=not args.any_system)
    print(f"Reading journals from: {journal_dir}")
    tracker.load_history()

    if args.verify:
        verify(tracker)
        return 0

    if args.console:
        tracker.history_report()          # usual pace and Imperial rate for the estimates
        print_report(tracker.report())
        return 0

    threading.Thread(target=watcher, args=(tracker,), daemon=True).start()
    threading.Thread(target=tracker.history_report, daemon=True).start()

    Handler.tracker = tracker
    try:
        server = Server(("127.0.0.1", args.port), Handler)
    except OSError as exc:
        return fail(f"Could not start on port {args.port}: {exc}",
                    "Something else is using it. Try another port:",
                    f"  {PROG} --port 8790")

    print()
    print(f"  {APP_NAME} running at {url}")
    print("  Close its window to stop (or press Ctrl+C here).")
    print()
    if not args.no_browser:
        window = open_window(url, tab=args.tab)
        threading.Thread(target=close_with_window, args=(server, window), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    print("Stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
