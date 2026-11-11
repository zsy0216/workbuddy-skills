"""
CSDN 发布（Playwright 驱动已登录 Chrome Profile · 不需要 Cookie / 不需要 CA 签名）

前置：先跑一次 login_csdn.py 扫码登录，登录态持久保存在本地 Profile，长期复用。

用法:
  python publish_csdn.py --title "标题" --file a.md                    # 只存草稿
  python publish_csdn.py --title "标题" --file a.md --publish          # 正式发布
  python publish_csdn.py --title "标题" --file a.md --publish --dry-run # 演练（走完弹窗不提交）
       --category "英语" --tags "标签1,标签2" --summary "摘要"

必须用装了 playwright 的解释器运行（可用环境变量 BLOG_SYNC_PYTHON 指定）。
"""
import argparse
import io
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (CSDN_EDITOR, PROFILE, SHOTS, browser_prefs,  # noqa: E402
                    load_config, resolve_chrome, split_tags)


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def shot(page, name):
    try:
        page.screenshot(path=str(SHOTS / f"{name}.png"))
    except Exception:
        pass


# 弹窗内按 label 文本定位 form-tag-box
BOX_JS = """(label) => {
    const dlg = [...document.querySelectorAll('.el-dialog, [role=dialog], div')]
        .filter(d => d.offsetHeight > 300 && (d.innerText||'').includes('分类专栏')).pop();
    if (!dlg) return null;
    const boxes = [...dlg.querySelectorAll('.form-tag-box')];
    return boxes.find(b => ((b.querySelector('.form-entry__label')||{}).innerText||'').includes(label)) || null;
}"""


def chips(page, label):
    """读取区域「已选中」的 chip。
    - 文章标签：结构是 span.el-tag
    - 分类专栏：结构是 .tag__name（但要排除下拉面板 .tag__options-content 里的候选项，
      否则会把未选中的建议项误判为已选）"""
    return page.evaluate("""(args) => {
        const [label, jsBody] = args;
        const box = (new Function('label', 'return (' + jsBody + ')(label)'))(label);
        if (!box) return [];
        if (String(label).includes('标签')) {
            return [...box.querySelectorAll('span.el-tag')].map(e => {
                const c = e.cloneNode(true); const ic = c.querySelector('i'); if (ic) ic.remove();
                return (c.textContent||'').trim();
            }).filter(Boolean);
        }
        const items = [...box.querySelectorAll('.tag__name')]
            .filter(e => !e.closest('.tag__options-content'));
        return [...new Set(items.map(e => (e.innerText||'').trim()))].filter(Boolean);
    }""", [label, BOX_JS])


def wait_dialog(page, timeout=20000):
    end = time.time() + timeout / 1000
    while time.time() < end:
        if page.evaluate("""() => [...document.querySelectorAll('.el-dialog, [role=dialog], div')]
                .some(x => x.offsetHeight > 300 && (x.innerText||'').includes('分类专栏'))"""):
            return True
        page.wait_for_timeout(800)
    return False


def set_title(page, title):
    el = page.query_selector("div.article-bar__title-display")
    if not el:
        return False
    el.click()
    page.wait_for_timeout(600)
    page.keyboard.press("Control+A")     # 编辑器可能恢复上次草稿标题，必须先清空
    page.keyboard.press("Delete")
    page.wait_for_timeout(200)
    page.keyboard.insert_text(title)
    return True


def set_body(page, md):
    for sel in ["pre.editor__inner", ".editor__inner"]:
        el = page.query_selector(sel)
        if el:
            el.click()
            page.wait_for_timeout(400)
            page.keyboard.press("Control+A")
            page.keyboard.press("Delete")
            page.wait_for_timeout(200)
            page.keyboard.insert_text(md)    # 一次性写入，保留换行
            return sel
    return None


def open_panel(page, label):
    if chips(page, label):        # 已有 chip 时点「新建」会多出空 chip
        return "has-chip"
    page.evaluate("""(args) => {
        const [label, jsBody] = args;
        const box = (new Function('label', 'return (' + jsBody + ')(label)'))(label);
        if (!box) return;
        const btn = box.querySelector('.tag__btn-tag');
        if (btn) btn.click();
    }""", [label, BOX_JS])
    page.wait_for_timeout(1600)
    return "opened"


def prune_tags(page, label, keep):
    """删掉不在 keep 里的 chip（CSDN 会把上次用过的标签带进弹窗）。
    用真实鼠标点击 i.el-tag__close —— 纯 JS click 对 Element UI 的 chip 无效。"""
    removed = []
    for _ in range(3):
        box = page.evaluate_handle("""(args) => {
            const [label, jsBody] = args;
            return (new Function('label','return ('+jsBody+')(label)'))(label);
        }""", [label, BOX_JS]).as_element()
        if not box:
            return "no-box"
        chips_el = box.query_selector_all("span.el-tag")
        if not chips_el:
            break
        acted = False
        for el in chips_el:
            try:
                name = (el.inner_text() or "").strip()
                if not name or name in keep:
                    continue
                close = el.query_selector("i.el-tag__close")
                if not close:
                    continue
                close.click(force=True, timeout=3000)
                removed.append(name)
                page.wait_for_timeout(500)
                acted = True
                break          # DOM 已变，重新取
            except Exception:
                continue
        if not acted:
            break
    return removed


