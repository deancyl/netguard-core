# NetGuard-Core v3.1.2 正式发布

> **公共 Wi-Fi 网页认证 (CaptivePortal) 原生智能豁免 · 零常驻 · 零延迟**

NetGuard-Core v3.1.2 正式发布！本次更新重点解决在开启 AdGuard Home 全局劫持后，连接需要 Web 门户认证的公共 Wi-Fi（如银行访客网、机场/高铁 Wi-Fi、酒店、企业内网、星巴克等）出现 `net::ERR_NAME_NOT_RESOLVED` 导致认证页面打不开的经典顽疾。

---

## 🌟 核心突破与功能更新

### 1. 公共 Wi-Fi 网页认证 (CaptivePortal) 智能豁免
- **痛点直击**：在公共热点尚未登录认证时，手机默认仍处于无外网连接状态，Android 会将蜂窝网络作为默认出站路由。此时 AdGuard Home 配置的公网上游 DNS（如 AliDNS `223.5.5.5` 或 DoH）根本无法解析企业内网专有认证域名（例如 `cmb-oa.wifi.com -> 2.2.2.1`），且 AdGuard Home 探测局域网网关 DNS 也会因路由走蜂窝而发生超时，导致认证页报错 `net::ERR_NAME_NOT_RESOLVED` 彻底卡死。
- **内核级放行**：动态读取 Android 系统 `/data/system/packages.list`（<1ms 耗时，绝不唤醒 Java/pm），精准提取 `com.google.android.captiveportallogin` 及 OEM 定制认证组件 UID（如 `10173`、`10001`）。
- **零配置直通**：在 `ADGUARD_REDIRECT_DNS`、`ADGUARD_BLOCK_DNS` 以及 IPv6 防泄漏链中自动注入 `-m owner --uid-owner <uid> -j RETURN` 豁免规则。由于 Android 原生网络栈会将认证组件显式绑定至 `wlan0`，认证组件发出的 DNS 查询将 0 延迟直达当前 Wi-Fi 网关获取内网认证 IP，无需用户手动编写任何自定义上游规则！

### 2. 纯净度与安全性保证（零副作用）
- **常规广告拦截 100% 保持**：普通应用（浏览器、微信、游戏、系统应用）的 DNS 查询继续全量重定向至 AdGuard Home 实施规则清洗与广告拦截。
- **Clash / mihomo 兼容性完整保留**：`-o tun+ -j RETURN` 规则协同工作，VPN 代理流量与节点连接不受任何影响。
- **稳态 0 常驻守护，0% CPU 功耗**：规则注入与恢复全自动内嵌在 `sync_rules` 与 `on_agh.sh` 熔断自愈流程中，保持零后台 Shell 轮询的极致克制。

---

## 📦 发布资产与完整性校验

| 资产文件 | 文件大小 | SHA-256 校验和 |
|---|---|---|
| `rmg-netguard-v3.1.2.zip` | 13,132 字节 | `6e42795f304d5cf2b20302f3b29d870c3d7e894d8cbb994eb40c6590acf246ae` |
| `rmg-netguard-v3.1.2.zip.sha256` | 90 字节 | - |

> **MD5**: `b487bf16f4732560500ec8f0ecb89775`  
> **核心组件**: 严格收敛为 9 个核心契约文件，100% 纯 LF 换行符与 0 UTF-8 BOM。

---

## 🚀 安装与升级指引

### 1. 标准 Root 环境（KernelSU / APatch / Magisk）
1. 在下方 Assets 中下载 `rmg-netguard-v3.1.2.zip`；
2. 打开 KernelSU / APatch / Magisk 管理器，在模块管理中本地刷入；
3. 刷入后点击【重启】（或通过卡片开关直接启用）。

### 2. 临时 Root / 越狱环境（免重启热部署）
如处于不便重启的临时 Root 状态，可通过 Root shell 热执行：
```sh
su -c 'sh /data/adb/modules/rmg_netguard/hotinstall.sh'
```
模块将自动热对齐内核规则并秒级拉起 `inotifyd` 熔断守护。

---

## 📋 变更日志 (Changelog)

- **Feature**: 增加 Android `CaptivePortalLogin` 系统组件 UID 智能识别与内核 iptables/ip6tables 豁免，彻底解决公共 Wi-Fi 认证页打不开的问题。
- **Reliability**: `sync_rules` 与 `on_agh_change` 自动化纳管热点认证放行规则，AGH 重启后毫秒级自愈恢复。
- **Tests**: 全量通过 66 项一致性门禁与 27 项端到端及实机回归测试。
