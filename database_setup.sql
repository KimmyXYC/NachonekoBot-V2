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

-- Add indexes for performance (if needed)
-- CREATE INDEX IF NOT EXISTS idx_remake_user_id ON remake(user_id);
-- CREATE INDEX IF NOT EXISTS idx_xiatou_time ON xiatou(time);

-- Grant permissions (uncomment and modify as needed)
-- GRANT ALL PRIVILEGES ON TABLE remake TO your_user;
-- GRANT ALL PRIVILEGES ON TABLE xiatou TO your_user;

-- Add comments to tables and columns for documentation
COMMENT ON TABLE remake IS 'Stores user remake information';
COMMENT ON COLUMN remake.user_id IS 'Telegram user ID';
COMMENT ON COLUMN remake.count IS 'Count of remakes';
COMMENT ON COLUMN remake.country IS 'User country';
COMMENT ON COLUMN remake.gender IS 'User gender';

COMMENT ON TABLE xiatou IS 'Stores xiatou time and count information';
COMMENT ON COLUMN xiatou.time IS 'Timestamp in UNIX format';
COMMENT ON COLUMN xiatou.count IS 'Count of xiatou events';

-- End of script