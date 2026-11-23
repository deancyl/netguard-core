# Changelog

本项目使用语义化版本。发布记录以 GitHub Releases 为准；标注「主线提交」的版本已合入 `main` 并部署到验证设备，但未创建 Release tag。

## v3.1.2 - 2026-11-23（CaptivePortal 热点认证智能豁免）

### 修复与架构增强
- **CaptivePortalLogin 智能免劫持**：在 `ADGUARD_REDIRECT_DNS`（IPv4 NAT）与 `ADGUARD_BLOCK_DNS`（IPv6 Filter）规则链顶部自动通过 `/data/system/packages.list` 极速探测并注入 `com.google.android.captiveportallogin`（UID `10173` 与 `10001` 等）的 `RETURN` 放行规则。
- **公共 Wi-Fi 兼容性重大突破**：彻底根治商用/公共 Wi-Fi（如企业内网、招行办公网 `cmb-oa.wifi.com`、酒店、机场、星巴克等热点）因内部私有认证域名在公网上游报 `NXDOMAIN` 触发 `net::ERR_NAME_NOT_RESOLVED` 的顽疾，实现全自动原生秒弹认证。
- **零副作用保障**：认证完成后，整机其他应用正常享受 AdGuard Home 过滤防护，Clash Meta `-o tun+ -j RETURN` 零延迟内核旁路保持稳固。

## v3.1.1 - 2026-11-21（KernelSU 模块规范补齐）

### KernelSU 规范与交互完善
- **补齐 `module/action.sh`**：遵循 KernelSU 模块开发规范，在管理器模块卡片恢复【执行】按钮（`hasActionScript=true`），支持秒级幂等规则对齐、`inotifyd` 自愈检查与结构化体检报告输出。
- **补齐 `module/customize.sh` 与 `module/hotinstall.sh`**：规范化 `set_perm` 权限设置与旧版 `run/` 配置迁移，**绝不触碰 `webroot` SELinux 标签**以保证管理器 WebUI 权限完整；声明支持 KernelSU 原生热安装（`MODULE_HOT_INSTALL_REQUEST=true`），刷入更新后免软重启即刻生效，避免卡片卡在待重启状态影响开关切换。
- **WebUI 与服务健壮性增强**：`webroot/index.html` 增加 `<link rel="icon" href="data:,">` 消除 `favicon.ico` 404 报错，补全 `tun+` 绕过状态展示与 15s Bridge 超时看门狗；`service.sh` 补充 `PATH` 兜底与 `disable` 开关防御。

## v3.1.0 - 2026-11-21（主线升级）

### 终极极简架构：0 常驻 Shell 进程 + 内核原生 0ms 双轨分流
- **内核原生 0ms 双轨分流**：在 `ADGUARD_REDIRECT_DNS` 与 `ADGUARD_BLOCK_DNS` 规则链顶部注入静态内核规则 `-o tun+ -j RETURN`。当 Clash VPN 开启时，tun 接口 DNS 流量由 Linux 内核路由表在数据面实现 0ms 原生绕过；彻底废除 `ip monitor link` 后台网络监听进程与 iptables 动态反复重写。
- **单 inotifyd 启停熔断闭环**：利用系统内置轻量 C 二进制 `inotifyd` 监听 `/data/adb/agh/bin:nd`（仅 `agh.pid` 增删）。AGH 停止时 `<100ms` 自动将 Clash 熔断降级至 `223.5.5.5`（杜绝断网），AGH 启动时 `<100ms` 自动恢复 `127.0.0.1:5591` 并补全内核豁免。
- **0 常驻 Shell 守护**：常驻进程由 v3.0 的 2 个进程收敛至仅 1 个原生 C 语言 `inotifyd` 监听器（~200KB 内存，0 个常驻 `sh` 进程，稳态 0 CPU Ticks）。
- **权限与上下文严格无损**：`patch_clash` 采用 `cat tmp > "$CFG"` 覆写策略，严禁 `mv` / `sed -i`，保证 UID、GID 与 SELinux 扩展上下文完全保真。

## v3.0.0 - 2026-11-19（主线重构）

