# 知乎归档

VisionJam 的知乎回答、想法与文章归档站。归档站与博客平行独立：博客负责日常写作，这里负责备份与展示；知乎文章草稿也可以在本仓库的本机目录中写作（见下）。

- 归档站：<https://visionjam.github.io/zhihu-archive/>
- 博客：<https://visionjam.github.io/>
- 参考项目：[ZhiHuArchive](https://github.com/L-M-Sherlock/ZhiHuArchive)

## 它做什么

- 同步本人在知乎发布的**回答、想法、文章**；想法转发按知乎页面呈现归档。
- 每篇内容生成一个 page bundle，图片下载到本地，保留原文链接。
- 与博客重复发布的文章会在 frontmatter 写入 `canonicalURL`，页面显示「本文同时发布于博客」；映射在 `data/crossposts.json`。
- 每篇标注知乎发布时间、最后编辑时间（仅当与发布时间不同）、赞同数、评论数、字数和预计阅读时长；`/ranking/` 按赞同数排行，并显示全站统计条。
- 每篇底部接入 Giscus：登录 GitHub 后可点 👍 或评论；站内赞数在构建前从 GitHub Discussions 读取。
- 已从知乎删除的内容继续保留，并在页面上标注。
- 第一次全量、之后增量；中断后可续跑。
- Cookie 只留本机；GitHub Actions 不持有知乎 Cookie，只使用自动注入的 `GITHUB_TOKEN`（以及可选的 `METRICS_TOKEN`）构建与部署。

## 知乎文章写作（本机）

- 可以在 `.local/drafts/<slug>/` 写知乎文章草稿：正文 `index.md` + 同目录 `assets/` 配图。`.local/` 已被 `.gitignore` 忽略，不会进入仓库或站点。
- 发布到知乎使用 Claude Code 的全局 skill `publish-to-zhihu`：上传图片 → 生成知乎导入版 md → 在网页版知乎导入并发布。
- Cookie 和图片映射只留在本机 `.local/`，发布完删除 Cookie。
- 发布成功后运行 `python tools/sync.py`，同步工具会把文章收进 `content/articles/`；不要手工把草稿放进 `content/`。

## 主页结构

- 主页按标签切换：`主页 / 全部 / 回答 / 文章 / 想法`。
- 「主页」只列最新的回答和文章（默认 20 条，可用 `params.homeLimit` 调整）；「全部」把回答、文章、想法混排。
- 简介下方显示全站统计条（收录数、分类、字数、知乎赞、站内赞）；顶部「更多」、首页与排行页统计条均设「统计」入口。
- 顶部导航保留「标签 / 归档 / 搜索」；排行、统计、博客、关于收进「更多」折叠面板，移动端同样可用。
- 置顶内容在 `data/pinned.yml` 中维护，按文件顺序显示在主页简介下方，支持站内路径和外部链接。同步会重写文章 front matter，所以置顶不要写在文章里。

## 站点结构（自定义部分）

- `layouts/list.html`：首页/栏目页布局覆盖——首页截取最新 `params.homeLimit` 条回答+文章，`/all/` 混排三类。
- `layouts/_partials/type_tabs.html`：首页与各列表页顶部的分类标签。
- `layouts/_partials/home_pinned.html` + `data/pinned.yml`：主页置顶区。
- `content/ranking/_index.md` + `layouts/ranking.html`：`/ranking/` 排行 section，从 `data/zhihu_stats.json` 读取并排序；支持 全部/回答/文章/想法 筛选（`?type=answers` 等）。
- `content/stats/_index.md` + `layouts/stats.html`：`/stats/` 统计页，按知乎原始发布时间统计发文频率、更新热力图、写作节奏和最近更新；数据来自 `data/zhihu_stats.json` 与页面 `lastmod`；入口在顶部「更多」、首页与排行页统计条，页内提供「查看排行」反向入口。
- `layouts/_partials/site_stats.html`：主页全站统计条，读取 `data/zhihu_stats.json` 与 `data/likes.json`，并链接到 `/stats/` 与 `/ranking/`。
- `layouts/_partials/header.html`：顶部导航覆盖，把 `params.group: more` 的菜单项收进「更多」折叠面板；`layouts/_partials/menu_link.html` 复用菜单链接渲染。
- `data/zhihu_stats.json`：同步生成的统计文件（赞、评论、字数、阅读时长）；`python tools/sync.py --refresh-stats` 可在不联网时从本地正文与缓存重建。
- `data/crossposts.json`：知乎文章 ID → 博客 URL 的映射；`python tools/sync.py --normalize` 会把 `canonicalURL` 与 `ShowCanonicalLink` 写入已有页面，并在同步结束时自动维护。
- `layouts/rss.xml`：RSS 覆盖模板，只收录回答/文章/想法并补 `lastBuildDate`；条数由 `services.rss.limit`（当前 50）控制。
- `layouts/single.html` + `layouts/_partials/zhihu_stats.html`：单篇标题下的统计行（含站内赞）。
- `layouts/_partials/comments.html`：Giscus 点赞/评论，仅知乎内容页。
- `layouts/_shortcodes/github-metrics.html`：关于页 GitHub 贡献图；CI 生成 `static/github-metrics.svg`（不入库）。
- `tools/fetch_likes.py` + `data/likes.json`：构建前读取 GitHub Discussions 主帖 👍 的快照；CI 每天 04:00 UTC 刷新。
- `content/all/_index.md`：`/all/` 聚合页；只输出 HTML，不生成 RSS，也不进入归档和搜索索引。
- `tests/test_site_build.py`：主页标签、置顶、20 条截取、排行页和统计行的构建测试。

页面链接注意站点部署在 `/zhihu-archive/` 子路径：模板里用不带前导斜杠的相对路径配 `relURL`，首页用 `site.Home.RelPermalink`。

浏览量说明：知乎接口不提供回答、文章、想法的浏览数。站内浏览量是可选的 GoatCounter 接入——在 `hugo.yml` 的 `params.goatcounter` 填入站点代码并在 GoatCounter 后台开启 visitor counts 后启用；留空时不加载任何第三方脚本，当前未启用。

站内赞说明：Giscus 主帖的 👍 存在 GitHub Discussions；构建前由 `tools/fetch_likes.py` 读取并写入 `data/likes.json`。点赞后要等下一次推送或每日 04:00 UTC 的定时构建才更新页面；访客需 GitHub 登录才能点赞。当前站内赞为 0（尚未有人点赞）。

## 本地预览

```bash
git submodule update --init --recursive
hugo server -D
```

生产构建：`hugo --minify --gc`。

## 环境

- Python 3.11+，依赖见 `requirements.txt`。
- Hugo 0.168.0 extended。

```bash
python -m pip install -r requirements.txt
```

## 准备 Cookie

1. 浏览器登录知乎。
2. 打开开发者工具 → Network → 刷新 → 右键任意 `zhihu.com` 请求 → Copy → **Copy as cURL**。
3. 把整段文本保存到 `%USERPROFILE%\.config\zhihu-archive\cookie.txt`（也可用 `ZHIHU_COOKIE_FILE` 指定其他路径）。

脚本支持 Netscape、cURL、`Cookie:` 头、JSON 导出和纯 cookie 字符串，会自动提取知乎域名下的 Cookie。

验证：

```bash
python tools/sync.py --check
```

成功时输出 `OK: <昵称> (url_token=...)`，不会打印 Cookie 值。

## 同步

```bash
python tools/sync.py --dry-run --limit 3   # 小样本检查，不写文件
python tools/sync.py                       # 全量或增量；写文件、扫描、提交、推送
python tools/sync.py --no-push             # 本地提交，不推送
python tools/sync.py --types answers,pins  # 只同步部分类型
python tools/sync.py --yes-images          # 确认本轮新增/修改的图片可以公开
python tools/sync.py --refresh-stats       # 不联网，重建 data/zhihu_stats.json
python tools/sync.py --normalize           # 不联网，刷新交叉发布、math 标记与重复图片
```

首次全量受知乎接口限速影响（每次请求随机等待 2–5 秒），内容多时需要较长时间；中断后重跑即可续跑。

### 每日自动同步

Windows 任务计划程序（在仓库根目录执行）：

```bat
schtasks /Create /SC DAILY /TN "ZhihuArchiveSync" /TR "\"%CD%\sync.bat\" --scheduled" /ST 09:00
```

`--scheduled` 让脚本不等待按键，适合任务计划；手动双击 `sync.bat` 则会在结束时暂停。电脑开机时才运行；失败会记录到 `.local\logs\`。

## 隐私与撤回

- 每次推送前自动扫描 `content/`：Cookie/密钥/本机路径/代理配置为硬拦截；电话、邮箱、内网地址等列为需确认。
- 仓库级放行名单在 `tools/privacy_allowlist.txt`（公开邮箱等可审计项，随仓库分发）；本机额外放行仍写 `.local/scan-allowlist.txt`，格式：`类型<TAB>相对路径<TAB>匹配串`。
- 临时不公开某条：把 `回答:ID`、`文章:ID` 或 `想法:ID`（也接受 `answers:`、`articles:`、`pins:`）写入 `.local/exclude.txt`，下一轮同步会把它从站点移除（`.local/raw/` 中的原始 JSON 仍保留）。
- 彻底撤回（连同公开 git 历史）：`python tools/purge.py --kind answers --id <ID>`。该操作会重写历史并用 `--force-with-lease=<旧 SHA>` 推送，执行前必须输入仓库目录名确认；他人已有的 fork/clone 与平台缓存不在保证范围内。

## 测试

```bash
python -m pytest tests
```

CI 在构建前运行 `python -m pytest -q`；测试覆盖同步、渲染、图片、隐私、交叉发布与 Hugo 站点构建。

## 状态

- 2026-10-22：首次全量同步 100 条（回答 12 / 文章 3 / 想法 85），图片 75 张；站点已上线。
- 2026-10-23：主页改为「分类标签 + 置顶 + 最新 20 条」；新增 `/all/` 聚合页；内容摘要统一去除 HTML 标签。
- 2026-10-24：新增 `/ranking/` 赞数排行与全站统计条；单篇显示赞同/评论/字数/阅读时长；统计写入 `data/zhihu_stats.json`，并预留 GoatCounter 站内浏览量。
- 2026-10-24：接入 Giscus 站内点赞/评论；构建前从 GitHub Discussions 读取 👍 写入 `data/likes.json`，排行页与单篇显示站内赞。
- 2026-10-24：全站统一白底；两站关于页结构对齐（常用链接、知乎归档、GitHub 贡献图）。
- 2026-10-24：单页显示知乎发布时间与最后编辑时间（`lastmod`，仅当与发布时间不同）；列表页保持原有样式，与博客站一致。
- 2026-10-27：RSS 只收录回答/文章/想法并补 `lastBuildDate`；博客重复发布的文章写入 canonical 并显示「本文同时发布于博客」；CI 在构建前跑 pytest；修复 `math: true` 误判与相邻重复图片；隐私 allowlist 增加仓库级默认文件。

### 当前状态与限制（2026-10-27）

- 站内赞：Giscus 👍，构建前取数；目前为 0（尚未有人点赞），点赞后需下一次推送或每日 04:00 UTC 构建才更新。
- 浏览量：知乎接口不提供；GoatCounter 未启用。
- 知乎赞/评论数：来自同步快照，具体时间见 `data/zhihu_stats.json` 的 `generated_at`；运行 `python tools/sync.py` 刷新。
- 交叉发布：`data/crossposts.json` 目前维护 5 篇 Android 指南；新增交叉发布文章后运行 `python tools/sync.py --normalize`，再把映射补进该文件。

## 内容与版权

归档内容来自知乎，版权归作者所有。页面保留原文链接；第三方内容、商标与图片权利归各自权利人。
