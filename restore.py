#!/usr/bin/env python3
"""一键导入 WorkBuddy Skill 到本地环境。

用法：
    git clone https://github.com/zsy0216/workbuddy-skills
    cd workbuddy-skills
    python restore.py

会把 skills/ 下的所有子目录复制到 ~/.workbuddy/skills/，
覆盖旧版本，然后重启 WorkBuddy 即可使用。
"""

import pathlib
import shutil
import sys

SRC = pathlib.Path(__file__).resolve().parent / "skills"
DST = pathlib.Path.home() / ".workbuddy" / "skills"


def main() -> int:
    if not SRC.is_dir():
        print(f"✗ 找不到 {SRC}，请在仓库根目录运行本脚本")
        return 1

    DST.mkdir(parents=True, exist_ok=True)
    count = 0

    for d in sorted(SRC.iterdir()):
        if not d.is_dir():
            continue
        target = DST / d.name
        if target.exists():
            shutil.rmtree(target)  # 覆盖旧版本
        shutil.copytree(d, target)
        print(f"✓ {d.name} -> {target}")
        count += 1

    print(f"\n完成：共导入 {count} 个 Skill")
    print("重启 WorkBuddy 后即可在技能列表中看到它们。")
    return 0


if __name__ == "__main__":
    sys.exit(main())