### 重大架构重构：最小必要原则与极简零功耗架构
- **架构收敛**：从 8 个脚本收敛为单一核心 `module/scripts/netguard.sh`，模块物理文件缩减为 5 个核心文件，废除所有冗余功能。
- **进程模型优化**：废除 `guard.sh` 多路管道与 inotifyd，采用原生 mksh 协同进程（`ip monitor link 2>/dev/null |&`），常驻进程数由 7 个严格降为 2 个，小核绑定，稳态 0% CPU 消耗。
- **纯内核只读判定**：彻底废除 `probe.sh`（0 主动发包）与 `do_agh_guard`（0 篡改 AGH 配置），废除 `kill -HUP` 信号干预，退守内核 `/proc`、`/sys` 状态只读探测。
- **对称双轨防护**：修复 `do_attach` 遗漏 IPv6 `ADGUARD_BLOCK_DNS` 阻断规则的问题，实现 IPv4 53 劫持与 IPv6 53 阻断的双向对称摘除与恢复。
- **Clash 补丁容错增强**：`patch_clash` awk 正则全面增强，支持 YAML 行尾注释、行内数组与中文规则名，AGH 宕机自动触发 223.5.5.5 熔断 fallback。
- **单屏极简 WebUI**：将 38KB 控制台精简至单屏卡片（<6KB），彻底消除后台轮询定时器（0 `setInterval`），按需读时对齐。
- **守护健壮性**：`service.sh` 引入 `nohup` 异步脱钩与防 PID 复用误杀校验；`uninstall.sh` 修复 `pkill -P` 短路缺陷。

## v2.3.2 - 2026-11-14（主线提交）

### 修复：rules_audit 在轨道 B 下的假阳性 WARN 误报
- **根因**：`rules_audit.sh` 仅依据 `AGH_PID != 0 && HIJACK != 1` 判定为不对称缺陷态并告警。但在 `auto` 模式（轨道 B，VPN 开启且主动摘除 53 劫持）或存在 `rescue.removed` 时，该拓扑属于完全正常的预期状态。
- **修复**：对齐 `guard.sh` 与 `probe.sh` 判据，当处于 `auto` 模式或存在 `rescue.removed` 标记时，输出 `OK AGH 进程存活，当前处于轨道 B (劫持已按预期摘除)` 且不累加 WARN 计数。

### 增强：AGH 上游看门狗与巡检时效
- **正则补齐**：`AGH_UNSAFE_PATTERN` 补齐匹配域名形态 DoH（`^[[:space:]]+-[[:space:]]+https://[a-zA-Z]`），杜绝因 `https://doh.pub/dns-query` 引发 bootstrap UDP/53 回环风险。
- **消除空窗期**：`guard.sh` 将巡检判定由取模等于 0 改为等于 1，在守护进程启动第 1 轮（第 0 秒）立即执行一次 CMFA 与 AGH 上游巡检，消除启动后首轮 7.5 至 15 分钟的延迟盲区。
- **卸载热重载**：`uninstall.sh` 在还原 Meta profile 备份后，若检测到 CMFA 运行中则广播发送 `PROFILE_CHANGED`，使内存中 mihomo 即刻生效。

### 升级：WebUI 状态展示与辅助徽章
- **AGH 上游状态行**：在「模式与 DNS 集成」卡片新增 `AGH 上游状态`，实时展示 `纯国内 IP DoH`、`含风险上游（看门狗将自动修正）` 等状态徽章。
- **集成状态辅助徽章**：`st_integ` 并列渲染 `GEOIP兜底` / `缺GEOIP`、`已备份`、`已漂移` 等紧凑辅助徽章。
- **热重载提示文案**：全面更新 WebUI 提示说明，写明自动广播触发 Clash Meta 热重载机制。

## v2.3.1 - 2026-11-11（主线提交）

### 修复：BusyBox nc 探针回归（probe_dns / filter_probe 静默失败）

**根因**：v2.3.0 将 `/data/adb/ksu/bin` 置于 PATH 开头，导致 `probe_dns()` 和
`filter_probe_domain()` 实际调用 BusyBox `nc`。BusyBox nc 在管道 stdin EOF 后
立即关闭 socket 返回，不等待 UDP 回包，造成探针始终返回空输出。

