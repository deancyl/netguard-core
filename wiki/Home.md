# NetGuard-Core Wiki

NetGuard-Core (前身 RMG NetGuard) 是面向 Android / KernelSU 的极简零常驻 DNS 双轨守护模块，专为解决 AdGuard Home 与 Clash Meta / mihomo 的 DNS 冲突而重构。

基于 Linux 内核数据面 0ms 旁路与 inotifyd 秒级熔断机制，稳态 0 常驻 Shell 进程；不改动任何系统分区，深度兼容临时 Root（如 CVE-2026-43499 / late-load）与常规完整 Root 环境。

## 快速入口

- [安装与升级](安装与升级)：前置条件、刷入、临时 Root 热安装、卸载和回滚。
- [WebUI 使用](WebUI-使用)：状态含义、按钮操作与极简架构。
- [架构与工作模式](架构与工作模式)：内核数据面 0ms 双轨分流、单 inotifyd 熔断看门狗。
- [故障排查与恢复](故障排查与恢复)：DNS 黑洞救援、状态自愈与 Action 脚本。
- [开发与验证](开发与验证)：构建、一致性测试门禁和代码结构。

## 当前版本

- 主线版本：`v3.1.1`（`versionCode=36`，已合入 `main` 并部署验证设备）
- 模块 ID：`rmg_netguard`
- 已验证环境：KernelSU 3.3.1 late-load、Android 16、SM-S9180
- 详细变更记录：[CHANGELOG](https://github.com/deancyl/netguard-core/blob/main/CHANGELOG.md)

## 核心设计原则

- **内核原生 0ms 放行**：通过 `-o tun+ -j RETURN` 静态内核规则实现 VPN 数据面直通，废除常驻网络监听进程。
- **0 常驻 Shell 进程**：稳态下 0 个后台 `sh` 进程，仅依托系统轻量 C 程序 `inotifyd` 监听 `agh.pid`。
- **<100ms 快速熔断**：AGH 异常退出时自动将 Clash Meta 降级至阿里公共 DNS (`223.5.5.5`)，防全机断网。
- **KernelSU 官方规范完全遵循**：提供卡片 Action 按钮（`action.sh`）、热安装支持（`hotinstall.sh`）与 <6KB 零定时器 WebUI。
- **绝对不修改系统文件**：零修改 `/system` 分区，支持临时 Root 与常规 Root 安全使用。
