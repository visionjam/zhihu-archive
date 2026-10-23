# 知乎归档

VisionJam 的知乎回答、想法与文章归档站。归档站与博客平行独立：博客负责写作，这里负责备份与展示。

- 归档站：<https://visionjam.github.io/zhihu-archive/>
- 博客：<https://visionjam.github.io/>
- 参考项目：[ZhiHuArchive](https://github.com/L-M-Sherlock/ZhiHuArchive)

## 它做什么

- 同步本人在知乎发布的**回答、想法、文章**；想法转发按知乎页面呈现归档。
- 每篇内容生成一个 page bundle，图片下载到本地，保留原文链接。
- 已从知乎删除的内容继续保留，并在页面上标注。
- 第一次全量、之后增量；中断后可续跑。
- Cookie 只留本机，GitHub Actions 不持有任何凭证，只负责构建与部署。

## 主页结构

- 主页按标签切换：`主页 / 全部 / 回答 / 文章 / 想法`。
- 「主页」只列最新的回答和文章（默认 20 条，可用 `params.homeLimit` 调整）；「全部」把回答、文章、想法混排。
- 置顶内容在 `data/pinned.yml` 中维护，按文件顺序显示在主页简介下方，支持站内路径和外部链接。同步会重写文章 front matter，所以置顶不要写在文章里。

## 站点结构（自定义部分）

- `layouts/list.html`：首页/栏目页布局覆盖——首页截取最新 `params.homeLimit` 条回答+文章，`/all/` 混排三类。
- `layouts/_partials/type_tabs.html`：首页与各列表页顶部的分类标签。
- `layouts/_partials/home_pinned.html` + `data/pinned.yml`：主页置顶区。
- `content/all/_index.md`：`/all/` 聚合页；只输出 HTML，不生成 RSS，也不进入归档和搜索索引。
- `tests/test_site_build.py`：主页标签、置顶、20 条截取和 `/all/` 的构建测试。

页面链接注意站点部署在 `/zhihu-archive/` 子路径：模板里用不带前导斜杠的相对路径配 `relURL`，首页用 `site.Home.RelPermalink`。

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
- 需确认项在人工核对后写入 `.local/scan-allowlist.txt`（仅本机、不入库），格式：`类型<TAB>相对路径<TAB>匹配串`。
- 临时不公开某条：把 `回答:ID`、`文章:ID` 或 `想法:ID`（也接受 `answers:`、`articles:`、`pins:`）写入 `.local/exclude.txt`，下一轮同步会把它从站点移除（`.local/raw/` 中的原始 JSON 仍保留）。
- 彻底撤回（连同公开 git 历史）：`python tools/purge.py --kind answers --id <ID>`。该操作会重写历史并用 `--force-with-lease=<旧 SHA>` 推送，执行前必须输入仓库目录名确认；他人已有的 fork/clone 与平台缓存不在保证范围内。

## 测试

```bash
python -m pytest tests
```

## 状态

- 2026-10-22：首次全量同步 100 条（回答 12 / 文章 3 / 想法 85），图片 75 张；站点已上线。
- 2026-10-23：主页改为「分类标签 + 置顶 + 最新 20 条」；新增 `/all/` 聚合页；内容摘要统一去除 HTML 标签。

## 内容与版权

归档内容来自知乎，版权归作者所有。页面保留原文链接；第三方内容、商标与图片权利归各自权利人。
