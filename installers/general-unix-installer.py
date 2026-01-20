#!/usr/bin/env python3
import urllib.request
import os
import stat

URL = "https://raw.githubusercontent.com/f1nnsauce/pvm-bootstrapper/refs/heads/master/pvm-wrapper.py"
DEST = "/usr/local/bin/pvm"

def fetch(url: str) -> str:
    with urllib.request.urlopen(url) as response:
        return response.read().decode("utf-8")

data = fetch(URL)

with open(DEST, "w") as f:
    f.write(data)

st = os.stat(DEST)
os.chmod(DEST, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
