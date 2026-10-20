# Cudy TR3600 OpenWrt

适用于 **Cudy TR3600 v1 / V1.0（R126）** 的自用 OpenWrt 固件，基于 [hyqhyq3/openwrt-cudy-tr3600](https://github.com/hyqhyq3/openwrt-cudy-tr3600) 制作，加上了网络加速、USB 管理、客户端管理和一些常用插件。

OpenWrt 25.12-SNAPSHOT · Linux 6.12.94 · 中文 LuCI · Argon

[固件下载](#下载) · [功能](#功能) · [刷机说明](#刷机说明)

## 功能

| 分类 | 内容 |
| --- | --- |
| 界面 | 中文 LuCI、Argon 主题、亮色 / 暗黑模式，适配手机显示 |
| 网络加速 | Netfilter 软件分载、MediaTek PPE 硬件分载、WED 无线加速 |
| NAT | 默认 NAT、受限锥形、全锥形，可选覆盖 TCP |
| 代理 | OpenClash，内置 Mihomo arm64 内核 |
| VPN | Tailscale、ZeroTier、WireGuard，配套 LuCI 页面 |
| DNS | HTTPS DNS Proxy、AdGuard Home 及管理入口；不包含个人配置和查询记录 |
| 文件共享 | Samba4、USB 硬盘挂载 |
| 存储驱动 | USB 3.0、UAS、ext4、NTFS3、exFAT、FAT32 |
| USB 上网 | Android / iPhone 网络共享、Realtek USB 网卡、QMI / MBIM 驱动及工具 |

### 这版加了什么

网络加速换回了原来的卡片设计，软件分载、硬件分载和 WED 放在一起管理。修复了 WED 开启后 Wi-Fi 无法连接的问题，双频连接和收发已在实机验证。

NAT 保留系统默认的 MASQUERADE，也可以选受限锥形或全锥形，按需覆盖 TCP；锥形模式默认不开，启用时会提醒风险。TCP 拥塞控制也能在页面里选。

客户端管理可以看设备、流量、连接方式，改别名、拉黑和限速。网络身份用来保存、切换各接口的 MAC 和 DHCP 主机名。USB 管理把硬盘挂载、手机共享和 USB 网卡放在一个页面里，概览也能直接查看 USB 状态。

信道分析重新整理了图表，坐标放到图外，补了无线技术和简化的加密信息。顺手修了一批 Argon 排版问题，包括接口列表、挂载点、HTTPS DNS 代理和 Tailscale 的手机显示。

开启流量分载后，客户端流量统计可能不全，代理连接也不一定能分载；限速和黑名单需先关闭流量分载再使用。

### 散热风扇控制

查看温度和风扇输出，支持自动、加强、全速三种模式，重启后保留设置。

## 下载

**[2026-10-20 Final 固件及配套软件包](https://github.com/EDBWDY/cudy-tr3600-openwrt/releases/tag/2026.10.20)**

在 Release 页面的 Assets 中下载固件和配套软件包。

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

## 构建

使用公有 Actions 分阶段编译，保留工具链和完整检查点，失败后可以续编。固件先上传，再独立做验证，测试失败不会把编译产物一起丢掉。详见[构建说明](docs/firmware-2026-10.md)。

## 致谢

- [openwrt/openwrt](https://github.com/openwrt/openwrt) 与 [openwrt/openwrt#24596](https://github.com/openwrt/openwrt/pull/24596) 的 TR3600 适配贡献者
- [hyqhyq3/openwrt-cudy-tr3600](https://github.com/hyqhyq3/openwrt-cudy-tr3600)
- [Cudy](https://www.cudy.com/zh-cn/pages/download-center/tr3600-1-0)
- [vernesong/OpenClash](https://github.com/vernesong/OpenClash)、[MetaCubeX/mihomo](https://github.com/MetaCubeX/mihomo)、[jerrykuku/luci-theme-argon](https://github.com/jerrykuku/luci-theme-argon)、[immortalwrt/luci](https://github.com/immortalwrt/luci)
