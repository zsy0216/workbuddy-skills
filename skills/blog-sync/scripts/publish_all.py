"""
一键双平台发布：博客园 + CSDN

  python publish_all.py --file a.md --category "英语" --tags "A,B" --publish
  python publish_all.py --file a.md --title "自定义标题" --category "英语" --dry-run

默认行为：
  - 未给 --title 时，取正文第一个一级标题作为标题，并从正文中剔除该行
  - 不给 --publish 时两边都只存草稿
"""
import argparse
import io
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from common import BLOG_SYNC_PYTHON, strip_h1  # noqa: E402

CNB = HERE / "publish_cnblogs.py"
CSDN = HERE / "publish_csdn.py"


def run(cmd, timeout=420):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="ignore")
    return p


def parse_json(out):
    for line in reversed((out or "").strip().split("\n")):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except Exception:
                continue
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="Markdown 文件")
    ap.add_argument("--title", default="")
    ap.add_argument("--category", default="", help="分类/分类专栏，两边同名")
    ap.add_argument("--tags", default="")
    ap.add_argument("--summary", default="")
    ap.add_argument("--publish", action="store_true", help="正式发布；否则只存草稿")
    ap.add_argument("--draft", action="store_true", help="强制草稿（覆盖 --publish）")
    ap.add_argument("--dry-run", action="store_true", help="只演练 CSDN 弹窗，不提交")
    ap.add_argument("--skip-cnblogs", action="store_true")
    ap.add_argument("--skip-csdn", action="store_true")
    ap.add_argument("--chrome", choices=["auto", "system", "testing"], default=None,
                    help="CSDN 使用的浏览器：auto=本机 Chrome（默认）")
    ap.add_argument("--show", action="store_true", help="CSDN 显示浏览器窗口")
    ap.add_argument("--headless", action="store_true", help="CSDN 完全无窗口")
    args = ap.parse_args()

    src = Path(args.file)
    if not src.exists():
        print(f"❌ 文件不存在: {src}")
        sys.exit(1)

    md = io.open(src, encoding="utf-8").read()
    derived, body = strip_h1(md)
    title = args.title.strip() or (derived or "")
    if not title:
        print("❌ 未提供 --title，且正文首行不是一级标题")
        sys.exit(1)

    # 标题自带的情况下，剔除与标题重复的首行 H1
    if args.title.strip():
        lines = md.split("\n")
        out, dropped = [], 0
        for ln in lines:
            if dropped < 2 and ln.startswith("# ") and not ln.startswith("## "):
                dropped += 1
                continue
            out.append(ln)
        body = "\n".join(out).lstrip("\n")

    tmp = Path(tempfile.gettempdir()) / f"blogsync_{int(time.time())}.md"
    io.open(tmp, "w", encoding="utf-8").write(body)
    print(f"标题: {title}")
    print(f"正文: {len(body)} 字符")
    print(f"分类: {args.category or '（未指定）'} | 标签: {args.tags or '（未指定）'}")
    print(f"模式: {'正式发布' if (args.publish and not args.draft) else '草稿'}\n")

    results = {}

    # 1) 博客园
    if not args.skip_cnblogs:
        cmd = [sys.executable, str(CNB), "--title", title, "--file", str(tmp), "--json"]
        if args.tags:
            cmd += ["--tags", args.tags]
        if args.category:
            cmd += ["--categories", args.category]
        if args.summary:
            cmd += ["--desc", args.summary]
        if not args.publish or args.draft:
            cmd += ["--draft"]
        print("→ 提交博客园 ...")
        p = run(cmd)
        r = parse_json(p.stdout)
        results["cnblogs"] = r or {"ok": False, "error": (p.stdout or "")[-200:] + (p.stderr or "")[-200:]}
        print(f"   博客园: {'✅ ' + str(r.get('postUrl')) if r.get('ok') else '❌ 失败'}")
    else:
        results["cnblogs"] = {"ok": None, "skipped": True}

    # 2) CSDN（需要 playwright）
    if not args.skip_csdn:
        cmd = [BLOG_SYNC_PYTHON, str(CSDN), "--title", title, "--file", str(tmp), "--json"]
        if args.tags:
            cmd += ["--tags", args.tags]
        if args.category:
            cmd += ["--category", args.category]
        if args.summary:
            cmd += ["--summary", args.summary]
        if args.publish and not args.draft:
            cmd += ["--publish"]
        if args.dry_run:
            cmd += ["--dry-run"]
        if args.chrome:
            cmd += ["--chrome", args.chrome]
        if args.show:
            cmd += ["--show"]
        if args.headless:
            cmd += ["--headless"]
        print("→ 提交 CSDN ...")
        p = run(cmd, timeout=600)
        r = parse_json(p.stdout)
        results["csdn"] = r or {"ok": False, "error": (p.stdout or "")[-200:] + (p.stderr or "")[-200:]}
        print(f"   CSDN: {'✅ ' + str(r.get('url') or r.get('articleId') or r.get('mode')) if r.get('ok') else '❌ 失败'}")
    else:
        results["csdn"] = {"ok": None, "skipped": True}

    print("\n===== 结果汇总 =====")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    try:
        tmp.unlink()
    except Exception:
        pass

    bad = [k for k, v in results.items() if v.get("ok") is False]
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
