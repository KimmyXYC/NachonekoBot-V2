# -*- coding: utf-8 -*-
# @Time    : 2025/6/14 16:42
# @Author  : KimmyXYC
# @File    : elaradb.py
# @Software: PyCharm
import elara

from pathlib import Path


class ElaraDB:
    def __init__(self, path: str = "elara"):
        """
        Initialize the ElaraDB connection.
        """
        self.client = elara.exe(path=path, commitdb=True)

    def get(self, key: str, default=None):
        """
        Get the value associated with the key from the database.

        :param key: The key to retrieve the value for.
        :param default: The default value to return if the key is not found.
        :return: The value associated with the key, or None if not found.
        """
        return self.client.get(key) if self.client.get(key) is not None else default

    def set(self, key: str, value):
        """
        Set the value for the specified key in the database.

        :param key: The key to set the value for.
        :param value: The value to set for the key.
        """
        self.client.set(key, value)

    def rem(self, key: str):
        """
        Remove the specified key from the database.

        :param key: The key to remove.
        """
        self.client.rem(key)

    def exists(self, key: str) -> bool:
        """
        Check if the specified key exists in the database.

        :param key: The key to check for existence.
        :return: True if the key exists, False otherwise.
        """
        return self.client.exists(key)


BotElara = ElaraDB(path=f"{str(Path.cwd())}/conf_dir/db.db")
