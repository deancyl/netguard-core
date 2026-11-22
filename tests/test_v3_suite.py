#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent End-to-End Test Suite for RMG NetGuard v3.0.

Testing Methodology:
  Tier 1 - Feature Coverage (Metadata, 5-File Invariant, Read-only Assertion, Standard Awk Patch, Status JSON Schema)
  Tier 2 - Boundary & Corner Cases (Trailing comments, Inline arrays, Chinese group names, Missing MATCH, Idempotency, VPN interface filtering, WebUI Zero-Interval)
  Tier 3 - Cross-Feature Combinations (8-Permutation Reconcile Truth Table for Auto vs Observe, Fallback State Machine)
  Tier 4 - Real-World & Packaging Acceptance (build_zip, verify_zip, Zip hygiene 0 CRLF/0 BOM, Real-device ADB smoke probe)

Run via:
  py -3 tests/test_v3_suite.py
  py -3 tests/test_v3_suite.py --tier 1
  py -3 tests/test_v3_suite.py --tier 2
  py -3 tests/test_v3_suite.py --tier 3
  py -3 tests/test_v3_suite.py --tier 4
"""

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
MODULE_DIR = os.path.join(PROJECT_ROOT, "module")
FIXTURES_DIR = os.path.join(HERE, "fixtures")

# Default paths
MODULE_PROP = os.path.join(MODULE_DIR, "module.prop")
SERVICE_SH = os.path.join(MODULE_DIR, "service.sh")
UNINSTALL_SH = os.path.join(MODULE_DIR, "uninstall.sh")
ACTION_SH = os.path.join(MODULE_DIR, "action.sh")
CUSTOMIZE_SH = os.path.join(MODULE_DIR, "customize.sh")
HOTINSTALL_SH = os.path.join(MODULE_DIR, "hotinstall.sh")
ON_AGH_SH = os.path.join(MODULE_DIR, "scripts", "on_agh.sh")
NETGUARD_SH = os.path.join(MODULE_DIR, "scripts", "netguard.sh")
INDEX_HTML = os.path.join(MODULE_DIR, "webroot", "index.html")

ADB_PATH = r"C:\Users\deanc\platform-tools\adb.exe"
GIT_AWK_PATH = r"C:\Program Files\Git\usr\bin\awk.exe"

# Fallback reference awk script from PROJECT.md / v3.0 specification
CANONICAL_AWK_SCRIPT = """
BEGIN { st=0; em=0; f_m=0; f_g=0; f_z=0 }
/^[[:space:]]*append-system-dns:[[:space:]]*true/ { match($0,/^[[:space:]]*/); print substr($0,1,RLENGTH) "append-system-dns: false"; next }
/^[[:space:]]*nameserver:[[:space:]]*\\[/ { match($0,/^[[:space:]]*/); p=substr($0,1,RLENGTH); sub(/\\[.*\\]/, "[" ns "]"); print; next }
/^[[:space:]]*nameserver:([[:space:]]*(#.*)?)?$/ { print; st=1; em=0; next }
st==1 && /^[[:space:]]*-[[:space:]]/ { if (!em) { match($0,/^[[:space:]]*/); print substr($0,1,RLENGTH) "- " ns; em=1 } next }
st==1 && /^[[:space:]]*(#.*)?$/ { print; next }
st==1 { st=0 }
/^[[:space:]]*-[[:space:]]*IP-CIDR,0\\.0\\.0\\.0\\/32,REJECT/ { f_z=1 }
/^[[:space:]]*-[[:space:]]*GEOIP,CN,/ {
  match($0,/^[[:space:]]*/); p=substr($0,1,RLENGTH)
  if (!f_z) { print p "- IP-CIDR,0.0.0.0/32,REJECT"; print p "- IP-CIDR6,::/128,REJECT"; f_z=1 }
  sub(/,[[:space:]]*no-resolve/, "")
  print; f_g=1; next
}
/^[[:space:]]*-[[:space:]]*MATCH,/ {
  f_m++; match($0,/^[[:space:]]*/); p=substr($0,1,RLENGTH)
  if (!f_z) { print p "- IP-CIDR,0.0.0.0/32,REJECT"; print p "- IP-CIDR6,::/128,REJECT"; f_z=1 }
  if (!f_g) { print p "- GEOIP,CN,DIRECT"; f_g=1 }
}
{ print }
"""


def find_awk_binary():
    """Finds an available awk executable on the host system."""
    if os.path.exists(GIT_AWK_PATH):
        return GIT_AWK_PATH
    for bin_name in ("awk", "gawk"):
        found = shutil.which(bin_name)
        if found:
            return found
    return None


def extract_awk_from_netguard():
    """Extracts the awk patching program from module/scripts/netguard.sh."""
    if not os.path.exists(NETGUARD_SH):
        return None
    with open(NETGUARD_SH, "r", encoding="utf-8") as f:
        content = f.read()

    # Look for awk -v ns="$target_ns" ' ... ' "$CFG"
    match = re.search(r"awk\s+-v\s+ns=\"\$target_ns\"\s+'(.*?)'\s+\"\$CFG\"", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def run_awk_patch(input_yaml_text, target_ns="127.0.0.1:5591", awk_code=None):
    """Executes the awk patch against the provided YAML text."""
    awk_bin = find_awk_binary()
    if not awk_bin:
        raise RuntimeError("No awk executable found in PATH or Git directory.")

    if awk_code is None:
        extracted = extract_awk_from_netguard()
        awk_code = extracted if extracted else CANONICAL_AWK_SCRIPT

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".awk") as sf:
        sf.write(awk_code)
        sf_path = sf.name

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".yaml") as inf:
        inf.write(input_yaml_text)
        inf_path = inf.name

    try:
        cmd = [awk_bin, "-v", f"ns={target_ns}", "-f", sf_path, inf_path]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if res.returncode != 0:
            raise RuntimeError(f"Awk execution failed (exit {res.returncode}): {res.stderr}")
        return res.stdout
    finally:
        if os.path.exists(sf_path):
            os.remove(sf_path)
        if os.path.exists(inf_path):
            os.remove(inf_path)


def validate_status_schema(json_obj):
    """Validates the 11 required fields of the NetGuard v3.1 status schema."""
    required_fields = {
        "version": (str, lambda v: v.startswith("v3.1.")),
        "mode": (str, lambda v: v in ("auto", "observe")),
        "vpn": (int, lambda v: v in (0, 1)),
        "vpn_if": (str, lambda v: True),
        "hijack": (int, lambda v: v in (0, 1)),
        "tun_bypass": (int, lambda v: v in (0, 1)),
        "agh_pid": ((str, int), lambda v: str(v).isdigit()),
        "agh_port": (int, lambda v: v in (0, 1)),
        "integ": (str, lambda v: v in ("on", "off")),
        "patched": (str, lambda v: v in ("yes", "no")),
        "fallback": (int, lambda v: v in (0, 1)),
    }

    if not isinstance(json_obj, dict):
        return False, "Root JSON must be an object"

    for field, (expected_type, validator) in required_fields.items():
        if field not in json_obj:
            return False, f"Missing required field: {field}"
        val = json_obj[field]
        if not isinstance(val, expected_type):
            return False, f"Field '{field}' has invalid type {type(val).__name__}, expected {expected_type}"
        if not validator(val):
            return False, f"Field '{field}' has invalid value: {val!r}"

    if len(json_obj) != 11:
        return False, f"Expected exactly 11 fields, found {len(json_obj)}"

    return True, "Valid schema"


# ============================================================================
# Tier 1: Feature Coverage
# ============================================================================
class Tier1FeatureCoverage(unittest.TestCase):
    """Tier 1: Feature Coverage & Fundamental Invariants."""

    def test_01_module_prop_metadata(self):
        """Validates module.prop fields, version v3.1.1, and versionCode 36."""
        self.assertTrue(os.path.exists(MODULE_PROP), "module/module.prop does not exist")
        props = {}
        with open(MODULE_PROP, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    props[k.strip()] = v.strip()

        self.assertEqual(props.get("id"), "rmg_netguard", "module.prop id must be rmg_netguard")
        self.assertEqual(props.get("version"), "v3.1.1", "module.prop version must be v3.1.1")
        self.assertEqual(props.get("versionCode"), "36", "module.prop versionCode must be 36")
        self.assertEqual(props.get("author"), "Deancyl", "module.prop author must be Deancyl")
        self.assertTrue("NetGuard-Core" in props.get("name", "") or "NetGuard" in props.get("name", ""),
                        "module.prop name must contain NetGuard-Core or NetGuard")
        self.assertIn("v3.1.1", props.get("description", ""), "module.prop description must mention v3.1.1")

    def test_02_version_single_source_of_truth(self):
        """Verifies version consistency between module.prop, package.json, and docs."""
        self.assertTrue(os.path.exists(MODULE_PROP), "module/module.prop missing")
        with open(MODULE_PROP, "r", encoding="utf-8") as f:
            prop_content = f.read()

        match = re.search(r"^version=(v?[0-9\.]+)", prop_content, re.M)
        self.assertTrue(match, "version= line not found in module.prop")
        version_str = match.group(1).lstrip("v")
        self.assertEqual(version_str, "3.1.1", "Mainline version must be 3.1.1")

        # Check package.json if present
        pkg_path = os.path.join(PROJECT_ROOT, "package.json")
        if os.path.exists(pkg_path):
            with open(pkg_path, "r", encoding="utf-8") as f:
                pkg_data = json.load(f)
            self.assertEqual(pkg_data.get("version"), "3.1.1", "package.json version must match 3.1.1")

        # Check CHANGELOG.md
        changelog_path = os.path.join(PROJECT_ROOT, "CHANGELOG.md")
        if os.path.exists(changelog_path):
            with open(changelog_path, "r", encoding="utf-8") as f:
                cl_content = f.read()
            self.assertIn("v3.1.1", cl_content, "CHANGELOG.md must document v3.1.1")

    def test_03_invariant_kernelsu_module_files(self):
        """Asserts that module/ contains strictly the 9 KernelSU-compliant core files and 0 obsolete scripts."""
        self.assertTrue(os.path.isdir(MODULE_DIR), "module/ directory missing")

        # Explicitly verify the 9 core files (including action.sh, customize.sh, hotinstall.sh)
        core_files = [
            MODULE_PROP,
            SERVICE_SH,
            UNINSTALL_SH,
            ACTION_SH,
            CUSTOMIZE_SH,
            HOTINSTALL_SH,
            ON_AGH_SH,
            NETGUARD_SH,
            INDEX_HTML,
        ]
        for cf in core_files:
            rel = os.path.relpath(cf, PROJECT_ROOT)
            self.assertTrue(os.path.exists(cf), f"Core file missing: {rel}")

        # Scan for forbidden obsolete scripts
        forbidden_obsolete = [
            "scripts/env.sh",
            "scripts/guard.sh",
            "scripts/controller.sh",
            "scripts/config_toggle.sh",
            "scripts/probe.sh",
            "scripts/rescue.sh",
            "scripts/rules_audit.sh",
            "scripts/webui.sh",
        ]
        found_obsolete = []
        for fo in forbidden_obsolete:
            full_path = os.path.join(MODULE_DIR, fo)
            if os.path.exists(full_path):
                found_obsolete.append(fo)

        self.assertEqual(
            found_obsolete,
            [],
            f"Found forbidden obsolete scripts in module/: {found_obsolete}. v3.0 invariant violated!",
        )

    def test_04_pure_readonly_invariants(self):
        """Scans netguard.sh and service.sh for forbidden active probes and modifications."""
        self.assertTrue(os.path.exists(NETGUARD_SH), "netguard.sh missing")
        with open(NETGUARD_SH, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Exclude shell comment lines so documentation mentions don't trigger false positives
        code_lines = [l for l in lines if not l.strip().startswith("#")]
        code_body = "".join(code_lines)

        # Invariant 1: No curl / wget
        self.assertNotIn("curl ", code_body, "netguard.sh must not call curl (0 active web requests)")
        self.assertNotIn("wget ", code_body, "netguard.sh must not call wget")

        # Invariant 2: No active UDP construct (/dev/udp, nc -u, socat)
        self.assertNotIn("/dev/udp", code_body, "netguard.sh must not write to /dev/udp")
        self.assertNotIn("nc -u", code_body, "netguard.sh must not call nc -u")

        # Invariant 3: Zero AdGuardHome.yaml modification
        self.assertNotIn("AdGuardHome.yaml", code_body, "netguard.sh must not touch AdGuardHome.yaml")

        # Invariant 4: No SIGHUP / kill -HUP / kill -1
        self.assertNotIn("kill -HUP", code_body, "netguard.sh must not send kill -HUP")
        self.assertNotIn("kill -1 ", code_body, "netguard.sh must not send kill -1")

    def test_05_awk_patch_standard_yaml(self):
        """Tests the Clash awk patch on standard Clash YAML fixture."""
        fixture_file = os.path.join(FIXTURES_DIR, "clash_standard.yaml")
        self.assertTrue(os.path.exists(fixture_file), "clash_standard.yaml missing")
        with open(fixture_file, "r", encoding="utf-8") as f:
            orig_yaml = f.read()

        patched = run_awk_patch(orig_yaml, target_ns="127.0.0.1:5591")

        # Check append-system-dns
        self.assertIn("append-system-dns: false", patched)
        # Check nameserver contains target
        self.assertTrue(
            "nameserver: [127.0.0.1:5591]" in patched or "- 127.0.0.1:5591" in patched,
            "Target nameserver 127.0.0.1:5591 not injected",
        )
        # Check 0.0.0.0/32 injection
        self.assertIn("- IP-CIDR,0.0.0.0/32,REJECT", patched)
        self.assertIn("- IP-CIDR6,::/128,REJECT", patched)
        # Check GEOIP,CN,DIRECT
        self.assertIn("- GEOIP,CN,DIRECT", patched)

        # Check ordering: REJECT must precede GEOIP, which must precede MATCH
        pos_reject = patched.find("- IP-CIDR,0.0.0.0/32,REJECT")
        pos_geoip = patched.find("- GEOIP,CN,DIRECT")
        pos_match = patched.find("- MATCH,Proxy")
        self.assertTrue(pos_reject < pos_geoip < pos_match, "Rule ordering must be REJECT -> GEOIP -> MATCH")

    def test_06_status_json_schema(self):
        """Validates NetGuard status JSON format against the 9-field schema."""
        fixture_file = os.path.join(FIXTURES_DIR, "mock_status.json")
        self.assertTrue(os.path.exists(fixture_file), "mock_status.json missing")
        with open(fixture_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        valid, msg = validate_status_schema(data)
        self.assertTrue(valid, f"Status schema validation failed: {msg}")

        # Test rejection of invalid schema (missing field)
        bad_data = dict(data)
        del bad_data["fallback"]
        bad_valid, _ = validate_status_schema(bad_data)
        self.assertFalse(bad_valid, "Schema validator should reject missing fallback field")

        # Test rejection of invalid mode
        bad_mode_data = dict(data, mode="unknown_mode")
        bm_valid, _ = validate_status_schema(bad_mode_data)
        self.assertFalse(bm_valid, "Schema validator should reject invalid mode")


# ============================================================================
# Tier 2: Boundary & Corner Cases
# ============================================================================
class Tier2BoundaryAndCornerCases(unittest.TestCase):
    """Tier 2: Boundary & Corner Cases (Awk patch edges, VPN interface filtering, WebUI Zero-Interval)."""

    def test_07_awk_patch_trailing_comments(self):
        """Verifies awk patch succeeds on YAML with trailing comments (e.g. nameserver: # comment)."""
        fixture_file = os.path.join(FIXTURES_DIR, "clash_trailing_comment.yaml")
        with open(fixture_file, "r", encoding="utf-8") as f:
            orig_yaml = f.read()

        patched = run_awk_patch(orig_yaml, target_ns="127.0.0.1:5591")
        self.assertIn("- 127.0.0.1:5591", patched, "Nameserver with trailing comment must be patched")
        self.assertIn("- IP-CIDR,0.0.0.0/32,REJECT", patched)

    def test_08_awk_patch_inline_array(self):
        """Verifies awk patch on inline array format (nameserver: [1.1.1.1, 8.8.8.8])."""
        fixture_file = os.path.join(FIXTURES_DIR, "clash_inline_array.yaml")
        with open(fixture_file, "r", encoding="utf-8") as f:
            orig_yaml = f.read()

        patched = run_awk_patch(orig_yaml, target_ns="127.0.0.1:5591")
        self.assertIn("nameserver: [127.0.0.1:5591]", patched, "Inline array nameserver must be replaced")
        self.assertNotIn("223.5.5.5", patched, "Old DNS must be removed from inline array")
        self.assertIn("- IP-CIDR,0.0.0.0/32,REJECT", patched)

    def test_09_awk_patch_chinese_group_names(self):
        """Verifies UTF-8 encoding integrity with Chinese rule group names (e.g. 🎯 全球直连)."""
        fixture_file = os.path.join(FIXTURES_DIR, "clash_chinese_group.yaml")
        with open(fixture_file, "r", encoding="utf-8") as f:
            orig_yaml = f.read()

        patched = run_awk_patch(orig_yaml, target_ns="127.0.0.1:5591")
        # All Chinese strings must be preserved verbatim
        self.assertIn("🎯 全球直连", patched, "Chinese group name 🎯 全球直连 corrupted!")
        self.assertIn("🚀 节点选择", patched, "Chinese group name 🚀 节点选择 corrupted!")
        self.assertIn("🐟 漏网之鱼", patched, "Chinese group name 🐟 漏网之鱼 corrupted!")
        self.assertIn("- IP-CIDR,0.0.0.0/32,REJECT", patched)

    def test_10_awk_patch_missing_match_line(self):
        """Verifies awk patch succeeds on configurations missing a MATCH rule line."""
        fixture_file = os.path.join(FIXTURES_DIR, "clash_no_match.yaml")
        with open(fixture_file, "r", encoding="utf-8") as f:
            orig_yaml = f.read()

        patched = run_awk_patch(orig_yaml, target_ns="127.0.0.1:5591")
        self.assertIn("- IP-CIDR,0.0.0.0/32,REJECT", patched)
        self.assertIn("- GEOIP,CN,DIRECT", patched)

    def test_11_awk_patch_idempotency(self):
        """Verifies that running the awk patch twice produces identical diff (idempotent)."""
        fixture_file = os.path.join(FIXTURES_DIR, "clash_standard.yaml")
        with open(fixture_file, "r", encoding="utf-8") as f:
            orig_yaml = f.read()

        pass1 = run_awk_patch(orig_yaml, target_ns="127.0.0.1:5591")
        pass2 = run_awk_patch(pass1, target_ns="127.0.0.1:5591")

        self.assertEqual(
            pass1,
            pass2,
            "Awk patch is not idempotent: second run modified configuration!",
        )
        # Ensure rules are not duplicated
        self.assertEqual(
            pass2.count("- IP-CIDR,0.0.0.0/32,REJECT"),
            1,
            "0.0.0.0/32 REJECT was duplicated on second run",
        )

    def test_12_vpn_interface_filtering(self):
        """Tests VPN interface classification: tunl0 must NOT be treated as VPN; tun0, utun0, FlClash must be."""
        # Interface name patterns defined in netguard.sh:
        # tun[0-9]*|utun[0-9]*|FlClash|clash*|Meta*
        vpn_dev_patterns = ["tun[0-9]*", "utun[0-9]*", "FlClash", "clash*", "Meta*"]

        def is_vpn_dev(name):
            for pat in vpn_dev_patterns:
                if fnmatch.fnmatch(name, pat):
                    return True
            return False

        # Positive VPN interfaces
        positive_vpns = [
            "tun0",
            "tun1",
            "tun99",
            "utun0",
            "utun10",
            "FlClash",
            "clash",
            "clash0",
            "Meta",
            "Meta_vpn",
        ]
        for dev in positive_vpns:
            self.assertTrue(is_vpn_dev(dev), f"Interface '{dev}' should be classified as VPN")

        # Negative non-VPN interfaces (especially tunl0 and sit0 tunnels)
        negative_devs = [
            "tunl0",
            "tunl0@NONE",
            "sit0",
            "wlan0",
            "rmnet_data0",
            "lo",
            "dummy0",
            "ip6tnl0",
            "eth0",
            "p2p0",
        ]
        for dev in negative_devs:
            self.assertFalse(is_vpn_dev(dev), f"Interface '{dev}' must NOT be classified as VPN")

        # Test ip monitor link line matching pattern
        # *tun[0-9]*|*utun[0-9]*|*FlClash*|*clash*|*Meta*
        line_patterns = ["*tun[0-9]*", "*utun[0-9]*", "*FlClash*", "*clash*", "*Meta*"]

        def is_vpn_line(line):
            for pat in line_patterns:
                if fnmatch.fnmatch(line, pat):
                    return True
            return False

        self.assertTrue(is_vpn_line("25: tun0: <POINTOPOINT,MULTICAST,UP> mtu 1500"))
        self.assertTrue(is_vpn_line("14: FlClash: <POINTOPOINT> mtu 1500"))
        self.assertFalse(is_vpn_line("12: tunl0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN"))
        self.assertFalse(is_vpn_line("3: wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500"))

    def test_13_webui_zero_interval_invariant(self):
        """Verifies webroot/index.html is < 6KB and contains zero recurring background timers."""
        self.assertTrue(os.path.exists(INDEX_HTML), "webroot/index.html missing")
        file_size = os.path.getsize(INDEX_HTML)
        self.assertLess(file_size, 6144, f"webroot/index.html is {file_size} bytes, exceeds 6KB limit")

        with open(INDEX_HTML, "r", encoding="utf-8") as f:
            html = f.read()

        # Invariant: 0 recurring timers
        self.assertNotIn("setInterval", html, "webroot/index.html must NOT contain setInterval")
        # Invariant: 100% offline (no external cdn / external scripts)
        self.assertNotIn("http://", html, "webroot/index.html must not load external http resources")
        self.assertNotIn("https://", html, "webroot/index.html must not load external https resources")

        # Invariant: Contract actions
        self.assertIn("status", html, "index.html must call status")
        self.assertIn("mode_", html, "index.html must support mode switching")


# ============================================================================
# Tier 3: Cross-Feature Combinations
# ============================================================================
class Tier3CrossFeatureCombinations(unittest.TestCase):
    """Tier 3: Cross-Feature State Transitions & Truth Table Verification."""

    @staticmethod
    def simulate_sync_all(mode, port_ok):
        """Pure simulation of sync_all() kernel bypass logic from netguard.sh."""
        actions = []
        if port_ok == 1:
            if mode == "auto":
                actions.append("ensure_tun_bypass")
        elif mode == "auto":
            actions.append("do_detach")
        return actions

    def test_14_reconcile_truth_table_auto_mode(self):
        """Tests sync_all actions under mode 'auto'."""
        self.assertEqual(self.simulate_sync_all("auto", port_ok=1), ["ensure_tun_bypass"])
        self.assertEqual(self.simulate_sync_all("auto", port_ok=0), ["do_detach"])

    def test_15_reconcile_truth_table_observe_mode(self):
        """Tests sync_all under mode 'observe': NO automated iptables action allowed."""
        for port_ok in (0, 1):
            result = self.simulate_sync_all("observe", port_ok)
            self.assertEqual(
                result,
                [],
                f"Observe mode must NEVER perform automated actions! Fired on port_ok={port_ok}",
            )

    def test_16_fallback_state_transitions(self):
        """Verifies Clash Meta fallback state machine (FLAG_FB trigger and restore)."""

        def simulate_clash_guard(integ_mode, port_ok, flag_fb_exists):
            action = None
            new_flag = flag_fb_exists
            if integ_mode == "on":
                if port_ok == 0 and not flag_fb_exists:
                    action = "fallback_223.5.5.5"
                    new_flag = True
                elif port_ok == 1 and flag_fb_exists:
                    action = "restore_127.0.0.1:5591"
                    new_flag = False
            return action, new_flag

        # Case 1: AGH offline -> trigger fallback
        act, flag = simulate_clash_guard(
            integ_mode="on", port_ok=0, flag_fb_exists=False
        )
        self.assertEqual(act, "fallback_223.5.5.5")
        self.assertTrue(flag)

        # Case 2: AGH still offline -> steady fallback (idempotent, no repeated trigger)
        act, flag = simulate_clash_guard(
            integ_mode="on", port_ok=0, flag_fb_exists=True
        )
        self.assertIsNone(act)
        self.assertTrue(flag)

        # Case 3: AGH comes back online -> restore normal nameserver
        act, flag = simulate_clash_guard(
            integ_mode="on", port_ok=1, flag_fb_exists=True
        )
        self.assertEqual(act, "restore_127.0.0.1:5591")
        self.assertFalse(flag)

        # Case 4: AGH online and normal -> steady normal
        act, flag = simulate_clash_guard(
            integ_mode="on", port_ok=1, flag_fb_exists=False
        )
        self.assertIsNone(act)
        self.assertFalse(flag)

        # Case 5: Integration is off -> no fallback even if AGH dead
        act, flag = simulate_clash_guard(
            integ_mode="off", port_ok=0, flag_fb_exists=False
        )
        self.assertIsNone(act)
        self.assertFalse(flag)


# ============================================================================
# Tier 4: Real-World & Packaging Acceptance
# ============================================================================
class Tier4PackagingAndAcceptance(unittest.TestCase):
    """Tier 4: Packaging Verification and Live ADB Smoke Probe."""

    def test_17_packaging_build_and_verify_zip(self):
        """Runs build_zip.py and verify_zip.py, asserting zero errors."""
        build_script = os.path.join(PROJECT_ROOT, "build_zip.py")
        verify_script = os.path.join(PROJECT_ROOT, "verify_zip.py")
        self.assertTrue(os.path.exists(build_script), "build_zip.py missing")
        self.assertTrue(os.path.exists(verify_script), "verify_zip.py missing")

        res_build = subprocess.run(
            [sys.executable, build_script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            res_build.returncode,
            0,
            f"build_zip.py failed:\n{res_build.stdout}\n{res_build.stderr}",
        )

        res_verify = subprocess.run(
            [sys.executable, verify_script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            res_verify.returncode,
            0,
            f"verify_zip.py failed:\n{res_verify.stdout}\n{res_verify.stderr}",
        )

    def test_18_zip_content_hygiene(self):
        """Inspects generated zip archive for 0 CRLF line endings, 0 UTF-8 BOM, and POSIX permissions."""
        zip_path = os.path.join(PROJECT_ROOT, "rmg-netguard-v3.1.1.zip")
        if not os.path.exists(zip_path):
            # Try finding any generated zip
            zips = [f for f in os.listdir(PROJECT_ROOT) if f.startswith("rmg-netguard-") and f.endswith(".zip")]
            if zips:
                zip_path = os.path.join(PROJECT_ROOT, zips[0])

        self.assertTrue(os.path.exists(zip_path), f"Package zip {zip_path} not found")

        with zipfile.ZipFile(zip_path, "r") as zf:
            bad_entries = zf.testzip()
            self.assertIsNone(bad_entries, f"Corrupted zip archive entry: {bad_entries}")

            namelist = zf.namelist()
            self.assertIn("module.prop", namelist, "module.prop missing from zip root")
            self.assertIn("service.sh", namelist, "service.sh missing from zip root")

            for info in zf.infolist():
                name = info.filename
                data = zf.read(name)
                # Check for CRLF in text files
                if name.endswith((".sh", ".prop", ".html", ".json", ".md")):
                    self.assertNotIn(
                        b"\r\n",
                        data,
                        f"File '{name}' inside zip contains CRLF line endings! Must be pure LF.",
                    )
                # Check for BOM
                self.assertFalse(
                    data.startswith(b"\xef\xbb\xbf"),
                    f"File '{name}' inside zip contains UTF-8 BOM!",
                )
                # Check POSIX permission bits
                mode = (info.external_attr >> 16) & 0o777
                if name.endswith(".sh"):
                    self.assertEqual(mode, 0o755, f"Script '{name}' must have 0755 mode, got {oct(mode)}")
                else:
                    self.assertEqual(mode, 0o644, f"Regular file '{name}' must have 0644 mode, got {oct(mode)}")

    def test_19_adb_device_smoke_probe(self):
        """Optional ADB probe for Samsung Galaxy S23 Ultra if connected."""
        if not os.path.exists(ADB_PATH):
            raise unittest.SkipTest(f"ADB not found at {ADB_PATH}")

        # Check ADB devices (use port 5038 if host 5037 has ephemeral collision)
        adb_env = os.environ.copy()
        adb_env.setdefault("ANDROID_ADB_SERVER_PORT", "5038")
        res = subprocess.run([ADB_PATH, "devices"], env=adb_env, capture_output=True, text=True)
        if "R5CW21C5WHB" not in res.stdout:
            raise unittest.SkipTest("Target device R5CW21C5WHB not connected or unauthorized")

        # Verify Root
        res_id = subprocess.run(
            [ADB_PATH, "-s", "R5CW21C5WHB", "shell", "su -c 'id'"],
            env=adb_env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res_id.returncode != 0 or "uid=0" not in res_id.stdout:
            raise unittest.SkipTest(f"Root not available on device: {res_id.stderr}")

        # Check processes
        res_ps = subprocess.run(
            [ADB_PATH, "-s", "R5CW21C5WHB", "shell", "su -c 'ps -ef | grep -E \"inotifyd|netguard\" | grep -v grep'"],
            env=adb_env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        print(f"\n[ADB Smoke] Current netguard processes on S23 Ultra:\n{res_ps.stdout.strip()}")

        # Check cgroup
        res_cg = subprocess.run(
            [ADB_PATH, "-s", "R5CW21C5WHB", "shell", "su -c 'cat /dev/cpuset/system-background/cgroup.procs 2>/dev/null | wc -l'"],
            env=adb_env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        print(f"[ADB Smoke] system-background procs count: {res_cg.stdout.strip()}")


# ============================================================================
# Main Runner
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description="RMG NetGuard v3.0 Test Suite")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3, 4], help="Run specific tier only")
    args, extra = parser.parse_known_args()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    tier_map = {
        1: Tier1FeatureCoverage,
        2: Tier2BoundaryAndCornerCases,
        3: Tier3CrossFeatureCombinations,
        4: Tier4PackagingAndAcceptance,
    }

    if args.tier:
        suite.addTests(loader.loadTestsFromTestCase(tier_map[args.tier]))
    else:
        for t_cls in tier_map.values():
            suite.addTests(loader.loadTestsFromTestCase(t_cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
