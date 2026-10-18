---
name: windows-residue-cleanup
description: Windows 软件卸载 + 卸载后残留清理的完整工作流——先卸载（注册表三仓库卸载入口发现、MSI/NSIS/Inno 静默卸载参数、winget/Appx、进程/服务/计划任务前置停止、卸载失败兜底），再按 147+ 维度全扫清残留（文件目录、注册表三仓库、共享父目录如 AppData\Roaming\Tencent、共用 SDK 组件交叉判定与精准删除）。含沙箱坑位（cmd/c 拦截、PowerShell 静默失败、reg.exe 黑名单、卸载器被拦）与 Python 扫描/删除/验证模板。触发词：卸载软件、卸载《指定软件》（如"卸载迅雷"、"卸载QQ"、"卸载PS"、"怎么卸载XX"、"把XX卸了"、"XX怎么卸载"等任意"卸载+软件名"句式）、卸载不了、卸载失败、强制卸载、彻底卸载、卸载干净、没卸干净、卸载残留、清理残留、残留清理、软件残留、软件卸载不干净、删除 AppData 残留、注册表幽灵项、卸载器、WeGame/微信/QQ/Tencent 残留清理、uninstall software、uninstaller、uninstall residue、remove software、leftover cleanup。
agent_created: true
---

# Windows 软件卸载 + 残留清理（完整流程）

本 skill 覆盖**卸载软件 → 验证卸载 → 残留清理 → 复核**的完整流程：先用官方卸载入口（注册表 UninstallString / MSI / winget / Appx）静默卸载目标软件，再按 147+ 维度扫描清理残留。核心准则：**能卸载就不直接删目录**（直接删目录会留 Windows Installer 数据库不一致，后续重装/更新报错）；清理时**先交叉判定、再精准删除、最后复核**——盲目删目录会误伤正在用的软件的共享数据。

## 零、软件卸载阶段（先卸载，再清残留）

完整流程 = **卸载 → 验证卸载 → 残留清理**。直接删目录而不走卸载器，会让 Windows Installer 数据库（`HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Installer`）残留不一致，后续重装/更新报错——必须优先走官方卸载入口。

### 0.1 卸载入口发现（模板 0，只读）

注册表三仓库 `Uninstall` 键下，每个软件键都带 `UninstallString` / `QuietUninstallString`（后者是静默卸载命令，MSI/NSIS/Inno 多数有）+ `InstallLocation`。配合包管理器枚举：

| 来源 | 发现方法 | 说明 |
|---|---|---|
| 注册表三仓库 | 读 `UninstallString` / `QuietUninstallString` / `InstallLocation` | **主入口**，模板 0 |
| MSI | 键名是 `{GUID}` 时即 ProductCode，可直接 `msiexec /x {GUID}` | 无需找卸载 exe |
| winget | `winget list` / `winget search <名称>` | 可顺便 `winget uninstall` |
| UWP/Appx | `Get-AppxPackage *关键字*` | Store 应用，`Remove-AppxPackage` 卸 |
| Get-Package | `Get-Package -Name *关键字*` | PowerShell 包视图（含 MSI/Programs） |

### 模板 0：卸载入口扫描（只读，阶段一入口）

```python
# -*- coding: utf-8 -*-
import winreg
TARGET = "wegame"  # 改成目标软件名关键字（小写）
for hkey, sub, tag in [
    (winreg.HKEY_CURRENT_USER,  r"Software\Microsoft\Windows\CurrentVersion\Uninstall", "HKCU"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", "HKLM"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall", "WOW64")]:
    try:
        with winreg.OpenKey(hkey, sub) as k:
            for i in range(winreg.QueryInfoKey(k)[0]):
                try:
                    name = winreg.EnumKey(k, i)
                    with winreg.OpenKey(k, name) as sk:
                        def val(v, sk=sk):
                            try: return winreg.QueryValueEx(sk, v)[0]
                            except OSError: return ""
                        disp = val("DisplayName")
                        if TARGET not in disp.lower(): continue
                        print(f"[{tag}] {disp} v{val('DisplayVersion')} | key={name}")
                        print(f"  uninstall : {val('UninstallString')}")
                        print(f"  quiet     : {val('QuietUninstallString')}")
                        print(f"  location  : {val('InstallLocation')}")
                except OSError: pass
    except OSError: pass
```

### 0.2 卸载方式选型（静默卸载参数速查）

| 安装器 | 静默卸载命令 | 备注 |
|---|---|---|
| MSI | `msiexec /x {ProductCode} /qn /norestart` | `/qn` 无界面；防意外重启加 `/norestart` |
| NSIS | `"<安装目录>\uninstall.exe" /S` | **`/S` 大写**；卸载器一般在安装目录下 |
| Inno Setup | `"<安装目录>\unins000.exe" /VERYSILENT` | `/SILENT` 也行；`/VERYSILENT` 连重启提示一起抑制 |
| InstallShield | `setup.exe /s -f1"<iss路径>"` | 需响应文件（先 `setup.exe /r` 录制 setup.iss） |
| WiX Burn | `setup.exe /uninstall /quiet` | — |
| winget | `winget uninstall --id <id> --silent` | 按 id 精确匹配，避免名称误删别的软件 |
| UWP/Appx | `Get-AppxPackage *关键字* \| Remove-AppxPackage` | per-machine 安装的需管理员 |
| wmic（已弃用） | `wmic product where "name='X'" call uninstall` | 仅老系统兜底 |

> 以上为各安装器常见约定，实际以软件文档/卸载器 `/?` 帮助为准。**卸载动作不可逆**：执行前用 AskUserQuestion 让用户确认清单（软件名 + 版本 + 安装位置 + 数据目录大小）。

### 0.3 卸载前置：释放占用（不做会卸载失败或留半截）

按顺序执行，再跑卸载器：
1. **杀进程**：`taskkill /f /im <exe>` 或 `Get-Process *关键字* | Stop-Process -Force`（含后台守护进程，如 `<app>tray.exe`、`<app>service.exe`、`<app>daemon.exe`）
2. **停服务**：`Get-Service *关键字* | Stop-Service`（卸载器一般会自己删服务；没删掉再 `sc delete <服务名>`）
3. **停计划任务**：`Get-ScheduledTask *关键字* | Unregister-ScheduledTask`（见六·六）

### 0.4 沙箱坑位（卸载动作一律交付用户机执行）

- **沙箱内运行第三方 uninstall.exe / setup.exe 基本被程序执行黑名单拦截** → 卸载命令一律打包成 `.cmd`/`.ps1` 交付用户本机运行（同系统级清理脚本规则）
- 卸载器常触发 UAC → 交付脚本注明“右键管理员运行”
- 交付规则同原则 6：脚本头部内嵌明细 + 独立清单文件 + 同批 present_files

### 0.5 卸载验证（三必查，缺一不可）

1. 注册表三仓库 `Uninstall` 下该软件的键**已消失**
2. 进程列表无相关进程（`Get-Process *关键字*`）
3. `InstallLocation` 目录已消失（注意：目录还在 ≠ 卸载失败，多数卸载器不清数据目录——此时正是阶段二要清的残留）

### 0.6 卸载失败兜底

| 情况 | 对策 |
|---|---|
| 卸载器一闪就退/报错 | 以管理员重跑；重定向日志 `> log.txt 2>&1` 看错误码 |
| MSI 报“卸载源不可用” | `msiexec /x {code}` 重试 → 仍失败用 Microsoft Program Install/Uninstall Troubleshooter |
| 卸载器文件已损坏/丢失 | 第三方强制卸载：**Geek Uninstaller（免费轻量，优先推荐）**、Revo Uninstaller（免费版够用）、IObit Uninstaller（免费版带广告）——它们会连带扫残留键 |
| 一切手段失败 | 手动卸载 = 停进程/服务 → 删安装目录 → 删注册表卸载项 → **转入本 skill 阶段二残留清理流程**（此时"已卸载"前提成立，147+ 维度清残留） |

---

## 一、卸载残留的“十个维度”（不要只查一个）

