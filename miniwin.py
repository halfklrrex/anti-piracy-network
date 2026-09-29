"""The mini window: a small panel at the top-left of the screen, above the
game, showing only what you choose from your stacks.

It's a native window of the app's own (tkinter, which comes with Python), not
a browser window. Windows can make one colour of an ordinary window fully
see-through, so everything around the rounded panel simply isn't there and the
game shows through. (An Edge window can't do that: Edge draws with
DirectComposition, which window shapes don't clip, so its white frame always
showed.) It stays on top, out of the taskbar and Alt-Tab, never takes focus,
and by default lets clicks through to the game. It draws in Saira, loaded for
this app alone from fonts/saira.ttf.

Nothing can show over a game in exclusive fullscreen, so Elite needs
Borderless or Windowed mode for it. Windows only; elsewhere `SUPPORTED` is
False and nothing here runs.
"""
from __future__ import annotations

import os
import re
import threading
from pathlib import Path

SUPPORTED = os.name == "nt"
WIDTHS = {"s": 240, "m": 300, "l": 380}    # at 100% display scaling
SCALES = {"s": .82, "m": 1.0, "l": 1.24}   # the size setting scales type and spacing too
MARGIN = 12                                # from the top-left corner of the screen
RADIUS = 10                                # the panel's rounded corners
KEY = "#010203"                            # the see-through colour: drawn nowhere else

# The dashboard's colours, as solid colours on the panel (tkinter has no alpha).
LABEL, GREEN, AMBER, RED = "#f4f2f8", "#34d15a", "#ffb340", "#ff6b61"

if SUPPORTED:
    import ctypes
    from ctypes import wintypes as wt

    user32 = ctypes.WinDLL("user32")
    gdi32 = ctypes.WinDLL("gdi32")
    gdi32.AddFontResourceExW.argtypes = [wt.LPCWSTR, wt.DWORD, ctypes.c_void_p]
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
    user32.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_long]
    user32.GetDpiForWindow.argtypes = [wt.HWND]
    user32.MonitorFromPoint.restype = wt.HANDLE
    user32.MonitorFromPoint.argtypes = [wt.POINT, wt.DWORD]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]

    user32.GetMonitorInfoW.argtypes = [wt.HANDLE, ctypes.POINTER(MONITORINFO)]

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_APPWINDOW, WS_EX_NOACTIVATE = 0x20, 0x80, 0x40000, 0x08000000
FR_PRIVATE = 0x10