def add_tags(page, tags):
    if not tags:
        return
    existing = chips(page, "文章标签")
    todo = [t for t in tags if t not in existing]
    if not todo:
        log(f"标签已齐: {existing}")
        return
    try:
        page.get_by_role("button", name="添加文章标签").first.click(timeout=8000)
        page.wait_for_timeout(1200)
    except Exception as e:
        log(f"标签面板打不开（可能已达 7 个上限）: {str(e)[:60]}")
        return
    for t in todo:
        try:
            inp = page.query_selector("input[placeholder*='标签']")
            if not inp:
                log("未找到标签输入框")
                break
            inp.click(timeout=6000)
            inp.fill("")
            inp.type(t, delay=25)
            page.wait_for_timeout(500)
            page.keyboard.press("Enter")
            page.wait_for_timeout(600)
            log(f"加标签: {t}")
        except Exception as e:
            log(f"标签失败 {t}: {str(e)[:80]}")


def _blur_dropdown(page):
    """点弹窗标题收起下拉。不能用 Escape —— 会关闭整个发布弹窗！"""
    try:
        page.get_by_text("发布文章", exact=True).first.click(timeout=4000)
    except Exception:
        pass
    page.wait_for_timeout(500)


def set_summary(page, summary):
    if not summary:
        return False
    _blur_dropdown(page)
    for i in range(3):
        try:
            ta = (page.query_selector("textarea[placeholder*='各展现列表']")
                  or page.query_selector("textarea.el-textarea__inner"))
            if not ta:
                page.wait_for_timeout(800)
                continue
            ta.scroll_into_view_if_needed()
            ta.click(timeout=6000)
            page.wait_for_timeout(300)
            page.keyboard.press("Control+A")
            page.keyboard.insert_text(summary[:250])
            page.wait_for_timeout(400)
            log("摘要已填")
            return True
        except Exception as e:
            log(f"摘要尝试{i+1}失败: {str(e)[:60]}")
            _blur_dropdown(page)
    log("⚠️ 摘要未填，继续")
    return False


def pick_column(page, category, attempts=3):
    if category in chips(page, "分类专栏"):
        log(f"专栏已选中: {category}")
        return True
    for i in range(attempts):
        open_panel(page, "分类专栏")
        r = page.evaluate("""(args) => {
            const [cat, jsBody] = args;
            const box = (new Function('label', 'return (' + jsBody + ')(label)'))('分类专栏');
            if (!box) return 'no-box';
            const panel = box.querySelector('.tag__options-content');
            if (!panel) return 'no-panel';
            const opts = [...panel.querySelectorAll('.tag__option-box')];
            const hit = opts.find(o => ((o.querySelector('.tag__option-label')||{}).innerText||'').trim() === cat);
            if (!hit) return 'not-found';
            (hit.querySelector('.tag__option-label') || hit).click();  // 必须点 label，点 box 无效
            return 'clicked';
        }""", [category, BOX_JS])
        page.wait_for_timeout(1400)
        names = chips(page, "分类专栏")
        log(f"第{i+1}次点选 {category}: {r} | chips={names}")
        if category in names:
            return True
    return False


