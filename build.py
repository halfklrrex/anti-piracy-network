"""Build "Imperial Anti-Piracy Network.exe": one file that runs without Python.

    python -m pip install pyinstaller
    python build.py

The .exe lands in dist/. It carries dashboard.html, the Saira font and the
emblem inside it; a config.json, offsets.json or emblem of your own goes
beside the .exe and takes precedence.
"""
import glob
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = "Imperial Anti-Piracy Network"


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
    png_to_ico(HERE / "emblem.png", icon)
    subprocess.run([
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--windowed", "--noconfirm", "--clean",
        "--name", NAME,
        "--icon", str(icon),
        "--distpath", str(HERE / "dist"),
        "--workpath", str(work / "build"),
        "--specpath", str(work),
        *data(HERE / "dashboard.html", "."),
        *data(HERE / "emblem.png", "."),
        # File by file: an escaped folder pattern nests as fonts/fonts/.
        *data(HERE / "fonts" / "saira.woff2", "fonts"),
        *data(HERE / "fonts" / "OFL.txt", "fonts"),
        str(HERE / "stacker.py"),
    ], check=True)
    print(f"\nBuilt dist\\{NAME}.exe")


if __name__ == "__main__":
    main()
