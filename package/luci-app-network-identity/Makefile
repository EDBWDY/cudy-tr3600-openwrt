include $(TOPDIR)/rules.mk
PKG_NAME:=luci-app-network-identity
PKG_VERSION:=1.0.0
PKG_RELEASE:=1
PKG_LICENSE:=MIT
include $(INCLUDE_DIR)/package.mk

define Package/luci-app-network-identity
  SECTION:=luci
  CATEGORY:=LuCI
  SUBMENU:=3. Applications
  TITLE:=Network MAC identity profiles
  DEPENDS:=+luci-base +rpcd +rpcd-mod-file +jshn +jsonfilter +ip-full
  PKGARCH:=all
endef

define Package/luci-app-network-identity/conffiles
/etc/interface-identity/
/etc/wan-identity/
endef

define Build/Compile
endef

define Package/luci-app-network-identity/install
	$(CP) ./files/* $(1)/
	chmod 0755 $(1)/usr/libexec/interface-identity $(1)/usr/libexec/wan-identity $(1)/usr/libexec/rpcd/interface.identity $(1)/usr/libexec/rpcd/wan.identity $(1)/www/cgi-bin/wan-identity-client
endef

$(eval $(call BuildPackage,luci-app-network-identity))