def run(args):
    from playwright.sync_api import sync_playwright

    md = io.open(args.file, encoding="utf-8").read()
    tags = split_tags(args.tags)
    result = {"platform": "csdn", "ok": False}

    pref, headless = browser_prefs(args)
    exe, label = resolve_chrome(pref)
    log(f"浏览器: {label} | {exe} | headless={headless}")
    result.update(browser=label, headless=headless)

    with sync_playwright() as pctx:
        ctx = pctx.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE), headless=headless, executable_path=exe,
            args=["--no-sandbox", "--disable-gpu"], no_viewport=True)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_default_timeout(8000)

        r = page.goto(CSDN_EDITOR, timeout=60000, wait_until="domcontentloaded")
        log(f"编辑器 {r.status if r else 'n/a'}")
        page.wait_for_timeout(4500)

        if "passport" in page.url or "/login" in page.url:
            log("❌ 未登录，先跑 login_csdn.py 扫码登录")
            result["error"] = "not-logged-in"
            ctx.close()
            return result

        try:
            q = page.evaluate("""() => {
                const m = (document.body.innerText||'').match(/今日发文额度还有\\s*(\\d+)\\s*篇/);
                return m ? +m[1] : null;}""")
            log(f"今日发文额度剩余: {q}")
            result["quota"] = q
        except Exception:
            pass

        log(f"写入标题: {args.title}")
        if not set_title(page, args.title):
            result["error"] = "title-failed"
            ctx.close()
            return result
        page.wait_for_timeout(600)

        sel = set_body(page, md)
        log(f"正文写入 {sel} | {len(md)} 字符")
        page.wait_for_timeout(2000)

        st = page.evaluate("""() => {
            const t=document.querySelector('.article-bar__title-display');
            const b=document.querySelector('.editor__inner');
            return {title:t?t.innerText.trim().slice(0,60):null, bodyLen:b?(b.innerText||'').length:0};}""")
        log(f"回读: {json.dumps(st, ensure_ascii=False)}")

        if not args.publish:
            page.get_by_role("button", name="保存草稿").first.click()
            page.wait_for_timeout(4000)
            shot(page, "draft_saved")
            log(f"草稿已存 | {page.url}")
            result.update(ok=True, mode="draft", url=page.url)
            ctx.close()
            return result

        page.get_by_role("button", name="发布文章").first.click()
        if not wait_dialog(page):
            log("❌ 发布弹窗未出现")
            shot(page, "no_dialog")
            result["error"] = "no-dialog"
            ctx.close()
            return result
        page.wait_for_timeout(1500)
        shot(page, "dialog")

        if tags:
            log(f"清理默认标签(前): {prune_tags(page, '文章标签', tags)}")
        add_tags(page, tags)
        if tags:
            log(f"清理默认标签(后): {prune_tags(page, '文章标签', tags)}")
        log(f"标签最终: {chips(page, '文章标签')}")
        set_summary(page, args.summary)

        col_ok = True
        if args.category:
            col_ok = pick_column(page, args.category)
        shot(page, "dialog_filled")

        if args.dry_run:
            log("🧪 演练模式：不提交")
            try:
                page.get_by_role("button", name="取消").last.click(timeout=5000)
                page.wait_for_timeout(1200)
            except Exception as e:
                log(f"取消失败 {e}")
            result.update(ok=True, mode="dry-run", column_ok=col_ok)
            ctx.close()
            return result

        if args.category and not col_ok:
            log("⚠️ 专栏未确认选中，仍继续发布（可在文章页补设）")

        btns = page.get_by_role("button", name="发布文章")
        try:
            btns.nth(btns.count() - 1).click(timeout=8000)
        except Exception as e:
            log(f"底部发布按钮失败: {e}")
        page.wait_for_timeout(6000)

        for name in ["确认发布", "确定", "继续发布"]:
            try:
                b = page.get_by_role("button", name=name)
                if b.count() and b.first.is_visible():
                    b.first.click(timeout=5000)
                    log(f"二次确认 {name}")
                    page.wait_for_timeout(4000)
                    break
            except Exception:
                continue

        shot(page, "after_publish")
        log(f"最终 URL: {page.url}")
        m = re.search(r"/creation/success/(\d+)", page.url) or re.search(r"/article/details/(\d+)", page.url)
        # 成功页上「查看文章」链接可拿到真实博客地址（含用户名）
        href = page.evaluate("""() => {
            const a = [...document.querySelectorAll('a')]
                .map(x => x.href).find(h => /\\/article\\/details\\/\\d+/.test(h));
            return a || null;}""")
        if m:
            aid = m.group(1)
            log(f"✅ CSDN 发布成功 articleId={aid}")
            result.update(ok=True, mode="publish", articleId=aid,
                          url=href or f"https://blog.csdn.net/article/details/{aid}")
        elif href:
            log(f"✅ CSDN 已提交: {href}")
            result.update(ok=True, mode="publish", url=href)
        else:
            log("⚠️ 未识别成功页，请查截图")
            result.update(error="unknown-result", url=page.url)
        page.wait_for_timeout(3000 + args.keep_window * 1000)
        ctx.close()
        return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--tags", default="")
    ap.add_argument("--category", default="")
    ap.add_argument("--summary", default="")
    ap.add_argument("--publish", action="store_true", help="正式发布；否则只存草稿")
    ap.add_argument("--dry-run", action="store_true", help="演练：不提交")
    ap.add_argument("--keep-window", type=int, default=0)
    ap.add_argument("--chrome", choices=["auto", "system", "testing"], default=None,
                    help="auto=优先本机 Chrome（默认）；testing=WorkBuddy 自带 Chrome for Testing")
    ap.add_argument("--headless", action="store_true", help="无头运行：完全不弹窗口")
    ap.add_argument("--show", action="store_true", help="强制显示浏览器窗口（调试用）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    res = run(args)
    # 无头模式遇到早期失败（标题/弹窗没出来）→ 自动换有头重试一次，便于排查与兜底
    if (not res.get("ok")) and res.get("headless") and res.get("error") in ("title-failed", "no-dialog"):
        log("无头模式未成功，自动切换为有头模式重试一次")
        args.show, args.headless = True, False
        res = run(args)
    if args.json:
        print(json.dumps(res, ensure_ascii=False))
    if not res.get("ok"):
        sys.exit(1)


if __name__ == "__main__":
    main()
