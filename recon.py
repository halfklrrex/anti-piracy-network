"""Recon: where to stack pirate massacre missions next.

Finds target systems -- a pirate faction's home -- with the most mission givers
in the systems around them, and ranks them with what your own journal says
about the game and about you:

- INTRA (iniv.space/intra) pairs each source system with the one target system
  its massacre missions can point at. Massacre missions always target a pirate
  faction within 10 ly (every stack in the author's journal was within 9.9 ly),
  and INTRA only pairs a source whose reach holds exactly one target system.
- EDSM names the factions in each of those systems, with their states.
- Your journal says how each of those factions sees you, how much a giver's
  state costs you, and what standing is worth per kill.

Only the reference position and system names leave your PC; your standing is
joined in here. Standard library only, like the rest of the app.
"""
from __future__ import annotations

import http.client
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

INTRA_URL = "https://iniv.space/intra/api/"
EDSM_URL = "https://www.edsm.net"
USER_AGENT = "Anti-Piracy-Network (+https://github.com/halfklrrex/anti-piracy-network)"

INTRA_TTL = 3600              # a search: INTRA's faction reports update through the day
FACTIONS_TTL = 6 * 3600       # a system's factions: the background simulation ticks daily
COORDS_TTL = 365 * 86400      # where a system is doesn't change
EDSM_GAP = 1.0                # at most one EDSM request a second (see edsm_json)
ENRICH_TARGETS = 40           # the best this many targets (INTRA's order) get their factions named
STATES_FRESH = 3 * 86400      # older states are ignored: an Election builds up over about 3 days
DATA_STALE = 7 * 86400        # a system not reported for a week is left out

# The journal names A. Lavigny-Duval; INTRA uses her full name.
INTRA_POWER = {"A. Lavigny-Duval": "Arissa Lavigny-Duval"}
JOURNAL_POWER = {v: k for k, v in INTRA_POWER.items()}
SUPERPOWERS = {"Empire", "Federation", "Alliance"}
NOT_GIVERS = {"Pilots' Federation Local Branch"}

# What a giver's state costs, where your own journal hasn't enough of it to
# say. Elections: none of 28 givers in one gave the author a massacre mission.
# War: INTRA's help -- warring factions only target each other. Famine and
# Outbreak: combat missions don't count toward them, and the board turns to
# food and medicine. Lockdown shuts station services.
STATE_DEFAULTS = {"Election": 0.0, "War": 0.3, "Famine": 0.5, "Outbreak": 0.5, "Lockdown": 0.5}
MIN_STATE_SAMPLES = 15
# Reward per kill against Neutral, where the journal hasn't enough to say
# (the author's: Cordial 2.0, Friendly 2.2, Allied 3.0).
PAY_DEFAULTS = {"Neutral": 1.0, "Cordial": 2.0, "Friendly": 2.2, "Allied": 3.0}
MIN_PAY_SAMPLES = 8


class ReconError(Exception):
    pass


# --------------------------------------------------------------------------
# What your journal says
# --------------------------------------------------------------------------

def state_weights(evidence):
    """How much a giver in each state is worth, next to one in no state:
    measured from your own stacking visits where there are enough of them,
    the defaults above otherwise. States only ever cost; a measured rate
    above the no-state one is noise, not a bonus."""
    rows = (evidence or {}).get("states") or {}
    weights = dict(STATE_DEFAULTS)
    measured = {}
    base = rows.get("None")
    if base and base["n"] >= MIN_STATE_SAMPLES and base["gave"]:
        rate = base["gave"] / base["n"]
        for state, row in rows.items():
            if state != "None" and row["n"] >= MIN_STATE_SAMPLES:
                weights[state] = round(min(1.0, row["gave"] / row["n"] / rate), 2)
                measured[state] = row
    return weights, measured


def pay_multipliers(evidence):
    """Reward per kill at each standing, against Neutral."""
    rows = (evidence or {}).get("pay") or {}
    mult = dict(PAY_DEFAULTS)
    base = rows.get("Neutral")
    if base and base["n"] >= MIN_PAY_SAMPLES and base["per_kill"]:
        for band, row in rows.items():
            if band in mult and band != "Neutral" and row["n"] >= MIN_PAY_SAMPLES:
                mult[band] = round(max(1.0, row["per_kill"] / base["per_kill"]), 1)
    return mult


# --------------------------------------------------------------------------
# Fetching, politely, with a cache
# --------------------------------------------------------------------------

