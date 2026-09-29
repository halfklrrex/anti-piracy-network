"""The app's own window: the dashboard in a frameless WebView2 window, whose
title bar is the dashboard's toolbar, with the red, yellow and green buttons at
its left, as on a Mac.

It needs pywebview (`pip install pywebview`; the .exe carries it) and Windows'
WebView2, which every copy of Windows 11 has. Without either, `run()` returns
False and the app opens the Edge app window it always has.

A frameless window loses what Windows' own title bar does, so this puts it
back: resizing from every edge (the resize border, minus the strip Windows
would reserve at the top for a title bar the window doesn't have), minimizing
from the taskbar, and dragging and top-edge resizing, which Python does by
following the mouse while its button is down (the page can't hand the press to
Windows: WebView2 holds the mouse in a process of its own). Its size, place and
whether it's maximized are remembered between runs.
"""
from __future__ import annotations

import os
import struct
import threading
import time
from pathlib import Path

try:
    import webview
    AVAILABLE = os.name == "nt"
except ImportError:                      # running from source without pywebview
    webview = None
    AVAILABLE = False

MIN_SIZE = (900, 600)
GROUND = "#0b0a0f"                       # shown before the page paints, instead of white

if AVAILABLE:
    import ctypes
    from ctypes import wintypes as wt

    user32 = ctypes.WinDLL("user32")
    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
    user32.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_long]
    user32.GetWindowLongPtrW.restype = ctypes.c_void_p
    user32.GetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
    user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    user32.SetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_void_p]
    user32.CallWindowProcW.restype = LRESULT
    user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
    user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
    user32.GetAsyncKeyState.restype = ctypes.c_short
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.IsZoomed.argtypes = [wt.HWND]
    user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
    user32.GetDpiForWindow.argtypes = [wt.HWND]
    user32.GetSystemMetricsForDpi.argtypes = [ctypes.c_int, wt.UINT]

    class NCCALCSIZE_PARAMS(ctypes.Structure):
        _fields_ = [("rgrc", wt.RECT * 3), ("lppos", ctypes.c_void_p)]

    class WINDOWPLACEMENT(ctypes.Structure):
        _fields_ = [("length", wt.UINT), ("flags", wt.UINT), ("showCmd", wt.UINT),
                    ("ptMinPosition", wt.POINT), ("ptMaxPosition", wt.POINT), ("rcNormalPosition", wt.RECT)]

    user32.GetWindowPlacement.argtypes = [wt.HWND, ctypes.POINTER(WINDOWPLACEMENT)]
    user32.SetWindowPlacement.argtypes = [wt.HWND, ctypes.POINTER(WINDOWPLACEMENT)]

GWL_STYLE, GWLP_WNDPROC = -16, -4
WS_THICKFRAME, WS_MINIMIZEBOX, WS_MAXIMIZEBOX = 0x00040000, 0x00020000, 0x00010000
WM_NCCALCSIZE = 0x0083
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE, SWP_FRAMECHANGED = 0x1, 0x2, 0x4, 0x10, 0x20
SW_MAXIMIZE, SW_RESTORE, SW_SHOWNORMAL = 3, 9, 1
VK_LBUTTON, SM_CYFRAME, SM_CXPADDEDBORDER = 0x01, 33, 92


def png_to_ico(png, ico):
    """A Windows icon holding a PNG as-is (as build.py makes the .exe's)."""
    data = Path(png).read_bytes()
    width, height = struct.unpack(">II", data[16:24])
    entry = struct.pack("<BBBBHHII", width % 256, height % 256, 0, 0, 1, 32, len(data), 6 + 16)
    Path(ico).write_bytes(struct.pack("<HHH", 0, 1, 1) + entry + data)


class Api:
    """What the page's own title bar asks of the window (window.pywebview.api)."""

    def __init__(self, win):
        self._win = win

    def close(self):
        self._win.window.destroy()

    def minimize(self):
        self._win.window.minimize()

    def zoom(self):
        user32.ShowWindow(self._win.hwnd, SW_RESTORE if user32.IsZoomed(self._win.hwnd) else SW_MAXIMIZE)

    def drag(self):
        self._win.follow_mouse("move")

    def resize_top(self):
        self._win.follow_mouse("top")


