# -*- coding: utf-8 -*-
# @Time    : 2025/10/29 19:18
# @Author  : KimmyXYC
# @File    : decorators.py
# @Software: PyCharm
import json
import os
import importlib
import sys
from typing import List, Optional, Dict
from loguru import logger

from .models import LocalPlugin, plugins_path


class PluginManager:
    """插件管理器"""

    def __init__(self):
        self.version_map: Dict[str, str] = {}
        self.plugins: List[LocalPlugin] = []
        self.loaded_handlers = []  # 存储已注册的处理器

        # 确保插件目录存在
        plugins_path.mkdir(exist_ok=True)
        if not (plugins_path / "__init__.py").exists():
            (plugins_path / "__init__.py").touch()

    def load_version_map(self):
        """加载版本信息"""
        version_file = plugins_path / "version.json"
        if version_file.exists():
            with open(version_file, "r", encoding="utf-8") as f:
                self.version_map = json.load(f)

    def save_version_map(self):
        """保存版本信息"""
        version_file = plugins_path / "version.json"
        with open(version_file, "w", encoding="utf-8") as f:
            json.dump(self.version_map, f, indent=2, ensure_ascii=False)

    def get_local_version(self, name: str) -> Optional[str]:
        """获取本地插件版本"""
        return self.version_map.get(name)

    def set_local_version(self, name: str, version: str):
        """设置插件版本"""
        self.version_map[name] = version
        self.save_version_map()

    def load_local_plugins(self) -> List[LocalPlugin]:
        """扫描并加载本地插件列表"""
        self.load_version_map()
        self.plugins = []

        if not plugins_path.exists():
            return self.plugins

        for file in os.listdir(plugins_path):
            if file.endswith(".py") or file.endswith(".py.disabled"):
                plugin_name = file.replace(".py.disabled", "").replace(".py", "")
                if plugin_name == "__init__":
                    continue

                self.plugins.append(
                    LocalPlugin(
                        name=plugin_name,
                        installed=plugin_name in self.version_map,
                        status=file.endswith(".py"),
                        version=self.get_local_version(plugin_name),
                    )
                )

        logger.info(f"发现 {len(self.plugins)} 个本地插件")
        return self.plugins

    def get_local_plugin(self, name: str) -> Optional[LocalPlugin]:
        """获取本地插件"""
        return next((p for p in self.plugins if p.name == name), None)

    def remove_plugin(self, name: str) -> bool:
        """删除插件"""
        if plugin := self.get_local_plugin(name):
            plugin.remove()
            if name in self.version_map:
                self.version_map.pop(name)
                self.save_version_map()

            # 从 sys.modules 中移除
            module_name = f"plugins.{name}"
            if module_name in sys.modules:
                del sys.modules[module_name]

            return True
        return False

    def enable_plugin(self, name: str) -> bool:
        """启用插件"""
        if plugin := self.get_local_plugin(name):
            return plugin.enable()
        return False

    def disable_plugin(self, name: str) -> bool:
        """禁用插件"""
        if plugin := self.get_local_plugin(name):
            return plugin.disable()
        return False

    async def load_plugin_handlers(self, bot):
        """动态加载所有启用的插件处理器"""
        loaded_count = 0
        failed_count = 0

        for plugin in self.plugins:
            if not plugin.status:
                continue

            try:
                # 动态导入插件模块
                module_name = f"plugins.{plugin.name}"

                if module_name in sys.modules:
                    # 重新加载已存在的模块
                    importlib.reload(sys.modules[module_name])
                else:
                    # 首次加载
                    importlib.import_module(module_name)

                module = sys.modules[module_name]

                # 调用插件的注册函数(如果存在)
                if hasattr(module, 'register_handlers'):
                    await module.register_handlers(bot)
                    loaded_count += 1
                    logger.success(f"✅ 插件 {plugin.name} 加载成功")
                elif hasattr(module, 'setup'):
                    await module.setup(bot)
                    loaded_count += 1
                    logger.success(f"✅ 插件 {plugin.name} 加载成功")
                else:
                    logger.warning(f"⚠️  插件 {plugin.name} 缺少 register_handlers 或 setup 函数")

            except Exception as e:
                failed_count += 1
                logger.error(f"❌ 插件 {plugin.name} 加载失败: {e}")

        logger.info(f"插件加载完成: 成功 {loaded_count}, 失败 {failed_count}")
        return loaded_count, failed_count

    async def reload_all_plugins(self, bot):
        """重新加载所有插件"""
        logger.info("开始重新加载所有插件...")

        # 清除已注册的处理器
        bot.message_handlers.clear()
        bot.callback_query_handlers.clear()

        # 重新扫描插件
        self.load_local_plugins()

        # 重新加载处理器
        await self.load_plugin_handlers(bot)

        logger.success("所有插件重新加载完成")


# 全局插件管理器实例
plugin_manager = PluginManager()
