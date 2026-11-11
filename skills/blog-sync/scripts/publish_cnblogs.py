"""
博客园发布（官方 OpenAPI · 纯标准库，任意 Python 3 均可跑）

接口: POST https://i.cnblogs.com/openapi/v1/posts
认证: Authorization: Bearer <PAT>  +  Authorization-Type: pat

用法:
  python publish_cnblogs.py --title "标题" --file a.md --publish --categories "英语" --tags "A,B"
  不加 --publish 则存草稿。
"""
import argparse
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import CNBLOGS_API, CNBLOGS_REVIEW, load_config  # noqa: E402


def api(url, payload, token):
    req = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {token}", "Authorization-Type": "pat",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def publish(token, title, body, description="", tags=None, categories=None,
            is_published=True, post_format="Markdown"):
    payload = {
        "title": title,
        "body": body,
        "description": description,
        "postFormat": post_format,        # Markdown | Html
        "isPublished": is_published,
        "isAllowComments": True,
        "isAigc": False,
    }
    if tags:
        payload["tags"] = tags            # string[]
    if categories:
        payload["categories"] = categories  # string[]，分类不存在时博客园会自动创建
    return api(CNBLOGS_API, payload, token)


def review_status(token, post_id=None, url=None):
    payload = {"postId": post_id} if post_id else {"url": url}
    return api(CNBLOGS_REVIEW, payload, token)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--desc", default="")
    ap.add_argument("--tags", default="")
    ap.add_argument("--categories", default="")
    ap.add_argument("--draft", action="store_true", help="只存草稿（默认直接发布）")
    ap.add_argument("--json", action="store_true", help="输出 JSON 便于程序解析")
    args = ap.parse_args()

    p = Path(args.file)
    if not p.exists():
        print(f"❌ 文件不存在: {p}")
        sys.exit(1)
    body = io.open(p, encoding="utf-8").read()

    cfg = load_config()
    token = cfg.get("cnblogs_token", "")
    if not token:
        print("❌ 未配置 cnblogs_token，请运行 scripts/setup.py 或在 config.json 中填写")
        sys.exit(2)

    tags = [t.strip() for t in args.tags.replace("，", ",").split(",") if t.strip()]
    cats = [c.strip() for c in args.categories.replace("，", ",").split(",") if c.strip()]

    status, resp = publish(token, args.title, body, args.desc, tags, cats, not args.draft)

    ok = isinstance(resp, dict) and resp.get("success")
    post_id = resp.get("value", {}).get("postId") if ok else None
    post_url = resp.get("value", {}).get("postUrl") if ok else None

    if args.json:
        print(json.dumps({"ok": bool(ok), "status": status, "postId": post_id,
                          "postUrl": post_url, "raw": resp}, ensure_ascii=False))
        return

    print(f"提交: {args.title} | {len(body)} 字符 | 分类={cats} | 草稿={args.draft}")
    print(f"状态码: {status}")
    if ok:
        print(f"✅ 博客园{'草稿' if args.draft else '发布'}成功")
        print(f"   postId: {post_id}")
        print(f"   URL: {post_url}")
    else:
        print("❌ 博客园提交失败")
        print(json.dumps(resp, ensure_ascii=False, indent=2) if isinstance(resp, dict) else resp)
        sys.exit(3)


if __name__ == "__main__":
    main()
