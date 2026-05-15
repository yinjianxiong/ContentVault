# NocoBase 集成设计

目标是让同事在 NocoBase 里录入 URL，后台 job 自动抓取、下载、分析，并把结果回写到可预览和下载的素材展示表。

## 表 1: URL 收集表

建议表名: `ai_url_submissions`

这张表只负责收集和排队，不直接存大段分析内容。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `url` | URL / 文本 | 是 | 同事提交的原始链接 |
| `normalized_url` | 文本 | 否 | 后端规范化后的 URL，用于去重 |
| `platform` | 单选 | 否 | `douyin` / `toutiao` / `xiaohongshu` / `unknown` |
| `title_hint` | 文本 | 否 | 提交人手填的标题或备注标题 |
| `submit_note` | 长文本 | 否 | 提交人说明为什么值得看 |
| `submitter` | 用户关系 | 否 | NocoBase 当前用户 |
| `priority` | 单选 | 是 | `normal` / `high`，默认 `normal` |
| `status` | 单选 | 是 | `pending` / `queued` / `processing` / `succeeded` / `failed` / `duplicate` / `ignored` |
| `duplicate_of` | 关系 | 否 | 指向被重复的 URL 收集记录 |
| `retry_count` | 整数 | 是 | 默认 `0` |
| `last_error` | 长文本 | 否 | 最近一次失败原因 |
| `picked_at` | 日期时间 | 否 | job 开始处理时间 |
| `processed_at` | 日期时间 | 否 | job 完成时间 |
| `createdAt` | 日期时间 | 自动 | NocoBase 默认字段 |
| `updatedAt` | 日期时间 | 自动 | NocoBase 默认字段 |

推荐索引:

- `normalized_url` 唯一索引或普通索引。如果短链会跳转，第一次可以先普通索引，后端确认 `final_url` 后再判重。
- `status + priority + createdAt` 用于 job 拉取待处理任务。

推荐视图:

- 待处理: `status in pending, failed`。
- 处理中: `status = processing`。
- 已完成: `status = succeeded`。
- 重复/忽略: `status in duplicate, ignored`。

## 表 2: 处理结果展示表

建议表名: `ai_processed_assets`

这张表面向预览、下载和二创分析阅读。它和 URL 收集表建议是一对一关系，但保留成多对一也可以，方便同一个 URL 未来多版本重跑。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `url_submission` | 关系 | 是 | 关联 `ai_url_submissions` |
| `source_url` | URL / 文本 | 是 | 原始 URL |
| `final_url` | URL / 文本 | 否 | 抓取后的最终 URL |
| `platform` | 单选 | 是 | 平台 |
| `title` | 文本 | 是 | 展示标题，优先使用视频文件名 |
| `archive_date` | 日期 | 是 | 归档日期，对应 `data/YYYY-MM-DD` |
| `local_folder` | 文本 | 是 | 本地素材目录绝对路径 |
| `media_paths` | JSON | 否 | 本地视频文件路径数组 |
| `primary_media_path` | 文本 | 否 | 主要视频文件路径 |
| `cover_paths` | JSON | 否 | 抽帧或缩略图路径 |
| `duration_seconds` | 数字 | 否 | 视频时长，后续可由 ffprobe 回填 |
| `file_size_bytes` | 整数 | 否 | 主视频文件大小 |
| `download_status` | 单选 | 是 | `none` / `downloaded` / `imported` / `failed` |
| `analysis_status` | 单选 | 是 | `none` / `brief_ready` / `report_ready` / `failed` |
| `summary_md` | 长文本 | 否 | `summary.md` 内容 |
| `codex_brief_md` | 长文本 | 否 | `analysis/codex_brief.md` 内容 |
| `creator_report_md` | 长文本 | 否 | `analysis/creator_report.md` 内容 |
| `obsidian_note_path` | 文本 | 否 | 已导出的 Obsidian 笔记路径 |
| `raw_meta` | JSON | 否 | `meta.json` 原始内容 |
| `createdAt` | 日期时间 | 自动 | NocoBase 默认字段 |
| `updatedAt` | 日期时间 | 自动 | NocoBase 默认字段 |

