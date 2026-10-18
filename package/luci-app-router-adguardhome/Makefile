include $(TOPDIR)/rules.mk
PKG_NAME:=luci-app-router-adguardhome
PKG_VERSION:=1.0.0
PKG_RELEASE:=1
PKG_LICENSE:=MIT
include $(INCLUDE_DIR)/package.mk
define Package/luci-app-router-adguardhome
  SECTION:=luci
  CATEGORY:=LuCI
  SUBMENU:=3. Applications
  TITLE:=AdGuard Home management entry
  DEPENDS:=+luci-base +adguardhome
  PKGARCH:=all
endef
define Build/Compile
endef
define Package/luci-app-router-adguardhome/install
	$(CP) ./files/* $(1)/
endef
$(eval $(call BuildPackage,luci-app-router-adguardhome))
