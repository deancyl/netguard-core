#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adversarial challenge test suite based on Challenger 1 findings."""
import os
import subprocess
import tempfile
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
NETGUARD_SH = os.path.join(PROJECT_ROOT, "module", "scripts", "netguard.sh")
GIT_AWK = r"C:\Program Files\Git\usr\bin\awk.exe"

def extract_awk():
    with open(NETGUARD_SH, "r", encoding="utf-8") as f:
        content = f.read()
    import re
    match = re.search(r"awk\s+-v\s+ns=\"\$target_ns\"\s+'(.*?)'\s+\"\$CFG\"", content, re.DOTALL)
    assert match, "Awk script could not be extracted from netguard.sh"
    return match.group(1).strip()

AWK_CODE = extract_awk()

def run_awk(yaml_text, ns="127.0.0.1:5591"):
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".yaml") as f:
        f.write(yaml_text)
        f_path = f.name
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".awk") as f:
        f.write(AWK_CODE)
        a_path = f.name
    try:
        res = subprocess.run([GIT_AWK, "-v", f"ns={ns}", "-f", a_path, f_path],
                             capture_output=True, text=True, encoding="utf-8")
        assert res.returncode == 0, f"awk failed: {res.stderr}"
        return res.stdout
    finally:
        os.remove(f_path)
        os.remove(a_path)

def test_tc01_basic():
    inp = "dns:\n  nameserver:\n    - 223.5.5.5\nrules:\n  - MATCH,proxy\n"
    out = run_awk(inp)
    assert "- 127.0.0.1:5591" in out
    assert "223.5.5.5" not in out
    yaml.safe_load(out)
    print("PASS: TC01_basic")

def test_tc02_inline_array():
    inp = "dns:\n  nameserver: [223.5.5.5, 114.114.114.114]\nrules:\n  - MATCH,proxy\n"
    out = run_awk(inp)
    assert "nameserver: [127.0.0.1:5591]" in out
    assert "223.5.5.5" not in out
    yaml.safe_load(out)
    print("PASS: TC02_inline_array")

def test_tc03_comment_directly_under_nameserver():
    inp = """dns:
  enable: true
  nameserver:
    # 腾讯公共DNS及阿里DNS
    - 223.5.5.5
    - 119.29.29.29
rules:
  - MATCH,proxy
"""
    out = run_awk(inp)
    assert "- 127.0.0.1:5591" in out, "Target DNS not injected!"
    assert "223.5.5.5" not in out, "223.5.5.5 not stripped!"
    assert "119.29.29.29" not in out, "119.29.29.29 not stripped!"
    assert "# 腾讯公共DNS及阿里DNS" in out, "Comment lost!"
    data = yaml.safe_load(out)
    assert data["dns"]["nameserver"] == ["127.0.0.1:5591"]
    print("PASS: TC03_comment_directly_under_nameserver")

def test_tc04_empty_line_under_nameserver():
    inp = """dns:
  enable: true
  nameserver:

    - 223.5.5.5
rules:
  - MATCH,proxy
"""
    out = run_awk(inp)
    assert "- 127.0.0.1:5591" in out
    assert "223.5.5.5" not in out
    data = yaml.safe_load(out)
    assert data["dns"]["nameserver"] == ["127.0.0.1:5591"]
    print("PASS: TC04_empty_line_under_nameserver")

def test_tc05_comment_between_nameserver_items():
    inp = """dns:
  enable: true
  nameserver:
    - 223.5.5.5
    # secondary dns
    - 119.29.29.29
rules:
  - MATCH,proxy
"""
    out = run_awk(inp)
    assert "- 127.0.0.1:5591" in out
    assert "223.5.5.5" not in out
    assert "119.29.29.29" not in out
    assert "# secondary dns" in out
    data = yaml.safe_load(out)
    assert data["dns"]["nameserver"] == ["127.0.0.1:5591"]
    print("PASS: TC05_comment_between_nameserver_items")

def test_tc06_emoji_custom_rule_group_5_cycles():
    inp = """dns:
  nameserver:
    - 223.5.5.5
rules:
  - GEOIP,CN,🚀 极速专线 [BGP] - 01,no-resolve
  - MATCH,🎯 全球直连
"""
    cur = inp
    pass1 = run_awk(cur)
    assert "- GEOIP,CN,🚀 极速专线 [BGP] - 01\n" in pass1
    assert "no-resolve" not in pass1
    assert "- GEOIP,CN,DIRECT" not in pass1, "Conflicting DIRECT rule was injected!"
    assert "- IP-CIDR,0.0.0.0/32,REJECT" in pass1

    # Run 5 cycles of idempotency
    cur = pass1
    for i in range(2, 6):
        next_pass = run_awk(cur)
        assert next_pass == cur, f"Cycle {i} diverged from previous cycle!"
        assert next_pass.count("- GEOIP,CN,DIRECT") == 0
        assert next_pass.count("0.0.0.0/32,REJECT") == 1
        cur = next_pass
        data = yaml.safe_load(cur)
        assert "- 127.0.0.1:5591" in cur
    print("PASS: TC06_emoji_custom_rule_group_5_cycles")

def test_tc07_space_no_resolve():
    inp = "rules:\n  - GEOIP,CN,DIRECT, no-resolve\n  - MATCH,proxy\n"
    out = run_awk(inp)
    assert "- GEOIP,CN,DIRECT\n" in out
    assert "no-resolve" not in out
    yaml.safe_load(out)
    print("PASS: TC07_space_no_resolve")