推荐索引:

- `url_submission`。
- `platform + archive_date`。
- `title` 普通索引，方便搜索。

推荐视图:

- 今日素材: `archive_date = today`。
- 可下载: `download_status in downloaded, imported`。
- 待分析: `analysis_status = brief_ready` 且 `creator_report_md` 为空。
- 已完成: `analysis_status = report_ready`。

## 关系设计

```text
ai_url_submissions 1 ---- 0..n ai_processed_assets
```

第一阶段建议按“一条 URL 只生成一个展示记录”来做。以后如果需要重跑不同分析版本，再允许一条 URL 关联多条展示记录。

## 状态流

```text
pending
  -> queued
  -> processing
  -> succeeded

processing
  -> failed

pending / processing
  -> duplicate
  -> ignored
```

后台 job 的推荐逻辑:

1. 从 `ai_url_submissions` 取 `status = pending` 的记录，按 `priority desc, createdAt asc` 排序。
2. 将记录更新为 `processing`，写入 `picked_at`。
3. 调用现有归档流程，把素材保存到 `data/YYYY-MM-DD/...`。
4. 下载或导入视频，生成 `media/`。
5. 调用 `analyze`，生成 `summary.md`、`analysis/codex_brief.md`、抽帧。
6. 生成 `ai_processed_assets` payload 并写入展示表。
7. 将 URL 收集记录更新为 `succeeded` 和 `processed_at`。
8. 任一步失败则写 `failed`、`last_error`、`retry_count + 1`。

## 页面建议

### URL 录入页

只露出少数字段:

- `url`
- `title_hint`
- `submit_note`
- `priority`

提交后默认:

- `status = pending`
- `retry_count = 0`

### 素材看板页

列表字段:

- `title`
- `platform`
- `archive_date`
- `download_status`
- `analysis_status`
- `primary_media_path`
- `source_url`

详情页字段:

- 视频路径 / 下载路径
- `summary_md`
- `creator_report_md`
- `codex_brief_md`
- `local_folder`
- `obsidian_note_path`

## 后端回写契约

当前代码新增了一个 payload 生成器:

```bash
python3 -m content_mvp nocobase-payload data/YYYY-MM-DD/platform_slug
```

它会读取素材目录并输出适合写入 `ai_processed_assets` 的 JSON。

## 直连数据库 + Prefect

既然 NocoBase 和 job 共用 MySQL，推荐让 job 直接连数据库，不再绕一层 NocoBase HTTP API:

```python
from prefect_sqlalchemy import SqlAlchemyConnector

database_block = SqlAlchemyConnector.load("local-mysql-3307")
```

当前项目准备使用 Prefect flow 调度这条链路:

```text
ai_url_submissions
  -> Prefect flow 拉取 pending
  -> 本地归档 / 下载 / analyze
  -> ai_processed_assets
  -> 回写 ai_url_submissions.status
```

推荐给 `ai_processed_assets.url_submission_id` 增加唯一索引，这样 flow 可以用 upsert 覆盖同一条提交的最新处理结果。

Prefect 适合作为调度层的原因:

- flow 本身保留每次运行历史、失败和重试。
- deployment 可以挂 schedule，让系统按固定间隔自动拉取待处理 URL。
- 后续如果下载、分析、同步 Obsidian 分成多个 task，也容易在 UI 里看清每一步状态。

项目里提供了初始 flow:

```text
content_mvp/prefect_jobs.py
```

默认 block 名:

```text
local-mysql-3307
```

本地先手工执行一次可以用:

```python
from content_mvp.prefect_jobs import process_pending_urls_flow

process_pending_urls_flow(limit=10)
```

正式部署时，再把这个 flow 注册为 Prefect deployment，并给 deployment 配置 schedule。
