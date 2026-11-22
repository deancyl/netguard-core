#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline unit tests for netguard.sh Clash awk patch logic."""
import subprocess
import tempfile
import os
import sys

AWK_SCRIPT = r"""
BEGIN { st=0; em=0; f_m=0; f_g=0; f_z=0 }
/^[[:space:]]*append-system-dns:[[:space:]]*true/ {
  match($0,/^[[:space:]]*/); print substr($0,1,RLENGTH) "append-system-dns: false"; next
}
/^[[:space:]]*nameserver:[[:space:]]*\[/ {
  match($0,/^[[:space:]]*/); p=substr($0,1,RLENGTH)
  sub(/\[.*\]/, "[" ns "]")
  print; next
}
/^[[:space:]]*nameserver:([[:space:]]*(#.*)?)?$/ {
  print; st=1; em=0; next
}
st==1 && /^[[:space:]]*-[[:space:]]/ {
  if (!em) { match($0,/^[[:space:]]*/); print substr($0,1,RLENGTH) "- " ns; em=1 }
  next
}
st==1 && /^[[:space:]]*(#.*)?$/ {
  # 保持 nameserver 块内的注释与空行，维持 st=1 不跌落
  print; next
}
st==1 {
  # 遇到真正的下一个非注释/非空配置项，退出 nameserver 块
  st=0
}
/^[[:space:]]*-[[:space:]]*IP-CIDR,0\.0\.0\.0\/32,REJECT/ { f_z=1 }
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

def find_awk():
    import shutil
    w = shutil.which("awk")
    if w:
        return w
    for p in [r"C:\Program Files\Git\usr\bin\awk.exe", r"C:\Program Files\Git\bin\awk.exe"]:
        if os.path.exists(p):
            return p
    return "awk"

AWK_BIN = find_awk()

def run_awk(content, ns="127.0.0.1:5591"):
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as f:
        f.write(content)
        tmp_path = f.name
    try:
        proc = subprocess.run(
            [AWK_BIN, "-v", f"ns={ns}", AWK_SCRIPT, tmp_path],
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        assert proc.returncode == 0, f"awk failed: {proc.stderr}"
        return proc.stdout
    finally:
        os.remove(tmp_path)

def test_inline_array():
    inp = "dns:\n  enable: true\n  nameserver: [https://dns.google/dns-query, 1.1.1.1]\n  append-system-dns: true\nrules:\n  - MATCH,proxy\n"
    out = run_awk(inp)
    assert "nameserver: [127.0.0.1:5591]" in out, f"Unexpected: {out}"
    assert "append-system-dns: false" in out, f"Unexpected: {out}"
    assert "- IP-CIDR,0.0.0.0/32,REJECT" in out, f"Unexpected: {out}"
    assert "- GEOIP,CN,DIRECT" in out, f"Unexpected: {out}"
    print("PASS: test_inline_array")

def test_block_list_with_comment():
    inp = "dns:\n  nameserver: # upstream servers\n    - 8.8.8.8\n    - 1.1.1.1\nrules:\n  - GEOIP,CN,DIRECT\n  - MATCH,proxy\n"
    out = run_awk(inp)
    assert "- 127.0.0.1:5591" in out, f"Unexpected: {out}"
    assert "8.8.8.8" not in out, f"Unexpected: {out}"
    assert "1.1.1.1" not in out, f"Unexpected: {out}"
    assert "- IP-CIDR,0.0.0.0/32,REJECT" in out, f"Unexpected: {out}"
    print("PASS: test_block_list_with_comment")

def test_chinese_rule_group():
    inp = "rules:\n  - GEOIP,CN,🎯 全球直连,no-resolve\n  - MATCH,proxy\n"
    out = run_awk(inp)
    assert "- IP-CIDR,0.0.0.0/32,REJECT" in out, f"Unexpected: {out}"
    assert "- IP-CIDR6,::/128,REJECT" in out, f"Unexpected: {out}"
    assert "- GEOIP,CN,🎯 全球直连\n" in out, f"Unexpected: {out}"
    assert "no-resolve" not in out, f"Unexpected: {out}"
    print("PASS: test_chinese_rule_group")

def test_idempotence():
    inp = "dns:\n  nameserver: [127.0.0.1:5591]\n  append-system-dns: false\nrules:\n  - IP-CIDR,0.0.0.0/32,REJECT\n  - IP-CIDR6,::/128,REJECT\n  - GEOIP,CN,DIRECT\n  - MATCH,proxy\n"
    out1 = run_awk(inp)
    out2 = run_awk(out1)
    assert out1 == out2, f"Diff detected:\n{out1}\nvs\n{out2}"
    assert out1.count("IP-CIDR,0.0.0.0/32,REJECT") == 1
    assert out1.count("GEOIP,CN,DIRECT") == 1
    print("PASS: test_idempotence")

def test_fallback_cycle():
    inp = "dns:\n  nameserver: [127.0.0.1:5591]\n"
    fb = run_awk(inp, ns="223.5.5.5")
    assert "nameserver: [223.5.5.5]" in fb
    restored = run_awk(fb, ns="127.0.0.1:5591")
    assert "nameserver: [127.0.0.1:5591]" in restored
    print("PASS: test_fallback_cycle")

if __name__ == "__main__":
    test_inline_array()
    test_block_list_with_comment()
    test_chinese_rule_group()
    test_idempotence()
    test_fallback_cycle()
    print("All awk unit tests passed successfully!")
