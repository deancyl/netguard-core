#!/system/bin/sh
# RMG NetGuard - KernelSU Manager 【执行】按钮入口 (action.sh)
# 功能：秒级幂等规则对齐 + inotifyd 监听器自愈 + 结构化运行体检报告

case ":$PATH:" in
  *:/data/adb/ksu/bin:*) ;;
  *) [ -d /data/adb/ksu/bin ] && export PATH="$PATH:/data/adb/ksu/bin" ;;
esac

MODDIR="${0%/*}"
[ "$MODDIR" = "$0" ] && MODDIR="/data/adb/modules/rmg_netguard"
RUN="$MODDIR/run"
mkdir -p "$RUN" 2>/dev/null

_VER=$(grep '^version=' "$MODDIR/module.prop" 2>/dev/null | head -n 1 | cut -d= -f2)
_VER="${_VER:-v3.1.1}"

echo "=========================================="
echo "  RMG NetGuard ${_VER} 实时体检与自愈"
echo "=========================================="
echo ""

DISABLED=0
if [ -f "$MODDIR/disable" ]; then
  DISABLED=1
  echo "[!] 模块开关状态: 已标记禁用 (disable)"
  echo "    注: 原生开关开启后将恢复开机自启；以下为当前内核只读观测。"
  echo ""
fi

is_inotify_alive() {
  [ -r "$RUN/inotify.pid" ] || return 1
  local p=""
  read -r p < "$RUN/inotify.pid" 2>/dev/null
  case "$p" in ''|*[!0-9]*) return 1 ;; esac
  [ -r "/proc/$p/cmdline" ] || return 1
  grep -q "on_agh.sh" "/proc/$p/cmdline" 2>/dev/null || return 1
  echo "$p"
  return 0
}

# 1. 若模块未禁用，自动检查并恢复 inotifyd 监听器与规则对齐
if [ "$DISABLED" = "0" ]; then
  INOTIFY_PID=$(is_inotify_alive)
  if [ -z "$INOTIFY_PID" ] && [ -d /data/adb/agh/bin ] && command -v inotifyd >/dev/null 2>&1; then
    inotifyd "$MODDIR/scripts/on_agh.sh" /data/adb/agh/bin:nd >/dev/null 2>&1 &
    INOTIFY_PID=$!
    echo "$INOTIFY_PID" > "$RUN/inotify.pid"
    echo "[+] 已自动拉起 inotifyd 监听器 (PID $INOTIFY_PID)"
  fi
  sh "$MODDIR/scripts/netguard.sh" sync_rules >/dev/null 2>&1
else
  INOTIFY_PID=$(is_inotify_alive)
fi

echo "[1] 监听器与核心进程:"
if [ -n "$INOTIFY_PID" ]; then
  echo "  * inotifyd (on_agh.sh): 运行中 (PID $INOTIFY_PID)"
else
  echo "  * inotifyd (on_agh.sh): 未运行"
fi

# 2. 获取统一只读状态 JSON 并解析展示
JSON=$(sh "$MODDIR/scripts/netguard.sh" status 2>/dev/null | tail -n 1)
if [ -n "$JSON" ]; then
  jget() {
    printf '%s\n' "$JSON" | sed -n "s/.*\"$1\":\"\([^\"]*\)\".*/\1/p; s/.*\"$1\":\([0-9]*\).*/\1/p" | head -n 1
  }
  MODE=$(jget mode)
  VPN=$(jget vpn)
  VPN_IF=$(jget vpn_if)
  HIJACK=$(jget hijack)
  BYPASS=$(jget tun_bypass)
  AGH_PID=$(jget agh_pid)
  AGH_PORT=$(jget agh_port)
  INTEG=$(jget integ)
  PATCHED=$(jget patched)
  FB=$(jget fallback)

  echo ""
  echo "[2] 内核分流与拓扑状态:"
  [ "$MODE" = "auto" ] && echo "  * 守卫模式: 自动双轨 (auto)" || echo "  * 守卫模式: 只读观测 (observe)"
  [ "$VPN" = "1" ] && echo "  * VPN 接口: 已连接 (${VPN_IF:-tun})" || echo "  * VPN 接口: 未连接"
  echo "  * 53 端口劫持: $([ "$HIJACK" = "1" ] && echo '已挂载 (-> 5591)' || echo '已摘除 (直通)')"
  echo "  * 内核 -o tun+ 绕过: $([ "$BYPASS" = "1" ] && echo '已注入 (0ms 绕过)' || echo '未注入')"
  echo "  * AdGuardHome: $([ "${AGH_PID:-0}" != "0" ] && echo "PID $AGH_PID" || echo '未启动') / $([ "$AGH_PORT" = "1" ] && echo '5591监听中' || echo '离线')"
  if [ "$INTEG" = "on" ]; then
    echo "  * Clash 串联补丁: 已开启 (补丁:${PATCHED:-no}$([ "$FB" = "1" ] && echo ' · 当前熔断223.5.5.5' || echo ''))"
  else
    echo "  * Clash 串联补丁: 已关闭"
  fi
else
  echo "  * 状态读取失败，请检查 netguard.sh"
fi

echo ""
echo "[3] 最近事件日志 (最近 5 条):"
if [ -s "$RUN/events.log" ]; then
  tail -n 5 "$RUN/events.log" | sed 's/^/  /'
else
  echo "  (暂无事件记录)"
fi

echo ""
echo "=========================================="
echo "如需切换模式、手动挂摘劫持或 Clash 补丁，请点击【打开】进入 WebUI"
exit 0
