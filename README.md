# ContentVault MVP

ContentVault 用来把同事发现的内容 URL 自动归档成可预览、可下载、可分析的素材记录。

当前主流程已经切到全自动化:

1. 同事在 NocoBase 录入 URL。
2. URL 进入 `ai_url_submissions`。
3. Prefect 按计划拉取待处理记录。
4. 本地 job 归档页面、调起 Downie 下载视频、生成分析包。
5. 结果写回 `ai_processed_assets`，供相关人员在 NocoBase 里查看。

## 全自动化流程

1. 同事在 NocoBase 录入一个内容 URL。
2. NocoBase 将这条记录写入 `ai_url_submissions`，初始状态为 `pending`。
3. Prefect deployment 按计划触发 `process_pending_urls_flow`。
4. flow 从 `ai_url_submissions` 中读取待处理记录，按 `priority` 和 `createdAt` 排序。
5. flow 把当前记录更新为 `processing`，并写入 `picked_at`。
6. flow 调用 `archive_link`，抓取页面并创建本地素材目录:

```text
data/YYYY-MM-DD/platform_slug/
```

7. 归档阶段先生成基础文件:

```text
meta.json
content.md
summary.md
raw.html
```

8. 如果本次 flow 开启了 Downie 自动下载，则会调起 `Downie 4.app`，监听 `~/Downloads`，等待新视频下载完成后复制到当前素材目录的 `media/`，并更新 `meta.json.media_download`。
9. 如果未启用 Downie，流程会跳过本地媒体导入，继续做基础分析。
10. flow 执行 `analyze_item`，生成:

```text
summary.md
analysis/codex_brief.md
analysis/frames/
```

11. flow 调用 `build_processed_asset_payload`，把素材目录整理成适合数据库展示的 payload，并 upsert 到 `ai_processed_assets`。
12. flow 将 `ai_url_submissions` 中对应记录更新为 `succeeded`，写入 `processed_at`。
13. 相关人员在 NocoBase 素材展示页查看结果，包括预览、下载和分析内容。
14. 如果任一步失败，flow 会把记录更新为 `failed`，同时写入 `retry_count + 1` 和 `last_error`，等待后续 Prefect 重试或人工处理。

配套图示:

![ContentVault 全自动化流程](docs/contentvault_auto_flowchart_hd.png)

Mermaid 源文件和文字版说明:

```text
docs/contentvault_automation_flow.mmd
docs/contentvault_automation_flow.md
```

## NocoBase 集成

当前使用两张表:

- `ai_url_submissions`: URL 收集和处理队列表。
- `ai_processed_assets`: 处理完成后的素材展示表。

详细字段设计见:

```text
docs/nocobase_integration.md
```

数据库通过 Prefect block 直连:

```python
from prefect_sqlalchemy import SqlAlchemyConnector

database_block = SqlAlchemyConnector.load("local-mysql-3307")
```

如果需要查看当前 schema 的后续可选优化，可参考:

```text
docs/nocobase_mysql_migration.sql
```

## Prefect Flow

主 flow 位于:

```text
content_mvp/prefect_jobs.py
```

本地手工触发一次:

```bash
arch -arm64 python3 -c "from content_mvp.prefect_jobs import process_pending_urls_flow; print(process_pending_urls_flow(limit=1, use_downie=True, downie_wait=180))"
```

典型状态流:

```text
pending -> processing -> succeeded
                         -> failed
```

Downie 自动下载链路:

```text
archive_link
-> open Downie 4
-> wait for ~/Downloads
-> import media/
-> analyze_item
-> upsert ai_processed_assets
```

运行限制: Downie 4 是 GUI 应用，所以 Prefect worker 必须运行在同一台有图形会话的 Mac 上，并且当前会话能够调起 `Downie 4.app`。如果未来 worker 迁移到远程 Linux 或无头会话，这条 Downie 自动下载链路将不可用，需要改用别的下载方案。

## 本地归档结构

每条内容会生成:

```text
data/YYYY-MM-DD/platform_slug/
  meta.json
  content.md
  summary.md
  raw.html
  media/
  analysis/
    codex_brief.md
    frames/
```

## 调试命令

这些命令主要用于单条排查或本地手工补录，不是现在的主生产链路。

手工归档一个 URL:

```bash
python3 -m content_mvp add "https://example.com/some-link"
```

手工归档并把链接交给 Downie:

```bash
python3 -m content_mvp add "复制来的链接" --open-downie
```

重新分析已有素材:

```bash
python3 -m content_mvp analyze data/YYYY-MM-DD/platform_slug
```

查看归档内容:

```bash
python3 -m content_mvp inspect data/YYYY-MM-DD
```

生成展示表 payload:

```bash
python3 -m content_mvp nocobase-payload data/YYYY-MM-DD/platform_slug
```

导出到 Obsidian:

```bash
python3 -m content_mvp export-obsidian data/YYYY-MM-DD --vault "/Users/jianxiongyin/MacTools/Obsidian/本地纪事/14_ContentVault"
```

## 可选依赖

```bash
python3 -m pip install -r requirements-optional.txt
python3 -m playwright install chromium
```

当前可选依赖用途:

- `yt-dlp`: 非 Downie 路径下的媒体下载尝试。
- `playwright`: 动态页面渲染。
- `prefect` / `prefect-sqlalchemy` / `pymysql`: 数据库 job 和调度。
