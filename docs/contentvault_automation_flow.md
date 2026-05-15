# ContentVault 全自动化流程图

```mermaid
flowchart TD
    A["同事在 NocoBase 录入 URL"] --> B["ai_url_submissions<br/>status = pending"]
    B --> C["Prefect Deployment 定时触发"]
    C --> D["process_pending_urls_flow"]
    D --> E["读取 pending URL<br/>按 priority / createdAt 排序"]
    E --> F["更新 ai_url_submissions<br/>status = processing<br/>picked_at = now"]

    F --> G["archive_link<br/>抓取页面并创建本地素材目录"]
    G --> H["data/YYYY-MM-DD/platform_slug/<br/>meta.json / content.md / summary.md"]

    H --> I{"是否启用 Downie 自动下载?"}
    I -- "是" --> J["调起 Downie 4.app"]
    J --> K["监听 ~/Downloads<br/>等待新视频完成"]
    K --> L["复制视频到 media/<br/>更新 meta.json.media_download"]
    I -- "否" --> M["无本地媒体<br/>继续基础分析"]

    L --> N["analyze_item"]
    M --> N
    N --> O["生成 summary.md<br/>analysis/codex_brief.md<br/>analysis/frames/"]

    O --> P["build_processed_asset_payload"]
    P --> Q["upsert ai_processed_assets"]
    Q --> R["更新 ai_url_submissions<br/>status = succeeded<br/>processed_at = now"]
    R --> S["NocoBase 素材展示页<br/>可预览 / 下载 / 查看分析"]

    F --> X{"任一步失败?"}
    X -- "是" --> Y["更新 ai_url_submissions<br/>status = failed<br/>retry_count + 1<br/>last_error"]
    Y --> Z["等待下次 Prefect 重试或人工处理"]
    X -- "否" --> G

    subgraph Runtime["运行前提"]
        T["Prefect worker 运行在同一台有图形会话的 Mac"]
        U["Downie 4.app 可被当前用户会话调起"]
        V["若 worker 迁移到远程 Linux / 无头环境<br/>Downie 链路不可用"]
        T --> U --> V
    end
```

## 文字版

1. 同事在 NocoBase 录入 URL。
2. URL 写入 `ai_url_submissions`，初始状态为 `pending`。
3. Prefect deployment 按计划触发 flow。
4. flow 拉取待处理 URL，先把状态改成 `processing`。
5. 本地创建素材目录并归档页面内容。
6. 如果开启 Downie 自动下载，则调起 `Downie 4.app`，等待视频下载完成后导入到当前素材目录的 `media/`。
7. 执行 `analyze_item`，生成摘要、Codex 分析包和关键帧。
8. 生成展示表 payload，并 upsert 到 `ai_processed_assets`。
9. 将 URL 收集表状态改成 `succeeded`。
10. 相关人员在 NocoBase 素材展示页预览、下载和查看分析结果。
11. 任一步失败则回写 `failed`、`retry_count` 和 `last_error`，等待后续重试。
