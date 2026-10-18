# WorkBuddy Skills

WorkBuddy 系统工具类 Skill 合集。纯文档型，无代码依赖，跨平台可用。

## 包含的 Skill

| Skill | 用途 | 触发词 |
|---|---|---|
| `migrate-session-to-workspace` | 把会话从一个空间迁移到另一个空间 | 迁移任务、移动会话、跨空间整理 |
| `windows-residue-cleanup` | Windows 软件卸载 + 残留清理（完整流程） | 卸载软件、卸载残留、注册表幽灵项、强制卸载 |
| `workbuddy-space-rename` | WorkBuddy 空间安全改名 | 空间改名、重命名空间、会话失联 |

## 一键导入（换电脑后使用）

```bash
# 1. 克隆仓库
git clone https://github.com/zsy0216/workbuddy-skills
cd workbuddy-skills

# 2. 一键导入所有 Skill
python restore.py

# 3. 重启 WorkBuddy，即可在技能列表中看到它们
```

`restore.py` 会把 `skills/` 下的所有目录复制到 `~/.workbuddy/skills/`，覆盖旧版本。

## 手动安装

也可以直接把 `skills/<name>/` 目录复制到 `~/.workbuddy/skills/` 下，重启 WorkBuddy 即可。

## 脱敏说明

所有 Skill 中的本地绝对路径（如 `C:\Users\ZSY\.workbuddy\`）已替换为占位符：
- `~/.workbuddy/` — WorkBuddy 主目录
- `<your-workspace-dir>/` — 你的工作空间目录

在你自己机器上使用时，按实际路径替换即可，功能不变。

## License

MIT — 见 [LICENSE](LICENSE)。