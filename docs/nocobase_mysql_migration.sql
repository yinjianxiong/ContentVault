-- Optional follow-up adjustments after the current NocoBase schema cleanup.
-- The two tables are already usable by the Prefect job.
-- Keep this file for non-blocking refinements only.

ALTER TABLE ai_processed_assets
    MODIFY source_url TEXT NULL,
    MODIFY final_url TEXT NULL,
    MODIFY local_folder TEXT NULL,
    MODIFY primary_media_path TEXT NULL,
    MODIFY raw_meta JSON NULL;

CREATE INDEX idx_ai_url_submissions_status_priority_created
    ON ai_url_submissions (status, priority, createdAt);

CREATE UNIQUE INDEX uk_ai_processed_assets_url_submission
    ON ai_processed_assets (url_submission);

CREATE INDEX idx_ai_processed_assets_platform_archive_date
    ON ai_processed_assets (platform, archive_date);
