from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .analyze import analyze_item
from .nocobase import build_processed_asset_payload
from .pipeline import ArchiveOptions, archive_link


PENDING_SUBMISSIONS_SQL = """
SELECT
    id,
    url,
    submit_note
FROM ai_url_submissions
WHERE status = 'pending'
ORDER BY
    CASE priority WHEN 'high' THEN 0 ELSE 1 END,
    createdAt ASC
LIMIT :limit
"""

MARK_PROCESSING_SQL = """
UPDATE ai_url_submissions
SET
    status = 'processing',
    picked_at = NOW(),
    updatedAt = NOW()
WHERE id = :submission_id
"""

MARK_SUCCEEDED_SQL = """
UPDATE ai_url_submissions
SET
    status = 'succeeded',
    processed_at = NOW(),
    last_error = NULL,
    updatedAt = NOW()
WHERE id = :submission_id
"""

MARK_FAILED_SQL = """
UPDATE ai_url_submissions
SET
    status = 'failed',
    retry_count = COALESCE(retry_count, 0) + 1,
    last_error = :last_error,
    updatedAt = NOW()
WHERE id = :submission_id
"""

UPSERT_PROCESSED_ASSET_SQL = """
INSERT INTO ai_processed_assets (
    url_submission_id,
    source_url,
    final_url,
    platform,
    title,
    archive_date,
    local_folder,
    media_paths,
    primary_media_path,
    cover_paths,
    duration_seconds,
    file_size_bytes,
    download_status,
    analysis_status,
    summary_md,
    codex_brief_md,
    creator_report_md,
    obsidian_note_path,
    raw_meta,
    createdAt,
    updatedAt
) VALUES (
    :url_submission_id,
    :source_url,
    :final_url,
    :platform,
    :title,
    :archive_date,
    :local_folder,
    :media_paths,
    :primary_media_path,
    :cover_paths,
    :duration_seconds,
    :file_size_bytes,
    :download_status,
    :analysis_status,
    :summary_md,
    :codex_brief_md,
    :creator_report_md,
    :obsidian_note_path,
    :raw_meta,
    NOW(),
    NOW()
)
ON DUPLICATE KEY UPDATE
    source_url = VALUES(source_url),
    final_url = VALUES(final_url),
    platform = VALUES(platform),
    title = VALUES(title),
    archive_date = VALUES(archive_date),
    local_folder = VALUES(local_folder),
    media_paths = VALUES(media_paths),
    primary_media_path = VALUES(primary_media_path),
    cover_paths = VALUES(cover_paths),
    duration_seconds = VALUES(duration_seconds),
    file_size_bytes = VALUES(file_size_bytes),
    download_status = VALUES(download_status),
    analysis_status = VALUES(analysis_status),
    summary_md = VALUES(summary_md),
    codex_brief_md = VALUES(codex_brief_md),
    creator_report_md = VALUES(creator_report_md),
    obsidian_note_path = VALUES(obsidian_note_path),
    raw_meta = VALUES(raw_meta),
    updatedAt = NOW()
"""


def process_pending_urls_flow(
    *,
    limit: int = 10,
    data_dir: str = "data",
    db_block_name: str = "local-mysql-3307",
    download_media: bool = False,
    cookies_from_browser: str = "",
) -> list[dict[str, Any]]:
    """Process pending NocoBase URL submissions through the local pipeline."""
    return _build_flow()(
        limit=limit,
        data_dir=data_dir,
        db_block_name=db_block_name,
        download_media=download_media,
        cookies_from_browser=cookies_from_browser,
    )


def _build_flow():
    from prefect import flow

    @flow(name="contentvault-process-pending-urls", log_prints=True)
    def _flow(
        *,
        limit: int = 10,
        data_dir: str = "data",
        db_block_name: str = "local-mysql-3307",
        download_media: bool = False,
        cookies_from_browser: str = "",
    ) -> list[dict[str, Any]]:
        from prefect_sqlalchemy import SqlAlchemyConnector

        results: list[dict[str, Any]] = []
        with SqlAlchemyConnector.load(db_block_name) as database_block:
            rows = database_block.fetch_many(
                PENDING_SUBMISSIONS_SQL,
                parameters={"limit": limit},
                size=limit,
            )

            for row in rows:
                submission = _submission_from_row(row)
                submission_id = submission["id"]
                try:
                    database_block.execute(
                        MARK_PROCESSING_SQL,
                        parameters={"submission_id": submission_id},
                    )
                    archive = archive_link(
                        submission["url"],
                        ArchiveOptions(
                            data_dir=data_dir,
                            note=submission["submit_note"],
                            download_media=download_media,
                            cookies_from_browser=cookies_from_browser,
                        ),
                    )
                    analyze_item(archive.item_dir)
                    payload = build_processed_asset_payload(archive.item_dir)
                    database_block.execute(
                        UPSERT_PROCESSED_ASSET_SQL,
                        parameters=_to_db_params(submission_id, payload),
                    )
                    database_block.execute(
                        MARK_SUCCEEDED_SQL,
                        parameters={"submission_id": submission_id},
                    )
                    results.append(
                        {
                            "submission_id": submission_id,
                            "status": "succeeded",
                            "item_dir": str(archive.item_dir),
                        }
                    )
                except Exception as exc:  # noqa: BLE001 - flow must persist failures.
                    database_block.execute(
                        MARK_FAILED_SQL,
                        parameters={
                            "submission_id": submission_id,
                            "last_error": str(exc)[:2000],
                        },
                    )
                    results.append(
                        {
                            "submission_id": submission_id,
                            "status": "failed",
                            "error": str(exc),
                        }
                    )

        return results

    return _flow


def _submission_from_row(row: Any) -> dict[str, Any]:
    if hasattr(row, "_mapping"):
        mapping = row._mapping
        return {
            "id": mapping["id"],
            "url": mapping["url"],
            "submit_note": mapping.get("submit_note") or "",
        }
    submission_id, url, submit_note = row
    return {
        "id": submission_id,
        "url": url,
        "submit_note": submit_note or "",
    }


def _to_db_params(submission_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "url_submission_id": submission_id,
        **payload,
        "media_paths": json.dumps(payload["media_paths"], ensure_ascii=False),
        "cover_paths": json.dumps(payload["cover_paths"], ensure_ascii=False),
        "raw_meta": json.dumps(payload["raw_meta"], ensure_ascii=False),
    }
