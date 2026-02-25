# -*- coding: utf-8 -*-
# @Time    : 2025/5/1 18:18
# @Author  : KimmyXYC
# @File    : postgres.py
# @Software: PyCharm

import asyncpg
from loguru import logger
import re

from utils.yaml import BotConfig


class AsyncPostgresDB:
    def __init__(self):
        self.host = BotConfig["database"]["host"]
        self.port = BotConfig["database"]["port"]
        self.dbname = BotConfig["database"]["dbname"]
        self.user = BotConfig["database"]["user"]
        self.password = BotConfig["database"]["password"]
        self.conn = None

    async def connect(self):
        """
        Connect to the PostgreSQL database using asyncpg.
        This method creates a connection pool for efficient database access.
        """
        try:
            self.conn = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.dbname,
                min_size=1,
                max_size=5,
            )
            logger.success(
                f"Successfully connected to PostgreSQL database at {self.host}:{self.port}/{self.dbname}"
            )
            # Create tables if they don't exist
            await self.ensure_tables_exist()
            # Ensure plugin setting table exists
            await self.ensure_settings_table()
            # Ensure scheduled jobs table exists
            await self.ensure_scheduled_jobs_table()
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL database: {str(e)}")
            raise

    async def close(self):
        """
        Close the connection pool to the PostgreSQL database.
        This method should be called when the application is shutting down.
        It ensures that all connections are properly closed and resources are released.
        :return: None
        """
        try:
            await self.conn.close()
            logger.info("PostgreSQL database connection closed successfully")
        except Exception as e:
            logger.error(f"Error closing PostgreSQL database connection: {str(e)}")
            raise

    async def ensure_tables_exist(self):
        """
        Check if required tables exist and create them if they don't.
        This method is called after the database connection is established.
        """
        try:
            async with self.conn.acquire() as connection:
                # Create remake table if it doesn't exist
                await connection.execute("""
                    CREATE TABLE IF NOT EXISTS remake (
                        user_id BIGINT PRIMARY KEY,
                        count INTEGER NOT NULL DEFAULT 0,
                        country TEXT NOT NULL,
                        gender TEXT NOT NULL
                    )
                """)

                # Create xiatou table if it doesn't exist
                await connection.execute("""
                    CREATE TABLE IF NOT EXISTS xiatou (
                        time BIGINT PRIMARY KEY,
                        count INTEGER NOT NULL DEFAULT 0
                    )
                """)

                # Create speech_stats table if it doesn't exist
                await connection.execute("""
                    CREATE TABLE IF NOT EXISTS speech_stats (
                        group_id BIGINT NOT NULL,
                        user_id BIGINT NOT NULL,
                        hour TIMESTAMPTZ NOT NULL,
                        count INTEGER NOT NULL DEFAULT 0,
                        display_name TEXT NOT NULL,
                        PRIMARY KEY (group_id, user_id, hour)
                    )
                """)

                await connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_speech_stats_group_hour
                    ON speech_stats (group_id, hour)
                """)

                # Create dragon_king_daily table if it doesn't exist
                await connection.execute("""
                    CREATE TABLE IF NOT EXISTS dragon_king_daily (
                        group_id BIGINT NOT NULL,
                        stat_date DATE NOT NULL,
                        user_id BIGINT NOT NULL,
                        display_name TEXT NOT NULL,
                        total INTEGER NOT NULL,
                        streak_days INTEGER NOT NULL DEFAULT 1,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        PRIMARY KEY (group_id, stat_date)
                    )
                """)

                await connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_dragon_king_daily_group_user_date
                    ON dragon_king_daily (group_id, user_id, stat_date DESC)
                """)

            logger.success("Database tables checked and created if needed")
        except Exception as e:
            logger.error(f"Error ensuring tables exist: {str(e)}")
            raise

    # ==================== Settings helpers ====================
    async def ensure_settings_table(self):
        """
        Ensure the `setting` table exists with at least one column: group_id BIGINT PRIMARY KEY.
        """
        try:
            async with self.conn.acquire() as connection:
                await connection.execute("""
                    CREATE TABLE IF NOT EXISTS setting (
                        group_id BIGINT PRIMARY KEY
                    )
                """)
            logger.success("Settings table ensured (setting)")
        except Exception as e:
            logger.error(f"Error ensuring settings table: {e}")
            raise

    async def ensure_scheduled_jobs_table(self):
        """Ensure the `scheduled_jobs` table exists for per-group cron job settings."""
        try:
            async with self.conn.acquire() as connection:
                await connection.execute("""
                    CREATE TABLE IF NOT EXISTS scheduled_jobs (
                        group_id BIGINT NOT NULL,
                        job_name TEXT NOT NULL,
                        enabled BOOLEAN NOT NULL DEFAULT FALSE,
                        timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
                        cron_expr TEXT NOT NULL DEFAULT '0 4 * * *',
                        payload TEXT,
                        PRIMARY KEY (group_id, job_name)
                    )
                """)
                await connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_job_enabled
                    ON scheduled_jobs (job_name, enabled)
                """)
            logger.success("Scheduled jobs table ensured (scheduled_jobs)")
        except Exception as e:
            logger.error(f"Error ensuring scheduled jobs table: {e}")
            raise

    def _sanitize_plugin_column(self, plugin_name: str) -> str:
        """Sanitize plugin name to be used as a SQL identifier (lowercase, alnum + underscore)."""
        col = plugin_name.strip().lower()
        col = re.sub(r"[^a-z0-9_]+", "_", col)
        col = re.sub(r"_+", "_", col).strip("_")
        if not col:
            col = "plugin"
        return col

    async def ensure_group_row(self, group_id: int):
        """Ensure a row exists for the given group_id in setting table."""
        try:
            async with self.conn.acquire() as connection:
                await connection.execute(
                    """
                    INSERT INTO setting (group_id) VALUES ($1)
                    ON CONFLICT (group_id) DO NOTHING
                    """,
                    int(group_id),
                )
        except Exception as e:
            logger.error(f"Error ensuring group row {group_id}: {e}")
            raise

    async def ensure_plugin_column(self, plugin_name: str):
        """
        Ensure a boolean column exists for the plugin in the setting table, default TRUE.
        Column name is derived from plugin __plugin_name__.
        """
        column = self._sanitize_plugin_column(plugin_name)
        try:
            async with self.conn.acquire() as connection:
                # Check if column exists
                exists = await connection.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'setting' AND column_name = $1
                    )
                    """,
                    column,
                )
                if not exists:
                    await connection.execute(
                        f'ALTER TABLE setting ADD COLUMN "{column}" BOOLEAN NOT NULL DEFAULT TRUE'
                    )
                    logger.info(
                        f"Added settings column for plugin '{plugin_name}' as '{column}' with default TRUE"
                    )
                else:
                    logger.debug(
                        f"Settings column already exists for plugin '{plugin_name}' as '{column}'"
                    )
        except Exception as e:
            logger.error(f"Error ensuring plugin column '{plugin_name}': {e}")
            raise

    async def get_plugin_enabled(self, group_id: int, plugin_name: str) -> bool:
        """
        Get whether the plugin is enabled in the given group. Defaults to True if row/column missing.
        Also ensures the group row exists.
        """
        column = self._sanitize_plugin_column(plugin_name)
        try:
            await self.ensure_group_row(group_id)
            async with self.conn.acquire() as connection:
                # If column missing, treat as enabled (True)
                exists = await connection.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'setting' AND column_name = $1
                    )
                    """,
                    column,
                )
                if not exists:
                    logger.warning(
                        f"Settings column '{column}' missing; treating as enabled for plugin '{plugin_name}'"
                    )
                    return True
                val = await connection.fetchval(
                    f'SELECT "{column}" FROM setting WHERE group_id = $1', int(group_id)
                )
                if val is None:
                    # Row exists but column is NULL? Treat as default True.
                    return True
                return bool(val)
        except Exception as e:
            logger.error(
                f"Error getting plugin enabled state for group {group_id}, plugin '{plugin_name}': {e}"
            )
            # Fail-open to avoid breaking bot functionality
            return True

    async def set_plugin_enabled(
        self, group_id: int, plugin_name: str, enabled: bool
    ) -> bool:
        """Set plugin enabled state for a group. Returns True if success."""
        column = self._sanitize_plugin_column(plugin_name)
        try:
            await self.ensure_group_row(group_id)
            async with self.conn.acquire() as connection:
                # Ensure column exists before update
                exists = await connection.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'setting' AND column_name = $1
                    )
                    """,
                    column,
                )
                if not exists:
                    await connection.execute(
                        f'ALTER TABLE setting ADD COLUMN "{column}" BOOLEAN NOT NULL DEFAULT TRUE'
                    )
                await connection.execute(
                    f'UPDATE setting SET "{column}" = $1 WHERE group_id = $2',
                    bool(enabled),
                    int(group_id),
                )
            logger.info(
                f"Set plugin '{plugin_name}' ({column}) enabled={enabled} for group {group_id}"
            )
            return True
        except Exception as e:
            logger.error(
                f"Error setting plugin enabled for group {group_id}, plugin '{plugin_name}': {e}"
            )
            return False

    # ==================== Scheduled jobs helpers ====================
    async def ensure_scheduled_job_row(
        self,
        group_id: int,
        job_name: str,
        timezone: str = "Asia/Shanghai",
        cron_expr: str = "0 4 * * *",
        payload: str = None,
    ):
        """Ensure a scheduled job row exists for the given group/job."""
        try:
            async with self.conn.acquire() as connection:
                await connection.execute(
                    """
                    INSERT INTO scheduled_jobs (group_id, job_name, enabled, timezone, cron_expr, payload)
                    VALUES ($1, $2, FALSE, $3, $4, $5)
                    ON CONFLICT (group_id, job_name) DO NOTHING
                    """,
                    int(group_id),
                    job_name,
                    timezone,
                    cron_expr,
                    payload,
                )
        except Exception as e:
            logger.error(f"Error ensuring scheduled job row {group_id}/{job_name}: {e}")
            raise

    async def get_scheduled_job_enabled(
        self,
        group_id: int,
        job_name: str,
        timezone: str = "Asia/Shanghai",
        cron_expr: str = "0 4 * * *",
        payload: str = None,
    ) -> bool:
        """Get whether a scheduled job is enabled in the given group. Defaults to False."""
        try:
            await self.ensure_scheduled_job_row(
                group_id, job_name, timezone, cron_expr, payload
            )
            async with self.conn.acquire() as connection:
                val = await connection.fetchval(
                    """
                    SELECT enabled
                    FROM scheduled_jobs
                    WHERE group_id = $1 AND job_name = $2
                    """,
                    int(group_id),
                    job_name,
                )
                if val is None:
                    return False
                return bool(val)
        except Exception as e:
            logger.error(
                f"Error getting scheduled job enabled state for group {group_id}, job '{job_name}': {e}"
            )
            return False

    async def set_scheduled_job_enabled(
        self,
        group_id: int,
        job_name: str,
        enabled: bool,
        timezone: str = None,
        cron_expr: str = None,
        payload: str = None,
    ) -> bool:
        """Set scheduled job enabled state for a group. Returns True if success."""
        try:
            await self.ensure_scheduled_job_row(group_id, job_name)
            fields = ["enabled = $1"]
            params = [bool(enabled)]
            idx = 2
            if timezone is not None:
                fields.append(f"timezone = ${idx}")
                params.append(timezone)
                idx += 1
            if cron_expr is not None:
                fields.append(f"cron_expr = ${idx}")
                params.append(cron_expr)
                idx += 1
            if payload is not None:
                fields.append(f"payload = ${idx}")
                params.append(payload)
                idx += 1
            params.extend([int(group_id), job_name])
            query = f"UPDATE scheduled_jobs SET {', '.join(fields)} WHERE group_id = ${idx} AND job_name = ${idx + 1}"
            async with self.conn.acquire() as connection:
                await connection.execute(query, *params)
            logger.info(
                f"Set scheduled job '{job_name}' enabled={enabled} for group {group_id}"
            )
            return True
        except Exception as e:
            logger.error(
                f"Error setting scheduled job enabled for group {group_id}, job '{job_name}': {e}"
            )
            return False

    async def get_enabled_scheduled_groups(self, job_name: str):
        """Get all groups with the scheduled job enabled."""
        try:
            async with self.conn.acquire() as connection:
                rows = await connection.fetch(
                    """
                    SELECT group_id, timezone, cron_expr, payload
                    FROM scheduled_jobs
                    WHERE job_name = $1 AND enabled = TRUE
                    """,
                    job_name,
                )
                return rows
        except Exception as e:
            logger.error(
                f"Error getting enabled scheduled groups for job '{job_name}': {e}"
            )
            return []


BotDatabase = AsyncPostgresDB()
