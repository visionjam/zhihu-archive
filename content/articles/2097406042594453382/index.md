---
title: "Android 优化体验指南（四）：进阶——adb 与 Shizuku"
date: 2026-10-24
lastmod: 2026-10-24
type: articles
zhihu_id: "2097406042594453382"
zhihu_url: "https://zhuanlan.zhihu.com/p/2097406042594453382"
deleted: false
archived_at: 2026-10-24
tags: []
summary: "文章 · 2026-10-24 · 本文是《Android 优化体验指南》系列第 4 篇，共 5 篇。 对应第 6 节 + 附录 C/D。 适合：愿意动手的玩机用户；基础读者可以先跳过，不影响前 3 篇。adb 和 Shizuku 能解决系统设置够不到的部分，但权限更大、风险更高；这一篇只保留最常用的命令和回滚方法"
---

> 本文是《Android 优化体验指南》系列第 4 篇，共 5 篇。  
> 对应第 6 节 + 附录 C/D。  
> 适合：愿意动手的玩机用户；基础读者可以先跳过，不影响前 3 篇。

adb 和 Shizuku 能解决系统设置够不到的部分，但权限更大、风险更高；这一篇只保留最常用的命令和回滚方法。

> 本篇命令较多；先看 6.2 准备环境，再按 6.3 做快照，最后才动包。  
> 文末有系列导航；文中“见 3.5”指第 3 篇的 3.5 节。  
> 带「HyperOS」的小节以小米/HyperOS 3 为准；带「通用」的适用于原生 Android 和其他 ROM。

### 6. 进阶：adb 与 Shizuku

### 6.1 shell 权限的边界

adb shell 能做的：

* 列出应用、版本、安装来源、APK 路径；
* 停用/启用应用：`pm disable-user` / `pm enable`（包和数据保留）；
* 为当前用户卸载应用：`pm uninstall --user 0`（系统应用可用 `cmd package install-existing` 恢复；用户自装应用则是真正卸载）；
* 强制停止应用；
* 读取基本诊断信息（如电池、内存）。

> 关键区别：`pm disable-user` 是“停用”，包和数据都在，`pm enable` 可恢复；`pm uninstall --user 0` 对系统应用是“对当前用户移除”，对用户自装应用等于卸载，数据会被清除（除非加 `-k`），恢复要重新安装 APK/商店版。

adb shell 不能做的：

* 修改系统分区、绕过签名校验；
* 读取其他应用的私有数据；
* 保证所有厂商系统都接受某条命令（HyperOS 对部分系统应用有保护）。

### 6.2 连接 adb（USB / 无线）

**准备**：

* 电脑安装 Android Platform Tools（含 adb），或使用 scrcpy 自带的 adb；把 adb 加入 PATH。
* Windows 用 USB 时需要手机驱动；无线调试不需要驱动。
* Windows 下建议用 Git Bash/WSL；cmd/PowerShell 也能执行，但管道语法不同。
* `adb shell ...` 是电脑端执行、在手机 shell 内运行；`adb devices`、`adb pull`、`adb logcat` 是电脑端命令。

**USB**：

1. 开发者选项 → USB 调试。
2. 数据线连接电脑，手机上确认 RSA 指纹。
3. `adb devices -l` 看到 `device` 即可。

**无线（Android 11+ 无线调试）**：

1. 开发者选项 → 无线调试 → 使用配对码配对设备。
2. 电脑执行 `adb pair <手机IP>:<配对端口>`，输入手机上的配对码。
3. 再执行 `adb connect <手机IP>:<连接端口>`。
4. `adb devices -l` 确认。

**旧式无线（USB 已连接）**：

```
adb tcpip 5555
adb connect <手机IP>:5555
```

示例：手机和电脑在同一热点/局域网时，先确认手机 IP（无线调试页面或路由器客户端列表），再执行 `adb connect <手机IP>:5555`。IP 由 DHCP 分配，重连后可能变化。

常见问题：

* `unauthorized`：手机上没确认 RSA 弹窗；重新插拔、`adb kill-server` 后重试，必要时撤销 USB 调试授权。
* `connection refused`：无线调试没开、端口变了、手机换了网络；重新配对/连接。
* `offline`：连接不稳定；`adb reconnect` 或重启 adb server。

### 6.3 改动前的快照

在改任何东西之前，先保存当前状态：

```
adb shell pm list packages -3 > user-apps.txt
adb shell pm list packages -s > system-apps.txt
adb shell pm list packages -d > disabled-apps.txt
```

需要 APK 路径时用 `pm path <包名>`；更完整的清单可以用 `pm list packages -f`。

同时建一个改动日志：

```
日期 | 包名 | 动作 | 原因 | 回滚命令 | 观察结果
```

