#!/usr/bin/env python3
"""Verify the built module zip matches the repo tree exactly."""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "module")


def module_version():
    """Same single source of truth as build_zip.py (no hardcoded version)."""
    with open(os.path.join(SRC, "module.prop"), "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("version="):
                return line.strip().split("=", 1)[1]
    raise SystemExit("version= not found in module/module.prop")


OUT = os.path.join(HERE, "rmg-netguard-%s.zip" % module_version())

EXPECTED_CORE_FILES = {
    "module.prop",
    "service.sh",
    "uninstall.sh",
    "action.sh",
    "customize.sh",
    "hotinstall.sh",
    "scripts/netguard.sh",
    "scripts/on_agh.sh",
    "webroot/index.html",
}

z = zipfile.ZipFile(OUT)
infolist = z.infolist()
names = [i.filename for i in infolist]
mismatch = []

# Exclusivity assertion: strictly the 9 KernelSU-compliant module files
if set(names) != EXPECTED_CORE_FILES:
    mismatch.append(f"entries mismatch: got {set(names)}, expected {EXPECTED_CORE_FILES}")

for n in names:
    a = z.read(n)
    p = os.path.join(SRC, n.replace("/", os.sep))
    if not os.path.exists(p):
        mismatch.append(n + " (missing in tree)")
        continue
    if a != open(p, "rb").read():
        mismatch.append(n + " (content differs)")

print("entries:", len(names))
print("mismatches:", mismatch if mismatch else "none")
print("module.prop at zip root:", "module.prop" in names)
print("webroot/index.html present:", "webroot/index.html" in names)

bad = []
for info in infolist:
    n = info.filename
    data = z.read(n)
    if b"\r\n" in data:
        bad.append(n + " (CRLF)")
    if data.startswith(b"\xef\xbb\xbf"):
        bad.append(n + " (BOM)")
    if ".bak" in n or n.endswith("~"):
        bad.append(n + " (backup file leaked)")

    # Permission checks (POSIX)
    mode = (info.external_attr >> 16) & 0o777
    if n.endswith(".sh"):
        if mode != 0o755:
            bad.append(f"{n} (invalid mode: {oct(mode)}, expected 0o755)")
    else:
        if mode != 0o644:
            bad.append(f"{n} (invalid mode: {oct(mode)}, expected 0o644)")

print("hygiene issues:", bad if bad else "none")

sys.exit(1 if (mismatch or bad) else 0)
