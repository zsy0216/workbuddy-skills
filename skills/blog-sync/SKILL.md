---
name: blog-sync
description: 一键把 Markdown 文章同步发布到博客园和 CSDN，全程不需要手动复制 Cookie 或计算签名。当用户说"发文章到博客园/CSDN""同步发布博客""一键双平台发布""把这篇文章发出去""存成草稿到 CSDN"，或提供了一篇 md/文档要发布到中文技术博客平台时使用。触发词：发布文章、同步博客、博客园发布、CSDN 发布、多平台分发、blog-sync。不适用于微信公众号、掘金、知乎（本技能只覆盖博客园 + CSDN）。
---

# 博客园 + CSDN 一键发布（blog-sync）

把一篇 Markdown 一次发到两个平台。博客园走官方 OpenAPI；CSDN 走"已登录 Chrome 自动化"，**不需要 Cookie、不需要阿里云 CA 签名**。

## 一、什么时候用

- 用户给了一篇 md / 文档，要发到博客园、CSDN 或"两边都发"
- 要批量把本地文章同步上博客
- 要存草稿而不是直接公开

不适用：微信公众号、掘金、知乎、Halo（本技能未实现）。

## 二、环境依赖（一次性）

| 项目 | 要求 |
| --- | --- |
| 博客园 PAT | 在 <https://account.cnblogs.com/settings/tokens> 创建，用 `scripts/setup.py --cnblogs-token <PAT>` 写入 |
| CSDN 登录 | 跑一次 `scripts/login_csdn.py`，在弹出的 Chrome 里扫码；登录态存进本地 Profile，之后长期复用 |
| 浏览器 | 默认用**你本机安装的 Google Chrome**（`C:\Program Files\Google\Chrome\Application\chrome.exe`）；找不到才回退 WorkBuddy 自带的 Chrome for Testing（测试版）。用 `scripts/setup.py --show` 可看当前指向哪个 |
| 是否弹窗 | 默认 **headless 无窗口**（后台跑完自动退出）；要亲眼看操作过程加 `--show` |
| Python | 博客园部分任意 Python 3 都行；CSDN 部分必须用装了 playwright 的解释器。默认用当前 `python`；若该解释器未装 playwright，设环境变量 `BLOG_SYNC_PYTHON` 指向对应 python 可执行文件 |

浏览器相关开关（脚本通用）：

```bash
--chrome auto|system|testing   # auto=本机 Chrome（默认）/ 强制系统 Chrome / 用测试版 Chrome
--show                          # 强制显示窗口（调试、或怀疑被反爬时）
--headless                      # 强制无窗口
```

偏好可持久化，避免每次传参：

```bash
python scripts/setup.py --chrome system --headless   # 写入 config.json 作为默认
python scripts/setup.py --headed                      # 改成默认显示窗口
```

检查环境：`python scripts/setup.py --show`

## 三、最常用命令

```bash
# 一键双平台正式发布（标题自动取正文第一个 # 一级标题）
python <SKILL_DIR>/scripts/publish_all.py --file a.md \
    --category "英语" --tags "新概念英语,英语语法" --summary "摘要（≤250字）" --publish

# 只存草稿（两边都进草稿箱，CSDN 不消耗当日发文额度）
python <SKILL_DIR>/scripts/publish_all.py --file a.md --category "英语"

# 先演练 CSDN 弹窗（不提交、不耗额度），确认标签/专栏都对
python <SKILL_DIR>/scripts/publish_all.py --file a.md --category "英语" --publish --dry-run

# 只发一个平台
python <SKILL_DIR>/scripts/publish_all.py --file a.md --category "英语" --publish --skip-csdn
python <SKILL_DIR>/scripts/publish_all.py --file a.md --category "英语" --publish --skip-cnblogs
```

单平台脚本（调试用）：

```bash
python <SKILL_DIR>/scripts/publish_cnblogs.py --title "T" --file a.md --publish --categories "英语" --tags "A,B"
python <SKILL_DIR>/scripts/publish_csdn.py --title "T" --file a.md --publish \
    --category "英语" --tags "A,B" --summary "..."
```

发布后校验：

