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
-- This table stores group/user speech counts by day
CREATE TABLE IF NOT EXISTS speech_stats (
    group_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    day DATE NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    display_name TEXT NOT NULL,
    PRIMARY KEY (group_id, user_id, day)
);

CREATE INDEX IF NOT EXISTS idx_speech_stats_group_day
ON speech_stats (group_id, day);

-- Add indexes for performance (if needed)
-- CREATE INDEX IF NOT EXISTS idx_remake_user_id ON remake(user_id);
-- CREATE INDEX IF NOT EXISTS idx_xiatou_time ON xiatou(time);
-- CREATE INDEX IF NOT EXISTS idx_speech_stats_group_day ON speech_stats(group_id, day);

-- Grant permissions (uncomment and modify as needed)
-- GRANT ALL PRIVILEGES ON TABLE remake TO your_user;
-- GRANT ALL PRIVILEGES ON TABLE xiatou TO your_user;
-- GRANT ALL PRIVILEGES ON TABLE speech_stats TO your_user;

-- Add comments to tables and columns for documentation
COMMENT ON TABLE remake IS 'Stores user remake information';
COMMENT ON COLUMN remake.user_id IS 'Telegram user ID';
COMMENT ON COLUMN remake.count IS 'Count of remakes';
COMMENT ON COLUMN remake.country IS 'User country';
COMMENT ON COLUMN remake.gender IS 'User gender';

COMMENT ON TABLE xiatou IS 'Stores xiatou time and count information';
COMMENT ON COLUMN xiatou.time IS 'Timestamp in UNIX format';
COMMENT ON COLUMN xiatou.count IS 'Count of xiatou events';

COMMENT ON TABLE speech_stats IS 'Stores group/user speech counts by day';
COMMENT ON COLUMN speech_stats.group_id IS 'Telegram group ID';
COMMENT ON COLUMN speech_stats.user_id IS 'Telegram user ID';
COMMENT ON COLUMN speech_stats.day IS 'Stat date in local timezone';
COMMENT ON COLUMN speech_stats.count IS 'Count of messages';
COMMENT ON COLUMN speech_stats.display_name IS 'Last known display name';

-- End of script