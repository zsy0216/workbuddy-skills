"""
发布后校验：博客园审核状态 + CSDN 文章页专栏/标签

  python verify.py --cnblogs-url https://www.cnblogs.com/xxx/p/123.html
  python verify.py --csdn-url https://blog.csdn.net/xxx/article/details/123
"""
import argparse
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import CNBLOGS_REVIEW, load_config  # noqa: E402

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")


def fetch(url):
    """先试 urllib；CSDN 对 urllib 有 521 反爬，回退到 curl"""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except Exception as e:
        import subprocess
        p = subprocess.run(["curl", "-sL", "--compressed", "--max-time", "30",
                            "-A", UA, url],
                           capture_output=True, timeout=45)
        if p.returncode == 0 and p.stdout:
            return 200, p.stdout.decode("utf-8", "ignore")
        raise e


def check_cnblogs(url):
    cfg = load_config()
    tok = cfg.get("cnblogs_token", "")
    if not tok:
        return {"ok": False, "error": "未配置 PAT"}
    body = json.dumps({"url": url}).encode()
    req = urllib.request.Request(CNBLOGS_REVIEW, data=body, method="POST", headers={
        "Authorization": f"Bearer {tok}", "Authorization-Type": "pat",
        "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read().decode())
        v = d.get("value", {})
        return {"ok": True, "postId": v.get("postId"), "reviewStatus": v.get("reviewStatus"),
                "statusText": v.get("description")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def check_csdn(url):
    try:
        st, h = fetch(url)
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}
    if "安全验证" in h or "Security Verification" in h:
        return {"ok": None, "blocked": True,
                "note": "CSDN 反爬拦截了脚本请求，请在浏览器里打开链接确认（发布本身不受影响）"}
    t = re.search(r"<title>(.*?)</title>", h, re.S)
    col = re.search(r'<span class="badge-name">([^<]*)</span>', h)
    kw = re.search(r'<meta name="keywords" content="([^"]*)"', h)
    return {"ok": st == 200, "http": st,
            "title": (t.group(1).strip() if t else None),
            "column": (col.group(1).strip() if col else None),
            "tags": (kw.group(1) if kw else None),
            "bodyLen": len(h)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cnblogs-url", default="")
    ap.add_argument("--csdn-url", default="")
    args = ap.parse_args()

    if args.cnblogs_url:
        print("博客园:", json.dumps(check_cnblogs(args.cnblogs_url), ensure_ascii=False))
    if args.csdn_url:
        print("CSDN  :", json.dumps(check_csdn(args.csdn_url), ensure_ascii=False))
    if not args.cnblogs_url and not args.csdn_url:
        print("请至少给一个 --cnblogs-url / --csdn-url")


if __name__ == "__main__":
    main()