### 6.4 命令速查

> 只保留最常用的命令；复杂诊断命令不展开。默认在 `adb shell` 内执行，`adb devices`/`adb pull` 等是电脑端命令。

| 目的 | 命令 | 回滚 |
| --- | --- | --- |
| 列出用户应用 | pm list packages -3 | — |
| 列出系统应用 | pm list packages -s | — |
| 停用/启用 | pm disable-user --user 0 <包名> / pm enable --user 0 <包名> | 反向命令 |
| 对当前用户卸载（系统应用） | pm uninstall --user 0 <包名> | cmd package install-existing --user 0 <包名> |
| 保留数据卸载（系统应用） | pm uninstall -k --user 0 <包名> | install-existing；用户应用需重装 |
| 查 APK 路径 | pm path <包名> | — |
| 强制停止 | am force-stop <包名> | 重新打开 |

几个注意点：

* `pm disable-user` 对受保护的系统应用可能失败；失败就停手。
* 判断系统应用用 `pm list packages -s`；`pm path` 在 `/data/app` 可能是系统应用的更新。
* 用户自装应用被卸载后，`install-existing` 无效，需要重装 APK/商店版；卸载前可以先备份 APK（`pm path` + `adb pull`），但 APK 备份不含数据。
* 一次只动一个包，观察 24 小时；恢复后验证包是否回来、通知/闹钟是否正常。

### 6.5 停用/卸载预装的决策表

> **先看这条**：停用 System UI、桌面、设置、包安装器、权限控制器等关键组件，可能导致无法开机/无法操作；重启后 adb 也可能不可用，安全模式未必能恢复。不要动这些包；准备官方线刷包/售后作为最后手段。

**相对安全、可优先考虑停用的类别**：

* 广告/分析/统计类服务；
* 重复的厂商应用（多个浏览器、多个输入法、多个视频/音乐商店）；
* 游戏中心、应用推荐、主题推荐；
* 你不用的 VR/AR、云盘、智能家居桥接；
* 演示/反馈/用户体验计划类应用；
* 与你的使用习惯无关的预装工具。

**高风险、不要轻易碰的类别**：

* 包安装器、权限控制器、设置、System UI、桌面（除非你已有替代桌面）；
* 电话、短信、通讯录/日历/媒体等 Provider；
* 蓝牙、Wi-Fi、NFC、移动网络、SIM 工具包；
* 账号、查找设备、紧急呼叫、锁屏/密码相关；
* 安全中心、应用商店（可能影响安装和权限）；
* 任何名字里带 `system`、`provider`、`service`、`framework`、`keychain` 且你不确定用途的包。

**操作方法**：

1. 先用 `pm list packages -s` 确认它是系统应用；`pm path` 在 `/data/app` 不代表一定不是系统应用（可能是系统应用的更新）。如果是用户应用，`adb pull` 只备份 APK，不备份数据；不带 `-k` 卸载会清数据。
2. 一次只停用一个包。重启前先确认桌面、设置、输入法、电话、短信正常；如果你停用了可能影响开机的组件，不要重启。重启后测试：通话、短信、Wi-Fi、蓝牙、相机、通知、支付、指纹/面部解锁。
3. 观察 24 小时；出问题按类型回滚：停用的用 `pm enable`；对当前用户卸载的系统应用用 `cmd package install-existing`；用户应用重新安装 APK/商店版。
4. 不要为了“应用列表好看”而追求数量；稳定比数字重要。

> 如果你不确定某个包的作用，先在设置里搜索它、在网上查包名，或者直接不要动。系统应用之间的依赖比看起来复杂。

### 6.6 恢复与回滚

按顺序尝试：

1. `pm enable --user 0 <包名>`（停用的应用）。
2. `cmd package install-existing --user 0 <包名>`（对当前用户卸载的**系统应用**；用户自装应用需要重装 APK/商店版）。
3. 恢复后验证：用 `pm list packages` 看包是否回来；打开应用、检查通知和闹钟。
4. 安全模式：长按电源键 → 长按“关机/重启” → 进入安全模式，排查第三方应用；它不能自动恢复你手动停用的系统包。
5. 恢复出厂设置（先备份）。
6. 官方线刷/售后（最后的恢复手段）。

> `install-existing` 只适用于系统应用；用户自装应用被卸载后，它不会把 APK 变回来。已更新的系统应用可能恢复到预装版本，更新需要重新安装。

把每次改动和回滚命令写进日志。真出问题时，你会感谢这份日志。

### 6.7 Shizuku 与常用工具

**Shizuku 是什么**：它通过 adb 或无线调试启动一个特权进程，让普通应用借用 shell 权限执行部分系统操作，不需要系统级修改。重启后通常需要重新启动 Shizuku。