**后果**：
- `health_gate` 判定 "AGH not answering on 5591"，永久阻塞 `controller.sh attach`
- `filter_probe` 始终输出 `UNKNOWN`，WebUI 过滤状态误显示为未知
- 实际上 AGH 5591 一直在线，仅探针侧工具出错

**修复（env.sh，v2.3.1）**：
- PATH 由开头预插改为末尾追加（ksu/bin 降为兜底，不再覆盖系统 toybox）
- `probe_dns()` 和 `filter_probe_domain()` 显式调用 `/system/bin/nc`（toybox），
  回退到裸 `nc` 仅当 `/system/bin/nc` 不可执行时

### 修复：AGH upstream 防漂移看门狗

**背景**：v2.3.0 人工移除了 `1.12.12.12`，但 AGH 模块升级后 `AdGuardHome.yaml`
会被重写，危险条目可能回流。

**变更**：
- **`rules_audit.sh`**：新增对 `1.12.12.12`（APNIC Anycast）和域名形 DoH
  （如 `doh.pub`）的 WARN 告警，与已有的 `1.1.1.1/8.8.8.8` 检查并列
- **`config_toggle.sh`** 新增 `agh_guard` 子命令（`do_agh_guard()`）：
  - 检测 yaml 中 `1.12.12.12/1.1.1.1/8.8.8.8` 存在性
  - 自动重写 `upstream_dns/fallback_dns/bootstrap_dns` 为纯 IP CNDoH
  - 首次修改前 `cp -a` 保存 `AdGuardHome.yaml.orig` 备份（不覆盖已存在备份）
  - 验证新 yaml 合法后 `cat > target`；仅在 PID cmdline 确认 `AdGuardHome` 时发 SIGHUP
- **`guard.sh`**：每 10 轮调用 `config_toggle.sh agh_guard`，实现周期性防漂移
- **`uninstall.sh`**：卸载时若存在 `AdGuardHome.yaml.orig` 则恢复原始 yaml，
  并向存活 AGH 进程发 SIGHUP

## v2.3.0 - 2026-11-10（主线提交）

### 修复：代理节点流量异常增加（取证确认的三条根因）

**根因 1：AGH upstream 1.12.12.12 进入 tun0 走代理节点**
- AGH 的 `upstream_dns` 包含 `https://1.12.12.12/dns-query`；1.12.12.12 作为
  APNIC Anycast 地址进入 tun0 后，在 Fake-IP 轨道 B 下 cn-ip 规则带 `no-resolve`
  跳过，又无 `GEOIP,CN,DIRECT` 兜底，全部落入 `MATCH,proxy` 走代理节点。
  从设备端日志实证：AGH bin.log 大量 `1.12.12.12:443 timeout/EOF`，tun0 RX 达 944 MB。
- 修复：在设备端 `/data/adb/agh/bin/AdGuardHome.yaml` 中将 `upstream_dns` 移除
  `1.12.12.12`，统一使用纯 IP 格式国内 DoH（`223.5.5.5`、`223.6.6.6`）。

**根因 2：config_toggle apply 从未成功执行，DNS 集成名义 on 但内存无效**
- 取证实证：`status = unpatched backup=no drifted=no`，说明 NS5591 从未写入，
  marker 也不存在，do_auto 看门狗故意跳过（v2.2.5 的防风暴保护机制）。
- `patch_nameserver` 仅修改磁盘文件，CMFA 在 VPN 存活期间不会自动重载，
  导致即便磁盘已打补丁，mihomo 内存中依然跑原始配置。

**根因 3：GEOIP,CN,DIRECT 缺失导致 Fake-IP 轨道 B 国内流量落入 MATCH**
- 轨道 B（hijack=0）下 App 拿到 Fake-IP（198.18.x.x），cn-ip 规则带 `no-resolve`
  对 Fake-IP 直接跳过，若无不带 `no-resolve` 的 `GEOIP,CN,DIRECT`，所有未命中
  域名规则的国内流量 100% 落入 MATCH+proxy。

### 功能变更

