# -*- coding: utf-8 -*-
# @Time    : 2025/10/29 19:15
# @Author  : KimmyXYC
# @File    : models.py
# @Software: PyCharm
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel
import os
import contextlib

plugins_path = Path("plugins")


class PluginMetadata(BaseModel):
    """插件元数据"""

    name: str
    version: str
    author: str = "Unknown"
    description: str = ""
    commands: List[str] = []
    dependencies: List[str] = []
    enabled: bool = True


class LocalPlugin(BaseModel):
    """本地插件"""

    name: str
    status: bool  # 是否启用
    installed: bool = False
    version: Optional[str] = None
    metadata: Optional[PluginMetadata] = None

    @property
    def normal_path(self) -> Path:
        return plugins_path / f"{self.name}.py"

    @property
    def disabled_path(self) -> Path:
        return plugins_path / f"{self.name}.py.disabled"

    @property
    def load_status(self) -> bool:
        """插件是否已加载到内存"""
        import sys

        return f"plugins.{self.name}" in sys.modules

    def remove(self):
        """删除插件文件"""
        with contextlib.suppress(FileNotFoundError):
            os.remove(self.normal_path)
        with contextlib.suppress(FileNotFoundError):
            os.remove(self.disabled_path)

    def enable(self) -> bool:
        """启用插件"""
        try:
            if self.disabled_path.exists():
                os.rename(self.disabled_path, self.normal_path)
                self.status = True
                return True
            return False
        except Exception:
            return False

    def disable(self) -> bool:
        """禁用插件"""
        try:
            if self.normal_path.exists():
                os.rename(self.normal_path, self.disabled_path)
                self.status = False
                return True
            return False
        except Exception:
            return False