```bash
python <SKILL_DIR>/scripts/verify.py \
    --cnblogs-url https://www.cnblogs.com/<blog>/p/<id> \
    --csdn-url https://blog.csdn.net/<user>/article/details/<id>
```

> CSDN 有反爬，脚本请求可能被拦成"安全验证"页，此时 `verify.py` 会返回 `blocked: true`（不代表发布失败）。要确认 CSDN 的专栏/标签，用浏览器打开文章页或看后台「内容管理」。

## 三·五、更新已发布文章（必须走真实浏览器，PAT/脚本做不到）

两个平台都**只能新建、不能改**（见坑位 17/20），而且都需要登录态。**用用户正在用的浏览器**（浏览器扩展接入，`browser_id` 通常为 2），不要另起 Playwright 的 Chrome —— 那个 profile 往往只有 CSDN 的登录态，博客园会掉登录。

### A. 博客园

1. 打开 `https://i.cnblogs.com/posts/edit;postId=<id>`（**分号**！`?postId=` 是空白新建页）。
2. **先刷新一次**：上一轮没保存的脏状态会被丢弃，回到已保存版本。
3. 标题框是独立 `<input>`，正文是 `<textarea name="editor">`。改正文前**先删 1 个字符并截图**确认焦点（坑位 22）。
4. 正文替换：`Set-Clipboard` 写文本 → 点正文 → `Ctrl+A` → `Delete` → `Ctrl+V`。只精简开头几行时更安全：`Ctrl+Home` + 连续 `Delete`。
5. 底部「保存修改」→ 出现绿色「保存成功」浮层 + 「随笔标题：…」回显。
6. 前台复核：标题只出现一次（正文里**不要再留 H1**，博客园标题已是 H1）、左栏目录节数正确、图片全部渲染。

### B. CSDN

1. 打开 `https://editor.csdn.net/md/?articleId=<id>`，articleId 不变即覆盖。
2. 正文替换同上（剪贴板，坑位 18）。
3. **逐张确认外链图转存结果**（坑位 19）：源码里必须是 `i-blog.csdnimg.cn/img_convert/...`；若是 `[外链图片转存中...]` 纯文本 → 换域名重贴（坑位 21）。
4. 「发布文章」→ 弹窗确认（标签/封面/摘要会自动沿用）→ 成功页有「查看文章」。
5. 线上复核：三张图都能渲染；审核期间页面标「审核中」属正常。

### C. 只用真实浏览器时的操作要点

- 长文本靠系统剪贴板，不靠 `type`（会丢换行 / 被自动补全改写）。
- `cua_execute` 的 `keypress` 单次最多 8 个键、且不支持 `Shift+End` 组合；清空一行用 `Ctrl+Home` + N 次 `Delete` 更可控。
- 页面滚动用 `keypress` 的 `PageDown` / `Home` 最稳（`cua_scroll` 经常超时）。
- 每次关键动作后取一张截图，别连续盲操作。

## 四、关键参数

| 参数 | 说明 |
| --- | --- |
| `--file` | Markdown 文件路径（必填） |
| `--title` | 不填则取正文第一个 `# ` 行；正文里重复的一级标题会被自动剔除 |
| `--category` | 分类名，**两边同名**：博客园=分类(categories)，CSDN=分类专栏 |
| `--tags` | 逗号分隔，CSDN 最多 7 个（含账号自动带上的旧标签） |
| `--summary` | 文章摘要，CSDN 上限 256 字 |
| `--publish` | 正式发布；缺省=只存草稿 |
| `--dry-run` | CSDN 走完发布弹窗但不点提交 |

## 五、平台行为差异（重要）

| 项目 | 博客园 | CSDN |
| --- | --- | --- |
| 通道 | 官方 REST API + PAT | 浏览器自动化（无公开 API） |
| 数据格式 | 直接吃 Markdown | 需写入 Markdown 编辑器（`pre.editor__inner`） |
| 分类 | `categories: ["英语"]`，不存在时自动创建 | 分类专栏必须已存在（或点「新建分类专栏」手建） |
| 审核 | 一般即时通过，可用 `reviewStatus:check` 查 | 发布后进"正在审核中"，通常数分钟 |
| 限制 | **无删除接口**（`DELETE` 404，MetaWeblog `deletePost` 也失败） | 免费账号有「今日发文额度」，超了要等次日 |
| 幂等 | 每次调用都新建一篇文章 | 每次发布都新建；同内容重复发布会重复 |