- **`config_toggle.sh`（v2.3.0）**：
  - `do_apply` 新增 `patch_geoip_rule()`：在 `- MATCH` 前注入
    `- GEOIP,CN,DIRECT`（幂等，已存在时跳过），防止 Fake-IP 在轨道 B 下泄漏到代理。
  - `do_apply`、`do_revert`、`do_auto` 完成写盘后调用 `broadcast_reload()`，
    向 CMFA 发送 `ACTION_PROFILE_CHANGED` 广播，触发 mihomo 内存热重载，
    消除「磁盘已打补丁但内存仍跑旧配置」的盲区。
  - `do_auto` 增加内容漂移再打逻辑：订阅更新后 marker MD5 变化（即便 NS 仍在）
    也触发 `do_apply` 以恢复 GEOIP 规则并刷新 marker。
  - `do_status` 新增 `geoip: yes/no` 字段。
- **`env.sh`（v2.3.0）**：
  - PATH 预插 `/data/adb/ksu/bin`（KernelSU busybox，存在时才加）。
  - `dns_latency_ms` 改用 `--head` 只发 HEAD 请求，避免拉取页面正文穿透 tun0。
- **`customize.sh`（v2.3.0）**：
  - 版本号从 `module.prop` 动态读取，消除硬编码 `v2.2.1` 残留。
  - 安装时检测旧 `run/` 目录，自动迁移 mode/integration/events.log/config/backups
    到新模块路径，升级不再丢失用户设置与历史数据。
- **`tests/test_config_toggle.sh`（v2.3.0）**：
  - 新增：GEOIP 注入断言（inline/block 两形态）、幂等性断言、订阅漂移后 do_auto
    恢复 GEOIP 的场景、`status` 包含 `geoip:` 字段断言。

## v2.2.5 - 2026-11-06

### 修复（零网络干预，隔离回归 24/24 通过）

- `config_toggle.sh` 支持**块列表格式**的 `nameserver:`（此前只认行内数组，遇到
  `nameserver:` + `- item` 的 profile 会永久 `FAIL: ambiguous nameserver lines (0)`，
  即 10-28 那 27 次补丁风暴的根因）；新增 awk 生成器，同时保留行内数组支持，
  并用截断重写保留 uid/SELinux context。
- 集成看门狗改为「只重打本模块曾经打过、后被覆盖的补丁」（marker 存在才动作）：
  不再见到 unpatched 就重打，避免覆盖用户手工配置的国内 DoH、也杜绝空转风暴。
- `rules_audit.sh` 修正误报：`RULE-SET,cn` / `cn-ip` / `GEOSITE,CN` 属等价的
  域名层直连覆盖，输出 INFO 而非 WARN；仍建议补 `GEOIP,CN,DIRECT` 作为 IP 兜底。
- 新增 `tests/test_config_toggle.sh`（隔离目录，覆盖两种 YAML 形态、备份/还原、
  看门狗两类场景与审计判据）；`verify_consistency.py` 增加对应源码断言。

## v2.2.4 - 2026-11-05

### 文档与 WebUI 说明一致性（零守护逻辑改动）

- 修正安全边界的反向陈述：「AGH 不应答时任何切换都会被拒绝」改为 `attach` 需健康门、`detach` 为 fail-open 救援方向（AGH 不健康时仍执行并记 RESCUE）。UI、README、Wiki 全部同步。
- 修正「只看不动 = 零干预」的过度承诺：明确 DNS 集成的备份/漂移重打/还原独立于模式，采样本身会产生少量测试流量。
- 状态机说明补充 v2.2.3 的例外：`auto` 模式或存在 rescue 标志时，AGH 存活 + 劫持摘除判为 `NORMAL`（轨道 B），不再误报「不一致」。
- 补齐使用流程断点：开启/关闭 DNS 集成均需重开一次 VPN 生效；自动切换需连续 2 轮（约 3 分钟）且切换本身不立即改变拓扑；动作结果带增加后续预期提示。
- 区分「AGH 未运行」（探针 SKIP）与「AGH/Clash 均未安装」（300 秒退避空载）；后台采样周期说明补充空载例外。
- WebUI 版本号改为由 `webui.sh` 读取 `module.prop` 动态注入；`build_zip.py` / `verify_zip.py` 共用同一版本源；新增 `verify_consistency.py` 与 CI 断言，防止文档与代码再次漂移。
- 事件日志按钮扩展到最近 50 条；危险动作与只读诊断分组标注；探针/日志年龄徽章增加就地解释。

