-- Recommended adjustments for the current NocoBase-generated tables.
-- Run after confirming NocoBase will keep these columns mapped as expected.

ALTER TABLE ai_url_submissions
    MODIFY url TEXT NULL,
    MODIFY normalized_url TEXT NULL,
    MODIFY submit_note TEXT NULL,
    MODIFY duplicate_of BIGINT NULL,
    MODIFY retry_count INT NOT NULL DEFAULT 0,
    MODIFY last_error TEXT NULL,
    MODIFY picked_at DATETIME(3) NULL,
    MODIFY processed_at DATETIME(3) NULL;

ALTER TABLE ai_processed_assets
    MODIFY url_submission BIGINT NULL,
    MODIFY source_url TEXT NULL,
    MODIFY final_url TEXT NULL,
    MODIFY local_folder TEXT NULL,
    MODIFY media_paths JSON NULL,
    MODIFY primary_media_path TEXT NULL,
    MODIFY cover_paths JSON NULL,
    MODIFY duration_seconds DECIMAL(10, 3) NULL,
    MODIFY file_size_bytes BIGINT NULL,
    MODIFY summary_md LONGTEXT NULL,
    MODIFY codex_brief_md LONGTEXT NULL,
    MODIFY creator_report_md LONGTEXT NULL,
    MODIFY obsidian_note_path TEXT NULL,
    MODIFY raw_meta JSON NULL;

CREATE INDEX idx_ai_url_submissions_status_priority_created
    ON ai_url_submissions (status, priority, createdAt);

CREATE UNIQUE INDEX uk_ai_processed_assets_url_submission
    ON ai_processed_assets (url_submission);

CREATE INDEX idx_ai_processed_assets_platform_archive_date
    ON ai_processed_assets (platform, archive_date);
