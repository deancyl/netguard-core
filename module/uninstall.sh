#!/system/bin/sh
MODDIR=${0%/*}
RUN="$MODDIR/run"
BKDIR="$RUN/backups"
META_PKG="com.github.metacubex.clash.meta"

# 清理 inotifyd 与相关进程（安全防误杀校验）
if [ -r "$RUN/inotify.pid" ]; then
  read -r p < "$RUN/inotify.pid" 2>/dev/null
  case "$p" in [0-9]*)
    if [ -r "/proc/$p/cmdline" ] && grep -q "on_agh.sh" "/proc/$p/cmdline" 2>/dev/null; then
      kill "$p" 2>/dev/null
    fi
    ;;
  esac
fi
pkill -f "on_agh.sh" 2>/dev/null
pkill -f "rmg_netguard/scripts/netguard.sh" 2>/dev/null

# 移除本模块注入的 -o tun+ 豁免规则
iptables -w -t nat -D ADGUARD_REDIRECT_DNS -o tun+ -j RETURN 2>/dev/null
ip6tables -w -t filter -D ADGUARD_BLOCK_DNS -o tun+ -j RETURN 2>/dev/null
ip6tables -w -t nat -D ADGUARD_REDIRECT_DNS6 -o tun+ -j RETURN 2>/dev/null

# 还原 Clash 活动配置备份并通知 Clash Meta 重新加载
for orig in "$BKDIR"/*.yaml.orig; do
  [ -f "$orig" ] || continue
  uuid=${orig##*/}; uuid=${uuid%.yaml.orig}
  tgt="/data/data/$META_PKG/files/imported/$uuid/config.yaml"
  if [ -f "$tgt" ] && grep -qE "127\.0\.0\.1:5591|IP-CIDR,0\.0\.0\.0/32,REJECT" "$tgt"; then
    cat "$orig" > "$tgt"
    am broadcast -a "${META_PKG}.intent.action.PROFILE_CHANGED" --es uuid "$uuid" -p "$META_PKG" >/dev/null 2>&1
  fi
done

rm -rf "$RUN" 2>/dev/null
exit 0

