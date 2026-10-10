include $(TOPDIR)/rules.mk

PKG_NAME:=luci-app-tr3600-fan
PKG_VERSION:=1.1.0
PKG_RELEASE:=1
PKG_LICENSE:=MIT
include $(INCLUDE_DIR)/package.mk

define Package/luci-app-tr3600-fan
  SECTION:=luci
  CATEGORY:=LuCI
  SUBMENU:=3. Applications
  TITLE:=Cudy TR3600 cooling fan control
  DEPENDS:=+luci-base +rpcd-mod-file +kmod-hwmon-pwmfan
  PKGARCH:=all
endef

define Package/luci-app-tr3600-fan/conffiles
/etc/config/tr3600_fan
endef

define Build/Compile
endef

define Package/luci-app-tr3600-fan/install
	$(CP) ./files/* $(1)/
	chmod 0755 $(1)/usr/libexec/tr3600-fan $(1)/etc/init.d/tr3600-fan
endef

$(eval $(call BuildPackage,luci-app-tr3600-fan))
