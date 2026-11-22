# NetGuard-Core v3.1.1 正式发布

> **零常驻 · 零延迟 · 面向 Android / KernelSU 的极简内核级 DNS/VPN 双轨网络守卫**

NetGuard-Core (前身 RMG NetGuard) v3.1.1 正式发布！本次更新是一次里程碑式的架构飞跃与工程重构：彻底废除过去依赖后台死循环 Shell 轮询的复杂架构，退守到 Linux 内核数据面与原生系统事件触发。无论是在**常规完整 Root（KernelSU / APatch / Magisk）**还是在**临时 Root（如 CVE-2026-43499 / late-load 越狱环境）**下，均能以**稳态 0 常驻 Shell、0% CPU 占用**完美解决本地 AdGuard Home 与 Clash Meta / mihomo 的共存痛点。

---

## 🌟 核心突破与痛点直击

### 1. 稳态 0 常驻 Shell 进程，0% CPU 功耗占用
- **彻底消除后台轮询**：废除 v2.x 时代的 `guard.sh`、`probe.sh` 等 8 个常驻脚本，稳态下**不存在任何后台 `sh` / `mksh` 进程**。
- **单 inotifyd 事件驱动**：仅依靠系统内置轻量 C 二进制 `inotifyd`（仅占用 ~200KB 内存，稳态 0 CPU Ticks）监听 `/data/adb/agh/bin/agh.pid` 增删事件，实现纯事件响应，绝不主动发包、绝不频繁唤醒系统。

### 2. Linux 内核原生 0ms 双轨分流
- **数据面直通**：在 `ADGUARD_REDIRECT_DNS` 与 `ADGUARD_BLOCK_DNS` netfilter 链顶部直接注入静态内核规则 `-o tun+ -j RETURN`。
- **零延迟放行**：当 Clash/mihomo VPN 开启时，tun 接口 DNS 数据包由 Linux 协议栈在内核层直接 0ms 原生放行，无需后台脚本监听网卡状态，无需动态重写 iptables 规则。

### 3. <100ms 秒级防断网熔断机制
- **断网黑洞自愈**：当 AdGuard Home 意外崩溃、闪退或重启时，`inotifyd` 在 `<100ms` 内自动将 Clash Meta 活动配置中的上游 DNS 熔断切换至阿里公共 DNS（`223.5.5.5`），彻底杜绝全机断网黑洞。
- **瞬时恢复对齐**：当 AdGuard Home 重新启动生成 pid 时，`<100ms` 内自动恢复 `127.0.0.1:5591` 并补齐内核规则豁免。

### 4. 深度契合临时 Root 与越狱模式
- **零修改系统分区**：严禁挂载读写或篡改 `/system`、`/vendor`，所有策略均作用于 Linux 内核运行时与模块私有目录。
- **免重启热安装生效**：支持免重启热拉起，避免临时 Root 环境因软硬重启而丢失 Root 权限。

### 5. 全面补齐 KernelSU 平台契约规范
- **卡片【▶️】执行按钮恢复（`hasActionScript=true`）**：补齐 `action.sh`，在管理器卡片上一键执行秒级规则对齐、`inotifyd` 自愈检查并输出结构化中文体检报告。
- **原生热部署（`hotinstall.sh` & `customize.sh`）**：声明 `MODULE_HOT_INSTALL_REQUEST=true`，刷入更新后免重启即刻生效，避免卡片处于待重启置灰状态导致开关无法切换。
- **单屏极简 WebUI（<6KB）**：彻底去除前端轮询定时器（0 `setInterval`），按需即时对齐，新增 `<link rel="icon" href="data:,">` 消除 404 日志噪音与 15s Bridge 超时看门狗。

---

## 📦 发布资产与完整性校验

| 资产文件 | 文件大小 | SHA-256 校验和 |
|---|---|---|
| `rmg-netguard-v3.1.1.zip` | 12,950 字节 | `d87faa31b4bae666f30fbf1e1a52be952fb9dcd4ce8e4962b58a582c32273fea` |
| `rmg-netguard-v3.1.1.zip.sha256` | 100 字节 | - |

> **MD5**: `da61fe173d9002ea9f35c863b8106956`  
> **模块文件结构**: 严格收敛为 9 个核心文件，0 冗余废弃脚本，100% 纯 LF 换行符与 0 UTF-8 BOM。

---

## 🚀 安装与升级指引

### 1. 标准 Root 环境（KernelSU / APatch / Magisk）
1. 在下方 Assets 中下载 `rmg-netguard-v3.1.1.zip`；
2. 打开 KernelSU / APatch / Magisk 管理器，在模块管理中本地刷入；
3. 刷入后点击【重启】（或通过卡片开关直接启用）。

### 2. 临时 Root / 越狱环境（免重启热部署）
如处于不便重启的临时 Root 状态，可通过 Root shell 热执行：
```sh
su -c 'sh /data/adb/modules/rmg_netguard/hotinstall.sh'
```
模块将自动清理历史残留孤儿进程、注入内核规则并秒级拉起 `inotifyd` 熔断守护。

---

## 📋 变更日志 (Changelog)

- **Architecture**: 8 脚本收敛为单一核心 `scripts/netguard.sh`，删除所有旧版废弃脚本。
- **Kernel Filter**: 引入 `-o tun+ -j RETURN` 静态放行规则，0 延迟双轨分流。
- **Circuit Breaker**: 引入系统轻量 C `inotifyd`，毫秒级 AGH 崩溃熔断与自动恢复。
- **KernelSU Spec**: 增加 `action.sh`、`customize.sh`、`hotinstall.sh`，完整支持卡片操作与热升级。
- **WebUI**: 精简为单屏卡片（<6KB），0 周期定时器，消除 404 噪音与超时保护。
- **Verification**: 增加 66 项一致性门禁与 19 项端到端及对抗压测自动化测试。
