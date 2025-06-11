# -*- coding: utf-8 -*-
# @Time    : 2025/5/1 18:18
# @Author  : KimmyXYC
# @File    : postgres.py
# @Software: PyCharm

import asyncpg
import asyncio
import json

from loguru import logger

from utils.yaml import BotConfig

class AsyncPostgresDB:
    def __init__(self):
        self.host = BotConfig["database"]["host"]
        self.port = BotConfig["database"]["port"]
        self.dbname = BotConfig["database"]["dbname"]
        self.user = BotConfig["database"]["user"]
        self.password = BotConfig["database"]["password"]
        self.pool = None

    async def connect(self):
        """
        Connect to the PostgreSQL database using asyncpg.
        This method creates a connection pool for efficient database access.
        """
        self.pool = await asyncpg.create_pool(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.dbname,
            min_size=1,
            max_size=5
        )


    async def close(self):
        """
        Close the connection pool to the PostgreSQL database.
        This method should be called when the application is shutting down.
        It ensures that all connections are properly closed and resources are released.
        :return: None
        """
        await self.pool.close()


BotDatabase = AsyncPostgresDB()
