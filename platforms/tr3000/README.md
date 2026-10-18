# TR3000 适配

用于现有 ImmortalWrt / mtwifi 系统的代码差异，不能直接当作 TR3000 固件刷入。TR3600 构建不会复制此目录。

- 客户端管理从 iwinfo 获取关联设备和无线协议，识别 HNAT 对统计的影响
- USB 管理使用适配后的 RPC、权限和界面
- 信道分析包含外置坐标、深浅色文字、技术与简化加密标签
- `tr3000-channel-geometry` 调用 `tr3000-scan-export` 读取驱动扫描缓存，避免反复触发扫描
- 扫描导出器仅适配 mt_wifi 7.6.6.1 WAPP ABI；源码需要使用匹配固件的工具链编译到 `/usr/libexec/tr3000-scan-export`，其他驱动版本不能照搬
- VPN 菜单位于网络之后；使用固件自带 TurboACC，不显示重复的自制加速菜单

网络身份使用通用 `luci-app-network-identity`，mtwifi 无线接口暂不支持单独改 MAC。TR3000 没有风扇，不安装风扇插件。没有携带网络、Wi-Fi、客户端策略、VPN 或挂载配置。
