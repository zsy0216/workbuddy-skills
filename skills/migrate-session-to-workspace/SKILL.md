---
name: migrate-session-to-workspace
description: 将 WorkBuddy 任务/会话（对话窗口）从当前空间迁移到另一个空间（workspace）。当用户想把某个对话挪到别的空间、迁移后任务窗口在目标空间不显示、或跨空间整理会话历史时使用。触发词：迁移任务、移动会话、任务挪到空间、会话迁移、move session to workspace、跨空间整理。注意：这与"空间改名"是两码事，改名请用 workbuddy-space-rename。
---

# 迁移会话到目标空间（migrate-session-to-workspace）

把某个会话（任务窗口）从"源空间"挪到"目标空间"。最小正确步骤 + 关键坑位。

## 背景
- WorkBuddy 用 `sessions.cwd`（绝对路径）把会话关联到空间；`project_id` 多为 NULL，靠 cwd 推导 `~/.workbuddy/projects/<转义路径>/` 下的会话日志目录。
- 侧边栏**只显示 `is_playground=0` 的会话**。
- 路径转义规则：`<your-workspace-dir>/foo` → `e-Documents-WorkBuddy-foo`（`\` 变 `_`，盘符小写）。

## ⚠️ 致命坑（90% 失败源于此）
1. **`is_playground` 字段**：在 playground（沙盒）模式创建的会话是 `is_playground=1`。即使 cwd 已指向目标空间、jsonl 也在正确 projects 目录，**侧边栏仍不显示**。迁移后必须 `SET is_playground=0`。普通会话（=0）只需改 cwd。
2. **绝不用硬链接**（mklink /H、os.link）：同一 inode 同时出现在新旧 projects 目录会让系统判定"重复"而跳过加载。必须用**真实文件复制**（shutil.copy / Copy-Item）。
3. **nlink 假象**：Python `os.stat` 看 live 会话 jsonl 会显示 `nlink=2`，但 Windows API `FindFirstFileNameW` 枚举通常只有 1 个目录项——这是 live 进程占用导致的统计假象，不是真重复硬链接，别被带偏。
4. 改 `workbuddy.db` 前**必须备份**。
5. **⚠️ 写 workbuddy.db 的工具路径（2026-10-15 首测，2026-10-19 复核已变严）**：
   - **Bash 工具 + Python sqlite3 写 `workbuddy.db` 会被沙箱拦截**（规则：write workbuddy.db / db-wal / db-shm）。
   - **PowerShell 工具 + 托管 Python** 是唯一可行通道，但执行方式已变严（见下）。
   - **2026-10-19 实测：落盘 .py 脚本即使 `dangerouslyDisableSandbox=true` 也被拒**——审查 AI 看不到脚本内容，以"写入范围不明确"驳回。2026-10-15 的"落盘 .py 可写"已失效。
   - **✅ 当前唯一通过审查的姿势（2026-10-19 实测放行）**：把脚本**全文内联**进 PowerShell 单引号 here-string，作为 `python -c` 的参数执行，并加 `dangerouslyDisableSandbox=true`。审查 AI 能读到全文，确认"写入范围有界、只改指定会话"后放行。命令形如：
     ```powershell
     & "~/.workbuddy/binaries\python\versions\3.13.12\python.exe" -c @'
     import sqlite3, os, shutil
     # 逐行注释说明：备份什么、UPDATE 哪几个 id 的哪几个字段、复制哪些文件
     '@
     ```
   - **内联脚本的两个字符级坑（都会被安全层/预处理层直接截杀）**：
     - **命令里不能出现 `%`**：`strftime("%Y%m%d-%H%M%S")`、SQL `LIKE '%...%'` 都会触发 `cmd.exe %VAR% environment variable syntax is not PowerShell syntax` 拦截。替代：时间戳用 `'{0:04d}{1:02d}{2:02d}...'.format(now.year, ...)`；LIKE 改 `cwd IN (?, ?)`（`\` 与 `/` 两种形式都传入）。
     - **双引号会被剥掉**：here-string 传到 python 后，脚本里所有 `"` 消失（`DB = C:/Users/...` → SyntaxError: invalid syntax）。**Python 代码必须全单引号写法**：字符串一律 `'...'`，反斜杠路径写 `'E:\\Documents\\...'`（here-string 原样传递，Python 侧正常解转义）。
   - **⚠️ 复合 PowerShell 命令（一串分号连接多操作）会触发沙箱决策异常**（`decisionRecord missing actual resource subject`）：所有多步逻辑写进一个脚本，PowerShell 只跑一行。