| 维度 | 位置 | 说明 |
|---|---|---|
| ① 安装目录 | `D:\Tencent\Xxx`、`C:\Program Files\...`、`AppData\Local\Programs\Xxx` | 主程序文件，多数卸载器已清 |
| ② 用户数据 Roaming | `AppData\Roaming\Xxx` 或 `AppData\Roaming\<厂商>\Xxx` | 配置/缓存/聊天记录，**大头常在这** |
| ③ 用户数据 Local | `AppData\Local\Xxx` | 同上，Electron 应用常装 `Local\Programs` |
| ④ 注册表 | 见下"三仓库" | 卸载项、幽灵项 |
| ⑤ 共享父目录子项 | `AppData\Roaming\Tencent\Xxx` 等 | **最易漏/最易误伤**，必须按子目录名精准删 |
| ⑥ **Common Files** | `C:\Program Files\Common Files\Xxx`、`D:\Program Files\Common Files\Xxx` | **最高危遗漏路径** — 很多软件把共享 DLL/组件装这里，卸载器经常不清理。Quark 就是漏在这里 |
| ⑦ **用户 Profile 根目录** | `C:\Users\<user>\.Xxx`（隐藏点目录）、`C:\Users\<user>\Xxx`（非隐藏） | 便携版/Electron 应用常把数据存在这里（如 `.SwitchHosts`、`.codex-session-delete`、`Documents\Codex`）。**不能一刀切 skip** |
| ⑧ **公共用户 Profile** | `C:\Users\Public\` | 快捷方式、数据可能落在公共账户下 |
| ⑨ **计划任务** | `C:\Windows\System32\Tasks\` + **`Tasks_Migrated\`** | **四种形态**：已注册任务（Unregister-ScheduledTask）/ 孤立 XML / **空目录壳**（任务注销后留下的 `Updates\` 空树，按目录名枚举）/ **Migrated 迁移遗留**（Win10 升级产物，死任务 XML）。**schtasks.exe 在沙箱被拦截，必须交付 .cmd/.ps1 给用户本机管理员运行** |
| ⑩ **启动项** | HKCU/HKLM Run + RunOnce + Startup 文件夹 | 之前漏了两次才发现 |

> **⚠️ 跨盘扫描：** 安装目录不只 C 盘。`D:\Program Files\*`、`D:\Program Files (x86)\*`、`E:\` 根等都要纳入。实战踩坑：Adobe 破解重打包版常装在 **`D:\Program Files\Adobe Photoshop 2020 SP` / `Adobe Premiere Pro 2020 SP`** 这类路径，而清理脚本只扫 C 盘 `C:\Program Files\Adobe` 会**完全漏掉 D 盘 3.3GB 重打包安装包**。扫描"已卸载软件残留"时必须逐盘枚举 `Program Files*` 关键词目录（见模板 D）。

注册表三仓库（查卸载项 + 幽灵项）：
- `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Uninstall`
- `HKEY_LOCAL_MACHINE\Software\Microsoft\Windows\CurrentVersion\Uninstall`
- `HKEY_LOCAL_MACHINE\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall`

## 一·五、完整扫描维度清单（147+ 维度，2026-10-17 四轮扫描验证）

### A. 文件系统（32 维）
1. Program Files / Program Files (x86) — 所有驱动器
2. ProgramData — **所有驱动器**（不止 C:）
3. AppData\Roaming
4. AppData\Local
5. **用户 Profile 根目录隐藏点目录** `C:\Users\<user>\.<appname>`
6. **用户 Profile 根目录非隐藏目录**（深度 3，无 skip 列表）
7. 桌面（用户 + 公共）
8. 开始菜单（用户 + 公共）
9. Startup 文件夹（用户 + 公共）
10. Quick Launch
11. 下载 / 文档 / 音乐 / 图片 / 视频 —— **文档要跟着重定向走**：`C:\Users\<user>\Documents` 可能被重定向到 `E:\Documents` 等，且根目录下会有产品用户数据目录（如 `E:\Documents\Visual Studio 2022\`，删前先确认空树/缓存，防误删用户资产）
12. 字体（Fonts 文件夹）
13. **公共用户 Profile** `C:\Users\Public\` 全量
14. **驱动器根目录** `C:\` `D:\` `E:\`
15. ProgramData 深度扫描（深度 4）
16. Windows 目录（深度 2）
17. WinSxS 缓存
18. Windows Diagnostic
19. Timeline / ConnectedDevicesPlatform
20. People Hub / Contacts
21. Sticky Notes
22. 辅助技术（Voice Access / Narrator / Magnifier）
23. MSI 安装缓存（C:\Windows\Installer）
24. Windows\Temp（需管理员）
25. Prefetch（需管理员）
26. 回收站
27. WindowsApps（Store 应用）
28. Windows 可选功能（dism）
29. Jump Lists / Recent 文件夹
30. 浏览器数据目录（Chrome/Edge/Firefox/Brave/Opera）
31. Quick Access / 收藏夹 / 链接
32. Windows 库

### B. 注册表（70 维）
33. HKCU\Software 树
34. HKLM\Software 树
35. HKLM\Software\WOW6432Node
36. Uninstall 条目（HKCU + HKLM + WOW6432Node）
37. **Run / RunOnce（HKCU + HKLM）** ← 启动项，之前漏了两次
38. Services（HKLM SYSTEM Services）
39. 环境变量（HKCU + HKLM Environment）
40. App Paths
41. RecentDocs
42. COM 组件（CLSID）
43. TypeLib
44. 文件关联（Classes\*\shell\OpenWith）
45. 协议处理器（Classes\*）
46. 右键菜单（Classes\*\shell、Classes\Directory\shell）
47. Explorer 扩展（Shell Folders / MenuExts / FindExtensions）
48. 任务栏 / 开始布局
49. 字体注册表（Fonts 键）
50. 打印机（Printers + Print 键）
51. WMI 提供程序（Autologger + Enum）
52. 网络连接 / 适配器
53. 组策略（Policies + Group Policy）
54. 控制面板 Applet
55. 声音 / 主题 / 电话
56. VolumeCache / Sidekick
57. Appx 包注册
58. OLE / COM（Interface / Record）
59. COM+ / DCOM
60. GAC（全局程序集缓存）
61. .NET Framework 注册
62. Visual C++ 可再发行组件
63. Windows Update / KB
64. WER（Windows 错误报告）
65. 凭据管理器 / Vault
66. 数字证书（用户 + 根证书）
67. 电源计划
68. 鼠标 / 键盘
69. 蓝牙
70. IIS
71. MSMQ
72. Windows 搜索索引
73. Windows 库
74. Quick Access / 收藏夹 / 链接
75. 跳转列表 / Recent
76. Hosts 文件
77. PowerShell 配置文件
78. Jump Lists（注册表 Recent 键）
79. PowerShell ModulePath（HKCU + HKLM Environment）
80. 证书存储（My/Root/CA/Trust）
81. COM+ / DCOM 深度（Activations/Class/LocalService/Outgoing/Packages）
82. TypeLib 深度
83. App Paths 深度（含子键值检查）
84. AppID / DCOM
85. 应用程序兼容性（Compatibility 键）
86. Quick Access 注册表
87. 计划任务注册表（Task Scheduler）
88. OLE / COM（Interface / Record）
89. COM+ / DCOM
90. GAC
91. .NET Framework
92. VC++ Redist
93. Windows Update
94. WER
95. Credentials / Vault
96. Digital Certs
97. Power Plans
98. Mouse / Keyboard
99. Bluetooth
100. IIS
101. MSMQ
102. Search Index
103. Libraries

### C. 浏览器（6 维）
104. Chrome 扩展（所有 Profile）
105. Edge 扩展
106. Firefox 扩展
107. Brave 扩展
108. Opera 扩展
109. 浏览器配置（Chrome/Edge/Firefox 数据目录）

### D. 系统 / 其他（44 维）
110. 计划任务（目录 + 注册表）
111. MSI 安装缓存
112. Prefetch
113. Windows\Temp
114. 回收站
115. Windows 可选功能
116. Jump Lists / Recent 文件夹
117. App Execution Aliases
118. Shell Folders / User Shell Folders
119. Speech / Search / Security Zones
120. Tray Notify / VolumeCache / SharedFiles / Sidekick
121. Explorer Extensions / Applets / Control Panel
122. Themes / Sounds / Telephony
123. Group Policy / Policies / Explorer Advanced
124. MenuExts / FindExtensions
125. Streams / Taskband / Playlists / TypedPaths
126. SortOrderValues / Volc / Position
127. Defender 实时排除（Paths/Processes/Extensions）
128. 防火墙规则
129. Windows Security / Diagnostic / Clipboard
130. Gaming / Voice Access
131. Terminal / SnippingTool / Photos / Mail / Calendar / Maps / People
132. QuickAssist / MediaCenter / 3DViewer / Paint3D / Notepad / ISE / Sandbox
133. Taskbar / StartLayout
134. OLE / COM registry
135. Windows 库
136. GAC
137. COM+ / DCOM
138. Windows Optional Features
139. VC++ Redistributable
140. .NET Framework
141. Windows Update / KB
142. WER
143. Credentials / Vault
144. Digital Certificates
145. Power plans
146. Mouse / Keyboard
147. Bluetooth
148. IIS
149. MSMQ
150. Search Index
151. Libraries
152. Taskbar / StartLayout
153. OLE / COM
154. **在用系统管家的资源库**（ProgramData 下）：如联想电脑管家 `C:\ProgramData\Lenovo\devicecenter\ico\` 缓存**所有被收录软件**的图标（含已卸载的：`C盘管家.ico`、`b55a2da9.ico`（VS 实例 GUID 命名）、`极速PDF阅读器.ico`）——按产品名搜 ProgramData 只在产品自己目录下找会漏；管家进程在跑（LenovoPcManagerService），删单个 ico 可能被重建，标注即可
155. **Tasks_Migrated 树**（`C:\Windows\System32\Tasks_Migrated\Microsoft\<产品>\`，Win10 升级迁移遗留，含 Enabled=false 死任务 XML）

### E. Everything 搜索策略（推荐作为日常扫描手段）
- **Everything 是文件系统即时搜索工具**，比 Python os.walk 快几个数量级
- **用户用 Everything 搜关键字 → 截图 → 我来分析**，比脚本扫描更高效
- 关键：让用户定期用 Everything 搜索已卸载软件名，把结果截图发我
- Everything 能发现脚本遗漏的路径（如 Common Files、非 C 盘 ProgramData）

---

## 二、核心原则（踩坑换来的）

1. **共享父目录绝不动父级。** 腾讯系全家桶共用 `AppData\Roaming\Tencent`、`AppData\Local\Tencent`。只删目标子目录（如 `WeGame`、`WeMeet`、`Cross`），**永远不删整个 `Tencent` 父目录**，否则微信 1.5GB 聊天记录、QQ 数据全没了。
2. **"目录名不像在用软件"≠ 可删。** 大量"未知目录"是厂商共用底层 SDK（`TBS` 浏览器内核、`beacon` 日志、`TXSSO` 登录、`TenioDL` 下载、`libsdk`/`qimei`/`pallas`…）。QQ/微信/管家启动都依赖，删之会崩。**判定能否删走三步交叉验证：①注册表有无该软件 → ②安装目录在不在 → ③同父目录别的软件依不依赖它。**
3. **同名旧目录可能是现役数据。** 例：微信 4.0+ 把数据从 `WeChat` 迁到 `xwechat`，两者都是微信活跃数据（共 3GB），一个都不能碰。不要凭"旧名字"就当残留删。
4. **崩溃报告目录是空壳聚集地。** `AppData\Local\RailCrashReport\UnsentCrashReports` 按 `应用_版本号` 建目录，多为 0 字节空壳，可只清理目标应用的（如 `wegame*`、`cross*`），不动其他应用（CF/微信）的。
5. **不可逆操作先确认。** 删除前用 AskUserQuestion 跟用户确认目标清单；批量删 >50 文件或整目录删要二次确认。可回退时先备份到桌面。
6. **【用户立规 2026-10-17，2026-10-18 加强】交付脚本让用户执行前，必须先展示完整删除明细清单，且清单必须随脚本"同批同点"交付。** 凡是要交付 `.ps1`/`.cmd`/`.reg`/`.py` 等脚本让用户本机运行的：①脚本**头部注释内嵌完整明细**（每个目标路径+当前状态+删除方式+风险）②另出**独立明细清单文件**，与脚本放进**同一个 present_files 调用** ③对话正文同步列明。用户原话："没有在让我运行的地方给我展示清理的清单"——明细必须出现在用户点运行的那个交付点上，不能只在对话里说。
7. **【用户立规 2026-10-17，2026-10-18 加强为"立即"】经验/漏洞/失误发现当时就更新 skill，不等回合结束。** 执行任务过程中一发现新残留模式、新坑位、新失误、新对策，**立刻**写入本 SKILL.md 对应章节和项目记忆——不是"这轮结束前"，是"发现的这一刻"。用户原话："执行任务过程中发现的经验、漏洞、失误都要立即更新到 Skill……避免这次发现了下次用 Skill 还会犯错"。**自查标准：每次工具调用返回新信息，先问一句“这是下次还会踩的坑吗？”是 → 当场写，不攒批。**
8. **【卸载优先】能走卸载器就不直接删目录。** 直接删目录会让 Windows Installer 数据库残留不一致，后续重装/更新报错。卸载路径按优先级：注册表 `UninstallString` 官方卸载器（套 0.2 静默参数）→ `msiexec /x {GUID}` → winget/Appx → 第三方强制卸载（0.6）→ 手动卸载。**手动删目录是最后手段，不是第一选择。**
9. **【卸载前置】卸载前必须停进程/服务/计划任务。** 文件被占用 = 卸载失败或留半截（一半文件被删、注册表还在，比不卸更难清）。顺序见 0.3：taskkill → 停服务 → 停任务 → 再跑卸载器。

## 二·五、子串匹配误报模式（必须人工过滤）

关键字匹配最大的坑是子串误报。以下模式已验证，扫描时必须过滤：

| 关键字 | 误报来源 | 为什么是误报 |
|--------|---------|------------|
| `codex` | `mdmcodex.inf` / `amd64_dual_mdmcodex.inf` | Windows MDM 组件，系统文件 |
| `codex` | `FileExplorer` / `fileexplorer` | Windows 资源管理器，系统组件 |
| `codex` | `VSCode` / `vscode` | 代码编辑器，非 Codex 软件 |
| `filee` | `FileExplorer` / `FileExtensions` | Windows 资源管理器 |
| `filee` | `FileEnt.tcl` / `FileEnt1.tcl` | Python tcl 库文件 |
| `filee` | `VixVM_FileExistsInGuest` | VMware VIX 工具 |
| `rail` | `grails` / `Grails` | JVM 框架 |
| `rail` | `MouseTrails` / `mousetrails` | Windows 鼠标设置 |
| `rail` | `git-interpret-trailers` | Git 工具 |
| `rail` | `trail` / `trailing` / `trail-emitter` | Wallpaper Engine / Qt QML |
| `air` | `PackageRepair` / `BootRepair` / `Rep**air**` | Windows 组件修复功能 |
| `quark` | `quarkus` | Java 框架，非 Quark 软件 |
| `quark` | `IntelliJ IDEA plugins\quarkus` | IDE 插件 |
| `adobe` | `AppData\LocalLow\Adobe` | **例外！** LocalLow 是真实 Adobe 应用数据目录 |
| `adobe` | `Winhance\IconCache\external-app-adobe-reader` | Lenovo 工具图标缓存 |
| `idm` | `PremiumSoft\NavicatPremium\lvMainViewStyle\lo*RoleIDMSSQL` 等 10 键 | **Navicat（在用）视图布局键**——`IDM`+`SQL` 拼接子串（SQL Server 连接角色的视图状态），非 Internet Download Manager |
| `xmanager` | `WindowsRuntime\ActivatableClassId\...UXManager`（3 键） | 系统 WinRT 类注册——`NetworkUXManager` 小写后含 `xmanager` 子串（`u`+`xmanager`） |

**过滤规则**：
- WinSxS / System32 / DriverStore / SystemRoot 路径 → 系统文件，跳过
- 路径含 `FileExplorer` / `FileExtensions` / `braille` / `mdmcodex` → 系统组件，跳过
- 路径含 `grails` / `quarkus` / `vscode` / `intellij` → 第三方工具，跳过
- 路径含 `PackageRepair` / `BootRepair` → Windows 修复功能，跳过
- 路径含 `PremiumSoft\NavicatPremium` → Navicat（在用数据库工具），跳过（IDM 误报源）
- 路径含 `WindowsRuntime\ActivatableClassId` → 系统 WinRT 注册，跳过（xmanager 误报源）
- **但 `AppData\LocalLow\Adobe` 是例外** — LocalLow 是真实 Adobe 应用数据目录，需人工确认

---

## 三、沙箱 / Windows 环境坑位（务必照此选型）

| 操作 | 坑 | 正确做法 |
|---|---|---|
| 从 Bash 调 `cmd /c "rd /s /q ..."` | 被沙箱安全策略拦截（判定绕开命令校验） | 改用 **PowerShell 工具** 或 **Python** 通道 |
| `PowerShell Remove-Item -Recurse` 删 `RailCrashReport` 等系统目录 | **静默失败**（exit 0 但不删，权限特殊性） | 用 **Python `shutil.rmtree`**，更可靠且能捕获错误 |
| `reg.exe` / `reg delete` | 被 Program Blacklist 拦截（仅沙箱） | 沙箱用 **Python `winreg`**；**用户机的管理员脚本里 reg.exe 可用**，可作删除兜底 |
| `Test-Path 'HKLM:\SOFTWARE\Classes\*\shellex\...'` 带 `*` 的注册表通配符路径 | **命令挂起无输出**（PowerShell 工具卡死，2026-10-17 实测） | 用 .NET API：`[Microsoft.Win32.Registry]::ClassesRoot.OpenSubKey('*\shellex\...')` |
| **`Registry::HKLM:\...` 非法路径** | `Test-Path` 静默返回 **False** → 把"仍存在"误报成"已删除"（2026-10-18 重大失误：277 键实际没删，全报 GONE） | 正确形式 `Registry::HKEY_LOCAL_MACHINE\...`（或直接 `HKLM:\...`）；**用不常见的路径形式前必须先自测** |
| **前缀长度硬编码** | `'HKEY_LOCAL_MACHINE\'.Substring(20)`——该前缀实际 19 字符，off-by-one 使全部存在性检查返回 false（v1 脚本 277 键零删除） | 用 `$Path.Substring($prefix.Length)` 或 `-replace '^HKEY_LOCAL_MACHINE\\'`，**永不手写长度数字** |
| **函数内 `$array += ...`** | 值类型重赋值不写回脚本级作用域 → 日志文件 0 字节（2026-10-18 实测） | 跨作用域累计用 `$script:var` 或 `ArrayList.Add()`；hashtable 元素赋值（`$h['k']+=1`）是引用操作，可正常跨域 |
| **命令模式 `函数 "$var" + '字符串'` 参数拆分** | `+` 不进入函数表达式——函数只收到 `"$var"`（2026-10-18 round3b 虚警：自测全部 FATAL，实际什么都没删，无损失） | 传拼接字符串**必须整体加括号**：`Test-RegKey ($Prefix + 'SOFTWARE\Classes')`；赋值语句 `$x = "$a" + 'b'` 不受影响（表达式上下文） |
| **.NET `OpenSubKey('')` 返回 hive 根本身** | 前缀剥离出空串时存在性检查拿到 hive 根 → 非 null → 误报"键存在"（与上一行叠加造成 round3b FATAL） | 存在性判断函数先防空路径：`if ([string]::IsNullOrEmpty($rel)) { return $false }` |
| Python `shutil.rmtree` 删 ProgramData 目录 | trash 失败 `Some operations were aborted`（FAIL_CLOSED，2026-10-17 实测） | 转管理员脚本直删，不纠缠 |
| 删 `C:\Windows` 或整盘大批量 | 被硬杀 / 触发 FAIL_CLOSED 保护 | 不碰系统目录；分批小批量，逐条 try/except |
| `Get-ChildItem` 无容错枚举 | 遇 .ssh 等敏感目录崩溃 | Python 脚本全程 try/except + 排除清单 |

