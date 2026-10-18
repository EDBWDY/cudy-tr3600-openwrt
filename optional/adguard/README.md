# AdGuard Home

`filter-lists.json` 保存可选订阅地址，`reading-ad-domains.txt` 是补充域名规则。按需导入；不会自动修改 DNS、上游或现有规则。

这里只包含通用规则，没有 AdGuard Home 配置、账号、查询记录或设备列表。DNS 规则无法区分同一域名下的业务与广告 URL，也不会清除应用缓存。

`luci-app-router-adguardhome` 提供管理入口，依赖软件源中的 AdGuard Home，未默认选入固件。TR3000 应先确认存储空间。
