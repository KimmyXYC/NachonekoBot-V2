# -*- coding: utf-8 -*-
# @Time    : 2025/10/29 19:16
# @Author  : KimmyXYC
# @File    : manager.py
# @Software: PyCharm
import json
import os
import importlib
import sys
from typing import List, Optional, Dict
from loguru import logger

from .models import LocalPlugin, plugins_path
from utils.postgres import BotDatabase


class PluginManager:
    """插件管理器"""

    def __init__(self):
        self.version_map: Dict[str, float] = {}
        self.plugins: List[LocalPlugin] = []
        self.loaded_handlers = {}

        # 导入中间件
        from .middleware import middleware
        self.middleware = middleware

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

    def get_local_version(self, name: str) -> Optional[float]:
        """获取本地插件版本"""
        return self.version_map.get(name)

    def set_local_version(self, name: str, version: float):
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
                if plugin_name in "__init__":
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
        """使用中间件加载插件"""
        loaded_count = 0
        failed_count = 0

        for plugin in self.plugins:
            if not plugin.status:
                continue

            try:
                module_name = f"plugins.{plugin.name}"

                if module_name in sys.modules:
                    importlib.reload(sys.modules[module_name])
                else:
                    importlib.import_module(module_name)

                module = sys.modules[module_name]

                # 若插件支持开关，确保 setting 表中存在对应列，并标记为可切换
                try:
                    if getattr(module, '__toggleable__', False):
                        await BotDatabase.ensure_plugin_column(plugin.name)
                        self.middleware.mark_toggleable(plugin.name)
                        logger.info(f"🔧 插件 {plugin.name} 已注册为可开关，并确保 settings 列存在")
                except Exception as e:
                    logger.error(f"初始化插件开关列失败: {plugin.name}: {e}")

                # 新方式：通过中间件注册
                if hasattr(module, 'register_handlers'):
                    # 检查函数签名，支持新旧两种方式
                    import inspect
                    sig = inspect.signature(module.register_handlers)
                    if len(sig.parameters) == 3:
                        # 新方式：register_handlers(bot, middleware, plugin_name)
                        await module.register_handlers(bot, self.middleware, plugin.name)
                    else:
                        # 旧方式：register_handlers(bot)
                        await module.register_handlers(bot)
                    loaded_count += 1
                    logger.success(f"✅ 插件 {plugin.name} 加载成功")

            except Exception as e:
                failed_count += 1
                logger.error(f"❌ 插件 {plugin.name} 加载失败: {e}")

        logger.info(f"插件加载完成: 成功 {loaded_count}, 失败 {failed_count}")
        return loaded_count, failed_count

    async def reload_all_plugins(self, bot):
        """重新加载所有插件"""
        logger.info("开始重新加载所有插件...")

        # 仅清除中间件中的处理器，保留核心（controller）已注册的 bot 级处理器
        self.middleware.clear_handlers()

        # 重新扫描插件
        self.load_local_plugins()

        # 重新加载处理器
        await self.load_plugin_handlers(bot)

        logger.success("所有插件重新加载完成")

    def get_plugin_commands_info(self):
        """
        从所有已加载的插件中收集命令信息
        返回: List of dicts with 'command', 'description', 'help_text'
        """
        commands_info = []
        
        for plugin in self.plugins:
            if not plugin.status:
                continue
            
            try:
                module_name = f"plugins.{plugin.name}"
                if module_name not in sys.modules:
                    continue
                    
                module = sys.modules[module_name]
                
                # 获取插件的命令列表
                if hasattr(module, '__commands__'):
                    plugin_commands = module.__commands__
                    
                    # 获取命令描述映射
                    command_descriptions = {}
                    command_help_texts = {}
                    
                    if hasattr(module, '__command_descriptions__'):
                        command_descriptions = module.__command_descriptions__
                    
                    if hasattr(module, '__command_help__'):
                        command_help_texts = module.__command_help__
                    
                    # 为每个命令添加信息
                    for cmd in plugin_commands:
                        commands_info.append({
                            'command': cmd,
                            'description': command_descriptions.get(cmd, ''),
                            'help_text': command_help_texts.get(cmd, ''),
                            'plugin': plugin.name
                        })
                        
            except Exception as e:
                logger.error(f"收集插件 {plugin.name} 命令信息时出错: {e}")
        
        return commands_info


# 全局插件管理器实例
plugin_manager = PluginManager()