class Cache:
    """Answers from INTRA and EDSM, kept in one JSON file."""

    def __init__(self, folder):
        self.path = Path(folder) / "cache.json"
        self.lock = threading.Lock()
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}
        now = time.time()
        self.data = {k: v for k, v in self.data.items()
                     if isinstance(v, list) and len(v) == 2 and now - v[0] < COORDS_TTL}

    def get(self, key, max_age):
        with self.lock:
            entry = self.data.get(key)
        if entry and time.time() - entry[0] <= max_age:
            return entry[1]
        return None

    def put(self, key, value):
        with self.lock:
            self.data[key] = [time.time(), value]

    def save(self):
        now = time.time()
        with self.lock:
            # Search results and factions are no use after a day; places are.
            keep = {k: v for k, v in self.data.items()
                    if k.startswith("coords:") or now - v[0] < 86400}
            body = json.dumps(keep)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(body, encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass


class Busy(ReconError):
    """The server asked us to slow down (HTTP 429)."""

    def __init__(self, retry_after):
        super().__init__(f"asked to wait {retry_after} s")
        self.retry_after = retry_after


def fetch_json(url, body=None, timeout=20):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            return json.loads(reply.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            try:
                wait = float(exc.headers.get("Retry-After") or 5)
            except ValueError:
                wait = 5.0
            raise Busy(min(max(wait, 1.0), 60.0)) from exc
        raise ReconError(str(exc)) from exc
    except (OSError, ValueError, http.client.HTTPException) as exc:
        raise ReconError(str(exc)) from exc


# EDSM sits behind Cloudflare, which answers 429 to a burst (measured: a
# request every half second was cut off after about 30). One a second, and
# slower each time it says so, never faster than it asks.
_edsm_gate = threading.Lock()
_edsm = {"last": 0.0, "gap": EDSM_GAP}


def edsm_json(path, **params):
    url = f"{EDSM_URL}{path}?{urllib.parse.urlencode(params)}"
    for attempt in range(4):
        with _edsm_gate:
            wait = _edsm["last"] + _edsm["gap"] - time.time()
            if wait > 0:
                time.sleep(wait)
            _edsm["last"] = time.time()
        try:
            return fetch_json(url)
        except Busy as busy:
            with _edsm_gate:
                _edsm["gap"] = min(_edsm["gap"] * 1.5, 4.0)
                _edsm["last"] = time.time() + busy.retry_after - _edsm["gap"]
    raise ReconError("EDSM is too busy")


def intra_pairs(cache, pos, radius, large_pads, power):
    """Source/target pairs near `pos`, best first by INTRA's own reckoning."""
    body = {"ver": 1, "lim": 99,
            "ref": {"x": pos[0], "y": pos[1], "z": pos[2], "max": radius},
            "shop": {}, "arena": {}}
    if large_pads:
        body["shop"]["dist"] = {"port": 1000000}       # needs a starport, at any distance
    if power:
        body["arena"]["pow"] = [INTRA_POWER.get(power, power)]
    key = "intra:" + json.dumps(body, sort_keys=True)
    hit = cache.get(key, INTRA_TTL)
    if hit is not None:
        return hit
    reply = fetch_json(INTRA_URL, body)
    if not isinstance(reply, dict) or not reply.get("ok"):
        raise ReconError((reply or {}).get("msg") or "INTRA refused the search")
    pairs = [p for p in reply.get("body") or [] if p.get("shop") and p.get("arena")]
    cache.put(key, pairs)
    return pairs


def edsm_factions(cache, system):
    """The factions present in a system (influence above zero: EDSM keeps
    factions that have left, at 0%), with their states."""
    key = "factions:" + system.lower()
    hit = cache.get(key, FACTIONS_TTL)
    if hit is not None:
        return hit
    reply = edsm_json("/api-system-v1/factions", systemName=system)
    record = {"known": isinstance(reply, dict) and "factions" in reply, "factions": []}
    for f in (reply.get("factions") if record["known"] else None) or []:
        if (f.get("influence") or 0) <= 0 or not f.get("name"):
            continue
        record["factions"].append({
            "name": f["name"], "government": f.get("government"),
            "allegiance": f.get("allegiance"), "influence": f.get("influence"),
            "states": [s.get("state") for s in f.get("activeStates") or [] if s.get("state")],
            "pending": [s.get("state") for s in f.get("pendingStates") or [] if s.get("state")],
            "updated": f.get("lastUpdate") or 0,
        })
    cache.put(key, record)
    return record


def edsm_coords(cache, name):
    """(name as EDSM spells it, (x, y, z)) for a system, or None."""
    key = "coords:" + name.strip().lower()
    hit = cache.get(key, COORDS_TTL)
    if hit is not None:
        return (hit[0], tuple(hit[1])) if hit else None
    reply = edsm_json("/api-v1/system", systemName=name.strip(), showCoordinates=1)
    c = reply.get("coords") if isinstance(reply, dict) else None
    found = [reply["name"], [c["x"], c["y"], c["z"]]] if c else []
    cache.put(key, found)
    return (found[0], tuple(found[1])) if found else None


# --------------------------------------------------------------------------
# Ranking
# --------------------------------------------------------------------------

def side(allegiance):
    return allegiance if allegiance in SUPERPOWERS else "Independent"


def rank(pairs, systems, standing_of, weights, pay_mult, prefs, stacked=None, now=None):
    """Targets, best first.

    A target's worth is its givers: every faction in its sources that can give
    pirate massacre missions (not an Anarchy), counted once however many of
    the sources it's in, because missions from one giver queue one after
    another. Each counts for what its state leaves of its board, and nothing
    if it dislikes you (Unfriendly or Hostile factions don't offer missions).
    The total is split between the target's pirate factions, since missions
    are spread between them. Ties go to pay: what your standing with the
    givers is worth per kill.
    """
    now = now or time.time()
    stacked = stacked or {}
    allegiance = prefs.get("allegiance") or "any"
    order, groups = [], {}
    for p in pairs:
        name = p["arena"]["name"]
        if name not in groups:
            groups[name] = {"arena": p["arena"], "shops": []}
            order.append(name)
        if all(s["name"] != p["shop"]["name"] for s in groups[name]["shops"]):
            groups[name]["shops"].append(p["shop"])

    out = []
    for position, name in enumerate(order):
        arena, shops = groups[name]["arena"], groups[name]["shops"]
        target = {
            "system": name, "intra_rank": position,
            "distance": arena.get("ref_d"),
            "power": JOURNAL_POWER.get(arena.get("pow"), arena.get("pow")) or None,
            "starport_ls": _ls(arena.get("port_d")), "outpost_ls": _ls(arena.get("post_d")),
            "res": {k: _res(arena.get(k)) for k in ("haz", "hi", "med", "low")},
            "cnb": arena.get("cnb4") == 1,
            "stacked": stacked.get(name, 0),
        }
        record = systems.get(name)
        if record is None:
            # Not named yet: INTRA's count of factions that give these
            # missions, summed over the sources, to show while EDSM answers.
            key = {"Empire": "e", "Federation": "f", "Alliance": "a", "Independent": "i"}.get(allegiance, "all")
            target.update(pending=True, sources=[_source(s, None, now) for s in shops],
                          estimate=sum((s.get("fac") or {}).get(key, 0) for s in shops))
            out.append(target)
            continue
        newest = max((f["updated"] for f in record["factions"]), default=0)
        if record["known"] and newest and now - newest > DATA_STALE:
            continue                                   # nobody has reported the target for a week
        pirates = [f["name"] for f in record["factions"] if f["government"] == "Anarchy"]

        givers, sources, pending = {}, [], False
        for s in shops:
            rec = systems.get(s["name"])
            src = _source(s, rec, now)
            if rec is None:
                pending = True
            elif src["stale"]:
                continue
            sources.append(src)
            for f in (rec or {}).get("factions") or []:
                if f["government"] == "Anarchy" or f["name"] in NOT_GIVERS:
                    continue
                src["givers"].append(f["name"])
                g = givers.get(f["name"])
                if g:
                    g["sources"].append(s["name"])
                    continue
                givers[f["name"]] = _giver(f, s["name"], standing_of(f["name"]), weights, now)

        score = pay = 0.0
        for g in givers.values():
            g["counted"] = allegiance == "any" or side(g["allegiance"]) == allegiance
            if g["counted"]:
                score += g["weight"]
                pay += g["weight"] * pay_mult.get(g["standing"] or "Neutral", 1.0)
        split = max(1, len(pirates))
        target.update(
            pending=pending, pirates=pirates, sources=sources,
            unnamed=not record["known"] or any(s["failed"] for s in sources),
            givers=sorted(givers.values(), key=lambda g: (not g["counted"], -g["weight"],
                                                          -(g["rep"] or 0), g["name"])),
            count=sum(1 for g in givers.values() if g["counted"] and g["weight"] > 0),
            score=round(score / split, 2), pay=round(pay / split, 2),
            updated=newest or None,
        )
        out.append(target)

    by_pay = prefs.get("sort") == "pay"

    def key(t):
        if t.get("pending"):
            return (2, 0, 0, t["intra_rank"])
        first, second = (t["pay"], t["score"]) if by_pay else (t["score"], t["pay"])
        # A target EDSM couldn't fully name would be undercounted: after the rest.
        return (1 if t["unnamed"] else 0, -first, -second, t["distance"] or 0)
    return sorted(out, key=key)


def _ls(value):
    return value if isinstance(value, (int, float)) and value >= 0 else None


def _res(status):
    """True when a RES of this kind is reported or confirmed, False when
    confirmed absent, None when nobody knows."""
    if not isinstance(status, dict):
        return None
    if status.get("c") in (0, 1):
        return bool(status["c"])
    return True if status.get("r") == 1 else None


def _source(shop, record, now):
    newest = max((f["updated"] for f in (record or {}).get("factions") or []), default=0)
    return {
        "system": shop["name"], "distance": shop.get("ref_d"),
        "power": JOURNAL_POWER.get(shop.get("pow"), shop.get("pow")) or None,
        "starport_ls": _ls(shop.get("port_d")), "outpost_ls": _ls(shop.get("post_d")),
        "givers": [], "pending": record is None, "failed": bool(record and record.get("failed")),
        "stale": bool(record and record["known"] and newest and now - newest > DATA_STALE),
    }


def _giver(f, source, standing, weights, now):
    fresh = f["updated"] and now - f["updated"] <= STATES_FRESH
    shunned = (standing or {}).get("standing") in ("Unfriendly", "Hostile")
    weight = 0.0 if shunned else 1.0
    if fresh and not shunned:
        weight = min([weights.get(s, 1.0) for s in f["states"]] or [1.0])
    return {
        "name": f["name"], "allegiance": side(f["allegiance"]), "government": f["government"],
        "states": f["states"] if fresh else [], "pending": f["pending"] if fresh else [],
        "states_known": bool(fresh), "updated": f["updated"] or None,
        "standing": (standing or {}).get("standing"), "rep": (standing or {}).get("rep"),
        "shunned": shunned, "weight": round(weight, 2), "sources": [source],
    }


# --------------------------------------------------------------------------
# The search, in the background
# --------------------------------------------------------------------------

class Recon:
    """One search at a time, run on a thread. Results are published as they
    arrive: targets straight from INTRA, then their factions one system at a
    time, so the page fills in rather than waiting."""

    def __init__(self, folder):
        self.cache = Cache(folder)
        self.lock = threading.Lock()
        self.gen = 0
        self.query = None
        self.status, self.error = "idle", None
        self.pairs, self.systems, self.queue, self.failed = [], {}, [], 0
        self.started = self.finished = None

    def start(self, query):
        """query: {"ref": name, "pos": (x, y, z) or None, "radius", "large", "power"}"""
        with self.lock:
            self.gen += 1
            gen = self.gen
            self.query = dict(query)
            self.status, self.error = "searching", None
            self.pairs, self.systems, self.queue, self.failed = [], {}, [], 0
            self.started, self.finished = time.time(), None
        threading.Thread(target=self._run, args=(gen, dict(query)), daemon=True).start()

    def _set(self, gen, **values):
        with self.lock:
            if gen != self.gen:
                return False
            for k, v in values.items():
                setattr(self, k, v)
            return True

    def _run(self, gen, q):
        try:
            if not q.get("pos"):
                found = edsm_coords(self.cache, q["ref"])
                if not found:
                    self._set(gen, status="error", error="unknown system",
                              finished=time.time())
                    return
                q["ref"], q["pos"] = found
                self._set(gen, query=dict(q))
            pairs = intra_pairs(self.cache, q["pos"], q["radius"], q["large"], q.get("power"))
        except ReconError:
            self._set(gen, status="error", error="intra", finished=time.time())
            self.cache.save()
            return

        # Factions for the best targets and their sources, best first.
        queue, seen = [], set()
        targets = []
        for p in pairs:
            if p["arena"]["name"] not in targets:
                targets.append(p["arena"]["name"])
        keep = set(targets[:ENRICH_TARGETS])
        for name in targets[:ENRICH_TARGETS]:
            for p in pairs:
                if p["arena"]["name"] == name:
                    for system in (name, p["shop"]["name"]):
                        if system not in seen:
                            seen.add(system)
                            queue.append(system)
        if not self._set(gen, pairs=[p for p in pairs if p["arena"]["name"] in keep],
                         queue=queue, status="naming"):
            return

        failures = successes = 0
        for system in queue:
            with self.lock:
                if gen != self.gen:
                    return
            try:
                record = edsm_factions(self.cache, system)
                successes += 1
            except ReconError:
                failures += 1
                record = {"known": False, "factions": [], "failed": True}
                if failures >= 3 and not successes:
                    self.cache.save()
                    self._set(gen, status="error", error="edsm", finished=time.time())
                    return
            with self.lock:
                if gen != self.gen:
                    return
                self.systems = dict(self.systems, **{system: record})
                self.failed = failures
            if successes and successes % 10 == 0:
                self.cache.save()
        self.cache.save()
        self._set(gen, status="done", finished=time.time())

    def snapshot(self, standing_of, weights, pay_mult, prefs, stacked):
        with self.lock:
            pairs, systems = self.pairs, self.systems
            head = {"status": self.status, "error": self.error, "query": self.query,
                    "checked": len(systems), "to_check": len(self.queue), "failed": self.failed,
                    "started": self.started, "finished": self.finished}
        head["targets"] = rank(pairs, systems, standing_of, weights, pay_mult, prefs, stacked)
        return head
