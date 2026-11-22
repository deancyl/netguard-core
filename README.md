# NetGuard-Core

> **零常驻 · 零延迟 · 面向 Android / KernelSU 的极简内核级 DNS/VPN 双轨网络守卫**

NetGuard-Core 专为彻底解决 Android 环境下 **AdGuard Home (AGH)** 与 **Clash Meta / mihomo (TUN 模式)** 协同运行时的网络冲突、断网黑洞与后台功耗痛点而重构。

基于 **Linux 内核数据面 0ms 旁路** 与 **单 inotifyd 秒级熔断机制**，实现稳态 **0 常驻 Shell 进程**、**稳态 0% CPU 占用**。不篡改任何系统分区，**深度兼容临时 Root（如 CVE-2026-43499 / late-load）与常规完整 Root 环境**。

[![Latest release](https://img.shields.io/github/v/release/deancyl/rmg-netguard?sort=semver)](https://github.com/deancyl/rmg-netguard/releases/latest)
[![KernelSU](https://img.shields.io/badge/KernelSU-v3.3.1%20compliant-2ea44f)](https://kernelsu.org/zh_CN/guide/module.html)
[![Android](https://img.shields.io/badge/Android-12%20--%2016+-3ddc84)](https://github.com/deancyl/rmg-netguard)
[![Architecture](https://img.shields.io/badge/Architecture-0%20Shell%20Daemon-blue)](https://github.com/deancyl/rmg-netguard)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 为什么需要 NetGuard-Core？（直击痛点）

在 Android 上通过 Root 同时使用本地广告拦截（AdGuard Home 监听 53/5591）与代理工具（Clash Meta / mihomo 的 TUN 虚拟网卡）时，绝大多数用户都会踩进以下四大痛点：

1. **双轨流量冲突与回环暴增**  
   iptables 将全局 DNS 强行重定向至本地 AGH，而代理客户端的 TUN 网卡也尝试处理 DNS。两套规则冲突极易导致 DNS 泄漏、回流死循环、查询超时，甚至使代理节点流量异常暴增（如 Fake-IP 漏入 MATCH 规则走代理节点）。
2. **AGH 崩溃/重启引发“全机断网黑洞”**  
   一旦 AdGuard Home 进程发生闪退、升级或因内存压力被系统回收，iptables 劫持与 Clash 上游依然指向 `127.0.0.1:5591`，整台手机所有网络请求在毫秒级内全部黑洞超时，App 与网页完全瘫痪。
3. **传统看门狗后台耗电与频繁唤醒**  
   现有大多数管理脚本使用后台死循环（`while true; do sleep ...`），不断启动 Shell 进程反复轮询网络状态、执行 `ip link` 或重写 iptables 规则。这不仅增加了系统调用开销，还会造成 CPU 频繁唤醒，显著增加待机功耗。
4. **临时 Root（越狱环境 / 无法重启）的生态缺失**  
   对于临时 Root（如通过 CVE-2026-43499 提权、KernelSU late-load 或未固化环境）用户而言，**重启手机意味着丢失 Root 权限**！传统模块动辄要求软重启、依赖复杂 init 挂载，或者因卡片状态未合并导致 KernelSU 开关被锁死；业界急需一款**零修改 `/system` 分区、纯运行时调度、支持免重启热安装与热生效**的生产级守卫模块。

---

## 核心架构突破（v3.1.1 极简零功耗设计）

NetGuard-Core v3.1.1 摒弃了早期版本的复杂轮询与多脚本进程，退守到 Linux 内核数据面与原生事件触发，实现极简与稳健的统一：

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                        Linux Kernel 数据面                              │
│                                                                         │
│   App DNS 请求 ───► [ iptables: ADGUARD_REDIRECT_DNS ]                  │
│                             │                                           │
│                 ┌───────────┴───────────┐                               │
│                 ▼                       ▼                               │
│        来自 tun+ (Clash VPN)       来自 物理网卡 (Wi-Fi/Cellular)       │
│                 │                       │                               │
│       [-o tun+ -j RETURN]               ▼                               │
│                 │               重定向至 AGH 本地监听                    │
│                 ▼                (127.0.0.1:5591)                       │
│        0ms 内核原生放行直通                                             │
└─────────────────┬───────────────────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────────────────┐
│                   零常驻 Shell · 事件驱动控制面                         │
│                                                                         │
│   轻量系统 C 进程: inotifyd (监听 /data/adb/agh/bin/agh.pid)             │
│            │                                                            │
│            ├─► [AGH 退出 / 崩溃] ──<100ms 自动熔断──► Clash 换阿里公共DNS  │
│            └─► [AGH 恢复 / 启动] ──<100ms 自动对齐──► 恢复 AGH + 注入内核豁免│
└─────────────────────────────────────────────────────────────────────────┘
```

### 1. Linux 内核原生 0ms 双轨分流
在 `ADGUARD_REDIRECT_DNS` 与 `ADGUARD_BLOCK_DNS` 链顶部直接注入静态内核规则 `-o tun+ -j RETURN`。  
当 Clash VPN 开启时，tun 网卡发出的 DNS 数据包由 Linux 协议栈在内核层直接快速放行，**彻底废除后台网络监听进程与动态 iptables 重写**，0 延迟、0 丢包。

### 2. 单 inotifyd 秒级熔断保护（0 常驻 Shell）
模块稳态下**不存在任何常驻的 `sh` / `mksh` 进程**。  
仅使用系统内置轻量 C 语言程序 `inotifyd`（内存仅约 200KB，0 CPU Ticks）监听 `agh.pid`：
- **AGH 停止/闪退时**：`<100ms` 内自动将 Clash Meta 活动配置中的上游熔断降级至阿里公共 DNS（`223.5.5.5`），彻底杜绝断网；
- **AGH 重新拉起时**：`<100ms` 内自动恢复 `127.0.0.1:5591` 并补齐内核规则豁免。

### 3. 无损可逆的配置串联
- 对 Clash Meta 配置的补丁写入严禁使用 `mv` 或 `sed -i`，强制采用原子覆写（`cat tmp > "$CFG"`），100% 保持文件 UID、GID 与 SELinux 扩展上下文完全保真；
- 自动备份原始配置（`.orig`），卸载模块时完整无损还原。

### 4. 全面遵从 KernelSU 官方规范
- **补齐 `action.sh`**：模块卡片恢复 `[▶️]` 执行按钮（`hasActionScript=true`），一键完成秒级规则对齐、`inotifyd` 自愈检查并输出结构化中文体检报告；
- **原生热安装支持**：声明 `MODULE_HOT_INSTALL_REQUEST=true` 与 `hotinstall.sh`，更新刷入即刻生效，无需软重启，告别卡片置灰与开关锁定；
- **极简单屏 WebUI**：单屏卡片界面（<6KB），0 后台轮询定时器（0 `setInterval`），按需读时对齐。

---

## 新旧架构对比

| 维度 | 传统多脚本轮询 (v2.x) | NetGuard-Core 极简架构 (v3.1.1) |
|---|---|---|
| **常驻进程** | 2~7 个后台 Shell 进程 (`guard.sh`, `probe.sh` 等) | **0 个常驻 Shell 进程**（仅 1 个系统 C `inotifyd`） |
| **稳态功耗** | 定时唤醒 CPU、高频 I/O 轮询 | **0 CPU Ticks，稳态 0% CPU 占用** |
| **双轨切换** | 依赖后台网络监听脚本动态重写 iptables | **内核层静态 `-o tun+ -j RETURN` 原生 0ms 放行** |
| **断网保护** | 轮询周期较长，AGH 崩溃时存在数秒断网盲区 | **`<100ms` 硬件级 inotify 熔断降级** |
| **WebUI 资源** | 38KB 控制台，30s 周期性轮询定时器 | **<6KB 极简单屏，0 定时器，按需即时对齐** |
| **KernelSU 契约** | 缺少 Action 按钮与热部署规范 | **完整实现 Action 脚本、热安装与 WebUI** |
| **临时 Root 适配** | 需谨慎重启、易产生状态锁定 | **针对免重启与越狱模式深度优化** |

---

## 安装与快速上手

### 运行环境要求
- **Android 系统**：Android 12 ~ 16+；
- **Root 方案**：KernelSU (推荐 v3.3.1+)、APatch、Magisk；完美支持临时 Root（如 CVE-2026-43499 / late-load）；
- **前置依赖**：已安装并运行 AdGuard Home（默认监听 `127.0.0.1:5591` 或 `53`），可选配合 Clash Meta / mihomo。

### 方式 1：标准 Root 用户（常规流程）
1. 从 [Releases](https://github.com/deancyl/rmg-netguard/releases/latest) 下载最新的 `rmg-netguard-v3.1.1.zip`；
2. 打开 KernelSU / APatch / Magisk 管理器，选择模块并在本地刷入；
3. 重启设备（或直接在管理器内开启模块）。

### 方式 2：临时 Root / 越狱模式（免重启热部署）
由于临时 Root 环境重启即失，请在获得 root shell 后执行免重启热拉起：
```sh
# 1. 刷入并热解包到模块目录后执行热启动
su -c 'sh /data/adb/modules/rmg_netguard/hotinstall.sh'
```
模块会自动清理历史残留、注入内核放行规则并拉起 `inotifyd` 守护，无需软硬重启！

---

## 日常管理与界面

### 1. KernelSU 模块卡片【▶️】执行按钮
在 KernelSU 管理器的模块列表卡片上，点击【▶️】按钮将触发 `action.sh`：
- 秒级自动校验并对齐 Linux 内核 `-o tun+ -j RETURN` 规则；
- 检查 `inotifyd` 熔断看门狗是否存活，脱管时自动自愈拉起；
- 在卡片内输出结构化运行健康报告与最近 5 条事件日志。

### 2. KernelSU WebUI 控制台
点击卡片上的【`< >`】按钮唤出内置单屏 WebUI：
- **实时运行拓扑**：一屏展示工作模式、VPN 状态、53 端口劫持状态、AGH 进程与 Clash 补丁状态；
- **手动控制面板**：支持一键模式切换、劫持挂摘与串联补丁修复；
- **纯按需加载**：页面无任何后台轮询定时器，打开即拉取，关闭即休眠，彻底消除前端资源占用。

---

## 安全边界与防变砖承诺 (Anti-Brick)

1. **绝对不修改系统文件**：严禁任何挂载读写或篡改 `/system`、`/vendor` 分区的行为；所有操作均在 Linux 内核运行时调度（内存级参数、iptables 链）与模块私有数据区。
2. **防误杀机制与单例自检**：杀进程前严格核验 `/proc/<pid>/cmdline`，严防 PID 复用误杀系统核心进程（如 `system_server`、`zygote`）。
3. **Fail-Open 救援机制**：AGH 异常退出时优先摘除劫持并回退公共 DNS，确保连通性优先，绝不会将用户置于断网环境。
4. **无痕卸载**：模块卸载时自动调用 `uninstall.sh`，彻底清理全部添加的 netfilter 规则、恢复 Clash Meta 原始备份配置，并清理运行标记。

---

## 验证与测试套件

本项目具备极高标准的工程交付纪律，内置四阶分层回归测试与一致性门禁：

```sh
# 1. 架构不变性与关键说明一致性门禁 (66 项断言)
py -3 verify_consistency.py

# 2. 物理 Zip 包卫生检查 (0 CRLF, 0 BOM, POSIX 权限)
py -3 verify_zip.py

# 3. 完整四阶功能与边界测试套件 (Awk 补丁、状态 Schema、熔断状态机)
py -3 tests/test_v3_suite.py
```

---

## 版本信息

- 当前主线版本：`v3.1.1`（`versionCode=36`）
- **模块唯一 ID**：`rmg_netguard`
- **项目仓库**：[deancyl/rmg-netguard](https://github.com/deancyl/rmg-netguard)
- **作者**：`Deancyl`
- 详细更新履历请查阅 [CHANGELOG.md](CHANGELOG.md)。
