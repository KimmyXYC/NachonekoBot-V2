-- NachonekoBot-V2 Database Setup Script
-- This script creates all the necessary tables for the NachonekoBot-V2 application
-- Author: KimmyXYC
-- Date: 2025/7/5

-- Connect to the database (uncomment and modify as needed)
-- \c your_database_name

-- Enable PostgreSQL extensions if needed
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create remake table
-- This table stores user remake information
CREATE TABLE IF NOT EXISTS remake (
    user_id BIGINT PRIMARY KEY,
    count INTEGER NOT NULL DEFAULT 0,
    country TEXT NOT NULL,
    gender TEXT NOT NULL
);

-- Create xiatou table
-- This table stores xiatou time and count information
CREATE TABLE IF NOT EXISTS xiatou (
    time BIGINT PRIMARY KEY,
    count INTEGER NOT NULL DEFAULT 0
);

-- Create speech_stats table
-- This table stores group/user speech counts by hour
CREATE TABLE IF NOT EXISTS speech_stats (
    group_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    hour TIMESTAMPTZ NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    display_name TEXT NOT NULL,
    PRIMARY KEY (group_id, user_id, hour)
);

CREATE INDEX IF NOT EXISTS idx_speech_stats_group_hour
ON speech_stats (group_id, hour);

-- Create dragon_king_daily table
-- This table stores per-group daily dragon king and streak information
CREATE TABLE IF NOT EXISTS dragon_king_daily (
    group_id BIGINT NOT NULL,
    stat_date DATE NOT NULL,
    user_id BIGINT NOT NULL,
    display_name TEXT NOT NULL,
    total INTEGER NOT NULL,
    streak_days INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (group_id, stat_date)
);

CREATE INDEX IF NOT EXISTS idx_dragon_king_daily_group_user_date
ON dragon_king_daily (group_id, user_id, stat_date DESC);

-- Create scheduled_jobs table
-- This table stores per-group scheduled job configs
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    group_id BIGINT NOT NULL,
    job_name TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
    cron_expr TEXT NOT NULL DEFAULT '0 4 * * *',
    payload TEXT,
    PRIMARY KEY (group_id, job_name)
);

CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_job_enabled
ON scheduled_jobs (job_name, enabled);

-- Add indexes for performance (if needed)
-- CREATE INDEX IF NOT EXISTS idx_remake_user_id ON remake(user_id);
-- CREATE INDEX IF NOT EXISTS idx_xiatou_time ON xiatou(time);
-- CREATE INDEX IF NOT EXISTS idx_speech_stats_group_hour ON speech_stats(group_id, hour);

-- Grant permissions (uncomment and modify as needed)
-- GRANT ALL PRIVILEGES ON TABLE remake TO your_user;
-- GRANT ALL PRIVILEGES ON TABLE xiatou TO your_user;
-- GRANT ALL PRIVILEGES ON TABLE speech_stats TO your_user;
-- GRANT ALL PRIVILEGES ON TABLE dragon_king_daily TO your_user;
-- GRANT ALL PRIVILEGES ON TABLE scheduled_jobs TO your_user;

-- Add comments to tables and columns for documentation
COMMENT ON TABLE remake IS 'Stores user remake information';
COMMENT ON COLUMN remake.user_id IS 'Telegram user ID';
COMMENT ON COLUMN remake.count IS 'Count of remakes';
COMMENT ON COLUMN remake.country IS 'User country';
COMMENT ON COLUMN remake.gender IS 'User gender';

COMMENT ON TABLE xiatou IS 'Stores xiatou time and count information';
COMMENT ON COLUMN xiatou.time IS 'Timestamp in UNIX format';
COMMENT ON COLUMN xiatou.count IS 'Count of xiatou events';

COMMENT ON TABLE speech_stats IS 'Stores group/user speech counts by hour';
COMMENT ON COLUMN speech_stats.group_id IS 'Telegram group ID';
COMMENT ON COLUMN speech_stats.user_id IS 'Telegram user ID';
COMMENT ON COLUMN speech_stats.hour IS 'Stat hour (bucketed) in local timezone';
COMMENT ON COLUMN speech_stats.count IS 'Count of messages';
COMMENT ON COLUMN speech_stats.display_name IS 'Last known display name';

COMMENT ON TABLE dragon_king_daily IS 'Stores per-group daily dragon king winners and streak days';
COMMENT ON COLUMN dragon_king_daily.group_id IS 'Telegram group ID';
COMMENT ON COLUMN dragon_king_daily.stat_date IS 'Stat date of the cycle';
COMMENT ON COLUMN dragon_king_daily.user_id IS 'Dragon king user ID';
COMMENT ON COLUMN dragon_king_daily.display_name IS 'Dragon king display name';
COMMENT ON COLUMN dragon_king_daily.total IS 'Total messages in the cycle';
COMMENT ON COLUMN dragon_king_daily.streak_days IS 'Consecutive dragon king days';
COMMENT ON COLUMN dragon_king_daily.created_at IS 'Record created time';

COMMENT ON TABLE scheduled_jobs IS 'Stores per-group scheduled job configs';
COMMENT ON COLUMN scheduled_jobs.group_id IS 'Telegram group ID';
COMMENT ON COLUMN scheduled_jobs.job_name IS 'Scheduled job name';
COMMENT ON COLUMN scheduled_jobs.enabled IS 'Whether job is enabled';
COMMENT ON COLUMN scheduled_jobs.timezone IS 'Cron timezone';
COMMENT ON COLUMN scheduled_jobs.cron_expr IS 'Cron expression';

-- End of script
