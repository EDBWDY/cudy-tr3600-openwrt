include $(TOPDIR)/rules.mk
PKG_NAME:=luci-app-tr3600-clients
PKG_VERSION:=1.0.15
PKG_RELEASE:=1
PKG_LICENSE:=MIT
include $(INCLUDE_DIR)/package.mk

define Package/luci-app-tr3600-clients
  SECTION:=luci
  CATEGORY:=LuCI
  SUBMENU:=3. Applications
  TITLE:=TR3600 client manager
  DEPENDS:=+luci-base +ucode +ucode-mod-fs +ucode-mod-uci +ucode-mod-ubus +nftables-json +kmod-nft-core +ip-full +flock +rpcd-mod-iwinfo
  PKGARCH:=all
endef

define Package/luci-app-tr3600-clients/conffiles
/etc/config/tr3600_clients
endef

define Build/Compile
endef

define Package/luci-app-tr3600-clients/install
	$(CP) ./files/* $(1)/
	$(LN) tr3600-clients.js $(1)/www/luci-static/resources/view/status/tr3600-clients-v1_0_15.js
	chmod 0755 $(1)/usr/libexec/tr3600-clients $(1)/usr/libexec/rpcd/tr3600.clients $(1)/etc/init.d/tr3600-clients
endef

$(eval $(call BuildPackage,luci-app-tr3600-clients))
