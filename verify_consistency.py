#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RMG NetGuard v3.1 Consistency & Architecture Invariant Gate.

Validates:
  1. Version Single Source of Truth (module/module.prop -> all docs, metadata, UI);
  2. Architecture Invariant (strict 6-file module exclusivity, redundant scripts deleted);
  3. Minimal Principle Violations (no kill -HUP, no active UDP probes, no setInterval, 0 shell daemons);
  4. Core Required Features (-o tun+ kernel bypass, inotifyd agh circuit breaker, reversible Clash integration).

Exit 0 = all green, 1 = invariant violated.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def read(rel):
    with open(os.path.join(HERE, rel), "r", encoding="utf-8") as f:
        return f.read()


def exists(rel):
    return os.path.exists(os.path.join(HERE, rel))


def version():
    for line in read("module/module.prop").splitlines():
        if line.startswith("version="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("FATAL: version= missing in module/module.prop")


V = version()
fails = []
passes = []


def check(name, ok, detail=""):
    (passes if ok else fails).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + ((" -> " + detail) if detail and not ok else ""))


# ---- 1. Version Single Source of Truth -------------------------------------
prop = read("module/module.prop")
check("module.prop version present", bool(V), V)
check("module.prop description starts with version",
      ("description=NetGuard-Core" in prop or "description=NetGuard" in prop or "description=RMG NetGuard" in prop) and V in prop)
vc = [l.split("=", 1)[1].strip() for l in prop.splitlines()
      if l.startswith("versionCode=")]
check("module.prop versionCode present", bool(vc and vc[0].isdigit()), vc[0] if vc else "missing")

check("index.html static fallback version",
      ('id="ui_ver">' + V + "<") in read("module/webroot/index.html"))

try:
    pkg = json.loads(read("package.json"))
    check("package.json version", pkg.get("version") == V.lstrip("v"),
          "got %s, want %s" % (pkg.get("version"), V.lstrip("v")))
except Exception as e:
    check("package.json version", False, str(e))

check("CHANGELOG contains current version", ("## " + V) in read("CHANGELOG.md"))
check("README version section",
      ("当前主线版本：`" + V + "`" in read("README.md") or "当前主线版本**：`" + V + "`" in read("README.md")))
check("wiki/Home mainline version", ("主线版本：`" + V + "`") in read("wiki/Home.md"))

for rel in ("build_zip.py", "verify_zip.py"):
    body = read(rel)
    check(rel + " reads module.prop", "module.prop" in body and "module_version()" in body)
    check(rel + " has no hardcoded zip version",
          ("rmg-netguard-" + V + ".zip") not in body and 'OUT = os.path.join(HERE, "rmg-netguard-v2.' not in body)

# ---- 2. v3.1.1 Architecture Invariant: Redundant scripts MUST NOT exist ---
OLD_SCRIPTS = [
    "module/scripts/env.sh",
    "module/scripts/guard.sh",
    "module/scripts/controller.sh",
    "module/scripts/config_toggle.sh",
    "module/scripts/probe.sh",
    "module/scripts/rescue.sh",
    "module/scripts/rules_audit.sh",
    "module/scripts/webui.sh",
]
for s in OLD_SCRIPTS:
    check("redundant script deleted: " + s, not exists(s), "file still exists!")

# ---- 3. v3.1.1 Core Files MUST exist (including KernelSU spec scripts) ----
CORE_FILES = [
    "module/module.prop",
    "module/service.sh",
    "module/uninstall.sh",
    "module/action.sh",
    "module/customize.sh",
    "module/hotinstall.sh",
    "module/scripts/on_agh.sh",
    "module/scripts/netguard.sh",
    "module/webroot/index.html",
]
for cf in CORE_FILES:
    check("core file present: " + cf, exists(cf), "missing core file")

# ---- 4. Statements that must NOT exist (Minimal principle violations) -----
FORBIDDEN = {
    "module/scripts/netguard.sh": [
        "kill -HUP",
        "kill -1 ",
        "AdGuardHome.yaml",
        "/dev/udp",
        "curl ",
        "ip monitor link",
    ],
    "module/webroot/index.html": [
        "setInterval",           # 0 background timers
        "webui.sh",              # no legacy controller calls
        "controller.sh",
        "window.confirm",
    ],
    "README.md": [
        "默认只观测、不修改网络",
        "当前版本：`v2.",
    ],
}
for rel, needles in FORBIDDEN.items():
    if not exists(rel):
        continue
    body = read(rel)
    for n in needles:
        check("no forbidden logic in " + rel + ": " + n[:28], n not in body, "found forbidden logic")

# ---- 5. Required statements (Core guarantees) ------------------------------
REQUIRED = {
    "module/scripts/netguard.sh": [
        "-o tun+ -j RETURN",
        "ensure_tun_bypass",
        "do_detach",
        "do_attach",
        "patch_clash",
        "sync_all",
        "IP-CIDR,0.0.0.0/32,REJECT",
        "GEOIP,CN,DIRECT",
    ],
    "module/scripts/on_agh.sh": [
        "agh.pid",
        "on_agh_change",
    ],
    "module/service.sh": [
        "inotifyd",
        "on_agh.sh",
        "sync_rules",
    ],
    "module/uninstall.sh": [
        "on_agh.sh",
        "ADGUARD_REDIRECT_DNS",
        ".yaml.orig",
    ],
    "module/action.sh": [
        "sync_rules",
        "netguard.sh",
    ],
    "module/customize.sh": [
        "MODULE_HOT_INSTALL_REQUEST=true",
        "MODULE_HOT_RUN_SCRIPT=hotinstall.sh",
    ],
    "module/hotinstall.sh": [
        "service.sh",
        "disable",
    ],
    "module/webroot/index.html": [
        "ui_ver",
        "netguard.sh",
        "status",
    ],
}
for rel, needles in REQUIRED.items():
    if not exists(rel):
        continue
    body = read(rel)
    for n in needles:
        check("required feature in " + rel + ": " + n[:28], n in body, "required feature missing")

print("\nversion=%s  passed=%d  failed=%d" % (V, len(passes), len(fails)))
if fails:
    print("Consistency gate FAILED. Fix the items above before pushing.")
    sys.exit(1)
print("Consistency gate OK.")