def game_display_mode():
    """How Elite is set to show: "fullscreen" (exclusive: nothing shows over
    it), "borderless" or "windowed"; None when the settings file isn't found.
    From its DisplaySettings.xml: <FullScreen> 0 windowed, 1 fullscreen,
    2 borderless."""
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return None
    path = Path(base) / "Frontier Developments" / "Elite Dangerous" / "Options" / "Graphics" / "DisplaySettings.xml"
    try:
        found = re.search(r"<FullScreen>\s*(\d)\s*</FullScreen>", path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    return {"0": "windowed", "1": "fullscreen", "2": "borderless"}.get(found.group(1)) if found else None


def mix(a, b, t):
    """Colour a laid over colour b at opacity t, both as #rrggbb."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x * t + y * (1 - t)):02x}" for x, y in zip(ca, cb))


def cr(n):
    return f"{int(n or 0):,}".replace(",", " ")


def short(n):
    n = n or 0
    return (f"{n / 1e9:.1f}B" if n >= 1e9 else f"{n / 1e6:.1f}M" if n >= 1e6
            else f"{round(n / 1e3)}K" if n >= 1e4 else cr(n))


def plural(n, one):
    return f"{n} {one}" + ("" if n == 1 else "s")


class MiniWindow:
    """The panel, on a thread of its own (tkinter keeps to the thread that
    made it). Once a second it asks `report()` for what to show, redraws, and
    fits the window to it."""

    def __init__(self, report, font_file=None, at=None):
        self.report = report                  # () -> Tracker.mini_report(...) with the saved choices
        self.font_file = Path(font_file) if font_file else None
        self.at = at                          # (x, y) instead of the top-left corner (for testing)
        self.on, self.size, self.opacity, self.click_through = False, "m", 90, True
        self.changed = True
        self.lock = threading.Lock()
        self.stopped = False
        self.thread = None
        if SUPPORTED:
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

    def configure(self, on, size="m", opacity=90, click_through=True):
        with self.lock:
            self.on = bool(on)
            self.size = size if size in WIDTHS else "m"
            self.opacity = max(60, min(100, int(opacity)))
            self.click_through = bool(click_through)
            self.changed = True

    def close(self):
        """Close it now (the app is quitting), and wait for its thread to let
        go of tkinter, which mustn't be torn down from another thread."""
        self.stopped = True
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3)

    # -- the window's own thread ----------------------------------------------

    def _run(self):
        try:
            user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))     # real pixels, per monitor
        except (AttributeError, OSError):
            pass
        if self.font_file and self.font_file.is_file():
            gdi32.AddFontResourceExW(str(self.font_file), FR_PRIVATE, None)
        import tkinter
        import tkinter.font as tkfont

        self.tkfont = tkfont
        root = tkinter.Tk()
        root.withdraw()
        root.overrideredirect(True)
        root.configure(bg=KEY)
        root.attributes("-topmost", True)
        root.attributes("-transparentcolor", KEY)
        canvas = tkinter.Canvas(root, bg=KEY, highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        families = set(tkfont.families(root))
        self.faces = ({"light": "Saira Light", "regular": "Saira", "bold": "Saira SemiBold"}
                      if {"Saira Light", "Saira SemiBold"} <= families
                      else {"light": "Segoe UI Light", "regular": "Segoe UI", "bold": "Segoe UI Semibold"})
        self.fonts = {}
        self.root, self.canvas, self.shown = root, canvas, False
        root.update_idletasks()
        self.hwnd = int(root.wm_frame(), 16)
        root.after(50, self._tick)
        try:
            root.mainloop()
        finally:
            # Let go of every tkinter object here, on this thread.
            self.fonts, self.canvas, self.root = {}, None, None

    def _tick(self):
        root = self.root
        if self.stopped:
            root.destroy()
            return
        with self.lock:
            on, size, opacity, through, changed = self.on, self.size, self.opacity, self.click_through, self.changed
            self.changed = False
        try:
            if not on:
                if self.shown:
                    root.withdraw()
                    self.shown = False
            else:
                scale = (user32.GetDpiForWindow(self.hwnd) or 96) / 96
                w, h = self._draw(self.report(), size, scale)
                if self.at:
                    x, y = self.at
                else:
                    info = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
                    user32.GetMonitorInfoW(user32.MonitorFromPoint(wt.POINT(0, 0), 1), ctypes.byref(info))
                    x = info.rcWork.left + round(MARGIN * scale)
                    y = info.rcWork.top + round(MARGIN * scale)
                root.geometry(f"{w}x{h}+{x}+{y}")
                if not self.shown:
                    self._style(opacity, through)      # before it shows, so it never takes focus
                    root.deiconify()
                    self.shown = True
                    self._style(opacity, through)
                elif changed:
                    self._style(opacity, through)
        except Exception:     # a bad moment in the journal mustn't take the window down
            pass
        root.after(1000, self._tick)

    def _style(self, opacity, through):
        """A tool window (no taskbar, no Alt-Tab) that never takes focus, and
        lets clicks through to the game unless you've said otherwise."""
        self.root.attributes("-alpha", opacity / 100)
        self.root.attributes("-topmost", True)
        ex = user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
        ex = (ex | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE) & ~WS_EX_APPWINDOW
        ex = ex | WS_EX_TRANSPARENT if through else ex & ~WS_EX_TRANSPARENT
        user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, ex)

    # -- drawing ------------------------------------------------------------

    def _font(self, face, px):
        key = (face, px)
        if key not in self.fonts:
            self.fonts[key] = self.tkfont.Font(root=self.root, family=self.faces[face], size=-px)
        return self.fonts[key]

    def _fit(self, text, font, width):
        if font.measure(text) <= width:
            return text
        while text and font.measure(text + "…") > width:
            text = text[:-1]
        return text + "…"

    def _runs(self, x, y, runs, right, px):
        """One line of text in pieces [(text, bold?, colour)], cut to end by `right`."""
        for text, bold, colour in runs:
            font = self._font("bold" if bold else "regular", px)
            if right - x <= 0:
                break
            text = self._fit(text, font, right - x)
            self.canvas.create_text(x, y, text=text, font=font, fill=colour, anchor="nw")
            x += font.measure(text)
        return x

    def _round_rect(self, x0, y0, x1, y1, r, fill, tag=""):
        c = self.canvas
        r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
        for cx, cy in ((x0, y0), (x1 - 2 * r, y0), (x0, y1 - 2 * r), (x1 - 2 * r, y1 - 2 * r)):
            c.create_oval(cx, cy, cx + 2 * r, cy + 2 * r, fill=fill, outline=fill, tags=tag)
        c.create_rectangle(x0 + r, y0, x1 - r, y1, fill=fill, outline=fill, tags=tag)
        c.create_rectangle(x0, y0 + r, x1, y1 - r, fill=fill, outline=fill, tags=tag)

    def _draw(self, m, size, scale):
        """Draw what `m` asks for; returns the window's (width, height)."""
        c = self.canvas
        c.delete("all")
        u = SCALES[size] * scale

        def S(v):
            return max(1, round(v * u))

        style = m.get("style") or {}
        panel = mix(style.get("ground") or "#140e1f", "#0b0a0f", .5)
        label2, label3 = mix(LABEL, panel, .64), mix(LABEL, panel, .52)
        accent = style.get("accent") or "#b890ff"
        W = round(WIDTHS[size] * scale)
        px = S(14)
        right = W - px
        want = set(m.get("fields") or [])
        st = m.get("stack")
        line_px = S(12)
        line_h = self._font("regular", line_px).metrics("linespace")
        y, drawn = S(10), False

        def gap():
            nonlocal y
            if drawn:
                y += S(7)

        def line(dot_colour, runs):
            nonlocal y, drawn
            gap()
            d = S(6)
            top = y + (line_h - d) / 2
            c.create_oval(px, top, px + d, top + d, fill=dot_colour, outline=dot_colour)
            self._runs(px + d + S(6), y, runs, right, line_px)
            y += line_h
            drawn = True

        if "kills" in want:
            big = self._font("light", S(44))
            has = m.get("kills") is not None and m.get("stacks")
            number = cr(m["kills"]) if has else "—"
            c.create_text(px - S(2), y, text=number, font=big, fill=LABEL if has else label3, anchor="nw")
            num_h = big.metrics("ascent") + big.metrics("descent") // 2
            if has:
                head = "kills to go"
                sub = (st or {}).get("name", "") + (f" · {m['stacks']} stacks" if m["stacks"] > 1 else "")
            else:
                head, sub = "No stacks", "No massacre missions held"
            bx = px + big.measure(number) + S(8)
            f13, f11 = self._font("bold", S(13)), self._font("regular", S(11.5))
            top = y + num_h - f13.metrics("linespace") - f11.metrics("linespace")
            c.create_text(bx, top, text=self._fit(head, f13, right - bx), font=f13, fill=LABEL, anchor="nw")
            c.create_text(bx, top + f13.metrics("linespace"), text=self._fit(sub, f11, right - bx),
                          font=f11, fill=label2, anchor="nw")
            y += num_h + S(2)
            drawn = True

        if "progress" in want and st and st.get("total"):
            gap()
            t = S(5)
            self._round_rect(px, y, right, y + t, t / 2, mix("#ffffff", panel, .07))
            share = min(1, st["done"] / st["total"])
            if share > 0:
                self._round_rect(px, y, px + max(t, (right - px) * share), y + t, t / 2, accent)
            y += t + S(4)
            self._runs(px, y, [(f"{cr(st['done'])} of {cr(st['total'])}" + (" · held" if st.get("held") else ""),
                                False, label2)], right, line_px)
            y += line_h
            drawn = True

        if "payout" in want and st and st.get("next_payout"):
            p = st["next_payout"]
            line(label3, [("Next payout in ", False, label2), (cr(p["kills"]), True, LABEL),
                          (f" · {plural(p['missions'], 'mission')} · {short(p['reward'])} Cr", False, label2)])

        t = m.get("target")
        if "target" in want and t:
            ship, v = t.get("ship") or "Target", t.get("verdict")
            if v == "counts":
                line(GREEN, [(ship, True, LABEL), (" counts" + (f" for {plural(t['missions'], 'mission')}"
                                                              if t.get("missions") else ""), False, label2)])
            elif v == "wrong_system":
                line(AMBER, [(ship, True, AMBER), (": right faction, wrong system", False, AMBER)])
            elif v == "clean":
                line(RED, [(ship, True, RED), (" is clean: attacking it is a crime", False, RED)])
            elif v == "unscanned":
                line(label3, [(ship, True, LABEL), (": scan it to see its faction", False, label2)])
            elif v == "other":
                line(label3, [(ship, True, LABEL), (" doesn't count", False, label2)])

        legal = m.get("legal")
        if "wanted" in want and legal:
            if legal.get("wanted"):
                owed = f" · {cr(legal['bounty'])} Cr" if legal.get("bounty") else ""
                line(RED, [("Wanted", True, RED), (f" in {legal.get('system')}{owed}", False, RED)])
            else:
                owed = f" · {cr(legal['fines'])} Cr" if legal.get("fines") else ""
                line(AMBER, [("Fine", True, AMBER), (f" owed in {legal.get('system')}{owed}", False, AMBER)])

        session, slots = m.get("session") or {}, m.get("slots")
        left = ([("This session ", False, label2), (f"{short(session['per_hour'])} Cr/h", True, LABEL)]
                if "session" in want and session.get("per_hour") else None)
        tail = ([("Missions ", False, label2), (f"{slots['used']}/{slots['cap']}", True, LABEL)]
                if "slots" in want and slots else None)
        if left or tail:
            gap()
            if left:
                self._runs(px, y, left, right, line_px)
            if tail:
                wd = sum(self._font("bold" if b else "regular", line_px).measure(tx) for tx, b, _ in tail)
                self._runs(right - wd, y, tail, right + 1, line_px)
            y += line_h
            drawn = True

        if not drawn:
            self._runs(px, y, [("Pick what to show under Settings.", False, label2)], right, line_px)
            y += line_h
        H = round(y + S(12))

        # The panel behind it all: a hairline edge, then the ground.
        r = round(RADIUS * scale)
        self._round_rect(0, 0, W - 1, H - 1, r, mix("#ffffff", panel, .09), "panel")
        self._round_rect(1, 1, W - 2, H - 2, r - 1, panel, "panel")
        c.tag_lower("panel")
        c.config(width=W, height=H)
        return W, H
