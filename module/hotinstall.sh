#!/system/bin/sh
# RMG NetGuard - KernelSU 原生热安装钩子 (由 ksud 在模块文件落盘后调用)
# 安全清理旧监听进程后，若模块未禁用则立即拉起新版 service.sh

MODDIR="${0%/*}"
[ "$MODDIR" = "$0" ] && MODDIR="/data/adb/modules/rmg_netguard"
RUN="$MODDIR/run"

# 1. 核验 cmdline 后安全停掉旧 inotifyd
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
sleep 1

# 2. 尊重模块开关状态：仅在未禁用时拉起新 service.sh
if [ ! -f "$MODDIR/disable" ] && [ -f "$MODDIR/service.sh" ]; then
  sh "$MODDIR/service.sh" >/dev/null 2>&1
fi

exit 0