## 六、坑位清单（都已踩过，改动前务必先看）

1. **`Escape` 会关掉整个 CSDN 发布弹窗**。收起下拉只能用点击弹窗标题的方式（脚本里是 `_blur_dropdown`）。
2. **点「新建分类专栏」只会生成一个空 chip**，不是选中已有专栏。选中必须点下拉面板里 `.tag__option-label`。
3. **CSDN 会记住上次的发布设置**（标签、专栏、摘要），下次打开弹窗是上次的状态。所以每步都要"读现状再决定加/删"，不能盲加。
4. 标签达 7 个上限后「添加文章标签」按钮会消失，脚本会记一条提示并继续。
5. 账号会**自动带上历史标签**（如 笔记/java/服务器），脚本用 `prune_tags` 按白名单清掉。
6. CSDN 编辑器可能**恢复上次草稿的标题**，写标题前必须 `Ctrl+A` + `Delete`。
7. 长文写入用 `keyboard.insert_text` 一次性插入（17k 字符约 4 秒），逐字 type 会超时。
8. 发布成功页 URL 是 `/creation/success/<articleId>`，不是文章页；真实博客地址要从"查看文章"链接取。
9. **本机实测环境（换机需重新确认）**：代理 7890 不通，Playwright 不要加 `--proxy-server`；若你的机器走代理，需按实际环境调整。
10. **本机实测环境（换机需重新确认）**：playwright 曾装在 Python 3.8、默认 `python` 是 3.13。发布版改为动态取解释器，不再写死版本号；用 `BLOG_SYNC_PYTHON` 覆盖即可。
11. 博客园新文章刚发布时公开 URL 可能短暂 404（CDN/缓存），过几十秒再访问；用 `reviewStatus:check` 判断更准。
12. 博客园「随笔分类」页需要登录才能看，脚本无法直接证实分类是否落到目标分类；判定依据是页面 `<meta name="keywords">` 里出现该分类名（博客园会把 categories 并进 keywords）+ 分类页计数。要 100% 确认请在博客后台看。
13. 纯 HTTP 拉 CSDN 文章页会被反爬（521 / 安全验证页），`verify.py` 已做 curl 回退并对拦截情况单独标记。
14. **浏览器与登录态是解耦的**：Profile 目录里的 Cookie 由 Chrome for Testing 写入，用本机 Chrome 读取正常（实测通过；本机版本为 Chrome 157，换机后可能不同）。想换浏览器不必重新扫码；只有 Profile 目录被删才要重新登录。
15. `chips()` 原来把专栏下拉的候选项也算成"已选中"（`.tag__name` 会同时出现在已选区和 `.tag__options-content` 里），导致标签清理失效、日志里冒出并不存在的标签。现已按区域区分：文章标签只认 `span.el-tag`，专栏排除 `.tag__options-content`。
16. Element UI 的 chip 删除按钮用纯 JS `element.click()` 无效，必须用 Playwright 的真实鼠标点击（`force=True`）。

