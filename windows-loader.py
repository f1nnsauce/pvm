#!/usr/bin/env python3
import sys, os
from pathlib import Path
from urllib.request import urlopen

# Use Windows-friendly path in LOCALAPPDATA
BASE_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "pvm"
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

# Argument parsing
if len(sys.argv) == 1:
    print("Expected argument. Use --help for usage information.")
    sys.exit(0)

arg = sys.argv[1]
arg2 = sys.argv[2] if len(sys.argv) > 2 else None

if arg == "--help":
    print(
        "Usage:\n"
        "  pvm file_path.pvm           Execute a PVM file\n"
        "Options:\n"
        "  --update                    Update the core\n"
        "  --update-loader             Update the loader\n"
        "  --mem-size <size>           Run a program with custom memory (default 256)\n"
        "  --regs <number>             Run a program with custom registers (default 200)\n"
        "  --bypass-v-check            Bypass version check for updates\n"
        "  --version                   Show PVM version"
    )
    sys.exit(0)

elif arg == "--version":
    if VERSION.exists():
        print(f"pvm v.{VERSION.read_text().strip()}")
    else:
        print("Version not installed.")
    sys.exit(0)

elif arg == "--update":
    if VERSION.exists() and VERSION.read_text() == fetch(VERSION_URL) and arg2 != "--bypass-v-check":
        print("Your PVM is up to date.")
        sys.exit(0)
    print("Updating PVM core...")
    VERSION.write_text(fetch(VERSION_URL))
    CORE.write_text(fetch(CORE_URL))
    print(f"Update complete. Updated to {fetch(VERSION_URL)}")
    sys.exit(0)

elif arg == "--update-loader":
    if LOADER_VERSION.exists() and LOADER_VERSION.read_text() == fetch(LOADER_VERSION_URL) and arg2 != "--bypass-v-check":
        print("Your PVM loader is up to date.")
        sys.exit(0)
    # Relaunch the main installer to update the loader
    os.execv(
        sys.executable,
        [
            sys.executable,
            str(Path(__file__)),
            "--update"
        ]
    )

# Execute core
if CORE.exists():
    exec(CORE.read_text(), {"__name__": "__main__"})
else:
    print("Core not found. Run `pvm --update` to download it first.")
