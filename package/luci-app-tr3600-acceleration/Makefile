include $(TOPDIR)/rules.mk
PKG_NAME:=luci-app-tr3600-acceleration
PKG_VERSION:=1.0.6
PKG_RELEASE:=1
PKG_LICENSE:=MIT
include $(INCLUDE_DIR)/package.mk

define Package/luci-app-tr3600-acceleration
  SECTION:=luci
  CATEGORY:=LuCI
  SUBMENU:=3. Applications
  TITLE:=TR3600 acceleration manager
  DEPENDS:=+luci-base +rpcd +ucode +ucode-mod-fs +ucode-mod-uci +firewall4 +flock
  PKGARCH:=all
endef

define Build/Compile
endef

define Package/luci-app-tr3600-acceleration/install
	$(CP) ./files/* $(1)/
	$(LN) tr3600-acceleration.js $(1)/www/luci-static/resources/view/network/tr3600-acceleration-v1_0_6.js
	$(LN) tr3600-acceleration.css $(1)/www/luci-static/resources/tr3600-acceleration-v1_0_6.css
	chmod 0755 $(1)/usr/libexec/tr3600-acceleration $(1)/usr/libexec/rpcd/tr3600.acceleration
endef

$(eval $(call BuildPackage,luci-app-tr3600-acceleration))
