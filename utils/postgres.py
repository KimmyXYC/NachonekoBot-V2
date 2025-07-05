# -*- coding: utf-8 -*-
# @Time    : 2025/5/1 18:18
# @Author  : KimmyXYC
# @File    : postgres.py
# @Software: PyCharm

import asyncpg
from loguru import logger

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

            logger.success("Database tables checked and created if needed")
        except Exception as e:
            logger.error(f"Error ensuring tables exist: {str(e)}")
            raise


BotDatabase = AsyncPostgresDB()
