include $(TOPDIR)/rules.mk

PKG_NAME:=luci-app-tr3600-usb
PKG_VERSION:=1.1.1
PKG_RELEASE:=1
PKG_LICENSE:=MIT
include $(INCLUDE_DIR)/package.mk

define Package/luci-app-tr3600-usb
  SECTION:=luci
  CATEGORY:=LuCI
  SUBMENU:=3. Applications
  TITLE:=Cudy TR3600 USB device and tethering manager
  DEPENDS:=+luci-base +rpcd +rpcd-mod-file +block-mount +firewall4 +usbutils
  PKGARCH:=all
endef

define Build/Compile
endef

define Package/luci-app-tr3600-usb/install
	$(CP) ./files/* $(1)/
	$(LN) tr3600-usb.js $(1)/www/luci-static/resources/view/system/tr3600-usb-v1_1_1.js
	chmod 0755 $(1)/usr/libexec/rpcd/tr3600.usb
endef

$(eval $(call BuildPackage,luci-app-tr3600-usb))
