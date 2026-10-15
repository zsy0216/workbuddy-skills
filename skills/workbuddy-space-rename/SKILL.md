---
name: workbuddy-space-rename
description: 安全重命名 WorkBuddy 空间（workspace）。当用户要修改空间磁盘文件夹名、发现改名后"任务对话/会话历史打不开/不能用了"、或想给时间戳空间起有意义的名字时使用。触发词：空间改名、重命名空间、空间命名、文件夹改名后对话不能用了、workspace rename、会话失联。
---

# WorkBuddy 空间安全改名

磁盘文件夹名 = 空间主键。WorkBuddy 在 `~/.workbuddy/projects/` 下用"绝对路径转义"为每个空间建目录（如 `E:\Documents\WorkBuddy\foo` → `e-Documents-WorkBuddy-foo`），存会话日志。侧边栏"显示名"独立存于 `~/.workbuddy/workspace-display-names.json`。

**只改磁盘文件夹名而不同步其他位置，会导致会话历史失联（"对话不能用了"）。必须同步以下 4 处：**

1. 重命名磁盘文件夹：`E:\Documents\WorkBuddy\<旧>` → `<新>`（或在 `C:\Users\ZSY\WorkBuddy\` 下的空间）
2. 重命名 `~/.workbuddy/projects/e-Documents-WorkBuddy-<旧>` → `...-<新>`（C盘路径对应 `c-Users-ZSY-WorkBuddy-<旧>`）
3. 改中央库 `C:\Users\ZSY\.workbuddy\workbuddy.db`：
   `UPDATE sessions SET cwd='<新绝对路径>' WHERE cwd='<旧绝对路径>';`（sessions.cwd 是会话关联空间与 projects 键的依据；project_id 多为 NULL，靠 cwd 推导键名）
4. 若 `workspace-display-names.json` 有该空间条目，同步其 **顶层 key、`id`、`path`** 三处为 `<新路径>`

## 执行前（必做）
- 备份（复制即可，可逆）：`workbuddy.db`、`workspace-display-names.json` → 加 `.bak-<时间戳>` 后缀。
- **当前正在使用的会话文件夹不可改名**（进程占用，Rename-Item 报"访问被拒绝"），须等空间关闭/会话结束后再处理。
- 建议先关闭 WorkBuddy 桌面端再改中央库，改完重启生效。

## 诊断（改名前/发现问题后）
用 Python（托管版 `C:\Users\ZSY\.workbuddy\binaries\python\versions\3.13.12\python.exe`）读 `workbuddy.db`：

```python
import sqlite3
con = sqlite3.connect(r"C:\Users\ZSY\.workbuddy\workbuddy.db"); cur = con.cursor()
print([r for r in cur.execute("SELECT path FROM workspaces")])          # 仅少量注册空间
for r in cur.execute("SELECT cwd, COUNT(*) FROM sessions GROUP BY cwd ORDER BY cwd"): print(r)
for r in cur.execute("SELECT cwds FROM automations"): print(r)
# automation_runs.source_cwd 也查一下
```

核对 `sessions.cwd`、`workspaces.path`、`automations.cwds`、`automation_runs.source_cwd` 是否仍指向旧名；`projects/` 目录键是否已随文件夹改名。

## 修复脚本（PowerShell 调 Python，sessions.cwd 批量替换）
```python
import sqlite3
con = sqlite3.connect(r"C:\Users\ZSY\.workbuddy\workbuddy.db")
con.execute("PRAGMA busy_timeout=15000"); cur = con.cursor()
mapping = [("<旧绝对路径>","<新绝对路径>"), ...]   # 旧用双反斜杠，如 "E:\\Documents\\WorkBuddy\\2026-08-30-18-23-04"
for old, new in mapping:
    n = cur.execute("UPDATE sessions SET cwd=? WHERE cwd=?", (new, old)).rowcount
    print(new, n)
con.commit(); con.close()
```
改完用 `SELECT DISTINCT cwd FROM sessions WHERE cwd LIKE '%<旧时间戳%'` 验证无残留。

## 注意
- 显示名 JSON 里《个人提升》这类自定义名按旧路径存；该空间改名时必须同步（否则显示名失配）。
- 备份文件可长期保留作安全网，确认无误后再清理。
