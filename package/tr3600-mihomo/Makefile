include $(TOPDIR)/rules.mk

PKG_NAME:=tr3600-mihomo
PKG_VERSION:=1.19.32
PKG_RELEASE:=1
PKG_LICENSE:=GPL-3.0-only
include $(INCLUDE_DIR)/package.mk

define Package/tr3600-mihomo
  SECTION:=net
  CATEGORY:=Network
  TITLE:=Verified arm64 mihomo core for OpenClash
  DEPENDS:=@aarch64 +luci-app-openclash
endef

define Build/Compile
endef

define Package/tr3600-mihomo/install
	$(INSTALL_DIR) $(1)/etc/openclash/core
	$(INSTALL_BIN) ./files/clash_meta $(1)/etc/openclash/core/clash_meta
endef

$(eval $(call BuildPackage,tr3600-mihomo))