17. **更新已发布文章不能走 publish_all.py**（它只新建，重复发布会多出一篇）。CSDN 的更新路径：打开 `https://editor.csdn.net/md/?articleId=<id>` → 覆盖标题/正文 → 点「发布文章」→ 弹窗直接确认，**articleId 不变**，几分钟审核后生效；审核期间文章会暂时从前台列表消失，属正常。
18. **CSDN 写入正文必须用剪贴板，不能用 `keyboard.insert_text`**：① 一次性 `insert_text(整篇)` 会把 `\n` 当普通字符，实测 109 行压成 2 行；② 逐行 `insert_text` + `Enter` 会触发编辑器自动补全，把 `2.` 写成 `2. 2.`、`>` 写成 `> >`。正确做法是 `navigator.clipboard.writeText(md)` + `Ctrl+V`（需先 `grant_permissions(["clipboard-read","clipboard-write"], origin=编辑器域名)`），粘贴走编辑器 paste 管线，逐字一致。
19. **CSDN 外链图片转存不保证成功，失败时占位符会被写进正文源码**。转存成功：源码里变成 `![图注](https://i-blog.csdnimg.cn/img_convert/xxxx.png)`；转存失败：源码里留下 `[外链图片转存中...(img-xxx)]` **纯文本**，线上就是一行乱码，不会「发布后自动替换」。**发布前必须在编辑器里看到 `i-blog.csdnimg.cn` 链接才算过**。
20. **博客园开放 API 只能新建，不能更新**：`PUT/PATCH /openapi/v1/posts/{id}` 均 404，也没有列表接口（`GET /posts` 405）。要改已发布文章只能走后台编辑页，需要**登录会话**（PAT 不够）——用同一个 Chrome profile 打开 `https://i.cnblogs.com/posts/edit;postId=<id>`（**分号**，写成 `?postId=` 会落到空白新建页），首次需用户扫码登录，登录态之后可复用。
21. **`cdn.jsdelivr.net/@master` 会被 301 到 `raw.githubusercontent.com`**（国内不可达），第三方平台服务端顺着跳转抓图就失败——这正是 CSDN 报「源站可能有防盗链机制」的真实原因。解决办法：把图片域名换成 jsdelivr 的镜像域名 **`gcore.jsdelivr.net`**（同样路径，直连 200，不跳转）。实测 `fastly.jsdelivr.net` 也被跳转，`jsdelivr.b-cdn.net` / `testingcf.jsdelivr.net` 可用。
22. **博客园后台编辑页标题框与正文框极易串焦点**：点正文 `textarea`（`name="editor"`）时可能实际落在标题 `<input>` 上，此时 `Ctrl+A`+`Delete` 会**清空标题**，接着 type 会把整篇正文灌进标题框。安全做法：先删 **1 个字符**并截图确认（`#` 消失就是对着正文），再继续；标题写完必须截图复核。
23. **MCP 浏览器工具没有文件上传能力**（无 `set_input_files`），`cua_execute` 的 keypress 也不支持 `Shift+End` 之类的组合键。要在真实浏览器里改长文本：用 **`Set-Clipboard` 写系统剪贴板 + `Ctrl+A`/`Delete`/`Ctrl+V`**（`Set-Clipboard -Value (Get-Content -Raw -Encoding UTF8 file)` 即可，不需要 Add-Type）；只删文件开头一小段时，用 `Ctrl+Home` + 连续 `Delete`（每次最多 8 个键位，按字符数算次数）。

## 七、产物与落盘位置

| 内容 | 路径 |
| --- | --- |
| 博客园 PAT | `~/.workbuddy/blog-sync/config.json` |
| CSDN 登录态 | `~/.workbuddy/blog-sync/skills/cnblogs-csdn/chrome-profile/`（勿删，删了要重新扫码） |
| 登录态备份 | `~/.workbuddy/blog-sync/csdn_state.json` |
| 发布截图 | `~/.workbuddy/blog-sync/screenshots/` |

## 八、安全边界

- PAT 只在本地配置文件，帖子内容只发给对应平台，不经第三方。
- **正式发布会对外公开内容**。用户没明确说"发布/发出去"时，默认走草稿，并把草稿链接回给用户确认。
- CSDN 当日额度可能只剩 1 篇，正式发布前先跑 `--dry-run` 确认标签和专栏。

## 九、发布版（GitHub 备份）说明

- 本副本已做**脱敏 + 可移植化改造**：Chrome for Testing 路径改为按 home 目录动态发现版本目录；CSDN 解释器改为 `BLOG_SYNC_PYTHON` 环境变量 / 当前解释器；`sys.path` 改为相对脚本目录。
- **不含任何凭据**：`config/config.json`（博客园 PAT）、`chrome-profile/`（CSDN 登录态 Cookie）、`csdn_state.json`、`screenshots/` 均为运行时数据，已列入 `.gitignore`，不随仓库分发。换电脑后需跑 `scripts/setup.py --cnblogs-token <PAT>` 与 `scripts/login_csdn.py` 重新配置。
- 坑位 9 / 10 / 14 中的版本号、代理端口、Python 路径属本机历史环境记录，换机后需重新确认。