def test_tc08_trailing_comment():
    inp = """dns:
  nameserver: # Primary upstream DNS
    - 223.5.5.5
rules:
  - GEOIP,CN,DIRECT # China Mainland Direct
  - MATCH,proxy
"""
    out = run_awk(inp)
    assert "- 127.0.0.1:5591" in out
    assert "# Primary upstream DNS" in out
    assert "# China Mainland Direct" in out
    yaml.safe_load(out)
    print("PASS: TC08_trailing_comment")

def test_tc09_rules_before_dns():
    inp = """rules:
  - GEOIP,CN,DIRECT
  - MATCH,proxy
dns:
  nameserver:
    - 8.8.8.8
"""
    out = run_awk(inp)
    assert "- 127.0.0.1:5591" in out
    assert "8.8.8.8" not in out
    assert "- IP-CIDR,0.0.0.0/32,REJECT" in out
    yaml.safe_load(out)
    print("PASS: TC09_rules_before_dns")

def test_tc10_no_match_line():
    inp = """dns:
  nameserver:
    - 223.5.5.5
rules:
  - GEOIP,CN,DIRECT
"""
    out = run_awk(inp)
    assert "- IP-CIDR,0.0.0.0/32,REJECT" in out
    yaml.safe_load(out)
    print("PASS: TC10_no_match_line")

def test_tc11_no_geoip_line():
    inp = """dns:
  nameserver:
    - 223.5.5.5
rules:
  - DOMAIN-SUFFIX,google.com,proxy
  - MATCH,proxy
"""
    out = run_awk(inp)
    assert "- IP-CIDR,0.0.0.0/32,REJECT" in out
    assert "- GEOIP,CN,DIRECT" in out
    yaml.safe_load(out)
    print("PASS: TC11_no_geoip_line")

def test_tc12_fallback_lifecycle():
    # Shell simulation of the patch_clash & integ_off lifecycle logic
    with tempfile.TemporaryDirectory() as td:
        bkdir = os.path.join(td, "backups")
        os.makedirs(bkdir)
        cfg_path = os.path.join(td, "config.yaml")
        orig_content = "dns:\n  nameserver:\n    - 223.5.5.5\nrules:\n  - MATCH,proxy\n"
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(orig_content)

        # Helper function replicating bash patch_clash & integ_off condition logic
        orig_file = os.path.join(bkdir, "test-uuid.yaml.orig")
        ns5591 = "127.0.0.1:5591"

        def patch_clash_sim(target_ns):
            nonlocal cfg_path, orig_file, ns5591
            with open(cfg_path, "r", encoding="utf-8") as f:
                c = f.read()
            # The newly patched condition:
            # [ ! -f "$orig" ] || ( ! grep -q "0.0.0.0/32,REJECT" "$CFG" && ! grep -q "$NS5591" "$CFG" )
            has_reject = "0.0.0.0/32,REJECT" in c
            has_5591 = ns5591 in c
            if not os.path.exists(orig_file) or (not has_reject and not has_5591):
                import shutil
                shutil.copy2(cfg_path, orig_file)
            new_c = run_awk(c, ns=target_ns)
            with open(cfg_path, "w", encoding="utf-8") as f:
                f.write(new_c)

        def integ_off_sim():
            nonlocal cfg_path, orig_file, ns5591
            with open(cfg_path, "r", encoding="utf-8") as f:
                c = f.read()
            has_reject = "0.0.0.0/32,REJECT" in c
            has_5591 = ns5591 in c
            if has_reject or has_5591:
                with open(orig_file, "r", encoding="utf-8") as f:
                    orig_data = f.read()
                with open(cfg_path, "w", encoding="utf-8") as f:
                    f.write(orig_data)

        # Step 1: integ_on -> patch_clash 5591
        patch_clash_sim("127.0.0.1:5591")
        assert os.path.exists(orig_file), "Orig backup was not created!"
        with open(orig_file, "r", encoding="utf-8") as f:
            assert f.read() == orig_content, "Orig backup content corrupted on first patch!"

        # Step 2: AGH offline -> fallback 223.5.5.5
        patch_clash_sim("223.5.5.5")
        with open(orig_file, "r", encoding="utf-8") as f:
            assert f.read() == orig_content, "Orig backup overwritten during 223.5.5.5 fallback!"

        # Step 3: AGH online -> restored 5591
        patch_clash_sim("127.0.0.1:5591")
        with open(orig_file, "r", encoding="utf-8") as f:
            assert f.read() == orig_content, "Orig backup overwritten during 5591 restore!"

        # Step 4: User disables integ_off
        integ_off_sim()
        with open(cfg_path, "r", encoding="utf-8") as f:
            reverted = f.read()
        assert reverted == orig_content, f"Reverted content mismatch:\n{reverted}\nvs\n{orig_content}"

        # Step 5: Test integ_off while in 223.5.5.5 fallback state!
        patch_clash_sim("127.0.0.1:5591")
        patch_clash_sim("223.5.5.5")  # now in fallback state!
        integ_off_sim()
        with open(cfg_path, "r", encoding="utf-8") as f:
            reverted_from_fb = f.read()
        assert reverted_from_fb == orig_content, f"Reverted from fallback mismatch:\n{reverted_from_fb}\nvs\n{orig_content}"

    print("PASS: TC12_fallback_lifecycle")

if __name__ == "__main__":
    test_tc01_basic()
    test_tc02_inline_array()
    test_tc03_comment_directly_under_nameserver()
    test_tc04_empty_line_under_nameserver()
    test_tc05_comment_between_nameserver_items()
    test_tc06_emoji_custom_rule_group_5_cycles()
    test_tc07_space_no_resolve()
    test_tc08_trailing_comment()
    test_tc09_rules_before_dns()
    test_tc10_no_match_line()
    test_tc11_no_geoip_line()
    test_tc12_fallback_lifecycle()
    print("\nALL 12 ADVERSARIAL CHALLENGE TESTS PASSED 100%!")
