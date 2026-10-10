# Cudy TR3600 OpenWrt

适用于 **Cudy TR3600 v1 / V1.0（R126）** 的自用 OpenWrt 固件，基于 [hyqhyq3/openwrt-cudy-tr3600](https://github.com/hyqhyq3/openwrt-cudy-tr3600) 制作，补充 USB 驱动、客户端管理和常用插件。

OpenWrt 25.12-SNAPSHOT · Linux 6.12.94 · 中文 LuCI · Argon

[固件下载](#下载) · [功能](#功能) · [刷机说明](#刷机说明)

## 功能

| 分类 | 内容 |
| --- | --- |
| 界面 | 中文 LuCI、Argon 主题、亮色 / 暗黑模式 |
| 代理 | OpenClash，内置 Mihomo arm64 内核 |
| VPN | Tailscale、ZeroTier、WireGuard，配套 LuCI 页面 |
| DNS | HTTPS DNS Proxy，中文 DoH 配置界面 |
| 文件共享 | Samba4、USB 硬盘挂载 |
| 存储驱动 | USB 3.0、UAS、ext4、NTFS3、exFAT、FAT32 |
| USB 上网 | Android / iPhone 网络共享、Realtek USB 网卡、QMI / MBIM 驱动及工具 |

### 客户端管理

在「状态 → 客户端管理」查看各设备的 IP、在线状态、连接方式、实时速率和累计流量，支持修改别名、加入黑名单、设置上下行限速。

卡片按设备单列排列，支持搜索，IPv6 地址可展开查看；无线设备标注频段和 BE / AX / AC / N，有线设备显示「有线」。

累计流量重启后清零。限速为速率上限控制，不含 SQM；统计和限速需要关闭流量分载。

### USB 管理

在「系统 → USB 管理」查看已连接的设备、硬盘分区和驱动状态，也可以配置手机或 USB 网卡上网。USB 状态同时显示在状态概览中。

手机开启 USB 共享后，在页面启用 USB 上网即可。有线 WAN 默认优先，USB 作为备用；目前需要手动启用，不支持插线自动配置或上游断网检测。

### 散热风扇控制

查看温度和风扇输出，支持自动、加强、全速三种模式，重启后保留设置。

## 下载

**[2026-10-07 固件及配套软件包](https://github.com/EDBWDY/cudy-tr3600-openwrt/releases/tag/2026.10.07)**

在 Release 页面的 Assets 中下载固件和配套软件包。

该版本未包含客户端管理插件，改动已经提交，但未测试重新构建。

| 文件 | 用途 |
| --- | --- |
| `openwrt-mediatek-filogic-cudy_tr3600-v1-squashfs-sysupgrade.bin` | 刷机、升级 |
| `openwrt-mediatek-filogic-cudy_tr3600-v1-initramfs-kernel.bin` | 内存启动、恢复 |
| `same-build-packages.tar.gz` | 同次构建的软件包和内核驱动 |

校验值及检查报告随包提供。内核驱动请使用配套软件包，避免混装不同 ABI 的 `kmod-*`。

## 刷机说明

仅适用于 **TR3600 v1 / R126**。刷前备份配置，用网线连接 LAN 口并保持供电。

- **原厂系统：** 先按 [Cudy 官方开发包](https://www.cudy.com/zh-cn/pages/download-center/tr3600-1-0)说明刷入过渡固件，再刷本项目的 `sysupgrade.bin`，首次迁移不保留配置。
- **兼容的 OpenWrt：** 在「系统 → 备份与更新」上传 `sysupgrade.bin`，核对校验值并通过兼容性检查后升级。
- **恢复原厂：** 参考 [Cudy TFTP 恢复说明](https://docs.cudy.com/faq/10002_How_to_recover_Cudy_devices%27_firmware_via_TFTP/)，本项目未实测该恢复流程。

默认管理地址：`192.168.1.1`

## 致谢

- [openwrt/openwrt](https://github.com/openwrt/openwrt) 与 [openwrt/openwrt#24596](https://github.com/openwrt/openwrt/pull/24596) 的 TR3600 适配贡献者
- [hyqhyq3/openwrt-cudy-tr3600](https://github.com/hyqhyq3/openwrt-cudy-tr3600)
- [Cudy](https://www.cudy.com/zh-cn/pages/download-center/tr3600-1-0)
- [vernesong/OpenClash](https://github.com/vernesong/OpenClash)、[MetaCubeX/mihomo](https://github.com/MetaCubeX/mihomo)、[jerrykuku/luci-theme-argon](https://github.com/jerrykuku/luci-theme-argon)、[immortalwrt/luci](https://github.com/immortalwrt/luci)
