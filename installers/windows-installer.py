#!/usr/bin/env python3
import urllib.request
import os
import sys
import shutil

URL = "https://raw.githubusercontent.com/f1nnsauce/pvm-bootstrapper/refs/heads/master/windows-pvm-wrapper.py"

# Choose install location
BIN_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.getcwd()), "pvm")
DEST_PY = os.path.join(BIN_DIR, "pvm.py")
DEST_CMD = os.path.join(BIN_DIR, "pvm.cmd")

def fetch(url: str) -> str:
    with urllib.request.urlopen(url) as response:
        return response.read().decode("utf-8")

os.makedirs(BIN_DIR, exist_ok=True)

data = fetch(URL)

with open(DEST_PY, "w", encoding="utf-8") as f:
    f.write(data)

# Create a command shim so `pvm` works like an executable
with open(DEST_CMD, "w", encoding="utf-8") as f:
    f.write(f"""@echo off
py "{DEST_PY}" %*
""")

print("Installed pvm to:", BIN_DIR)
print("Add this directory to your PATH to use `pvm` globally.")
print("PATH example:")
print(f'  setx PATH "%PATH%;{BIN_DIR}"')
