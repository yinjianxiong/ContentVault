# ContentVault MVP

这是一个本地归档小工具：复制抖音、头条、小红书或普通网页链接后，把链接内容保存到本地，并生成一份方便二创的总结草稿。

当前版本偏稳妥：一天几个链接、手动运行、本地保存，不做批量抓取。

## 快速开始

```bash
python3 -m content_mvp add "https://example.com/some-link"
```

归档会生成在：

```text
data/YYYY-MM-DD/platform_slug/
```

每条内容包含：

```text
meta.json       # 链接、平台、标题、摘要、图片/视频线索等元数据
content.md      # 提取出的正文和页面信息
summary.md      # 二创分析草稿
raw.html        # 原始 HTML，方便以后复查
media/          # 可选媒体下载目录
```

## 常用命令

保存链接：

```bash
python3 -m content_mvp add "复制来的链接"
```

指定备注：

```bash
python3 -m content_mvp add "复制来的链接" --note "选题不错，适合做观点拆解"
```

尝试下载视频/图片媒体：

```bash
python3 -m content_mvp add "复制来的链接" --download-media
```

这个功能会优先调用本机的 `yt-dlp`。如果没有安装，会跳过并在 `meta.json` 里记录原因。
抖音等平台经常需要浏览器登录态，可以让 `yt-dlp` 读取本机浏览器 cookies：

```bash
python3 -m content_mvp add "复制来的链接" --download-media --cookies-from-browser chrome
```

Firefox 也可以指定：

```bash
python3 -m content_mvp add "复制来的链接" --download-media --cookies-from-browser firefox
```

如果你导出了 `cookies.txt`，也可以这样用：

```bash
python3 -m content_mvp add "复制来的链接" --download-media --cookies-file cookies.txt
```

如果终端设置了代理，但平台对代理环境比较敏感，可以关闭媒体下载代理：

```bash
python3 -m content_mvp add "复制来的链接" --download-media --cookies-from-browser firefox --no-media-proxy
```

如果本机安装了 Downie 4，也可以归档后把链接交给 Downie：

```bash
python3 -m content_mvp add "复制来的链接" --open-downie
```

默认会等待最多 180 秒，把 Downie 新下载到 `~/Downloads` 的视频复制到当前归档的 `media/` 目录。如果你只想打开 Downie，不想等待导入：

```bash
python3 -m content_mvp add "复制来的链接" --open-downie --downie-wait 0
```

尝试用浏览器渲染动态页面：

```bash
python3 -m content_mvp add "复制来的链接" --browser
```

这个功能需要本机已经安装 Python 版 Playwright。动态平台页面经常需要登录，本工具只做本地个人归档，不绕过平台权限。

可选增强依赖：

```bash
python3 -m pip install -r requirements-optional.txt
python3 -m playwright install chromium
```

## 输出用途

`summary.md` 会给你一份二创起点：

- 一句话总结
- 核心信息
- 可能的爆点
- 可二创角度
- 标题方向
- 风险提醒
- 改写脚本骨架

后续可以接入更强的模型总结、语音转文字、剪贴板监听和本地数据库。