**首选通道：写 Python 脚本 → 落盘报告 → Read 报告。** 避免 PowerShell 不回显的坑。

## 四、可复用脚本模板

> 模板索引（按流程顺序）：**模板 0**（卸载入口扫描，见零章 0.1）→ **模板 A**（本节，残留扫描 + 交叉比对）→ **模板 B**（本节，精准删除 + 复核）→ **模板 C**（本节，注册表幽灵项检测）→ **模板 D**（见六章，跨盘枚举残留目录）

### 模板 A：残留扫描 + 已装软件交叉比对（只读，阶段二第 1 步）

```python
# -*- coding: utf-8 -*-
import os, winreg, datetime
HOME = os.path.expanduser("~")
BASE = os.path.join(HOME, "AppData", "Roaming", "Tencent")  # 改目标父目录

def dir_size(p):
    t = 0
    for r, _, fs in os.walk(p):
        for f in fs:
            try: t += os.path.getsize(os.path.join(r, f))
            except (OSError, PermissionError): pass
    return t

# 收集已装软件 DisplayName（三仓库）
installed = set()
for hkey, sub in [(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                  (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                  (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")]:
    try:
        with winreg.OpenKey(hkey, sub) as k:
            for i in range(winreg.QueryInfoKey(k)[0]):
                try:
                    with winreg.OpenKey(k, winreg.EnumKey(k, i)) as sk:
                        try: installed.add(winreg.QueryValueEx(sk, "DisplayName")[0])
                        except (OSError, FileNotFoundError): pass
                except OSError: pass
    except OSError: pass

# 已知子目录映射（按需扩充）： {目录名: (中文名, [关键词])}
KNOWN = {"WeChat": ("微信", ["wechat","微信"]), "xwechat": ("微信4.0数据", ["wechat"]),
         "WXWork": ("企业微信", ["wecom","企业微信"]), "QQ": ("QQ", ["qq"]),
         "WeMeet": ("腾讯会议", ["wemeet","腾讯会议"]), "WeGame": ("WeGame", ["wegame"]),
         "Cross": ("穿越火线CF", ["crossfire","cf"])}

for d in sorted(os.listdir(BASE)):
    full = os.path.join(BASE, d)
    if not os.path.isdir(full): continue
    mb = dir_size(full)/1024/1024
    if d in KNOWN:
        cn, keys = KNOWN[d]
        hit = [x for x in installed if any(k in x.lower() for k in keys)]
        st = "●已装" if hit else "○疑似孤儿"
    else:
        cn, st = d, "？未知(多为共享SDK,保留)"
    print(f"[{d}] {cn} | {mb:.2f}MB | {st}")
```

