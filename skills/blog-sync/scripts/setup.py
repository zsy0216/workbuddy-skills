"""
配置博客园 PAT 并检查环境

  python setup.py --cnblogs-token 你的PAT
  python setup.py --show
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (CONFIG, DATA, PROFILE, BLOG_SYNC_PYTHON, browser_prefs,  # noqa: E402
                    load_config, resolve_chrome, save_config)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cnblogs-token", default="")
    ap.add_argument("--chrome", choices=["auto", "system", "testing"], default=None,
                    help="写入浏览器偏好：auto/system/testing")
    ap.add_argument("--headed", action="store_true", help="写入配置：CSDN 默认显示窗口")
    ap.add_argument("--headless", action="store_true", help="写入配置：CSDN 默认无窗口")
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    changed = False
    if args.cnblogs_token:
        cfg["cnblogs_token"] = args.cnblogs_token.strip()
        changed = True
    if args.chrome:
        cfg["csdn_chrome"] = args.chrome
        changed = True
    if args.headless:
        cfg["csdn_headless"] = True
        changed = True
    if args.headed:
        cfg["csdn_headless"] = False
        changed = True
    if changed:
        save_config(cfg)
        print(f"✅ 已写入 {CONFIG}")

    print("== 当前配置 ==")
    tok = cfg.get("cnblogs_token", "")
    print(f"  博客园 PAT: {tok[:8] + '...' + tok[-4:] if len(tok) > 14 else ('未配置' if not tok else '已配置')}")
    print(f"  配置文件  : {CONFIG}  ({'存在' if CONFIG.exists() else '不存在'})")
    print(f"  数据目录  : {DATA}")
    print(f"  登录 Profile: {PROFILE}  ({'存在' if PROFILE.exists() else '不存在，需跑 login_csdn.py'})")
    print("\n== 环境 ==")
    pref, headless = browser_prefs(None, cfg)
    try:
        exe, label = resolve_chrome(pref)
        print(f"  CSDN 浏览器: {label} | {exe}")
    except Exception as e:
        print(f"  CSDN 浏览器: ❌ {e}")
    print(f"  CSDN 窗口  : {'无窗口（headless）' if headless else '会弹出窗口'}")
    print(f"  CSDN 解释器: {BLOG_SYNC_PYTHON}  ({'存在' if Path(BLOG_SYNC_PYTHON).exists() else '缺失'})")
    try:
        import playwright  # noqa: F401
        print(f"  playwright: 当前解释器已安装 ({sys.executable})")
    except Exception:
        print("  playwright: 当前解释器未安装（请设 BLOG_SYNC_PYTHON 指向装了 playwright 的解释器）")


if __name__ == "__main__":
    main()
