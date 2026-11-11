# 博客园 / CSDN 接口速查（维护用）

## 博客园（官方 OpenAPI v1）

来源：博客园团队《博客后台 API 说明文档》 <https://www.cnblogs.com/cmt/articles/19246558>（2025-11-20）

| 用途 | 方法与地址 |
| --- | --- |
| 发布/存草稿 | `POST https://i.cnblogs.com/openapi/v1/posts` |
| 查审核状态 | `POST https://i.cnblogs.com/openapi/v1/posts/reviewStatus:check` |
| 企业博客额度 | `GET https://i.cnblogs.com/openapi/v1/corp/info` |

请求头：

```
Authorization: Bearer <PAT>
Authorization-Type: pat
Content-Type: application/json
```

请求体（C# DTO 对照）：

| 字段 | 类型 | 备注 |
| --- | --- | --- |
| `title` | string | 必填 |
| `body` | string | 必填 |
| `postFormat` | `Markdown` / `Html` | 默认 Markdown |
| `description` | string | 摘要 |
| `categories` | string[] | 分类名，**不存在会被创建** |
| `tags` | string[] | 标签 |
| `isPublished` | bool | 默认 true；false = 草稿 |
| `isAllowComments` | bool | 默认 true |
| `isAigc` | bool | AI 生成标识 |
| `postType` | `BlogPost` / `Article` | 默认 BlogPost |
| `slug` | string | 友好地址 |

返回：`{"value":{"postId":123,"postUrl":"https://..."},"success":true}`

**已确认不存在**：删除接口（`DELETE /openapi/v1/posts/{id}` → 404）、读取单篇接口（返回 SPA HTML）。MetaWeblog `deletePost` 也失败（博客园已取消密码登录，MetaWeblog 通道不可靠）。删文只能后台手删。

审核状态码：`0` 待审核 / `1` 通过 / `2` 不通过。

## CSDN（无公开 API，走浏览器）

- 编辑器：`https://editor.csdn.net/md/`
- 后台接口 `bizapi.csdn.net/blog-console-api/v3/mdeditor/saveArticle` 需要 Cookie + `x-ca-key` / `x-ca-nonce` / `x-ca-signature`（HMAC-SHA256），签名每次现算，维护成本高 → **本技能不用它**，改用持久化 Profile 驱动编辑器。

### 编辑器 DOM

| 元素 | 选择器 |
| --- | --- |
| 标题显示区 | `div.article-bar__title-display`（点击后变可编辑） |
| 正文 | `pre.editor__inner`（contenteditable） |
| 保存草稿 / 发布文章 | `role=button name=保存草稿` / `name=发布文章`（有 2 个"发布文章"，底部那个要取 last） |

### 发布弹窗 DOM

| 元素 | 选择器 |
| --- | --- |
| 弹窗容器 | 含文本「分类专栏」且高度 > 300 的 `.el-dialog` / `[role=dialog]` |
| 区域块 | `.form-tag-box`，块内 `.form-entry__label` 文本区分「文章标签 / 分类专栏」 |
| 分类专栏 chip | `.tag__item-box > span.tag__name` + `button.tag__btn-tag-delete` |
| 文章标签 chip | `.mark_selection[typename=tags] span.el-tag` + `i.el-tag__close` |
| 选项面板 | `.tag__options-content`（默认 display:none） |
| 选项条目 | `.tag__option-box > .tag__option-label`（**必须点 label**） |
| 摘要输入 | `textarea[placeholder*='各展现列表']` |
| 打开面板的按钮 | 区域块内 `.tag__btn-tag`（专栏叫「新建分类专栏」，标签叫「添加文章标签」） |

### 交互陷阱

1. 点 `.tag__btn-tag`（新建分类专栏）只会插入一个**空的** contenteditable chip，不代表选中任何专栏；选中要走选项面板点 label。
2. 标签区已达 7 个时，「添加文章标签」按钮消失；标签总数 = 账号历史标签 + 新增。
3. 按键 `Escape` 会关闭整个发布弹窗（不是关下拉）。收起下拉请点弹窗标题文字。
4. 弹窗状态会被记住（同一草稿再次打开发布弹窗，标签/专栏/摘要仍是上次的）。脚本因此全部采用"先读后改"。
5. 成功页 `/creation/success/<id>`，真实文章地址要从页面上的 "查看文章" `<a>` 取。
6. 发布后状态为「正在审核中」，公开页可能短暂不可访问。
7. 编辑器会自动恢复上次未保存的标题，写标题前要 `Ctrl+A`+`Delete`。