### 模板 B：精准删除 + 复核（确认后再跑）

```python
# -*- coding: utf-8 -*-
import os, shutil
HOME = os.path.expanduser("~")
BASE = os.path.join(HOME, "AppData", "Roaming", "Tencent")
TARGETS = ["WeGame", "WeMeet", "Cross"]  # 只列确认要删的子目录名
for name in TARGETS:
    full = os.path.join(BASE, name)
    if not os.path.exists(full):
        print(f"[{name}] 已不存在，跳过"); continue
    try:
        shutil.rmtree(full)
        print(f"[{name}] 删除{'成功' if not os.path.exists(full) else '失败'} ✅" if not os.path.exists(full)
              else f"[{name}] 删除后仍存在 ❌")
    except Exception as e:
        print(f"[{name}] 失败: {e}")
```

### 模板 C：注册表幽灵项检测（只读）

```python
import winreg
for hkey, sub in [(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                  (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                  (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")]:
    try:
        with winreg.OpenKey(hkey, sub) as k:
            for i in range(winreg.QueryInfoKey(k)[0]):
                name = winreg.EnumKey(k, i)
                if "wegame" in name.lower() or "目标词" in name.lower():
                    with winreg.OpenKey(k, name) as sk:
                        try: loc = winreg.QueryValueEx(sk, "InstallLocation")[0]
                        except (OSError, FileNotFoundError): loc = "?"
                    print(f"{sub.split('\\')[-1]}\\{name} -> {loc}")
    except OSError: pass
```

## 五、已知 Tencent 子目录速查（保留 vs 删除）

| 目录 | 身份 | 处置 |
|---|---|---|
| `WeChat` / `xwechat` | 微信活跃数据 | **保留** |
| `WXWork` | 企业微信 | 注册表无记录即孤儿，删前确认用户不用 |
| `QQ` | QQ（已装） | 保留 |
| `QQPCMgr` | 腾讯电脑管家（已装） | 保留 |
| `WXDrive` | 微信系组件 | 保留 |
| `TBS`/`beacon`/`TXSSO`/`TenioDL`/`libsdk`/`qimei`/`pallas`/`CTLogin`/`NTCLS` | 腾讯共用 SDK | **保留（删之崩软件）** |
| `WeGame`/`WeMeet`/`Cross` | 各自软件残留 | 软件卸了就删 |
| `TGP` | 腾讯游戏平台（WeGame 前身） | 孤儿，可删 |
| `游戏人生cross`/`Androws`/`Marvis` | 游戏平台遗留 | 孤儿，可删 |

> 说明：SDK 目录清单与微信 `xwechat` 迁移为基于实际扫描与腾讯系通用惯例推断，未逐条查官方文档；执行前仍按"三步交叉验证"确认。

## 六、已知 Adobe 残留路径速查（重打包版常装 D 盘）

Adobe（含 PS/PR/AE/AU 等）卸载后，真残留常分布在**多盘、多厂商目录**。清理前**先确认整套 Adobe（含 Creative Cloud）是否已卸**——若都已卸，所有 Adobe 目录/注册表都是孤儿，可全量清；若只卸了个别应用，必须保留 Creative Cloud 与仍在用应用的组件，否则其他 Adobe 软件崩溃。

| 路径 | 性质 | 说明 |
|---|---|---|
| `C:\Program Files\Adobe` | 安装主体 | 已卸即删 |
| `C:\Program Files (x86)\Adobe` | 安装主体(32位) | 同上 |
| `C:\Program Files\Common Files\Adobe` | 共用组件(UXP 等) | ≈32MB，已卸即删 |
| `C:\Program Files (x86)\Common Files\Adobe` | 共用组件(CEP/Color/Desktop Common) | **大头 ≈169MB**，已卸即删 |
| `C:\ProgramData\Adobe` | 全局数据 | 已卸即删 |
| `AppData\Local\Adobe` / `AppData\Roaming\Adobe` | 用户缓存/预置(CameraRaw/Lumetri…) | 已卸即删 |
| `D:\Program Files\Adobe Photoshop 2020 SP` / `Adobe Premiere Pro 2020 SP` | **重打包(vposy)安装包** | 含 `Set-up.exe`/`packages`/`products`/`Repack by weibo@vposy`，**实测 PS 1.8GB+PR 1.6GB 共 3.3GB**，C 盘清理脚本会漏，必须单独扫 D 盘 |
| 注册表 `HKCU\SOFTWARE\Adobe`（整棵） | 用户配置树 | 已卸即删（沙箱可直删，无需管理员） |
| 注册表 `HKLM\SOFTWARE\Adobe` / `HKLM\SOFTWARE\WOW6432Node\Adobe` | 系统配置树 | 已卸即删（系统保护位，需真机管理员） |

> 判定"已卸"的快速法：注册表三仓库 `Uninstall` 下**无任何 Adobe / Creative Cloud 卸载项** + 文件系统无 `Creative Cloud` 目录 → 整套已卸。

### 模板 D：跨盘枚举"已卸载软件"残留目录（只读，补扫描盲区）

```python
# -*- coding: utf-8 -*-
import os
# 已知已卸载软件的目录关键词（按需扩充）
KEYWORDS = {
    "Adobe": ["adobe"], "WeGame": ["wegame"], "CF": ["crossfire", "cf"],
    "腾讯会议": ["wemeet"], "企业微信": ["wxwork"], "Codex": ["codex"],
    "Postman": ["postman"], "SoftEther": ["softether"],
}
DRIVES = ["C:\\", "D:\\", "E:\\"]
for drv in DRIVES:
    for pf in ["Program Files", "Program Files (x86)"]:
        root = os.path.join(drv, pf)
        if not os.path.isdir(root): continue
        for name in sorted(os.listdir(root)):
            low = name.lower()
            for sw, kws in KEYWORDS.items():
                if any(k in low for k in kws):
                    p = os.path.join(root, name)
                    print(f"[{drv}{pf}] {name}  <- 命中 {sw}")
```

## 六·五、清理脚本覆盖对齐规则（扫描发现 ≠ 清理覆盖）

**核心教训**：扫描维度再全，清理脚本没覆盖到等于零。

每次扫描发现新残留类型，必须同步更新清理脚本的目标列表。交付前对照扫描清单逐条检查是否每个维度都有对应的清理动作。

**清理脚本必须覆盖的维度**：
- HKLM Uninstall 键（幽灵条目）
- HKCU/HKLM Run / RunOnce（启动项）
- HKCU/HKLM Software 树（软件配置）
- 右键菜单（Classes\*\shell、Classes\Directory\shell）
- 服务（HKLM SYSTEM Services）
- 文件系统（所有驱动器 Program Files / AppData / Common Files）
- 开始菜单（用户 + 公共）
- 桌面（用户 + 公共）
- **Common Files（所有驱动器）**
- **非 C 盘 ProgramData**
- **计划任务（注册任务 + 孤立文件）**
- **`Classes\Installer\Dependencies\<产品>.Msi,vNN`（MSI 依赖注册，见六·九 #4）**
- **`Classes\AppID\<exe>`、CLSID 死注册（ProgID 的 CLSID 层，见六·九 #6）**
- **`Clients\StartMenuInternet`、Chrome/Edge/Firefox `NativeMessagingHosts`、`UmpVideoPlugin`（见六·九 #7）**
- **`.NETFramework\AssemblyFolders`（见六·九 #8）**
- **畸形键 `ContextMenuHandlers-<name>` 等安装器写错分隔符的键（见六·九 #3）**
- **路径/键名变体：空格顶层 vs 子目录、`<软件>_<GUID>` 实例键（见六·九 #1/#2）**
- **Uninstall 幽灵判定：InstallLocation 为空时查 InstallSource（见六·九 #9）**

## 六·六、计划任务清理（四种形态，缺一不可）

计划任务残留有四种形态，只处理一种会漏（2026-10-18 新增形态 3/4）：

