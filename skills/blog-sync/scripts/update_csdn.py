"""更新 CSDN 已发布文章（就地覆盖标题/正文，标签与专栏保留原设置，articleId 不变）。

用法:
    python update_csdn.py --article 170247326 --file docs/promo-post.md [--dry-run]
"""
import argparse
import io
import os
import re
import sys
import pathlib
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PROFILE, resolve_chrome  # noqa
from playwright.sync_api import sync_playwright


def log(m):
    print(m, flush=True)


def has_dialog(page):
    return page.evaluate("""() => [...document.querySelectorAll('.el-dialog, [role=dialog], div')]
            .some(x => x.offsetHeight > 300 && (x.innerText||'').includes('分类专栏'))""")


def set_title(page, title):
    el = page.query_selector("div.article-bar__title-display")
    if not el:
        return False
    el.click()
    page.wait_for_timeout(500)
    page.keyboard.press("Control+A")
    page.keyboard.press("Delete")
    page.wait_for_timeout(200)
    page.keyboard.insert_text(title)
    return True


def set_body(page, md):
    """用系统剪贴板 + Ctrl+V 写入。
    逐键 insert_text 会让 CSDN 的自动补全改写内容（`2.` → `2. 2.`、`>` → `> >`），
    粘贴走的是编辑器的 paste 管线，按原文插入，实测 109 行逐字一致。"""
    for sel in ["pre.editor__inner", ".editor__inner"]:
        el = page.query_selector(sel)
        if el:
            el.click()
            page.wait_for_timeout(400)
            page.keyboard.press("Control+A")
            page.keyboard.press("Delete")
            page.wait_for_timeout(300)
            page.evaluate("(t) => navigator.clipboard.writeText(t)", md)
            page.wait_for_timeout(500)
            page.keyboard.press("Control+V")
            page.wait_for_timeout(4000)
            return sel
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--article", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-title", action="store_true", help="沿用线上原标题")
    args = ap.parse_args()

    raw = io.open(args.file, encoding="utf-8").read()
    lines = raw.split("\n")
    # 首行 H1 作为标题，正文里去掉（CSDN 标题是独立字段）
    title = None
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        body = "\n".join(lines[1:]).lstrip("\n")
    else:
        raise SystemExit("文件第一行不是 # 标题")

    exe, label = resolve_chrome("system")
    log("浏览器: %s | 标题: %s | 正文 %d 字符" % (label, title, len(body)))

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE), headless=True, executable_path=exe,
            args=["--no-sandbox", "--disable-gpu"], viewport={"width": 1440, "height": 900})
        ctx.grant_permissions(["clipboard-read", "clipboard-write"],
                              origin="https://editor.csdn.net")
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_default_timeout(12000)

        url = "https://editor.csdn.net/md/?articleId=" + args.article
        log("打开 " + url)
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        log("落地 " + page.url)

        if "passport" in page.url or "/login" in page.url:
            log("❌ 未登录")
            ctx.close()
            return

        for txt in ("放弃", "取消"):
            try:
                btn = page.get_by_role("button", name=txt).first
                if btn.is_visible():
                    btn.click(timeout=2000)
                    log("弹窗处理: " + txt)
                    page.wait_for_timeout(1500)
                    break
            except Exception:
                pass

        before = page.evaluate("""() => {
            const b = document.querySelector('.editor__inner');
            return b ? (b.innerText||'').length : 0;}""")
        log("现有正文 %d 字符" % before)

        if args.keep_title:
            log("标题保持不变")
        else:
            if not set_title(page, title):
                log("❌ 标题写入失败")
                ctx.close()
                return
            page.wait_for_timeout(500)
        sel = set_body(page, body)
        log("正文写入 %s" % sel)
        page.wait_for_timeout(2500)

        after = page.evaluate("""() => {
            const t=document.querySelector('.article-bar__title-display');
            const b=document.querySelector('.editor__inner');
            return {title:t?t.innerText.trim():null, len:b?(b.innerText||'').length:0};}""")
        log("回读 %s" % after)

        if args.dry_run:
            got = page.evaluate("""() => {
                const b = document.querySelector('.editor__inner');
                return b ? (b.innerText || '') : '';}""")
            dump = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_dryrun_readback.txt")
            io.open(dump, "w", encoding="utf-8", newline="\n").write(got)
            log("🧪 dry-run：不提交，回读已存 " + dump)
            ctx.close()
            return

        page.get_by_role("button", name="发布文章").first.click()
        end = time.time() + 25
        while time.time() < end and not has_dialog(page):
            page.wait_for_timeout(800)
        log("发布弹窗 %s" % ("已出现" if has_dialog(page) else "未出现"))
        page.wait_for_timeout(1500)

        btns = page.get_by_role("button", name="发布文章")
        try:
            btns.nth(btns.count() - 1).click(timeout=8000)
        except Exception as e:
            log("底部发布按钮失败: %s" % e)
        page.wait_for_timeout(6000)

        for name in ("确认发布", "确定", "继续发布"):
            try:
                b = page.get_by_role("button", name=name)
                if b.count() and b.first.is_visible():
                    b.first.click(timeout=5000)
                    log("二次确认 " + name)
                    page.wait_for_timeout(4000)
                    break
            except Exception:
                continue

        log("最终 URL " + page.url)
        m = re.search(r"/(?:creation/success|article/details)/(\d+)", page.url)
        log("✅ 已更新 articleId=%s" % (m.group(1) if m else args.article))
        ctx.close()


if __name__ == "__main__":
    main()
