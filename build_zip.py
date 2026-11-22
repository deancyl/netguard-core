#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build rmg-netguard module zip (KSU module format: files at zip root).

Pure ASCII output, LF line endings preserved as-is (binary copy), no BOM.
"""
import hashlib
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "module")


def module_version():
    """Single source of truth: module/module.prop -> version=..."""
    with open(os.path.join(SRC, "module.prop"), "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("version="):
                return line.strip().split("=", 1)[1]
    raise SystemExit("version= not found in module/module.prop")


OUT = os.path.join(HERE, "rmg-netguard-%s.zip" % module_version())
OUT_SHA256 = OUT + ".sha256"


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    if os.path.exists(OUT):
        os.remove(OUT)
    if os.path.exists(OUT_SHA256):
        os.remove(OUT_SHA256)
    files = []
    for root, dirs, names in os.walk(SRC):
        dirs.sort()
        # Exclude runtime state directories (run/ is created on device, not shipped)
        dirs[:] = [d for d in dirs if d != "run"]
        for n in sorted(names):
            # Never ship editor/backup leftovers (e.g. *.bak-v2.1.0) into a
            # module zip: KernelSU installs everything at the zip root.
            if n.startswith(".") or ".bak" in n or n.endswith("~"):
                continue
            p = os.path.join(root, n)
            files.append(p)

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            arc = os.path.relpath(p, SRC).replace("\\", "/")
            zinfo = zipfile.ZipInfo.from_file(p, arc)
            zinfo.create_system = 3  # Unix
            if arc.endswith(".sh"):
                zinfo.external_attr = 0o100755 << 16
            else:
                zinfo.external_attr = 0o100644 << 16
            with open(p, "rb") as f:
                z.writestr(zinfo, f.read(), compress_type=zipfile.ZIP_DEFLATED)

    with zipfile.ZipFile(OUT) as z:
        bad = z.testzip()
        if bad:
            print("CORRUPT ENTRY: " + bad)
            sys.exit(1)
        names = z.namelist()

    # sanity: module.prop at zip root, LF check on scripts
    assert "module.prop" in names, "module.prop missing at zip root"
    for p in files:
        data = open(p, "rb").read()
        assert b"\r\n" not in data, "CRLF found in " + p
        assert not data.startswith(b"\xef\xbb\xbf"), "BOM found in " + p

    size = os.path.getsize(OUT)
    zip_sha256 = sha256(OUT)

    with open(OUT_SHA256, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"{zip_sha256}  {os.path.basename(OUT)}\n")

    print("zip: " + OUT)
    print("md5: " + md5(OUT))
    print("sha256: " + zip_sha256)
    print("size: %d bytes, %d entries" % (size, len(names)))
    for n in names:
        print("  " + n)


if __name__ == "__main__":
    main()