## v2.2.3 - 2026-10-29（主线提交，未打 tag）

- 状态分类器把 `auto` 模式 / rescue 标志下的轨道 B 判为 `NORMAL`，修复用户实际看到的「不一致」误报；`probe.sh` 同步输出轨道 B 说明。

## v2.2.2 - 2026-10-29（主线提交，未打 tag）

- `controller.sh` 的 detach 改为 fail-open：AGH 死亡/不应答时不再被健康门阻断 DNS 黑洞自救；attach 仍严格门控。WebUI 确认文案与底部边界同步。

## v2.2.1 - 2026-10-24

### 修复

- WebUI 启动时真正启用“每 30 秒自动刷新”；此前复选框默认勾选，但定时器未初始化。
- `webui.sh` 在体检、审计、统计、日志、模式切换、DNS 集成和劫持切换后正确传播
  退出码；界面不再把失败显示为成功。
- 模式显示统一采用 controller 的实时 `mode=`，避免切换后头部状态与详情卡相互矛盾。
- 首次打开时过滤探针显示“未检测”，不再使用容易误解的 `--`。
- `BLOCKED + UNKNOWN` 探针组合改为“双探针结果不一致”，移除未经证实的
  “AGH 退化，建议重启”结论。
- querylog 年龄不再单独触发黄色告警；无新查询不能直接判定 AGH 故障。

### 文档与发布

- README 重写为安装、使用、安全边界和开发入口。
- 新增 GitHub Wiki：安装升级、WebUI、架构、故障恢复、开发验证。
- 新增项目简介、仓库主题、自动发布流程和 WebUI Chromium 回归测试。
- 版本统一提升至 `v2.2.1`，`versionCode=23`。

## v2.2.0 - 2026-10-16

### WebUI 交互重做

- 新增轻量 `status_fast`，首屏跳过最慢的 DNS 探针，避免打开面板即占用全局操作锁。
- 新增 sticky 顶部状态条、快照年龄、就近结果反馈和面板内确认。
- 移除阻塞式 `window.confirm`；忙碌点击不再静默丢弃。
- 集成状态以活动 profile 是否实际含 `NS5591` 为准，标志文件仅作兜底。
- 构建脚本排除编辑器备份和点文件。

## v2.1.0 - 2026-10-15

### 性能与无依赖降级

- 过滤探针并行执行，DNS 延迟改为并发采样，端口探测与 querylog 统计减少遍历。
- WebUI 增加单飞任务锁、按钮忙碌态、进度提示和 90 秒看门狗。
- AGH / Clash 缺失时即时 SKIP 并进入纯观测空载，guard 使用 300 秒退避。
- 修复 toybox `flock -w` 不兼容、部分脚本无条件 `exit 0` 和硬编码路径问题。
- 空载模式不产生 netfilter 规则，实测 guard CPU 为零 ticks。

## v2.0.0 - 2026-10-15

### 双轨架构

- 引入 VPN 关闭 / 开启时的 DNS 双轨拓扑。
- 新增 `observe` 与 `auto` 模式，以及 VPN 滞留防抖和健康门控切换。
- 新增 Clash Meta 活动 profile 的 DNS 集成、原始备份、漂移检测和自动重打。
- 新增过滤探针、活动客户端识别、querylog 统计和规则审计。
- 卸载时自动还原 profile 补丁与模块摘除的 AGH 劫持。

## v1.0.1 - 2026-10-15

### 稳定性

- DNS 延迟探测降频，告警只使用新鲜样本。
- kill 旧 guard 前校验 PID 对应 cmdline，避免 PID 复用误杀。
- `run/config` 增加白名单校验，拒绝非赋值语句。
- 状态迁移时立即执行一次规则审计。

## v1.0.0 - 2026-10-15

- 首个 KernelSU DNS / VPN 观测守护版本。
