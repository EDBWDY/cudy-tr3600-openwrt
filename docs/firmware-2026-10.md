# 2026-10 固件候选与断点续编

当前目标为 Cudy TR3600 v1 / R126，固定 OpenWrt、LuCI、feeds、Linux 6.12.94、mac80211 backports 和 mt76 版本。不会远程刷机、替换正在使用的驱动或重启路由器。

## 已验证与尚未验证

[配对后端验证 39172068655](https://github.com/EDBWDY/cudy-tr3600-openwrt/actions/runs/39172068655) 完成 ARM64 内核、以太网/PPE/WED、cfg80211/mac80211、mt7996e 模块链接，并在真正运行 OpenWrt/fw4 的隔离虚拟机中通过 17 项报文测试。

测试包括端点无关映射、受限锥形按已联系的外部 IP 放行、全锥形放行、两个客户端端口冲突隔离、关闭/切换时删除旧 UDP 映射、同一 TCP 连接保持、实际软件流量分载、fw4 故障回滚及保留无关待提交配置。LuCI 的安全确认使用固定版本的实际 Class 运行时测试。

虚拟机不能验证 MediaTek 物理 DMA、WED/PPE 实际无线转发、吞吐或长时间稳定性。WED 默认为关闭；页面显示真实附加状态和日志，不能仅凭保存开关就声称正在加速。新固件须待独立镜像验证和后续受控实机测试。

## 纳入的通用修改

- 网络身份、客户端管理和 USB 管理；不导入保存的个人方案、别名或设备标识。
- 信道分析坐标、带宽/技术/加密显示和 TR3000 驱动适配源码。
- Argon 响应式表格、挂载点、服务控制、Tailscale 表格与按钮布局；保持已有主题样式。
- AdGuard Home 管理入口及通用可选域名列表；不导入 DNS 查询记录、客户端设置或私人规则。
- 匹配的 WED3.1/mt76 移植和真正控制 fw4/PPE/内核 NAT 的 TurboACC；替代旧加速插件，避免两个控制器同时写入。

公有提交仅导入审查过的源码快照，没有导入私有 Git 历史、系统备份、密码、订阅、VPN 身份或运行配置。执行 `python3 scripts/public_source_audit.py` 重新检查整个公开快照；固件内容还有独立的隐私检查。

## 构建顺序

1. **tools**：准备固定版本源码，下载校验过的源包，编译工具与交叉编译器。
2. **rust**：恢复 tools 完整检查点，编译 Rust/LLVM。
3. **firmware**：恢复 rust 完整检查点，编译内核、软件包和固件。
4. **先保存**：收集固件及同次构建的软件包，立即上传 `candidate-*` Release，然后保存完整编译检查点。
5. **独立验证**：另一任务恢复已编译目录，只运行镜像检查和回归测试，不运行 make。报告单独追加到已存在的候选 Release；测试失败不会删除已上传的固件或检查点。

每一编译阶段均预留检查点上传时间。超时或失败照样保存已完成的工作，状态记录 `stage_complete=false`，之后续编同一阶段，禁止误跳到后续阶段。上个阶段成功才自动进入下个阶段。

## 检查点

检查点是 GNU PAX tar + zstd 流式压缩的完整 OpenWrt 构建目录，保留 stamp、硬链接、纳秒时间戳和 dl 下载包；不重新 checkout 编译子目录。保留上游公开源码的 Git 对象、refs 和 index，以维持 getver/LuCI 包版本；排除可能携带凭据的 Git 配置、hooks 和主目录状态。每个 128 MiB 压缩块用 AES-256-GCM 认证加密后上传 Release，最后才上传完整清单；中断的上传不会被误当作完整检查点。

恢复密钥是 `TR3600_CHECKPOINT_KEY_V1` Actions Secret，只在保存/恢复步骤可用，编译步骤不能读取该环境变量。它也保护构建系统生成的包签名私钥。不要删除这个 Secret，否则既有检查点无法恢复。

恢复时校验加密块、源码配方、配置和绝对路径。修复独立验证器或测试文件不改变编译指纹，因此可以对已有固件重新验证；修改内核、驱动或其他编译输入会被拒绝静默复用旧目录。

用 `build.yml` 的 `start_stage` 和 `resume_release` 从检查点继续。只重新验证时运行 `verify-candidate.yml`，提供 firmware 检查点标签、已有候选 Release 标签和公开的验证源码 ref。工具链和产物不占用 Actions artifact/cache 配额。

修复目标驱动补丁或自定义软件包后，可显式选择 `refresh_target` 继续。它只允许审查过的目标源码变化，固定源码版本、主机编译设置和目标架构必须保持一致；重新准备配对补丁，清理受影响的目标构建目录，保留交叉编译器与 Rust。涉及内核补丁时清理内核及其外部模块目录，避免混入旧 ABI 模块；还会删除旧镜像，防止新编译失败后误上传旧文件。完整 Rust 检查点需通过有时限的真实 GCC/Rust 依赖复用检查。独立验证不能使用此选项偷偷修改已有固件。

## 上游

- [OpenWrt](https://github.com/openwrt/openwrt) 与 [mt76](https://github.com/openwrt/mt76)
- [MediaTek OpenWrt feeds](https://github.com/mediatek/mtk-openwrt-feeds)
- [TurboACC 原始界面与实现](https://github.com/padavanonly/immortalwrt-mt798x-6.6)
- [固定版本与适配范围](../experiments/turboacc/README.md)

源版本和补丁 SHA256 随镜像的 `/usr/share/turboacc/port-manifest.json` 提供。未移植的厂商扩展详见实验目录的 `port-scope.json`；不将其描述为完整厂商驱动等价替换。
