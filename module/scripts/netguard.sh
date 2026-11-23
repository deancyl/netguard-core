#!/system/bin/sh
# RMG NetGuard v3.1.2 — Kernel-Native -o tun+ Bypass & Reversible Clash Integration
# 0 permanent shell daemons, 0 curl, 0 UDP probes, 0 SIGHUP, 0 AGH config edits.
case ":$PATH:" in
  *:/data/adb/ksu/bin:*) ;;
  *) [ -d /data/adb/ksu/bin ] && export PATH="$PATH:/data/adb/ksu/bin" ;;
esac

MODDIR="${0%/*}"
case "$MODDIR" in */scripts) MODDIR="${MODDIR%/scripts}" ;; *) MODDIR="/data/adb/modules/rmg_netguard" ;; esac

RUN="$MODDIR/run"
BKDIR="$RUN/backups"
MODE_FILE="$RUN/mode"          # auto | observe
INTEG_FILE="$RUN/integration"  # on | off
LOG_FILE="$RUN/events.log"
FLAG_FB="$RUN/fallback"
LOCK_DIR="$RUN/.lock"

AGH_PID_FILE="/data/adb/agh/bin/agh.pid"
AGH_CHAIN="ADGUARD_REDIRECT_DNS"
AGH_CHAIN6="ADGUARD_REDIRECT_DNS6"
AGH_BLOCK6="ADGUARD_BLOCK_DNS"
META_PKG="com.github.metacubex.clash.meta"
META_PREFS="/data/data/$META_PKG/shared_prefs/service.xml"
META_IMPORT="/data/data/$META_PKG/files/imported"
NS5591="127.0.0.1:5591"

mkdir -p "$RUN" "$BKDIR" 2>/dev/null

log_ev() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') [$1] $2" >> "$LOG_FILE"
  n=$(grep -c '' "$LOG_FILE" 2>/dev/null)
  [ "${n:-0}" -gt 120 ] && tail -n 80 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
}

with_lock() {
  local i=0
  while ! mkdir "$LOCK_DIR" 2>/dev/null; do
    i=$(( i + 1 ))
    if [ "$i" -ge 15 ]; then
      rm -rf "$LOCK_DIR" 2>/dev/null
      mkdir "$LOCK_DIR" 2>/dev/null || return 1
      break
    fi
    sleep 0.2 2>/dev/null || sleep 1
  done
  "$@"
  local rc=$?
  rmdir "$LOCK_DIR" 2>/dev/null
  return "$rc"
}

mode_get() {
  local m=""
  [ -r "$MODE_FILE" ] && read -r m < "$MODE_FILE" 2>/dev/null
  [ "$m" = "observe" ] && echo "observe" || echo "auto"
}

integ_get() {
  local i=""
  [ -r "$INTEG_FILE" ] && read -r i < "$INTEG_FILE" 2>/dev/null
  [ "$i" = "on" ] && echo "on" || echo "off"
}

