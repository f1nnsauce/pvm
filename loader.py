#!/usr/bin/env python3
import sys, os
from pathlib import Path
from urllib.request import urlopen

BASE_DIR = Path.home() / ".local/share/pvm"
VERSION = BASE_DIR / "version.txt"
CORE = BASE_DIR / "core.py"
LOADER_VERSION = BASE_DIR / "pvm-version-loader.txt"

VERSION_URL = "https://raw.githubusercontent.com/f1nnsauce/pvm/refs/heads/main/version.txt"
CORE_URL = "https://raw.githubusercontent.com/f1nnsauce/pvm/refs/heads/main/core.py"
LOADER_VERSION_URL = "https://raw.githubusercontent.com/f1nnsauce/pvm/refs/heads/main/pvm-version-loader.txt"

BASE_DIR.mkdir(parents=True, exist_ok=True)

def fetch(url: str) -> str:
    with urlopen(url) as r:
        return r.read().decode("utf-8")

if len(sys.argv) == 1:
    print("expected argument")
    sys.exit(0)

arg = sys.argv[1]
arg2 = None
if len(sys.argv) == 3:
    arg2 = sys.argv[2]

if arg == "--help":
    print("Use 'pvm file_path.pvm' to execute a file.")
    sys.exit(0)

elif arg == "--version":
    print(f"pvm v.{VERSION.read_text().strip()}")
    sys.exit(0)

elif arg == "--update":
    if VERSION.read_text() == fetch(VERSION_URL) and not arg2 and not arg2 == "--bypass-v-check":
        print("Your PVM is up to date.")
        sys.exit(0)
    print("Updating PVM...")
    VERSION.write_text(fetch(VERSION_URL))
    print("Core updated, finishing up...")
    CORE.write_text(fetch(CORE_URL))
    print(f"Update complete. Updated to {fetch(VERSION_URL)}")
    sys.exit(0)

#updating the loader is the minimal file's job
elif arg == "--update-loader":
    if LOADER_VERSION.read_text() == fetch(LOADER_VERSION_URL) and not arg2 and not arg2 == "--bypass-v-check":
        print("Your PVM loader is up to date.")
        sys.exit(0)
    os.execv(
        sys.executable,
        [
            sys.executable,
            str(Path("/usr/local/bin/pvm")),
            "update"
        ]
    )


exec(CORE.read_text(), {"__name__": "__main__"})
