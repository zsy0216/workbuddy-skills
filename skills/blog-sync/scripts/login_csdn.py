"""
CSDN 登录（持久化用户目录，一次扫码长期复用）

- launch_persistent_context(user_data_dir=PROFILE) → 登录 Cookie 自动长期保存
- 之后 publish_csdn.py 复用同一 Profile，无需任何 Cookie / 签名
- 轮询检测登录态，成功后导出 storage_state 备份

用法: python login_csdn.py [--timeout 600]
"""
import argparse
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import DATA, PROFILE, browser_prefs, resolve_chrome  # noqa: E402

STATE = DATA / "csdn_state.json"
LOG = DATA / "login_status.log"


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def is_logged_in(ctx):
    try:
        names = {c["name"] for c in ctx.cookies() if "csdn.net" in c.get("domain", "")}
        key = {"UserToken", "UserName", "UserNick", "UserInfo"} & names
        return bool(key), sorted(key)
    except Exception:
        return False, []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=600, help="等待登录的秒数")
    ap.add_argument("--chrome", choices=["auto", "system", "testing"], default=None,
                    help="auto=优先本机 Chrome（默认）")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    pref, _ = browser_prefs(args)
    exe, label = resolve_chrome(pref)
    log(f"浏览器: {label} | {exe}")

    PROFILE.mkdir(parents=True, exist_ok=True)
    log("启动 CSDN 登录（持久化用户目录）")
    log(f"Profile: {PROFILE}")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE), headless=False, executable_path=exe,
            args=["--no-sandbox", "--disable-gpu", "--start-maximized"], no_viewport=True)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        ok, keys = is_logged_in(ctx)
        if ok:
            log(f"已存在登录态: {keys}")
        else:
            log("未检测到登录态，打开登录页，请在浏览器窗口扫码登录")
            try:
                page.goto("https://passport.csdn.net/login", timeout=40000,
                          wait_until="domcontentloaded")
            except Exception as e:
                log(f"打开登录页异常: {e}")

        deadline = time.time() + args.timeout
        last = 0
        while time.time() < deadline:
            time.sleep(3)
            ok, keys = is_logged_in(ctx)
            if ok:
                log(f"✅ 登录成功: {keys}")
                break
            if time.time() - last > 30:
                log("等待登录中...（请在浏览器窗口完成扫码/登录）")
                last = time.time()

        ok, keys = is_logged_in(ctx)
        if ok:
            try:
                ctx.storage_state(path=str(STATE))
                log(f"登录态已备份: {STATE}")
                vp = ctx.new_page()
                r = vp.goto("https://editor.csdn.net/md/", timeout=40000,
                            wait_until="domcontentloaded")
                log(f"编辑器验证: HTTP {r.status if r else 'n/a'}")
                vp.close()
            except Exception as e:
                log(f"验证异常: {e}")
            log("RESULT=SUCCESS")
        else:
            log("RESULT=FAILED 超时未检测到登录态")
        try:
            ctx.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