vpn_up() {
  VPN_IF=""
  for d in /sys/class/net/*; do
    dev="${d#/sys/class/net/}"
    case "$dev" in
      tun[0-9]*|utun[0-9]*|FlClash|clash*|Meta*) VPN_IF="$dev"; return 0 ;;
    esac
  done
  return 1
}

agh_pid() {
  local p="" comm="" st=""
  [ -r "$AGH_PID_FILE" ] && read -r p < "$AGH_PID_FILE" 2>/dev/null
  if [ -z "$p" ]; then
    p=$(pidof AdGuardHome 2>/dev/null)
    p="${p%% *}"
  fi
  case "$p" in ''|*[!0-9]*) echo 0; return 1 ;; esac
  [ -r "/proc/$p/comm" ] || { echo 0; return 1; }
  read -r comm < "/proc/$p/comm" 2>/dev/null
  [ "$comm" = "AdGuardHome" ] || { echo 0; return 1; }
  read -r st < "/proc/$p/stat" 2>/dev/null
  st="${st##*) }"
  [ "${st%% *}" != "Z" ] || { echo 0; return 1; }
  echo "$p"
  return 0
}

agh_port_up() {
  grep -q ":15D7 " /proc/net/udp /proc/net/udp6 2>/dev/null
}

# 核心 1：向 AGH 规则链顶部幂等注入 -o tun+ -j RETURN 及 CaptivePortal 智能豁免
ensure_tun_bypass() {
  [ "$(mode_get)" = "auto" ] || return 0
  local uids uid
  uids=$(grep 'captiveportallogin' /data/system/packages.list 2>/dev/null | cut -d' ' -f2)
  [ -z "$uids" ] && uids="10173"

  if iptables -w -t nat -L "$AGH_CHAIN" >/dev/null 2>&1; then
    if ! iptables -w -t nat -C "$AGH_CHAIN" -o tun+ -j RETURN 2>/dev/null; then
      iptables -w -t nat -I "$AGH_CHAIN" 1 -o tun+ -j RETURN 2>/dev/null && \
        log_ev "RULE" "injected -o tun+ -j RETURN at top of $AGH_CHAIN"
    fi
    for uid in $uids; do
      case "$uid" in ''|*[!0-9]*) continue ;; esac
      if ! iptables -w -t nat -C "$AGH_CHAIN" -m owner --uid-owner "$uid" -j RETURN 2>/dev/null; then
        iptables -w -t nat -I "$AGH_CHAIN" 1 -m owner --uid-owner "$uid" -j RETURN 2>/dev/null && \
          log_ev "RULE" "injected CaptivePortal bypass (UID $uid) into $AGH_CHAIN"
      fi
    done
  fi
  if ip6tables -w -t filter -L "$AGH_BLOCK6" >/dev/null 2>&1; then
    ip6tables -w -t filter -C "$AGH_BLOCK6" -o tun+ -j RETURN 2>/dev/null || \
      ip6tables -w -t filter -I "$AGH_BLOCK6" 1 -o tun+ -j RETURN 2>/dev/null
    for uid in $uids; do
      case "$uid" in ''|*[!0-9]*) continue ;; esac
      ip6tables -w -t filter -C "$AGH_BLOCK6" -m owner --uid-owner "$uid" -j RETURN 2>/dev/null || \
        ip6tables -w -t filter -I "$AGH_BLOCK6" 1 -m owner --uid-owner "$uid" -j RETURN 2>/dev/null
    done
  fi
  if ip6tables -w -t nat -L "$AGH_CHAIN6" >/dev/null 2>&1; then
    ip6tables -w -t nat -C "$AGH_CHAIN6" -o tun+ -j RETURN 2>/dev/null || \
      ip6tables -w -t nat -I "$AGH_CHAIN6" 1 -o tun+ -j RETURN 2>/dev/null
    for uid in $uids; do
      case "$uid" in ''|*[!0-9]*) continue ;; esac
      ip6tables -w -t nat -C "$AGH_CHAIN6" -m owner --uid-owner "$uid" -j RETURN 2>/dev/null || \
        ip6tables -w -t nat -I "$AGH_CHAIN6" 1 -m owner --uid-owner "$uid" -j RETURN 2>/dev/null
    done
  fi
}

do_detach() {
  local c=0
  while iptables -w -t nat -C OUTPUT -j "$AGH_CHAIN" 2>/dev/null; do
    iptables -w -t nat -D OUTPUT -j "$AGH_CHAIN" 2>/dev/null || break
    c=$(( c + 1 )); [ "$c" -ge 10 ] && break
  done
  while ip6tables -w -t filter -C OUTPUT -j "$AGH_BLOCK6" 2>/dev/null; do
    ip6tables -w -t filter -D OUTPUT -j "$AGH_BLOCK6" 2>/dev/null || break
  done
  while ip6tables -w -t nat -C OUTPUT -j "$AGH_CHAIN6" 2>/dev/null; do
    ip6tables -w -t nat -D OUTPUT -j "$AGH_CHAIN6" 2>/dev/null || break
  done
  [ "$c" -ge 1 ] && log_ev "CTRL" "detached OUTPUT -> $AGH_CHAIN (removed=$c)"
  echo "OK: detached ($c)"
}

do_attach() {
  local p
  p=$(agh_pid)
  if [ "$p" = "0" ] || ! agh_port_up; then
    echo "SKIP: AGH not ready"
    return 2
  fi
  ensure_tun_bypass
  if ! iptables -w -t nat -C OUTPUT -j "$AGH_CHAIN" 2>/dev/null; then
    iptables -w -t nat -I OUTPUT 1 -j "$AGH_CHAIN" 2>/dev/null &&       log_ev "CTRL" "attached OUTPUT -> $AGH_CHAIN"
  fi
  echo "OK: attached"
}

active_profile() {
  UUID=$(grep -o 'active_profile">[a-f0-9-]*' "$META_PREFS" 2>/dev/null | head -n 1 | sed 's/.*">//')
  [ -n "$UUID" ] || return 1
  CFG="$META_IMPORT/$UUID/config.yaml"
  [ -r "$CFG" ]
}

reload_meta() {
  am broadcast -a "${META_PKG}.intent.action.PROFILE_CHANGED" --es uuid "$1" -p "$META_PKG" >/dev/null 2>&1
}

# 核心 2：三段式健壮 Awk 补丁（严格使用 cat tmp > "$CFG" 保留 UID 与 SELinux 上下文）
patch_clash() {
  local target_ns="$1"
  active_profile || { echo "FAIL: no active Clash profile"; return 1; }
  local orig="$BKDIR/${UUID}.yaml.orig"
  if [ ! -f "$orig" ] || ( ! grep -q "0.0.0.0/32,REJECT" "$CFG" 2>/dev/null && ! grep -q "$NS5591" "$CFG" 2>/dev/null ); then
    cp -a "$CFG" "$orig" 2>/dev/null || return 1
  fi
  awk -v ns="$target_ns" '
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
      print; next
    }
    st==1 {
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
  ' "$CFG" > "$RUN/.cfg.tmp" && [ -s "$RUN/.cfg.tmp" ] && cat "$RUN/.cfg.tmp" > "$CFG" && rm -f "$RUN/.cfg.tmp"
  reload_meta "$UUID"
}

sync_all() {
  local p port_ok=0 v_up=0
  p=$(agh_pid)
  [ "$p" != "0" ] && agh_port_up && port_ok=1
  vpn_up && v_up=1

  if [ "$port_ok" = "1" ]; then
    ensure_tun_bypass
  elif [ "$(mode_get)" = "auto" ]; then
    do_detach >/dev/null
  fi

  if [ "$(integ_get)" = "on" ]; then
    if [ "$port_ok" = "0" ] && [ ! -f "$FLAG_FB" ]; then
      patch_clash "223.5.5.5" && touch "$FLAG_FB" && log_ev "INTEG" "AGH offline -> fallback 223.5.5.5"
    elif [ "$port_ok" = "1" ] && [ -f "$FLAG_FB" ]; then
      patch_clash "$NS5591" && rm -f "$FLAG_FB" && log_ev "INTEG" "AGH online -> restored $NS5591"
    fi
  fi
}

do_status() {
  with_lock sync_all
  local p port_ok=0 v_up=0 h_on=0 tun_bypass=0 patched="no"
  p=$(agh_pid)
  [ "$p" != "0" ] && agh_port_up && port_ok=1
  vpn_up && v_up=1
  iptables -w -t nat -C OUTPUT -j "$AGH_CHAIN" 2>/dev/null && h_on=1
  iptables -w -t nat -C "$AGH_CHAIN" -o tun+ -j RETURN 2>/dev/null && tun_bypass=1
  if active_profile && grep -q "$NS5591" "$CFG" 2>/dev/null; then patched="yes"; fi
  local ver="v3.1.2"
  if [ -r "$MODDIR/module.prop" ]; then
    local pv
    pv=$(grep '^version=' "$MODDIR/module.prop" 2>/dev/null | head -n 1 | cut -d= -f2)
    [ -n "$pv" ] && ver="$pv"
  fi
  printf '{"version":"%s","mode":"%s","vpn":%d,"vpn_if":"%s","hijack":%d,"tun_bypass":%d,"agh_pid":%s,"agh_port":%d,"integ":"%s","patched":"%s","fallback":%d}\n' \
    "$ver" "$(mode_get)" "$v_up" "$VPN_IF" "$h_on" "$tun_bypass" "$p" "$port_ok" "$(integ_get)" "$patched" "$([ -f "$FLAG_FB" ] && echo 1 || echo 0)"
}

case "$1" in
  sync_rules|on_agh_change) with_lock sync_all ;;
  status)     do_status ;;
  detach)     with_lock do_detach ;;
  attach)     with_lock do_attach ;;
  mode_auto)  echo auto > "$MODE_FILE"; with_lock sync_all; echo "OK: mode=auto" ;;
  mode_obs)   echo observe > "$MODE_FILE"; echo "OK: mode=observe" ;;
  integ_on)   with_lock patch_clash "$NS5591" && { echo on > "$INTEG_FILE"; rm -f "$FLAG_FB"; echo "OK: patched $UUID"; } ;;
  integ_off)
    active_profile && [ -f "$BKDIR/${UUID}.yaml.orig" ] && {
      cat "$BKDIR/${UUID}.yaml.orig" > "$CFG"
      rm -f "$FLAG_FB"
      echo off > "$INTEG_FILE"
      reload_meta "$UUID"
      echo "OK: reverted $UUID"
    } || echo "FAIL: no backup"
    ;;
  log)        tail -n 30 "$LOG_FILE" 2>/dev/null ;;
  *)          echo "Usage: netguard.sh {sync_rules|status|detach|attach|mode_auto|mode_obs|integ_on|integ_off|log}"; exit 1 ;;
esac
