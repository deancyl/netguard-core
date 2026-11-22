#!/system/bin/sh
# inotifyd 回调参数: $1=事件(n=创建/d=删除) $2=目录 $3=文件名
MODDIR="${0%/*}"
case "$MODDIR" in */scripts) MODDIR="${MODDIR%/scripts}" ;; *) MODDIR="/data/adb/modules/rmg_netguard" ;; esac

[ "$3" = "agh.pid" ] || exit 0

if [ "$1" = "d" ]; then
  # AGH 进程退出或 PID 文件移除：零延迟立即熔断降级与规则脱钩
  exec sh "$MODDIR/scripts/netguard.sh" on_agh_change "$1"
fi

# AGH 启动 (n 事件)：动态探测端口就绪与规则链创建（最多等待 6 秒）
i=0
while [ "$i" -lt 12 ]; do
  [ -f /data/adb/agh/bin/agh.pid ] || exit 0
  if grep -q ":15D7 " /proc/net/udp /proc/net/udp6 2>/dev/null && \
     iptables -w -t nat -L ADGUARD_REDIRECT_DNS >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
  i=$(( i + 1 ))
done

[ -f /data/adb/agh/bin/agh.pid ] || exit 0
exec sh "$MODDIR/scripts/netguard.sh" on_agh_change "$1"