class AppWindow:
    def __init__(self, url, title, placement=None, save_placement=None, icon_png=None, data_dir=None):
        self.url, self.title = url, title
        self.placement = placement               # {"show", "rect": [l, t, r, b]} from the last run, or None
        self.save_placement = save_placement     # called with the same when the window closes
        self.icon_png, self.data_dir = icon_png, Path(data_dir) if data_dir else None
        self.window, self.hwnd, self._proc = None, None, None
        self._following = threading.Lock()

    # -- running ---------------------------------------------------------------

    def run(self):
        """Open the window and return when it's closed: True. False when it
        couldn't open at all (no WebView2), so the app can fall back."""
        webview.settings["ALLOW_DOWNLOADS"] = True           # Save PNG on the export sheet
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        self.window = webview.create_window(
            self.title, self.url, js_api=Api(self), frameless=True, easy_drag=False,
            width=1440, height=900, min_size=MIN_SIZE, background_color=GROUND, text_select=True)
        self.window.events.before_show += self._before_show
        self.window.events.closing += self._closing
        icon = None
        if self.icon_png and self.data_dir and Path(self.icon_png).is_file():
            try:
                self.data_dir.mkdir(parents=True, exist_ok=True)
                icon = str(self.data_dir / "app.ico")
                png_to_ico(self.icon_png, icon)
            except OSError:
                icon = None
        storage = str(self.data_dir / "webview") if self.data_dir else None
        try:
            webview.start(gui="edgechromium", private_mode=False, storage_path=storage, icon=icon)
        except Exception:
            return False
        return self.hwnd is not None

    def _before_show(self, window):
        self.hwnd = wt.HWND(window.native.Handle.ToInt64())
        self._frame()
        if self.placement:
            self._restore_placement()

    def _closing(self, window):
        if self.save_placement and self.hwnd:
            wp = WINDOWPLACEMENT(length=ctypes.sizeof(WINDOWPLACEMENT))
            if user32.GetWindowPlacement(self.hwnd, ctypes.byref(wp)):
                r = wp.rcNormalPosition
                self.save_placement({"maximized": bool(user32.IsZoomed(self.hwnd)),
                                     "rect": [r.left, r.top, r.right, r.bottom]})

    def _restore_placement(self):
        rect = self.placement.get("rect") or []
        if len(rect) != 4 or rect[2] - rect[0] < MIN_SIZE[0] // 2 or rect[3] - rect[1] < MIN_SIZE[1] // 2:
            return
        wp = WINDOWPLACEMENT(length=ctypes.sizeof(WINDOWPLACEMENT))
        user32.GetWindowPlacement(self.hwnd, ctypes.byref(wp))
        wp.rcNormalPosition = wt.RECT(*rect)
        wp.showCmd = SW_MAXIMIZE if self.placement.get("maximized") else SW_SHOWNORMAL
        user32.SetWindowPlacement(self.hwnd, ctypes.byref(wp))   # Windows keeps it on a screen that exists

    # -- the frame -------------------------------------------------------------

    def _frame(self):
        """Resize borders and the taskbar's minimize back, and no strip at the
        top: Windows would otherwise draw one for the title bar the window
        doesn't have. When maximized, the top keeps the border's depth, or the
        toolbar would sit partly above the screen."""
        hwnd = self.hwnd
        old = user32.GetWindowLongPtrW(hwnd, GWLP_WNDPROC)

        def proc(hw, msg, wparam, lparam):
            if msg == WM_NCCALCSIZE and wparam:
                params = ctypes.cast(lparam, ctypes.POINTER(NCCALCSIZE_PARAMS)).contents
                top = params.rgrc[0].top
                result = user32.CallWindowProcW(old, hw, msg, wparam, lparam)
                if user32.IsZoomed(hw):
                    dpi = user32.GetDpiForWindow(hw) or 96
                    top += user32.GetSystemMetricsForDpi(SM_CYFRAME, dpi) + \
                        user32.GetSystemMetricsForDpi(SM_CXPADDEDBORDER, dpi)
                params.rgrc[0].top = top
                return result
            return user32.CallWindowProcW(old, hw, msg, wparam, lparam)

        self._proc = WNDPROC(proc)                                  # kept alive with the window
        user32.SetWindowLongPtrW(hwnd, GWLP_WNDPROC, ctypes.cast(self._proc, ctypes.c_void_p))
        style = user32.GetWindowLongW(hwnd, GWL_STYLE)
        user32.SetWindowLongW(hwnd, GWL_STYLE, style | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                            SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)

    # -- dragging and top-edge resizing ------------------------------------------

    def follow_mouse(self, how):
        """Move the window ("move"), or its top edge ("top"), with the mouse
        until the button is let go."""
        if not self._following.acquire(blocking=False):
            return                                                   # already following
        try:
            hwnd = self.hwnd
            start, rect = wt.POINT(), wt.RECT()
            user32.GetCursorPos(ctypes.byref(start))
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            moved = False
            while user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000:
                now = wt.POINT()
                user32.GetCursorPos(ctypes.byref(now))
                dx, dy = now.x - start.x, now.y - start.y
                if not moved and abs(dx) < 3 and abs(dy) < 3:
                    time.sleep(0.008)
                    continue                                         # a click, not a drag, so far
                moved = True
                if how == "move" and user32.IsZoomed(hwnd):
                    # Dragging a maximized window restores it under the pointer:
                    # the same share of its width to the pointer's left, and the
                    # same distance from its top.
                    share = (start.x - rect.left) / max(1, rect.right - rect.left)
                    below_top = max(0, start.y - rect.top)
                    user32.ShowWindow(hwnd, SW_RESTORE)
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    left = now.x - round((rect.right - rect.left) * share)
                    user32.SetWindowPos(hwnd, None, left, now.y - below_top, 0, 0,
                                        SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    start = now
                    continue
                if how == "move":
                    user32.SetWindowPos(hwnd, None, rect.left + dx, rect.top + dy, 0, 0,
                                        SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
                else:
                    dpi = user32.GetDpiForWindow(hwnd) or 96
                    lowest = rect.bottom - round(MIN_SIZE[1] * dpi / 96)
                    top = min(rect.top + dy, lowest)
                    user32.SetWindowPos(hwnd, None, rect.left, top, rect.right - rect.left, rect.bottom - top,
                                        SWP_NOZORDER | SWP_NOACTIVATE)
                time.sleep(0.008)
        finally:
            self._following.release()
