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
                max_size=5
            )
            logger.success(f"Successfully connected to PostgreSQL database at {self.host}:{self.port}/{self.dbname}")
            # Create tables if they don't exist
            await self.ensure_tables_exist()
            # Ensure plugin setting table exists
            await self.ensure_settings_table()
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
                await connection.execute('''
                    CREATE TABLE IF NOT EXISTS remake (
                        user_id BIGINT PRIMARY KEY,
                        count INTEGER NOT NULL DEFAULT 0,
                        country TEXT NOT NULL,
                        gender TEXT NOT NULL
                    )
                ''')

                # Create xiatou table if it doesn't exist
                await connection.execute('''
                    CREATE TABLE IF NOT EXISTS xiatou (
                        time BIGINT PRIMARY KEY,
                        count INTEGER NOT NULL DEFAULT 0
                    )
                ''')

                # Create speech_stats table if it doesn't exist
                await connection.execute('''
                    CREATE TABLE IF NOT EXISTS speech_stats (
                        group_id BIGINT NOT NULL,
                        user_id BIGINT NOT NULL,
                        day DATE NOT NULL,
                        count INTEGER NOT NULL DEFAULT 0,
                        display_name TEXT NOT NULL,
                        PRIMARY KEY (group_id, user_id, day)
                    )
                ''')

                await connection.execute('''
                    CREATE INDEX IF NOT EXISTS idx_speech_stats_group_day
                    ON speech_stats (group_id, day)
                ''')

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
                await connection.execute('''
                    CREATE TABLE IF NOT EXISTS setting (
                        group_id BIGINT PRIMARY KEY
                    )
                ''')
            logger.success("Settings table ensured (setting)")
        except Exception as e:
            logger.error(f"Error ensuring settings table: {e}")
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
                    await connection.execute(f"ALTER TABLE setting ADD COLUMN \"{column}\" BOOLEAN NOT NULL DEFAULT TRUE")
                    logger.info(f"Added settings column for plugin '{plugin_name}' as '{column}' with default TRUE")
                else:
                    logger.debug(f"Settings column already exists for plugin '{plugin_name}' as '{column}'")
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
                    logger.warning(f"Settings column '{column}' missing; treating as enabled for plugin '{plugin_name}'")
                    return True
                val = await connection.fetchval(f"SELECT \"{column}\" FROM setting WHERE group_id = $1", int(group_id))
                if val is None:
                    # Row exists but column is NULL? Treat as default True.
                    return True
                return bool(val)
        except Exception as e:
            logger.error(f"Error getting plugin enabled state for group {group_id}, plugin '{plugin_name}': {e}")
            # Fail-open to avoid breaking bot functionality
            return True

    async def set_plugin_enabled(self, group_id: int, plugin_name: str, enabled: bool) -> bool:
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
                    await connection.execute(f"ALTER TABLE setting ADD COLUMN \"{column}\" BOOLEAN NOT NULL DEFAULT TRUE")
                await connection.execute(
                    f"UPDATE setting SET \"{column}\" = $1 WHERE group_id = $2",
                    bool(enabled),
                    int(group_id),
                )
            logger.info(f"Set plugin '{plugin_name}' ({column}) enabled={enabled} for group {group_id}")
            return True
        except Exception as e:
            logger.error(f"Error setting plugin enabled for group {group_id}, plugin '{plugin_name}': {e}")
            return False


BotDatabase = AsyncPostgresDB()
