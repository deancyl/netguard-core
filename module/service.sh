#!/system/bin/sh
case ":$PATH:" in
  *:/data/adb/ksu/bin:*) ;;
  *) [ -d /data/adb/ksu/bin ] && export PATH="$PATH:/data/adb/ksu/bin" ;;
esac
MODDIR=${0%/*}
[ -f "$MODDIR/disable" ] && exit 0
RUN="$MODDIR/run"
mkdir -p "$RUN" 2>/dev/null

is_inotify_alive() {
  [ -r "$RUN/inotify.pid" ] || return 1
  local p=""
  read -r p < "$RUN/inotify.pid" 2>/dev/null
  case "$p" in ''|*[!0-9]*) return 1 ;; esac
  [ -r "/proc/$p/cmdline" ] || return 1
  grep -q "on_agh.sh" "/proc/$p/cmdline" 2>/dev/null
}

# 清理旧版与现有残留进程（确保升级或重启时加载最新脚本）
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
for pat in "rmg_netguard/scripts/guard.sh" "rmg_netguard/scripts/netguard.sh"; do
  pkill -f "$pat" 2>/dev/null
done

# 开机等待 AGH 初始化完成并注入内核 -o tun+ 豁免规则
(
  if [ "$(getprop sys.boot_completed 2>/dev/null)" = "1" ]; then
    sleep 1
  else
    sleep 15
  fi
  sh "$MODDIR/scripts/netguard.sh" sync_rules >/dev/null 2>&1
  # 启动单进程原生 C 监听器（仅监听 /data/adb/agh/bin 下 agh.pid 创建与删除）
  if [ -d /data/adb/agh/bin ] && command -v inotifyd >/dev/null 2>&1; then
    if ! is_inotify_alive; then
      inotifyd "$MODDIR/scripts/on_agh.sh" /data/adb/agh/bin:nd >/dev/null 2>&1 &
      echo $! > "$RUN/inotify.pid"
    fi
  fi
) &
exit 0


