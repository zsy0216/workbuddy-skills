"""blog-sync 公共配置与工具"""
import io
import json
import re
import os
import sys
from pathlib import Path

DATA = Path(os.path.expanduser("~/.workbuddy/blog-sync"))
CONFIG = DATA / "config.json"
# 登录态 Profile 沿用历史路径（移动会破坏已保存的 CSDN 登录）
PROFILE = DATA / "skills" / "cnblogs-csdn" / "chrome-profile"
SHOTS = DATA / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)

# CSDN 脚本解释器：默认当前解释器；可用环境变量 BLOG_SYNC_PYTHON 覆盖
BLOG_SYNC_PYTHON = os.environ.get("BLOG_SYNC_PYTHON") or sys.executable

# 浏览器候选：system=你本机安装的正版 Chrome；testing=WorkBuddy 自带的 Chrome for Testing
CHROME_SYSTEM = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]
# Chrome for Testing：按 home 目录动态发现，不写死用户名与版本号
def _chrome_ver_key(p):
    m = re.search(r"chrome-([\d.]+)", p.parent.name)
    return tuple(int(x) for x in m.group(1).split(".")) if m else (0,)

_BROWSERS = Path.home() / ".agent-browser" / "browsers"
CHROME_TESTING = [str(p) for p in sorted(
    _BROWSERS.glob("chrome-*/chrome.exe"), key=_chrome_ver_key, reverse=True)]
# 兼容旧引用
CHROME = CHROME_TESTING[0] if CHROME_TESTING else ""


def resolve_chrome(pref="auto"):
    """按偏好返回 (可执行文件路径, 说明)。auto=优先本机 Chrome，缺失则用 Chrome for Testing。"""
    pref = (pref or "auto").lower()
    system = next((p for p in CHROME_SYSTEM if os.path.isfile(p)), None)
    testing = next((p for p in CHROME_TESTING if os.path.isfile(p)), None)
    if pref == "system":
        if not system:
            raise RuntimeError("未找到本机安装的 Google Chrome，请改 --chrome testing")
        return system, "本机 Chrome"
    if pref == "testing":
        if not testing:
            raise RuntimeError("未找到 Chrome for Testing")
        return testing, "Chrome for Testing（测试版）"
    if system:
        return system, "本机 Chrome"
    if testing:
        return testing, "Chrome for Testing（测试版）"
    raise RuntimeError("未找到任何可用的 Chrome")


def browser_prefs(args=None, cfg=None):
    """合并命令行参数与 config.json 的浏览器偏好，返回 (chrome_pref, headless)"""
    cfg = cfg if cfg is not None else load_config()
    pref = getattr(args, "chrome", None) or cfg.get("csdn_chrome") or "auto"
    if getattr(args, "show", False):
        headless = False
    elif getattr(args, "headless", False):
        headless = True
    else:
        headless = bool(cfg.get("csdn_headless", True))
    return pref, headless

CNBLOGS_API = "https://i.cnblogs.com/openapi/v1/posts"
CNBLOGS_REVIEW = "https://i.cnblogs.com/openapi/v1/posts/reviewStatus:check"
CSDN_EDITOR = "https://editor.csdn.net/md/"


def load_config():
    if CONFIG.exists():
        return json.loads(io.open(CONFIG, encoding="utf-8").read())
    # 兼容历史位置
    legacy = DATA / "skills" / "cnblogs-csdn" / "config.json"
    if legacy.exists():
        return json.loads(io.open(legacy, encoding="utf-8").read())
    return {}


def save_config(cfg):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    io.open(CONFIG, "w", encoding="utf-8").write(
        json.dumps(cfg, ensure_ascii=False, indent=2))


def strip_h1(md):
    """去掉正文开头 1~2 个一级标题（导出文件常自带重复标题），返回 (标题, 正文)"""
    lines = md.split("\n")
    title, out, dropped = None, [], 0
    for ln in lines:
        if dropped < 2 and ln.startswith("# ") and not ln.startswith("## "):
            if title is None:
                title = ln[2:].strip()
            dropped += 1
            continue
        out.append(ln)
    return title, "\n".join(out).lstrip("\n")


def split_tags(s):
    import re
    return [t.strip() for t in re.split(r"[,，]", s or "") if t.strip()]