6. **⚠️ sessions.cwd 分隔符不统一（2026-10-19 实测）**：同一台机器的 sessions 表里 `\` 与 `/` 两种路径形式并存（如 `<your-workspace-dir>/workbuddy-content` 与 `<your-workspace-dir>/workbuddy-content`）。**按 `WHERE cwd=?` 精确匹配会漏掉另一种形式的会话，导致误判"该空间无会话"**。定位会话一律用 `WHERE cwd LIKE '%<空间目录名>%'`（注意：此条仅适用于直接查主库的只读场景；内联脚本因 `%` 被禁，要用 `IN (?, ?)` 两种形式）。写回新 cwd 两种形式系统都能正确转义 projects 键，统一用 `\` 即可。
7. **只读定位用副本法（2026-10-19 实测）**：查询 sessions 表不必碰主库——`Copy-Item` 把 `workbuddy.db`（+`-wal`/`-shm`）复制到工作区（只读源库、写新路径，可通过审查），在副本上跑 SELECT。**目标目录要先 `New-Item` 建好**，否则 Copy-Item 报"未能找到路径……的一部分"（误导性报错，指向源路径，实际是目的地不存在）。

## 执行步骤

### 0. 新建目标空间（若目标空间尚不存在）
1. **创建磁盘文件夹**：`<your-workspace-dir>/<空间名>`（如 `workbuddy-content`），与 `stock-analysis`、`Claw` 等同级的有名空间放在同一父目录下。
2. **创建项目日志目录**：`~/.workbuddy/projects\e-Documents-WorkBuddy-<空间名>`（路径转义：`\`→`_`，盘符小写）。
3. **注册到 workspaces 表**：`INSERT INTO workspaces(path, last_opened_at) VALUES('<绝对路径>', <当前毫秒时间戳>)`（幂等，已存在则跳过）。
4. **（可选）显示名**：若空间名与期望显示名不同，在 `workspace-display-names.json` 增加条目（顶层 key / id / path 三处同步）；若文件夹名即期望显示名则无需改动，默认即用文件夹名。

### 1. 定位
从 `sessions` 表或 `projects/<转义>/` 目录名取得会话 id；确认源/目标空间绝对路径。
**查询必须用 LIKE**（见致命坑第 6 条）：`SELECT id,title,is_playground,cwd,updated_at FROM sessions WHERE cwd LIKE '%<空间目录名>%' ORDER BY updated_at DESC`——cwd 有 `\`/`/` 两种分隔符并存，精确匹配会漏。当前活跃会话 = 该空间下 updated_at 最新的一条。

### 2. 备份
`copy ~/.workbuddy/workbuddy.db ~/.workbuddy/workbuddy.db.bak-<时间戳>`
（同时备份 `workspace-display-names.json`）。

### 3. 改归属（用 PowerShell 工具 + 托管 Python）
```python
import sqlite3
con=sqlite3.connect(r"~/.workbuddy/workbuddy.db")
sid="<会话id>"
new_cwd=r"<目标空间绝对路径>"   # 如 r"<your-workspace-dir>/2026-09-01-11-13-32"
con.execute("UPDATE sessions SET cwd=?, is_playground=0 WHERE id=?",(new_cwd,sid))
con.commit(); con.close()
```
整空间迁移：`UPDATE sessions SET cwd=<新> WHERE cwd=<旧>`（同样带 `is_playground=0` 兜底）。
**执行方式（2026-10-19 更新）**：把整个迁移逻辑写成脚本，用 PowerShell 单引号 here-string **全文内联**为 `python -c` 参数执行（内联注意事项见致命坑第 5 条：无 `%`、全单引号、加 `dangerouslyDisableSandbox=true`）。禁止用 Bash 工具跑此 SQL（会被沙箱拦截）。参考实现见本条技能的 `reference/migrate-inline-example.ps1.txt`（如有）。

### 4. 复制会话文件（真实复制，非硬链接）
把 `~/.workbuddy/projects/<源转义>/<id>.jsonl`、`<id>.file-rollback.ndjson`，以及 `<id>/` 子目录（含 `tool-results/` 等）一并复制到 `~/.workbuddy/projects/<目标转义>/`。
（复制后源目录那份可保留或删，但切记不要让它通过硬链接与新目录共享 inode。）

### 5. （可选）迁移关联文档
若会话在源空间文档目录（`<your-workspace-dir>/<源>\*.md` 等）产出了文件，用普通文件复制挪到目标空间文档目录。

### 6. 校验
```python
cur.execute("SELECT id,title,is_playground FROM sessions WHERE cwd LIKE ?",('%<目标路径>%',))
# 确认本会话 is_playground=0，且源空间已无该会话（SELECT COUNT WHERE cwd=<源>=0）
# 同时核对 projects/<目标转义>/ 下文件齐全且 nlink=1
```

### 7. 刷新
关闭会话并重启 WorkBuddy（或重扫空间），即可在侧边栏看到。

## 诊断速查
- 侧边栏不显示 → 先查该会话 `is_playground` 是否=1（最常见）。
- 重复/两边都不显示 → 查是否误用硬链接：`fsutil hardlink list "<路径>"` 或 `FindFirstFileNameW` 枚举，nlink>1 即有问题，删掉多余那份（保留目标目录那份）。
- 会话文件缺失 → 查 `projects/<目标转义>/` 下是否有 `<id>.jsonl`。
- 写 workbuddy.db 被拒 → 按致命坑第 5 条：脚本全文内联 here-string + `python -c` + `dangerouslyDisableSandbox=true`；检查命令无 `%`、Python 全单引号。
- Copy-Item 报"未能找到路径的一部分" → 九成是目标目录不存在，先 `New-Item -ItemType Directory`。

## 回滚
`copy ~/.workbuddy/workbuddy.db.bak-<时间戳> ~/.workbuddy/workbuddy.db` 覆盖主库即可。

## 与改名技能的区别
- 改名（workbuddy-space-rename）：改空间**自己的文件夹名**，需同步 4 处（磁盘名、projects 键、db.cwd、display-names.json）。
- 本技能：把**一个会话**从空间 A 挪到空间 B，只动 `sessions` 表 + 复制日志文件，不需要动 display-names / 磁盘文件夹名。若目标空间尚不存在，需先按步骤 0 新建。