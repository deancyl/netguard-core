#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent Adversarial Deep Probe Suite for Challenger 1 (Milestone 1 Iteration 2).

This suite independently stress-tests the 3 high-risk vulnerabilities:
1. Awk state machine under comments, empty lines, and complex syntax
2. Emoji and custom proxy group GEOIP rule idempotency across 5 passes
3. Real bash execution of the circuit breaker lifecycle and .orig backup preservation
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
NETGUARD_SH = os.path.join(PROJECT_ROOT, "module", "scripts", "netguard.sh")
GIT_AWK = r"C:\Program Files\Git\usr\bin\awk.exe"
GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"


def extract_awk_code():
    with open(NETGUARD_SH, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r"awk\s+-v\s+ns=\"\$target_ns\"\s+'(.*?)'\s+\"\$CFG\"", content, re.DOTALL)
    assert match, "Could not extract Awk script from netguard.sh"
    return match.group(1).strip()


AWK_SCRIPT = extract_awk_code()


def run_awk(yaml_content, ns="127.0.0.1:5591"):
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".yaml") as f:
        f.write(yaml_content)
        f_path = f.name
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".awk") as f:
        f.write(AWK_SCRIPT)
        a_path = f.name
    try:
        res = subprocess.run(
            [GIT_AWK, "-v", f"ns={ns}", "-f", a_path, f_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert res.returncode == 0, f"Awk failed: {res.stderr}"
        return res.stdout
    finally:
        if os.path.exists(f_path):
            os.remove(f_path)
        if os.path.exists(a_path):
            os.remove(a_path)


class AdversarialAwkStressTests(unittest.TestCase):
    """Deep adversarial testing of Awk state machine resilience."""

    def test_01_multiple_comments_directly_under_nameserver(self):
        """Test nameserver followed by multiple comment lines before list items."""
        inp = """dns:
  enable: true
  nameserver:
    # 第一行注释：国内公共DNS服务
    # 第二行注释：包含腾讯与阿里
    # 第三行注释：备用DNS
    - 223.5.5.5
    - 119.29.29.29
    - 180.76.76.76
rules:
  - MATCH,proxy
"""
        out = run_awk(inp)
        self.assertIn("- 127.0.0.1:5591", out)
        self.assertNotIn("223.5.5.5", out)
        self.assertNotIn("119.29.29.29", out)
        self.assertNotIn("180.76.76.76", out)
        self.assertIn("# 第一行注释：国内公共DNS服务", out)
        self.assertIn("# 第二行注释：包含腾讯与阿里", out)
        self.assertIn("# 第三行注释：备用DNS", out)
        data = yaml.safe_load(out)
        self.assertEqual(data["dns"]["nameserver"], ["127.0.0.1:5591"])

    def test_02_multiple_empty_lines_and_whitespace(self):
        """Test nameserver followed by blank lines, indented empty lines, and tabs."""
        inp = """dns:
  enable: true
  nameserver:
    

        
    - 223.5.5.5
    - 1.1.1.1
rules:
  - MATCH,proxy
"""
        out = run_awk(inp)
        self.assertIn("- 127.0.0.1:5591", out)
        self.assertNotIn("223.5.5.5", out)
        self.assertNotIn("1.1.1.1", out)
        data = yaml.safe_load(out)
        self.assertEqual(data["dns"]["nameserver"], ["127.0.0.1:5591"])

    def test_03_mixed_interleaved_comments_and_empty_lines(self):
        """Test nameserver with interleaved comments and empty lines between each DNS item."""
        inp = """dns:
  enable: true
  nameserver:
    # 顶部注释
    
    - 223.5.5.5
    # 中间注释 A
    
    - 119.29.29.29
    # 中间注释 B
    - 8.8.8.8
    
fallback:
  - 8.8.4.4
rules:
  - MATCH,proxy
"""
        out = run_awk(inp)
        self.assertIn("- 127.0.0.1:5591", out)
        self.assertNotIn("223.5.5.5", out)
        self.assertNotIn("119.29.29.29", out)
        self.assertNotIn("8.8.8.8", out)
        self.assertIn("fallback:", out)
        self.assertIn("- 8.8.4.4", out)
        data = yaml.safe_load(out)
        self.assertEqual(data["dns"]["nameserver"], ["127.0.0.1:5591"])
        self.assertEqual(data["fallback"], ["8.8.4.4"])

    def test_04_inline_array_with_trailing_comment(self):
        """Test nameserver inline array with trailing comments and spaces."""
        inp = """dns:
  nameserver: [ 223.5.5.5, 114.114.114.114 ] # Public DNS Array
rules:
  - MATCH,proxy
"""
        out = run_awk(inp)
        self.assertIn("nameserver: [127.0.0.1:5591]", out)
        self.assertNotIn("223.5.5.5", out)
        self.assertNotIn("114.114.114.114", out)
        data = yaml.safe_load(out)
        self.assertEqual(data["dns"]["nameserver"], ["127.0.0.1:5591"])


class AdversarialGeoipIdempotencyTests(unittest.TestCase):
    """Deep adversarial testing of GEOIP rule rewriting and idempotency."""

    def test_01_complex_emoji_and_special_chars_5_rounds(self):
        """5 continuous passes on YAML with Emoji, brackets, and multiple proxy group names."""
        inp = """dns:
  nameserver:
    - 223.5.5.5
rules:
  - GEOIP,CN,🚀 极速专线 [BGP] - 01,no-resolve
  - GEOIP,CN,🇨🇳 国内直连 (Direct) 流量, no-resolve
  - GEOIP,CN,DIRECT
  - MATCH,🎯 全球直连
"""
        cur = inp
        history = []
        for round_idx in range(1, 6):
            cur = run_awk(cur)
            history.append(cur)
            data = yaml.safe_load(cur)
            self.assertEqual(data["dns"]["nameserver"], ["127.0.0.1:5591"])
            # In pass 1 and all subsequent passes:
            # - IP-CIDR,0.0.0.0/32,REJECT must appear exactly once
            # - IP-CIDR6,::/128,REJECT must appear exactly once
            self.assertEqual(cur.count("IP-CIDR,0.0.0.0/32,REJECT"), 1)
            self.assertEqual(cur.count("IP-CIDR6,::/128,REJECT"), 1)
            # no-resolve must be stripped from all GEOIP,CN lines
            self.assertNotIn("no-resolve", cur)
            # The original proxy group names must be preserved intact!
            self.assertIn("🚀 极速专线 [BGP] - 01", cur)
            self.assertIn("🇨🇳 国内直连 (Direct) 流量", cur)

        # Assert strict idempotency across all rounds 1 through 5!
        for i in range(1, 5):
            self.assertEqual(
                history[i],
                history[0],
                f"Pass {i+1} diverged from Pass 1! Idempotency violation!",
            )

    def test_02_missing_geoip_and_missing_match(self):
        """Edge case: Rule list has no GEOIP rule, and no MATCH rule."""
        inp = """dns:
  nameserver:
    - 223.5.5.5
rules:
  - DOMAIN-SUFFIX,google.com,proxy
  - DOMAIN-KEYWORD,github,proxy
"""
        cur = run_awk(inp)
        # Without GEOIP or MATCH, verify YAML loads safely
        data = yaml.safe_load(cur)
        self.assertEqual(data["dns"]["nameserver"], ["127.0.0.1:5591"])
        # Second pass must be identical
        cur2 = run_awk(cur)
        self.assertEqual(cur, cur2)


    def test_03_multiple_different_geoip_rules_5_rounds(self):
        """Test multiple distinct GEOIP,CN rules with different proxy targets."""
        inp = """dns:
  nameserver:
    - 223.5.5.5
rules:
  - GEOIP,CN,🚀 专线节点,no-resolve
  - GEOIP,CN,DIRECT,no-resolve
  - MATCH,🎯 全球直连
"""
        cur = inp
        history = []
        for round_idx in range(1, 6):
            cur = run_awk(cur)
            history.append(cur)
            data = yaml.safe_load(cur)
            self.assertEqual(data["dns"]["nameserver"], ["127.0.0.1:5591"])
            self.assertEqual(cur.count("IP-CIDR,0.0.0.0/32,REJECT"), 1)
            self.assertEqual(cur.count("IP-CIDR6,::/128,REJECT"), 1)
            self.assertEqual(cur.count("🚀 专线节点"), 1)
            self.assertEqual(cur.count("DIRECT"), 1)
            self.assertNotIn("no-resolve", cur)

        for i in range(1, 5):
            self.assertEqual(history[i], history[0], f"Round {i+1} diverged!")


class AdversarialCircuitBreakerLifecycleTests(unittest.TestCase):
    """Execute real Bash script commands to test backup protection and restoration."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="rmg_test_cb_")
        self.mod_dir = os.path.join(self.test_dir, "module")
        shutil.copytree(os.path.join(PROJECT_ROOT, "module"), self.mod_dir)

        self.mock_dir = os.path.join(self.test_dir, "mock_bin")
        os.makedirs(self.mock_dir)

        # Mock commands like am, iptables, ip6tables, renice
        for cmd in ["am", "iptables", "ip6tables", "renice"]:
            cmd_path = os.path.join(self.mock_dir, cmd)
            with open(cmd_path, "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\nexit 0\n")
            os.chmod(cmd_path, 0o755)

        # Setup mock Clash prefs and import dirs
        self.clash_dir = os.path.join(self.test_dir, "clash")
        self.uuid = "a1b2c3d4-e5f6-7890-abcd-ef0123456789"
        self.meta_prefs = os.path.join(self.clash_dir, "service.xml")
        self.meta_import = os.path.join(self.clash_dir, "imported")
        self.profile_dir = os.path.join(self.meta_import, self.uuid)
        os.makedirs(self.profile_dir, exist_ok=True)

        os.makedirs(os.path.dirname(self.meta_prefs), exist_ok=True)
        with open(self.meta_prefs, "w", encoding="utf-8") as f:
            f.write(f'<string name="active_profile">{self.uuid}</string>\n')

        self.initial_config = """dns:
  enable: true
  nameserver:
    # 原始用户自定义 DNS
    - 114.114.114.114
    - 223.5.5.5
rules:
  - GEOIP,CN,DIRECT,no-resolve
  - MATCH,🎯 全球直连
"""
        self.cfg_path = os.path.join(self.profile_dir, "config.yaml")
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            f.write(self.initial_config)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def run_bash_script(self, action, env_overrides=None):
        script_path = os.path.join(self.mod_dir, "scripts", "netguard.sh")
        run_dir = os.path.join(self.test_dir, "run")
        bkdir = os.path.join(self.test_dir, "backups")
        os.makedirs(run_dir, exist_ok=True)
        os.makedirs(bkdir, exist_ok=True)

        # Convert Windows paths to posix for cygwin/git bash
        def to_posix(path):
            drive, rest = os.path.splitdrive(os.path.abspath(path))
            return "/" + drive.rstrip(":").lower() + rest.replace("\\", "/")

        env = os.environ.copy()
        env["PATH"] = to_posix(self.mock_dir) + ":" + env.get("PATH", "")
        # Override paths in netguard.sh via environment variables or sed
        # Let's inspect how netguard.sh sets RUN and BKDIR
        # In netguard.sh:
        # RUN="/data/adb/modules/rmg_netguard/run"
        # BKDIR="/data/local/tmp/rmg_netguard_bk"
        # META_PREFS="/data/data/$META_PKG/shared_prefs/service.xml"
        # META_IMPORT="/data/data/$META_PKG/files/imported"
        pass

    def test_full_circuit_breaker_lifecycle_in_bash(self):
        """Simulate the complete lifecycle using real bash execution."""
        script_path = os.path.join(self.mod_dir, "scripts", "netguard.sh")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Adapt path constants for test sandbox
        run_dir = os.path.join(self.test_dir, "run")
        bk_dir = os.path.join(self.test_dir, "backups")
        os.makedirs(run_dir, exist_ok=True)
        os.makedirs(bk_dir, exist_ok=True)

        def to_p(p):
            drive, rest = os.path.splitdrive(os.path.abspath(p))
            return "/" + drive.rstrip(":").lower() + rest.replace("\\", "/")

        p_run = to_p(run_dir)
        p_bk = to_p(bk_dir)
        p_prefs = to_p(self.meta_prefs)
        p_import = to_p(self.meta_import)

        patched_content = re.sub(r'RUN=".*?"', f'RUN="{p_run}"', content)
        patched_content = re.sub(r'BKDIR=".*?"', f'BKDIR="{p_bk}"', patched_content)
        patched_content = re.sub(r'META_PREFS=".*?"', f'META_PREFS="{p_prefs}"', patched_content)
        patched_content = re.sub(r'META_IMPORT=".*?"', f'META_IMPORT="{p_import}"', patched_content)

        # Add test hooks to the case statement
        test_case_hooks = """  fallback)   patch_clash "223.5.5.5" ;;
  restore)    patch_clash "$NS5591" ;;
  reconcile)  reconcile ;;
  integ_on)"""
        patched_content = patched_content.replace("  integ_on)", test_case_hooks)
        test_script_path = os.path.join(self.test_dir, "test_netguard.sh")
        with open(test_script_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(patched_content)

        def call_netguard(action):
            res = subprocess.run(
                [GIT_BASH, to_p(test_script_path), action],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={
                    **os.environ,
                    "PATH": to_p(self.mock_dir) + ":/usr/bin:/bin:" + os.environ.get("PATH", ""),
                },
            )
            return res

        orig_backup_path = os.path.join(bk_dir, f"{self.uuid}.yaml.orig")

        # Step 1: integ_on -> patch_clash 127.0.0.1:5591
        r1 = call_netguard("integ_on")
        self.assertEqual(r1.returncode, 0, f"integ_on failed: {r1.stderr}")
        self.assertTrue(os.path.exists(orig_backup_path), "Backup .orig was NOT created!")
        with open(orig_backup_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), self.initial_config, ".orig backup does not match initial config!")

        with open(self.cfg_path, "r", encoding="utf-8") as f:
            c1 = f.read()
        self.assertIn("127.0.0.1:5591", c1)
        self.assertIn("0.0.0.0/32,REJECT", c1)

        # Step 2: Simulate AGH offline -> fallback 223.5.5.5
        rfb = call_netguard("fallback")
        self.assertEqual(rfb.returncode, 0, f"fallback patch failed: {rfb.stderr}")

        with open(self.cfg_path, "r", encoding="utf-8") as f:
            cfb = f.read()
        self.assertIn("223.5.5.5", cfb)
        self.assertNotIn("127.0.0.1:5591", cfb)

        # CRITICAL ASSERTION: .orig MUST NOT be overwritten during fallback!
        with open(orig_backup_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), self.initial_config, "CRITICAL: .orig backup was corrupted during 223.5.5.5 fallback!")

        # Step 3: Simulate AGH online -> restored 127.0.0.1:5591
        rrest = call_netguard("restore")
        self.assertEqual(rrest.returncode, 0, f"restore patch failed: {rrest.stderr}")

        with open(self.cfg_path, "r", encoding="utf-8") as f:
            crest = f.read()
        self.assertIn("127.0.0.1:5591", crest)

        # CRITICAL ASSERTION: .orig MUST STILL NOT be overwritten during restore!
        with open(orig_backup_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), self.initial_config, "CRITICAL: .orig backup was corrupted during 5591 restore!")

        # Step 4: Call integ_off -> config.yaml must be 100% byte-for-byte restored!
        r_off = call_netguard("integ_off")
        self.assertEqual(r_off.returncode, 0, f"integ_off failed: {r_off.stderr}")

        with open(self.cfg_path, "r", encoding="utf-8") as f:
            final_cfg = f.read()
        self.assertEqual(final_cfg, self.initial_config, "CRITICAL: config.yaml after integ_off does NOT match initial config!")

        # Step 5: Test calling integ_off WHILE IN FALLBACK STATE (223.5.5.5)
        # Re-enable integ_on
        call_netguard("integ_on")
        # Trigger fallback to 223.5.5.5
        call_netguard("fallback")
        # Now user turns off integration while still in fallback!
        r_off_fb = call_netguard("integ_off")
        self.assertEqual(r_off_fb.returncode, 0)
        with open(self.cfg_path, "r", encoding="utf-8") as f:
            final_cfg_fb = f.read()
        self.assertEqual(final_cfg_fb, self.initial_config, "CRITICAL: config.yaml after integ_off from fallback does NOT match initial config!")

        # Step 6: External subscription update detection
        # While in integ_on, user downloads a brand new clean subscription
        call_netguard("integ_on")
        new_subscription = """dns:
  nameserver:
    - 1.1.1.1
rules:
  - MATCH,new_proxy
"""
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            f.write(new_subscription)

        # Now patch_clash is called: because CFG has neither 0.0.0.0/32,REJECT nor 5591,
        # it should update .orig to this new subscription!
        call_netguard("integ_on")
        with open(orig_backup_path, "r", encoding="utf-8") as f:
            new_orig = f.read()
        self.assertEqual(new_orig, new_subscription, "External subscription update was not backed up to .orig!")


if __name__ == "__main__":
    unittest.main(verbosity=2)