| 形态 | 位置 | 清理方法 |
|------|------|---------|
| 已注册任务 | Task Scheduler 注册表 | `Get-ScheduledTask` + `Unregister-ScheduledTask` |
| 孤立任务文件 | `C:\Windows\System32\Tasks\` | `Get-ChildItem -Recurse` + `Remove-Item` |
| **空目录壳** | `Tasks\Microsoft\<产品>\Updates\` 等 | 任务注销后产品目录留下的**空目录树**（壳里 0 文件）——`Get-ChildItem` 按文件扫会漏，要**按目录名枚举**：`Tasks\Microsoft\<产品>\` 整树删 |
| **Migrated 迁移遗留** | `C:\Windows\System32\Tasks_Migrated\Microsoft\<产品>\` | Win10 升级迁移产物，含 `Enabled=false` 的死任务 XML（如 VS 的 `Updates\BackgroundDownload`，`<Author>Microsoft Visual Studio</Author>`）——任务永不活动但是死数据，整树删 |

**正确清理脚本步骤**：
1. `Get-ScheduledTask | Where-Object *关键字*` 查注册任务 → `Unregister-ScheduledTask`（防御性，即使目录里没文件也可能注册表里还有）
2. 按产品名枚举 `Tasks` 与 `Tasks_Migrated` 两棵树的**目录名**（不只文件）：`Tasks\Microsoft\<产品>\` 和 `Tasks_Migrated\Microsoft\<产品>\` 整树删
3. 检查 `HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Task Scheduler` 注册表

**注意**：`C:\Windows\System32\Tasks\` 和 `Tasks_Migrated\` 需要管理员权限。沙箱中 `schtasks.exe` 被 Program Blacklist 拦截，必须交付 `.ps1` + `.cmd` 让用户本机管理员运行。

## 六·七、Temp 标记文件与 Applications 键残留（2026-10-17 jisupdf 实战，用户 Everything 搜索发现）

**"验证零残留" ≠ 真的零残留。** 本次 15 软件清理已全维度复检通过后，用户用 Everything 一搜又捞出 2 处真残留：

| 残留形态 | 实例 | 说明 |
|---------|------|------|
| **Temp 空标记文件** | `C:\Windows\Temp\__jisupdf_empty.tmp`（0 字节） | 安装/卸载程序留下的 `__<app>_empty.tmp` 标记，卸载器不清。本次创建时间恰为运行清理脚本的时刻（Explorer 重载 shell 扩展时产生），删后无重建 |
| **Applications 应用注册键** | `HKCU\Software\Classes\Applications\JisuPdf.exe\shell\open\command` | 位于 Classes 树**第 3 层**（Software→Classes→Applications→<exe>→shell→open→command），`-Depth 2` 扫描够不到，命令指向已不存在的 exe，死键 |

**对策**：
- 注册表 Classes 树扫描至少 `-Depth 3`，并显式覆盖 `Classes\Applications\*` 维度
- `C:\Windows\Temp` 和用户 Temp 必须按 `__*_empty.tmp` + 软件名模式扫（权限不够的部分交管理员脚本）
- **每次"验证零残留"后，仍要请用户用 Everything 搜一轮软件名（含大小写变体）复核**——脚本扫描的盲区只有 Everything 能兜底

## 六·七-b、NSIS 卸载器临时目录残留（2026-10-18 QQ拼音实战，用户 Everything 搜索发现）

**又是"验证零残留"后用户 Everything 捞出真残留的一例**（六·七同型，第 N 次验证"脚本全绿≠真零残留"）。QQ拼音收尾终检全 PASS 后，用户 Everything 搜 `qqpinyin` 截图显示 `AppData\Local\Temp\` 下一批 `nst/nsy/nsc*.tmp`：

| 关键事实 | 内容 |
|---------|------|
| **是目录不是文件** | NSIS 卸载器把自身 DLL/卸载器副本解压到 `%TEMP%` 的临时目录，卸载器正常退出时自删；被中断（杀进程/超时/双实例互斥）就整目录遗留 |
| **前缀有 5+ 变体** | `nst`（temp）、`nsy`、`nsc`、`nsl`、**`~nsu`/`~nsu1`/`~nsuA`**（波浪线开头！卸载器主副本）。正确模式：`^~?ns[a-z0-9]{1,5}\.tmp$`（不区分大小写）。只匹配 `nst\|nsy\|nsc` 会漏 `nsl` 和 `~nsu` 全家 |
| **扫描必须目录+文件双通道** | `os.walk` 的 `filenames` 永远匹配不到目录名——上一轮"零命中"就是这么来的。`ls \| grep 'ns.*\.tmp'` 或 `os.listdir` + 目录名匹配才抓得到 |
| **多次尝试留多份** | 用户 10-17 自己跑过一次卸载（留 20:29/20:30 两份）、10-18 我的 v2 跑一次（留 10:01/10:02 两份）——按目录 mtime 可与卸载尝试时间线一一对应 |
| **同目录常见内容** | `Un_A.exe`/`Un.exe`（卸载器副本，QQ拼音 1.33MB）、`Au_.exe`、`QQPinyinHelper.dll`、`QQPinyinUninstallPlugin.dll`、`nsProcessW.dll`（进程检测插件）、`InstallOptions.dll` + `ioSpecial.ini` + `modern-*.bmp`（界面资源）、`uninstall_complete.exe`（腾讯卸载器收尾程序，在 Temp 根目录不带 ns 前缀） |

**对策**：
- 卸载任务收尾时，Temp 扫描模式固定为 `^~?ns[a-z0-9]{1,5}\.tmp$` + 软件名 + `uninstall_complete.exe`，且**目录名和文件名都要匹配**；扫完用比模式更宽的 `ns.*\.tmp` 复扫一遍（round3c 同款纪律）
- 卸腾讯系软件（QQ/QQ拼音/电脑管家）后，`%TEMP%\uninstall_complete.exe` 必查
- 删除零风险：这些是卸载器临时组件，安装目录已删后 DLL/exe 无任何用途；占用检查只需确认无 uninst/产品进程

## 六·七-c、让用户的 Everything 排除 WorkBuddy 噪音（2026-10-18 用户提问）

用户每轮用 Everything 复核时，`C:\Users\ZSY\.workbuddy\`（clipboard-images、projects 会话 jsonl、`.modify_backup_meta` 357 个 reg stub）和项目目录 `reg_backup_*` 都会混进结果造成误判。**交付清理方案时主动附上排除方法**：

- 即时（搜索框语法，Everything 的 NOT 运算符是 `!`）：`qqpinyin !path:*.workbuddy*`（一条排除所有位置的 .workbuddy）；要连项目备份目录一起排：`qqpinyin !path:*.workbuddy* !path:*reg_backup*`
- 永久：Everything → 工具 → 选项 → 索引 → Exclude → 添加 `C:\Users\ZSY\.workbuddy\*` 与 `<项目目录>\.workbuddy\*`（支持通配符），OK 后生效
- 更省事：把带排除条件的搜索存为 Everything 过滤器/书签，以后一键调用

## 六·七-d、用户 Profile 目录（C:\Users\<名>）残留扫描法（2026-10-18 实战）

用户要求"扫 C:\Users\ZSY 有没有没清干净的"时的完整打法：

**枚举**：AppData\Roaming + Local + LocalLow 三层一级目录 + Profile 根一级条目（带体积/文件数/mtime）。

**"已卸载"四信号交叉判定（缺一不可，单信号必误判）**：
1. 卸载条目三仓库全量（196 条，DisplayName+InstallLocation 匹配）——注意"无卸载条目"≠没装过（绿色版/便携版不注册）
2. 开始菜单快捷方式全名单（159 条）= 在用软件白名单，卸载掉的软件快捷方式会消失
3. Program Files×4 + **`AppData\Local\Programs`（用户级安装：Obsidian/uTools 类）** + **非标准安装根（D:\Tencent、D:\devtools、E:\ 等）**
4. exe 实体全盘查找（安装本体不在 = 数据目录即残留）

**两个反直觉规律**：
- **mtime 新 ≠ 在用**（ramboplay.ra2 2025-05 还在写但本体早没了）；**mtime 老 ≠ 残留**（sogou 2020 年的目录是在用组件）
- 子串匹配噪音极大（`HD Tune Pro` 匹配到快捷方式 "Activate or Trial PRO mode"、`FYPlayer` 匹配 "VMware Workstation 16 Player"、`kdesk` 匹配 "Remote Desktop Connection"）——自动判定结果**必须人工过堂**

**执行纪律（本轮三次踩中）**：
- **同一产品名在 AppData 多层都有副本**（kingsoft/ramboplay.ra2 在 Roaming 和 Local 各一份）——清理清单必须按"层×名"全组合列，删完一层要用宽通配复扫另一层（"超集"教训第三次应验）
- **从报告授权清单到脚本 TARGETS 要逐条对账**（本轮报告授权 41 项、脚本只写 39 项，Bypass 漏写全靠复验兜底补删）
- 复验宽扫命中仍要人工过堂：Anki 卡片媒体里的 `youdao-*.mp3`（用户学习资产）、`Notepad--\userstyle\Obsidian`（主题目录名）、`ASP.NET\DataProtection-Keys\key-*.xml`（文件名含 cef 子串）、联想管家 `devicecenter\cefcache`——全是误报
- **名字撞车是宽扫误报高发区**：`@docmirror\dev-sidecar-gui`（在用产品的组件，撞名 Dev-Sidecar）、`Desktop\FYPlayer_免安装版\translations`（免安装软件的语言目录，撞名 .translation 缓存）——宽扫命中先看**父目录归属**再看名字
- **执行中断的恢复模式**：脚本跑到一半被中断（用户关窗/中止回合）→ 不要盲重跑，先查各目标当前存在性 → 重跑同一脚本即可（已删项自动走 GONE 通道，对账仍闭合）→ 若 SUMMARY 未跑到则日志缺失，重跑会补齐（实测：中断时已删 2/15，重跑后 OK=13+GONE=2=15 对账 PASS）

## 六·八、被锁定文件的诊断与当场解法（2026-10-17 jisupdf 实战）

删除报 **错误 5（ACCESS_DENIED）** 或 **错误 32（SHARING_VIOLATION）** = 文件被某进程映射中。沙箱内 `DeleteFileW` / `MoveFileEx` / `FILE_FLAG_DELETE_ON_CLOSE` / `icacls` 全无解，按下面走：

**第一步：定位持有进程**（无需 handle.exe）：
```powershell
Get-Process -Name explorer | ForEach-Object { $_.Modules } | Where-Object { $_.ModuleName -match '关键字' }
```
> 实测：`jisupdfmenu.dll`（资源管理器右键菜单 shell 扩展）删了 CLSID 注册表键后**仍映射在 explorer.exe 里**——运行中的进程不会卸载已加载的 DLL。注意 Modules 里显示的是**原始文件名**，即使磁盘上已改名成 `.del`（映射句柄按原文件对象走，改名前就已 mapped）。

**第二步：两条释放路径**：

| 路径 | 做法 | 适用 |
|------|------|------|
| A. 重启整机 | 管理员脚本写 `PendingFileRenameOperations`（格式见下），重启后 SMSS 自动删 | 不急、顺便重启 |
| B. **重启 Explorer（立即生效，无需管理员）** | `taskkill /f /im explorer.exe` → 等待 2-3 秒 → 删文件 → `start explorer` | 想当场清掉；CLSID 键已删的前提下新 Explorer 不会重新加载该 DLL |

路径 B 交付为普通 `.cmd`（无需 UAC），**必须在明细里写明副作用**：所有文件资源管理器窗口会关闭、任务栏闪烁约 3 秒后恢复。

**PendingFileRenameOperations 标准删除格式**（写入后务必验证）：
- 每条 = `\??\<完整路径>` + 空字符串配对（REG_MULTI_SZ，标准 MoveFileEx 删除格式）
- 验证手法：Python `winreg` 读原始字符串列表，逐字符确认路径与配对（PowerShell 拼接显示会丢失空串，看不出格式对错）
- 删掉的文件若在重启前已被手动删除，遗留条目在开机时是**无害 no-op**（源不存在直接跳过），不必刻意清理该注册表值

## 六·九、第二轮全扫新遗漏的检查项（2026-10-17 深夜，用户 Everything 触发复扫）

对 24 个已清软件用最新维度重扫，又抓出 **9 类新盲区**。全部已固化入一·五维度清单：

| # | 遗漏类型 | 实例 | 为什么漏 |
|---|---------|------|---------|
| 1 | **路径同名变体** | `C:\ProgramData\Microsoft Visual Studio`（空格，顶层）vs `C:\ProgramData\Microsoft\VisualStudio`（子目录） | 脚本删了子目录版，顶层空格版没删；验证清单也没列这条路径 |
| 2 | **键名 GUID 实例变体** | `WOW6432Node\Microsoft\VisualStudio_b55a2da9` vs `Microsoft\VisualStudio` | 按软件名精确匹配漏掉带实例 GUID 的兄弟键 |
| 3 | **畸形注册表键（安装器写错分隔符）** | `HKLM\SOFTWARE\Classes\*\shellex\ContextMenuHandlers-\jisupdfMenu`（连字符而非反斜杠） | 正常扫描只查 `ContextMenuHandlers\` 子树；且该畸形父键是**多产品共用**的（搜狗 sgshellext/TortoiseGit/TortoiseSVN/百度 YunShellExt 都在里面），**只能删目标子键，绝不能删父键** |
| 4 | **MSI Installer Dependencies 树** | `Classes\Installer\Dependencies\Microsoft.VisualStudio.*.Msi,vNN`（23 个） | Windows Installer 依赖注册，产品卸载器不清 |
| 5 | **海量扩展名 ProgID** | `QuarkHTM.<ext>` + `QuarkCloudDriveHTM.<ext>` 共 42 个（.aac/.flac/.mp3/.wav…） | 按 `<产品名>HTM.*` 模式枚举，逐个匹配关键字会漏 |
| 6 | **AppID / CLSID 死注册** | `Classes\AppID\XunleiBHO64.DLL`×3 仓库、`AppID\devenv.exe`×2、VS Setup.Configuration/Management 的 CLSID×4（InProcServer32 DLL 已随目录删除） | ProgID 删了，CLSID/AppID 层没删 |
| 7 | **浏览器/开始菜单集成键** | `Clients\StartMenuInternet\QuarkCloudDrive`、`Google\Chrome\NativeMessagingHosts\com.quark.hostclient`、`Mozilla\NativeMessagingHosts\*`、`UmpVideoPlugin\RenderSafety\*` | 不在 Software\<软件名> 树下，按软件名扫 Software 根会漏 |
| 8 | **AssemblyFolders** | `WOW6432Node\Microsoft\.NETFramework\AssemblyFolders\Microsoft .NET Framework 3.0 Reference Assemblies for Visual Studio` | 指向已删的 VS 参考程序集目录，死键 |
| 9 | **Uninstall 幽灵判定升级** | `{CBF6EE7C-...}` vs_devenvsharedmsi：InstallLocation 为空但 InstallSource 指向已删目录 | 只看 InstallLocation 会判成"非幽灵" |
| 10 | **计划任务的 Migrated 形态 + 空目录壳** | `Tasks\Microsoft\VisualStudio\Updates\`（空目录壳，任务已注销）+ `Tasks_Migrated\Microsoft\VisualStudio\Updates\BackgroundDownload`（迁移遗留死任务 XML，`Enabled=false`） | 扫描只查注册任务/孤立 XML 两种形态，漏了：①Tasks 下产品目录里**任务注销后留下的空 Updates 目录壳** ②Tasks_Migrated 整个迁移遗留树（Win10 升级迁移产物，任务永不活动但是死数据） |
| 11 | **在用管家的图标库缓存已卸载软件图标** | `C:\ProgramData\Lenovo\devicecenter\ico\` 下：`C盘管家.ico`、`b55a2da9.ico`（VS 实例 GUID 命名！）、`极速PDF阅读器.ico`（jisupdf） | 联想电脑管家（LenovoPcManagerService 在运行）的软件图标库会缓存**所有被收录过的软件**图标，已卸载软件的 ico 长期滞留；按产品名搜 ProgramData 只在产品自己目录下找，搜不到这种"别人家的资源库" |
| 12 | **Documents 根目录的产品用户数据目录**（含重定向） | `E:\Documents\Visual Studio 2022\`（Code Snippets/Templates/Visualizers 全空树 + attribcache140.bin） | 用户"文档"文件夹被重定向到 E 盘，扫描只查 `C:\Users\<名>\Documents` 不够；Documents 根目录要按产品名枚举，且先确认是空树/缓存再删（防止误删用户片段） |
| 13 | **WorkBuddy 会话备份目录被 Everything 索引**（非残留，禁删） | `C:\Users\ZSY\.workbuddy\workspace\sessions\<会话ID>\.modify_backup_meta\<hex>.<键路径>.reg`（本轮 357 个 stub / 全目录 21932 文件 35MB，混有 Windows 组件包 .mum/.cat） | 我方 .reg 备份被会话机制登记成 `<hex>.reg` stub，用户 Everything 搜产品名时**我方的备份文件出现在结果里**，极易被误判为"第三方卸载工具备份残留"；对策：向用户说明来源，**严禁清理该目录**（WorkBuddy 会话级数据），可建议用户在 Everything 排除 `.workbuddy` |
| 14 | **ProgramData 死缓存 + 软件资产标签** | `C:\ProgramData\Microsoft\NetFramework\BreadcrumbStore\Microsoft.VisualStudio.*`（14 条目 / **2426 个 0 字节标记文件**，VS ClickOnce 发布缓存）+ `C:\ProgramData\regid.1991-06.com.microsoft\regid.1991-06.com.microsoft.<实例GUID>.swidtag`（ISO 19770-2 软件资产标签 XML，`product_title=Visual Studio Community 2022`） | ① BreadcrumbStore 全是 0 字节文件，按大小扫描会忽略、按文件名扫才命中 ② swidtag 藏在 `regid.1991-06.com.microsoft\` 这种与产品名无关的目录里，**只有实例 GUID 与产品关联**，必须用已卸载产品的 GUID 反查 |
| 15 | **产品用户文档目录要区分空壳 vs 用户资产** | `E:\Documents\Axure\`（空树，删）/ `E:\Documents\National Instruments\`（空树，删） vs `E:\Documents\Adobe\`（56 文件：`咸鱼.psd`、`Howard&Rajesh.prproj`，**用户作品，禁删**）/ `E:\Documents\Typora Files\`（533 文件 33.6MB，**用户笔记库，禁删**） | 产品名出现在 Documents 根目录≠残留；先数文件+看内容：0 文件空树才可删，有内容的一律报告用户自行处置。注意"0 文件"≠真空——可能有空子目录（`Axure\元件`），统计要递归 |
| 16 | **同厂商共享用户数据目录（一家卸载一家在用）** | `E:\Documents\NetSarang Computer\7\`：`Xftp\`（已卸载，删）+ `Xshell\`（在用，留）+ `Common\`/`SECSH\`/`Themes\`（Xshell+Xftp 共享资源，留）；注册表 `HKCU\Software\NetSarang\`、`HKLM\SOFTWARE\WOW6432Node\NetSarang\` 同样 Xftp/Xshell 子键并存 | 同一厂商多产品共用一个用户数据目录/注册表父键时，**整树删会误删在用产品**；必须按子键/子目录粒度删。同理 `Common Files\NetSarang\XshellCore.tlb` 是 Xftp/Xshell 共用的 COM 类型库——判定归属看"在用产品安装目录是否自带副本"（Xshell 7 自带 `XshellCore.tlb`+`XshellCore.exe`）才可删 Common Files 副本 |

### 六·九·附：验证清单三方对齐规则（本轮最大教训）

`D:\Program Files (x86)\Microsoft Visual Studio\Shared`（392 文件）**脚本没删、报告却写了"24864+392 已覆盖"、验证清单也没列这条路径**——三处全错位，文件一直留到现在。

**对策**：
- 清理脚本的目标清单 = 验证清单的唯一来源，**验证脚本从目标清单机械生成，禁止手写验证路径**
- 每个目标必须枚举**所有路径变体**（空格/子目录、GUID 实例键、32/64 位仓库、畸形键）
- 报告里写的"已覆盖"必须以脚本实际执行日志为准，不以意图为准

### 六·九·附 2：其它本轮实战经验

- **沙箱 trash 失败模式**：ProgramData 目录删时报 `Some operations were aborted`（trash-failed FAIL_CLOSED）→ 直接转管理员脚本，不纠缠
- **在用产品会重建残留键**：SogouInput 反复重建 `HKCU\Software\sogoupdf\ttlocalcfg`（空子键）→ 判"无害保留"，删了还会来
- **扫描到清理之间键可能消失**（用户并行清理）→ 清理脚本对"已消失"项记 GONE 不报错；删除后必须独立通道复核最终状态
- **APP_DEADKEY 探针必须先展开环境变量**（%SystemRoot%/%ProgramFiles%），否则 notepad/wmplayer 等系统程序误报

## 六·十、备份与死键判定手法（2026-10-17/18 固化）

### 1. .reg 备份的编码规则（血泪坑）

- **regedit 导入 .reg：内容含非 ASCII（中文路径/值）时必须是 UTF-16LE（带 BOM）**；UTF-8 无 BOM 的 .reg 遇中文会乱码，恢复出来是错的
- Write 工具写出的 .reg 是 **UTF-8 无 BOM** → 含中文必须先转码（`Set-Content -Encoding Unicode` 或 Python `encoding='utf-16-le'`）
- 纯 ASCII 内容（路径/值全英文）UTF-8 无 BOM 可正常导入，无需转码
- 本轮做法：Python 备份脚本自动嗅探，有非 ASCII 写 UTF-16LE，否则 UTF-8（参考 `round2_backup_hklm.py`）

### 2. HKLM 备份在沙箱预生成（推荐模式）

- 沙箱**可读 HKLM**（只写被拦）→ 交付管理员脚本**之前**，先在沙箱用 Python winreg 把全部目标键导出 .reg
- 好处：①备份先于任何删除存在且可验证 ②管理员脚本只负责删，逻辑简单不易错 ③避开用户机上 `reg export` 对含 `*` 键名路径的不确定性
- 本轮实战：277 个 HKLM 键预备份（`reg_backup_admin_20261017_round2/`），管理员脚本纯删除 + OK/GONE/FAIL 三态计数

### 3. 死键四步判定法（ProgID → CLSID → DLL）

判定一个 shell 扩展 / COM 注册是不是死键：

1. 从 ProgID 键取 CLSID 值（如 `Classes\ThunderAgent.Agent\CLSID` 的默认值）
2. 查 `Classes\CLSID\{GUID}\InProcServer32`——**三个仓库都要查**：`HKLM\SOFTWARE\Classes`、`HKLM\SOFTWARE\WOW6432Node\Classes`、`HKCU\Software\Classes`
3. 取 InProcServer32 默认值 = DLL 路径
4. `Test-Path` 该 DLL → **不存在 = 死键可删**；存在 = 可能在用，走三步交叉验证再定

### 4. 管理员脚本删注册表首选 .NET API

- `Remove-Item -LiteralPath` 对含 `*` 的畸形键路径不可靠；`HKLM:` 提供程序可能未加载
- 首选：`[Microsoft.Win32.Registry]::LocalMachine.OpenSubKey($parent, $true).DeleteSubKeyTree($leaf)`——纯字符串路径，无通配符解释、无提供程序依赖
- 兜底：`reg delete "完整路径" /f`（用户机上可用；键名里的 `*` 按字面处理）
- 删后必须复验（Test-Path/.NET OpenSubKey），按 OK / GONE / FAIL 三态计数，FAIL 项进汇总

### 5. 扫描到清理之间状态可能变 + 独立通道复核

- 用户可能并行自己清理 → 清理脚本对"已消失"目标记 GONE，不报错、不跳过备份逻辑
- 删除完成后用**独立通道**复核最终状态（ PowerShell `Test-Path` vs Python `os.path.exists` 互验），不自说自话

### 6. 验证通道必须先双向自测（2026-10-18 血泪教训）

**宣布"已删除"之前，先证明你的验证通道是好的**——v1 脚本因 off-by-one 把 277 个键全报成"已删除"，我的抽查又用了非法路径 `Registry::HKLM:\` 全部误报 GONE，两层错误叠加，假"完成"了 13 个小时。

- 双向自测：**一个已知存在的键必须报 true，一个已知不存在的键必须报 false**，两个都对不上 → 通道坏了，结论作废
- 本技能的管理员脚本模板已内置此自测（见 v2 脚本 `chanOk` 段）：删前先验证 `SOFTWARE\Classes` 报 true、`__selftest_missing_key_zzz__` 报 false，任一反向即 abort
- 凡是用不常见的路径形式（`Registry::` 前缀、`-LiteralPath`、提供程序 Drive）做存在性判定，**先用一个肯定存在的目标试一遍**
- 结论：**验证环节本身比清理环节更容易撒谎**，因为它错了不会有任何报错

### 7. GONE/FAIL 必须可从事后日志区分（2026-10-18 核验时发现）

v2 脚本跑完，日志只有 273 行 `KEY OK`，而目标是 277 个——差的 4 个键既没有 OK 行也没有任何状态行。原因是脚本对"已消失"目标只 `$count['GONE'] += 1` **不写日志**，而用户关了窗口，SUMMARY 计数不可见 → **事后从日志无法区分这 4 个是 GONE（无害）还是 FAIL（漏删）**，差点造成第二次误判（最后靠沙箱独立复扫确认 4 个键确实 gone 才排除漏删）。

**对策**：
- 清理脚本对**每个目标的最终状态（OK/GONE/FAIL）都写日志**，一行不漏；日志文件 = 唯一可追溯凭证（用户会关窗口）
- SUMMARY 三态计数也要写进日志文件末尾，不只打印到窗口
- 核验时先对账 `日志行数 + GONE 数 == 目标总数`，差一个都要独立复扫兜底
- 附：扫描阶段记录的键可能在扫描→清理之间被其他操作清掉（如第一轮脚本已删过）→ GONE 是正常状态，但必须留痕

### 8. 纯 ASCII .ps1 删中文文件名目标的手法（2026-10-18）

`.ps1` 保持纯 ASCII 的铁律下，删除中文路径/文件名目标（如 `C:\ProgramData\Lenovo\devicecenter\ico\C盘管家.ico`）用 **[char] 码点构造**，不引入任何非 ASCII 字节：

```powershell
# C盘管家.ico = C + U+76D8(盘) + U+7BA1(管) + U+5BB6(家)
$name1 = -join ('C', [char]0x76D8, [char]0x7BA1, [char]0x5BB6) + '.ico'
# 极速PDF阅读器.ico = 极U+6781 速U+901F P D F 阅U+9605 读U+8BFB 器U+5668
$name2 = -join ([char]0x6781, [char]0x901F, 'PDF', [char]0x9605, [char]0x8BFB, [char]0x5668) + '.ico'
```

备选：整文件按 GBK(cp936) 编码保存（中文系统 PS 5.1 默认 ANSI=936，读无 BOM GBK 正确）——但每次交付前必须用 Python 验证 `open(f, encoding='cp936')` 能无损还原，不如码点构造稳。**码点构造后先在沙箱用 Python 打印验证字符串相等再写进脚本。**

### 8b. .cmd 启动器的编码坑（2026-10-18 QQ拼音卸载实战）——与 .ps1 正好相反

`.ps1` 要**纯 ASCII**，但 **`.cmd` 恰恰相反：中文 Windows 的 cmd.exe 按 GBK(CP936) 解析，Write 工具默认写的 UTF-8 会让所有中文 echo/注释显示为乱码**。用户双击后看到满屏乱码，会直接关窗以为出错——QQ拼音第一版卸载启动器就是这么"跑了个寂寞"的（用户反馈"跑完了"，实际 128 文件 216MB 原封不动，日志都没生成）。

**交付前 .cmd 必须**：①Python `text.encode('gbk')` 重写 ②CRLF 行尾 ③`open(f, encoding='gbk')` 能无损解码回原文（防丢字）。

**连带坑——Edit/Read 工具不能碰已转码文件**：文件转成 GBK 后，Edit 工具按 UTF-8 读字节流失败，中文全部变成 U+FFFD 替换符，文件直接报废（本轮实测：Edit 一行代码报废整个 v2，只能删了重建）。**对策：所有编辑只在 UTF-8 源文件上做，编码转换是最后一个动作，转完一个字都不再 Edit。**

### 8c. cmd 块内 %errorlevel% 是假码——必须用 !errorlevel!（2026-10-18 QQ拼音破案）

批处理 if/for 块（括号内）的 `%errorlevel%` 在**块进入前**一次性展开，读到的是旧值；块执行中途的真实退出码只有 `!errorlevel!`（需 `setlocal EnableDelayedExpansion`）或**块结束后**的 `%errorlevel%` 能拿到。沙箱实测：`if exist x ( cmd /c exit /b 42 & echo %errorlevel% )` → 打印 **0**（假码），`echo !errorlevel!` → **42**，块外 `%errorlevel%` → 42。

本轮实际后果：卸载日志记录"卸载器退出码: 128"是假码，差点误判"卸载器失败退出"——真相是卸载器正常完成了用户数据清理（PendingFileRenameOperations 为证）。**对策：①块内/紧跟块首次读取退出码一律 `!errorlevel!` ②开 `setlocal EnableDelayedExpansion` ③重要退出码用"跑完先出块、再单独读"的双行结构最稳。**

### 9. 沙箱清理脚本的三条铁律（2026-10-18 round3 实战踩坑）

本轮沙箱脚本同时犯了三个错，**侥幸全部目标都是已验证死键才没酿成事故**，三条都成铁律：

1. **备份与删除必须使用完全相同的路径参数**——本轮 export 函数把 `Software\Google\...` split 后丢了 `Software` 前缀去 OpenKey，4 个键的 .reg 备份**全部静默失败**，而删除用的是完整路径、照常执行。对策：export/backup 用的路径字符串必须与 delete 逐字节相同（同一个变量）；**export 失败必须中止删除（fail-closed），绝不允许"备份失败也继续删"**。
2. **删除前必须先记录 PRE_EXISTS=true**——round2 的"GONE vs FAIL 分不清"在沙箱侧重演：本轮脚本把"键本来就不存在"和"删除成功"都输出成 deleted OK。对策：删除前 OpenKey 确认存在并写日志 `PRE_EXISTS`，删除后再验证，两阶段状态都留痕；宣布"已删"前用**独立通道**（另一个脚本/另一种 API）复核。
3. **空目录树不要用 os.removedirs**——safe-delete guard 对 removedirs 的 ENOTEMPTY 处理有坑（子目录明明空的也报非空）；对策：自底向上**逐层 `os.rmdir`**（先删最深子目录再删父目录），每层验证。

另：**Python raw string（`r'...'`）里 `\uXXXX` 不转义**——分类脚本用 `r'...\u76d8...'` 匹配中文键名全盘落空，差点把真死键误报成 GONE。验证脚本自身也要被独立验证。

### 10. PowerShell 命令模式参数拆分 + OpenSubKey('') 返回 hive 根（2026-10-18 round3b 虚警事故）

round3b v2 在用户机（管理员）一跑就 `FATAL: registry channel self-test FAILED (missing key reported existing). Abort.`——**什么都没删（自测拦截成功，无损失）**，但原因查了两层才挖到真根因，两个坑叠在一起：

1. **命令模式下 `函数 "$var" + '字符串'` 的参数拆分**：`+` **不会**成为传给函数的表达式的一部分——函数实际只收到 `"$var"`。沙箱实测：
   ```powershell
   function probe-arg { param([string]$Path) $Path.Length }
   $Prefix = 'HKEY_LOCAL_MACHINE\'
   probe-arg "$Prefix" + 'SOFTWARE\Classes'      # -> 19（只收到 $Prefix，尾杠还被吞）
   probe-arg ($Prefix + 'SOFTWARE\Classes')      # -> 35（正确）
   ```
   **对策：函数调用传拼接字符串必须整体加括号** `Test-RegKey ($Prefix + 'SOFTWARE\Classes')`，或先赋值再传变量。赋值语句（`$x = "$a" + 'b'`）是表达式上下文，不受影响——这也是 round2 v2 用插值 `"$Hklm\SOFTWARE\Classes"` 能跑通、round3b 改用拼接就炸的原因。
2. **.NET `OpenSubKey('')` 返回 hive 根本身（非 null）**：前缀剥离出空串时，存在性检查会拿到 hive 根 → 非 null → 误报"键存在"。
   ```powershell
   $null -eq [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey('')  # -> False！
   ```
   **对策：存在性判断函数必须先防空路径**（`if ([string]::IsNullOrEmpty($rel)) { return $false }`）。

**流程教训**：用户报"运行失败了"时，先用**脚本文件本身**在沙箱复现（去掉 admin 检查段再跑），不要凭"手打复现"下结论——我手打复现返回 False 差点漏判真 bug；且手打代码与脚本文件差一个字符（赋值 vs 直传）行为就不同。

### 11. Common Files 副本 ≠ 冗余：TypeLib/CLSID 指向哪个哪个就是活的（2026-10-18 round4 差点误删）

round4 判定 `C:\Program Files (x86)\Common Files\NetSarang\XshellCore.tlb`（Xftp/Xshell 共用的 COM 类型库，Xshell 7 已卸载 Xftp 但仍在用）时，因"Xshell 7 安装目录自带同名同大小同时间戳副本"就下了"Common Files 副本冗余可删"的结论——**险些误删在用产品的注册类型库**。补查后真相：

1. **TypeLib 探测两层坑**：① `win32` 值在 `Classes\TypeLib\{GUID}\{版本}\{lcid}\win32` **第四层**，递归 maxdepth 给 2 会整棵漏掉；② **32 位产品的 TypeLib 注册在 `WOW6432Node\Classes\TypeLib`**，只查 64 位根等于没查。实测 `{76F8E8FE-E047-44E6-80B1-302E70CB6B27}\1.0\0\win32` 在两个视图里都指向 Common Files 那份 tlb → 它是**注册表指向的活动文件**，删了 Xshell 的 COM 互操作即坏。
2. **"目录里有同名副本"的唯一判据是注册表指向，不是文件属性**——同名、同大小、同时间戳都不说明冗余；注册表（TypeLib/CLSID/AppID/Installer）指向哪个路径，哪个就是活的。
3. **反向用法**：同一轮发现 `HKLM\SOFTWARE\Classes\CLSID\{037DA433-DCF0-480e-9A61-DCE5F59F1F7D}\InProcServer32 = ...\Common Files\NetSarang\NsCopyHook3.dll`——**DLL 全盘不存在**，注册是死的 → 这才是可删项。且该 CLSID 键名是 GUID，按产品名（netsarang）扫键名**永远扫不到**，只有按值路径扫（APP_DEADKEY 模式）才能命中。
4. **对策固化**：删 Common Files 下任何文件前，先查两个 TypeLib 根 + 两个 CLSID 根 + AppID 的**值路径**是否指向它；厂商多产品共用目录（Common Files\<vendor>）整目录删前必须做这一步。

### 12. 清理模式的匹配集必须是扫描命中集的超集（2026-10-18 round3c 补刀）

round3b v3 删除 BreadcrumbStore 时用 `-like 'Microsoft.VisualStudio.*'`，而复扫阶段实际命中 **22 个**条目——其中 14 个名字是 `netcore,Microsoft.VisualStudio.XXX`（`netcore,` 前缀），模式只覆盖 8 个，**漏删一半**。发现方式：删完后独立复扫按 `*visualstudio*`（宽松通配）重列目录才对上账。

**对策**：
- 清理脚本的匹配模式必须在**扫描命中集**里回放验证：把复扫抓到的每个命中名拿去匹配清理模式，覆盖率必须 100%，差一个就补模式
- 模式要覆盖**前缀/后缀变体**：`Microsoft.VisualStudio.*`、`*Microsoft.VisualStudio.*`、`netcore,*` 是不同形态；宁宽勿窄（宽模式误伤时再收窄，漏删不会自己报错）
- 删完后的独立复扫要用**比清理模式更宽**的通配（如按 `*visualstudio*` 子串匹配，而非前缀匹配），否则自己的复扫会复制自己的盲区

## 七、标准执行顺序（卸载 + 清残留完整流程）

**阶段一：卸载（零章节）**
1. **AskUserQuestion 确认卸载清单**（软件名/版本/安装位置/数据目录大小；卸载不可逆，务必确认）。
2. **跑模板 0** 扫卸载入口（三仓库 `UninstallString`/`QuietUninstallString`/`InstallLocation`）+ `winget list` / `Get-AppxPackage` 补充。
3. **前置释放占用**：taskkill 进程 → 停服务 → 停计划任务（0.3）。
4. **交付卸载脚本**（`.cmd`/`.ps1`，套 0.2 静默参数；沙箱内跑卸载器会被拦截）给用户本机管理员运行；明细清单随脚本同批交付（原则 6）。
5. **卸载验证**（0.5 三必查）：Uninstall 键消失 + 进程消失 + 安装目录消失。失败走 0.6 兜底；一切手段失败转手动卸载，直接进阶段二。

**阶段二：残留清理**
6. **跑全量扫描**（模板 A + 一·五的 147+ 维度清单）→ 输出报告给用户。
7. **用户 Everything 搜索验证** → 让用户用 Everything 搜已卸载软件名，截图发我。这步比脚本扫描更高效，能发现脚本遗漏的路径。
8. 对“疑似孤儿”跑模板 C 查注册表 + 探测真实安装目录，确认是否真卸载。
9. **AskUserQuestion 确认删除清单**（标注每个目标大小与风险；352MB 级数据务必二次确认）。
10. **用户级清理**：跑模板 B（Python 直接删 AppData/HKCU/开始菜单等）。
11. **系统级清理**：交付 `.ps1` + `.cmd` 管理员脚本（Program Files/Common Files/HKLM/计划任务等），让用户本机运行。**交付前必须先展示完整删除明细清单（逐条路径+当前状态+删除方式+风险），用户过目同意后再交付（见原则 6）。**
12. **验证 + 重扫**：用户运行后，用新维度重扫所有已清理软件，确认零残留；**并请用户用 Everything 复核一轮**（见六·七，“验证零残留” ≠ 真零残留）。
13. **更新记忆**：自动将新发现的维度、误报模式、清理方案追加到 SKILL.md 和项目 memory。

### 每次发现新漏洞的自动流程
```
用户 Everything 截图 → 分析遗漏根因 → 修复扫描维度/清理脚本
→ 重扫所有已清理软件 → 更新 SKILL.md + MEMORY.md → 交付用户验证
```

**本流程由原则 7 强制执行，且是"即时"不是"收盘"**：执行中每次发现新漏洞/新模式，**当场**写 SKILL.md + 记忆，不等回合结束（用户 2026-10-18 立规："执行任务过程中发现的经验、漏洞、失误都要立即更新到 Skill……避免这次发现了下次用 Skill 还会犯错"）。
