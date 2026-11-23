# RMG NetGuard customize.sh (由 KernelSU 安装器 source 执行)
# 纪律：绝不 exit / return，不强制覆写 webroot 的 SELinux 上下文，保障 WebUI 正常读取。

_VER=$(grep '^version=' "$MODPATH/module.prop" 2>/dev/null | head -n 1 | cut -d= -f2)
_VER="${_VER:-v3.1.2}"

ui_print "- RMG NetGuard ${_VER} (rmg_netguard)"
ui_print "- 内核原生 -o tun+ 双轨分流 + 单 inotifyd 启停熔断"
ui_print "- 设备: $(getprop ro.product.model) / Android $(getprop ro.build.version.release)"

# 规范设置脚本执行权限；绝不触碰 webroot 目录及其 SELinux 标签
if command -v set_perm_recursive >/dev/null 2>&1; then
  set_perm_recursive "$MODPATH/scripts" 0 0 0755 0755
  set_perm "$MODPATH/service.sh" 0 0 0755
  set_perm "$MODPATH/uninstall.sh" 0 0 0755
  set_perm "$MODPATH/action.sh" 0 0 0755
  set_perm "$MODPATH/hotinstall.sh" 0 0 0755
  set_perm "$MODPATH/customize.sh" 0 0 0755
  set_perm "$MODPATH/module.prop" 0 0 0644
else
  chmod 0755 "$MODPATH" "$MODPATH/scripts" 2>/dev/null
  chmod 0755 "$MODPATH"/*.sh "$MODPATH/scripts"/*.sh 2>/dev/null
  chmod 0644 "$MODPATH/module.prop" 2>/dev/null
fi

mkdir -p "$MODPATH/run" 2>/dev/null
chmod 0755 "$MODPATH/run" 2>/dev/null

# 升级迁移：保留用户持久状态（mode/integration/events.log/backups），不迁移旧 PID 与锁文件
_OLD_RUN="/data/adb/modules/rmg_netguard/run"
_NEW_RUN="$MODPATH/run"
if [ -d "$_OLD_RUN" ]; then
  ui_print "- 升级迁移: 保留用户配置与备份"
  for _f in mode integration events.log fallback; do
    if [ -f "$_OLD_RUN/$_f" ]; then
      cp -a "$_OLD_RUN/$_f" "$_NEW_RUN/$_f" 2>/dev/null \
        && ui_print "  已迁移: $_f"
    fi
  done
  if [ -d "$_OLD_RUN/backups" ]; then
    mkdir -p "$_NEW_RUN/backups" 2>/dev/null
    cp -a "$_OLD_RUN/backups/." "$_NEW_RUN/backups/" 2>/dev/null \
      && ui_print "  已迁移: backups/"
  fi
fi

# 声明支持 KernelSU 原生热安装（刷入后无需软重启即可生效并允许直接切换开关）
export MODULE_HOT_INSTALL_REQUEST=true
export MODULE_HOT_RUN_SCRIPT=hotinstall.sh

ui_print "- 安装就绪 (支持 KernelSU 原生热安装)"
ui_print "- 卡片【执行】按钮: 一键体检自愈 | 【打开】按钮: WebUI 控制台"
