"""Build "Anti-Piracy-Network.exe": one file that runs without Python.

    python -m pip install pyinstaller pywebview
    python build.py

pywebview gives the .exe the app's own window (appwindow.py); built without
it, the .exe opens the dashboard in an Edge app window instead.

The .exe lands in dist/. It carries dashboard.html, the Saira font and every
style's emblem inside it; your own settings, corrections and emblem live in an
"Anti-Piracy Network" folder beside your journals. Its icon is the Interstellar
(no-style) emblem.
"""
import glob
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = "Anti-Piracy-Network"      # hyphenated: GitHub turns spaces in release files into dots


def png_to_ico(png, ico):
    """Windows icons can hold a PNG as-is (Vista onward), so no imaging library
    is needed: a 6-byte header, one 16-byte directory entry, then the PNG."""
    data = png.read_bytes()
    width, height = struct.unpack(">II", data[16:24])        # from the IHDR chunk
    entry = struct.pack("<BBBBHHII", width % 256, height % 256, 0, 0, 1, 32, len(data), 6 + 16)
    ico.write_bytes(struct.pack("<HHH", 0, 1, 1) + entry + data)


def data(source, target):
    # PyInstaller reads the source as a glob pattern, and folder names like
    # "[iCloud Directory]" are character classes to glob, so escape them.
    return ["--add-data", f"{glob.escape(str(source))}{os.pathsep}{target}"]


def main():
    # Build scratch goes to a temporary folder, not beside the source (which
    # may be a synced folder that would upload every intermediate file).
    work = Path(tempfile.mkdtemp(prefix="iapn-build-"))
    icon = work / "emblem.ico"
    mark = HERE / "styles" / "interstellar.png"
    png_to_ico(mark if mark.is_file() else HERE / "styles" / "ald.png", icon)
    subprocess.run([
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--windowed", "--noconfirm", "--clean",
        "--name", NAME,
        "--icon", str(icon),
        "--distpath", str(HERE / "dist"),
        "--workpath", str(work / "build"),
        "--specpath", str(work),
        *data(HERE / "dashboard.html", "."),
        *[arg for png in sorted((HERE / "styles").glob("*.png")) for arg in data(png, "styles")],
        # Arissa's emblem, if a synced folder has moved it back to the top level.
        *(data(HERE / "emblem.png", ".") if (HERE / "emblem.png").is_file() else []),
        # File by file: an escaped folder pattern nests as fonts/fonts/.
        *data(HERE / "fonts" / "saira.woff2", "fonts"),
        # The mini window is drawn by Windows itself, which can't read WOFF2.
        *data(HERE / "fonts" / "saira.ttf", "fonts"),
        *data(HERE / "fonts" / "OFL.txt", "fonts"),
        str(HERE / "stacker.py"),
    ], check=True)
    print(f"\nBuilt dist\\{NAME}.exe")


if __name__ == "__main__":
    main()