**怎么开始**：

1. 从官方渠道安装 Shizuku（GitHub Releases、Google Play 或 F-Droid）。
2. 打开 Shizuku，按应用内指引启动：已连电脑就用 USB/无线调试；没连电脑就用“通过无线调试启动”。具体命令以应用内显示为准，本文不展开。
3. 启动成功后，在 Shizuku 里授权需要它的应用（Hail 等）。
4. 重启手机后 Shizuku 通常会停止，需要重新启动。

**适合用 Shizuku 做的事**：

* 冻结/停用不用的应用（如 Hail）；
* 更细的权限和 appops 管理（如 App Ops）；
* 深度清理（如清浊 `com.farplace.qingzhuo`，需 Shizuku 授权）；
* 安装/卸载辅助（部分安装器应用）；
* 自动化工具调用系统设置。

**安全建议**：

* 只给可信应用授权；不用的授权及时撤销。
* 不要在 Shizuku 里授予来源不明的插件。
* 冻结应用前确认它不是桌面、输入法、通知、支付依赖的组件。
* Shizuku 的权限来自 adb，等同于“电脑上的调试权限”；手机借给别人时注意。

### 6.8 自动化与 GKD

* **GKD** 基于无障碍服务跳过开屏广告、弹窗。规则由社区维护，可能误点或失效；建议只对常用应用启用，排除银行、支付、密码管理器等敏感应用。
* **Tasker/MacroDroid** 可以结合 Shizuku 自动切换设置（如到家开 Wi-Fi、出门关高刷），但自动化越复杂越容易出问题；从一两条简单规则开始。
* 不要写“定时杀后台”“循环清理”的自动化；这类规则通常弊大于利。

### 6.9 安全底线

* 不用来路不明的“优化模块”。
* 不关闭温控、不超频、不改分区，除非你有明确的恢复方案。
* 不把 adb 无线调试长期暴露在不可信网络；用完后关闭无线调试。
* 不把 bugreport、应用清单、日志上传到不可信的公开服务。
* 任何“一键优化脚本”先读一遍再运行；看不懂就不运行。

### 6.10 延伸阅读

* [awesome-shizuku](https://github.com/timschneeb/awesome-shizuku)：Shizuku 生态的工具与用法合集。

### 附录 C：一页纸命令清单

> 只保留最常用的几条；复杂诊断命令不展开。

```
# 电脑端
adb devices -l
adb connect <手机IP>:5555

# 设备端
pm list packages -3
pm list packages -s
pm list packages -d
pm path <包名>
pm disable-user --user 0 <包名>
pm enable --user 0 <包名>
pm uninstall --user 0 <包名>
cmd package install-existing --user 0 <包名>
am force-stop <包名>
```

### 附录 D：术语表

* **Doze**：熄屏静止后的深度省电状态，延迟网络和任务。
* **App Standby**：按使用频率给应用分桶，越不常用限制越强。
* **LMK**：Low Memory Killer，内存不足时按优先级回收进程。
* **ZRAM**：压缩内存交换区；与“内存扩展”（用存储做 swap）不是一回事。
* **Wakelock**：阻止系统休眠的锁；滥用会导致待机耗电。
* **Foreground Service**：带常驻通知的前台服务。
* **Alarm / Job**：定时唤醒与延迟任务。
* **ABI**：应用的 native 库架构，如 arm64-v8a、armeabi-v7a。
* **targetSdk**：应用目标 Android 版本，影响系统对它的行为兼容策略。
* **OAID/Ad ID**：广告标识符，可在隐私设置中重置/删除。
* **APEX**：Android 的可更新系统模块格式。
* **RRO**：运行时资源覆盖（Overlay），常用于主题和厂商定制。
* **关联启动**：应用 A 唤醒/拉起应用 B 的行为；默认建议禁止，确需时再开。
* **智能限制 / 严格限制**：HyperOS 的电池策略；原生 Android 对应“优化/受限”。
* **私有 DNS（DoT）**：用 DNS-over-TLS 加密解析；先填 specifier 再切 hostname，顺序反了可能断网。

---

**系列导航**

1. 先建立优化观，再做体检（第 0–1 节）
2. 系统设置与隐私（第 2、7 节）
3. 后台、省电、存储与流畅度（第 3–5 节）
4. 进阶：adb 与 Shizuku（第 6 节）
5. 推荐指南（第 8–9 节）

> 文中“见 6.4”指第 4 篇的 6.4 节；“见 2.1”指第 2 篇的 2.1 节。  
> 上一篇：《后台、省电、存储与流畅度》 · 下一篇：《推荐指南》。

---

原文链接：[查看知乎原文](https://zhuanlan.zhihu.com/p/2097406042594453382)
