# WorkBuddy Skills — 自生成 Skill 云端备份

本人自生成的 WorkBuddy Skill 备份仓库。换电脑时克隆本仓库并运行 `restore.py`，即可一次性还原所有已收录 Skill。

仓库：<https://github.com/zsy0216/workbuddy-skills>（Public）

## 备份范围（数据截至 2026-11-11）

本机 `~/.workbuddy/skills/` 共 9 个 Skill：8 个自生成（需备份）、1 个从 SkillHub 安装（换机后重新安装即可，不必备份）。

| # | Skill | 类型 | SKILL.md 行数 | 最后修改 | 备份状态 |
|---|---|---|---|---|---|
| 1 | `blog-sync` | 含 Python 脚本 | 172 | 2026-11-11 | ✅ 本次纳入 |
| 2 | `migrate-session-to-workspace` | 纯文档 | 158 | 2026-11-11 | ✅ 已收录（本次同步更新） |
| 3 | `windows-residue-cleanup` | 纯文档 | 936 | 2026-10-28 | ✅ 已收录 |
| 4 | `workbuddy-space-rename` | 纯文档 | 52 | 2026-09-15 | ✅ 已收录（本次补齐脱敏） |
| 5 | `cn-fund-market-data` | 含配方 / assets | 246 | 2026-09-18 | ⬜ 未纳入 |
| 6 | `html-tool-verify` | 含 JS 脚本 | 261 | 2026-09-14 | ⬜ 未纳入 |
| 7 | `windows-playwright-browser-automation` | 含脚本 / references | 63 | 2026-09-18 | ⬜ 未纳入 |
| 8 | `xhs-reading-notes` | 含脚本 / 素材 | 192 | 2026-09-07 | ⬜ 未纳入 |
| — | `workbuddy-reward-helper` | SkillHub 安装 | 191 | 2026-10-09 | ➖ 不需备份（重新安装） |

> 行数与修改时间为本机 SKILL.md 实测值，非引用外部数据。未纳入的 4 个仍只有本地一份，存在单点风险。

## 一键导入（换电脑后使用）

```bash
# 1. 克隆仓库
git clone https://github.com/zsy0216/workbuddy-skills
cd workbuddy-skills

# 2. 一键导入所有 Skill
python restore.py

# 3. 重启 WorkBuddy，即可在技能列表中看到它们
```

`restore.py` 会把 `skills/` 下的所有子目录复制到 `~/.workbuddy/skills/`，覆盖同名旧版本。

> ⚠️ **不要在本机（已装这些 Skill 的机器）运行 `restore.py`**。它用于新电脑首次导入，会覆盖同名目录。本机 `blog-sync` 含个性化配置与本机专用解释器路径，被发布版覆盖后需重新设置 `BLOG_SYNC_PYTHON` 指向装了 playwright 的解释器。运行时凭据（`config.json`、`chrome-profile/`）存放在 `~/.workbuddy/blog-sync/` 数据目录，不受影响。

## 手动安装

也可以直接把 `skills/<name>/` 目录复制到 `~/.workbuddy/skills/` 下，重启 WorkBuddy 即可。

## blog-sync 的特殊说明（务必先读）

该 Skill 含 Python 脚本与运行时凭据，与其余纯文档 Skill 不同：

| 项目 | 是否随仓库分发 | 换电脑后要做 |
|---|---|---|
| `scripts/*.py`、`references/`、`config/config.example.json` | ✅ 是 | — |
| `config/config.json`（博客园 PAT） | ❌ 否 | `python scripts/setup.py --cnblogs-token <PAT>` |
| `~/.workbuddy/blog-sync/.../chrome-profile/`（CSDN 登录态） | ❌ 否 | `python scripts/login_csdn.py` 扫码一次 |
| `csdn_state.json`、`screenshots/`、`__pycache__/` | ❌ 否 | 运行时自动生成 |

依赖：Python 3、CSDN 部分需 `playwright`、本机 Google Chrome 或 Chrome for Testing、博客园 PAT。

**发布版已做可移植化改造**，因此与本机原始 Skill 并非逐字节一致：

- Chrome for Testing 路径改为按 `Path.home()` 动态发现版本目录，不写死用户名与版本号
- CSDN 解释器由硬编码的 `d:/devtools/python38/python` 改为当前解释器，可用环境变量 `BLOG_SYNC_PYTHON` 覆盖
- `sys.path` 改为 `Path(__file__).parent`，不再写死 skills 目录
- 本机专属环境记录（代理端口、Python 版本、Chrome 版本）已在 SKILL.md 中标注为「本机实测环境」，换机需重新确认

本机 `~/.workbuddy/skills/blog-sync/` 下的原始版本保持不变，本地使用不受影响。

## 脱敏说明

发布副本中的本机绝对路径与个人信息已替换为占位符：

- `~/.workbuddy/` — WorkBuddy 主目录（原始形式类似 `C:\Users\<用户名>\.workbuddy\`）
- `<your-workspace-dir>/` — 工作空间目录
- `your-email@example.com` / `your-machine@your-pc` — 邮箱与机器名

代码与示例代码中的硬编码路径已改为运行时动态解析，而非仅做字符串替换——因为 Python 字符串里的 `~` 不会被自动展开，只替换文本会导致换机后代码直接失效（含 `sqlite3.connect(r"~/...")` 这类示例，已统一改为 `os.path.expanduser(...)`）。

仍需注意：文档中出现的 `~/.workbuddy/binaries/python/versions/<版本>/python.exe` 中版本号属本机环境，换机后按实际版本调整。

发布前扫描范围：本机用户名路径、邮箱、机器名、工作区绝对路径、本机专用解释器路径、Python 字符串里未展开的 `~`，要求零残留。

## 新增 Skill 到备份

把脱敏后的目录放进 `skills/<name>/`，更新上方备份范围表，commit 推送即可。`restore.py` 遍历 `skills/` 下所有子目录，无需修改。

## License

MIT — 见 [LICENSE](LICENSE)。
