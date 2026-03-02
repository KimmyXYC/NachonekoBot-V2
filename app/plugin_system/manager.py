# -*- coding: utf-8 -*-
# @Time    : 2025/10/29 19:16
# @Author  : KimmyXYC
# @File    : manager.py
# @Software: PyCharm
import json
import os
import importlib
import sys
import ast
from typing import List, Optional, Dict
from loguru import logger

from .models import LocalPlugin, plugins_path
from utils.postgres import BotDatabase
from utils.i18n import plugin_t


COMMAND_CATEGORY_PRIORITY = {
    "core": 0,
    "network": 10,
    "query": 20,
    "tool": 30,
    "admin": 40,
    "fun": 50,
    "utility": 60,
    "misc": 99,
}


class PluginManager:
    """插件管理器"""

    def __init__(self):
        self.version_map: Dict[str, str] = {}
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

    def get_local_version(self, name: str) -> Optional[str]:
        """获取本地插件版本"""
        return self.version_map.get(name)

    def set_local_version(self, name: str, version: str):
        """设置插件版本"""
        self.version_map[name] = version
        self.save_version_map()

    def sync_plugin_versions(self) -> Dict[str, tuple]:
        """
        强制同步所有插件版本
        返回: Dict[plugin_name, (old_version, new_version)]
        """
        self.load_version_map()
        updates = {}

        if not plugins_path.exists():
            return updates

        for file in sorted(os.listdir(plugins_path), key=str.lower):
            if file.endswith(".py") or file.endswith(".py.disabled"):
                plugin_name = file.replace(".py.disabled", "").replace(".py", "")
                if plugin_name == "__init__":
                    continue

                try:
                    file_path = plugins_path / file
                    with open(file_path, "r", encoding="utf-8") as pf:
                        source = pf.read()

                    tree = ast.parse(source, filename=str(file_path))
                    for node in tree.body:
                        if isinstance(node, ast.Assign):
                            target_names = [
                                t.id for t in node.targets if isinstance(t, ast.Name)
                            ]
                            if "__version__" in target_names:
                                value = node.value
                                v = None
                                if hasattr(ast, "Constant") and isinstance(
                                    value, ast.Constant
                                ):
                                    v = value.value
                                elif isinstance(value, ast.Num):
                                    v = value.n
                                elif isinstance(value, ast.Str):
                                    v = value.s

                                parsed_version = None
                                if isinstance(v, (int, float)):
                                    # 将数字转换为字符串格式的版本号
                                    parsed_version = str(float(v))
                                elif isinstance(v, str):
                                    # 直接使用字符串版本号
                                    parsed_version = v.strip()

                                if parsed_version is not None:
                                    old_version = self.version_map.get(plugin_name)
                                    if old_version != parsed_version:
                                        self.version_map[plugin_name] = parsed_version
                                        updates[plugin_name] = (
                                            old_version,
                                            parsed_version,
                                        )
                                break
                except Exception as e:
                    logger.error(f"同步插件 {plugin_name} 版本失败: {e}")

        if updates:
            self.save_version_map()
            logger.info(f"✅ 同步了 {len(updates)} 个插件的版本信息")

        return updates

    def load_local_plugins(self) -> List[LocalPlugin]:
        """扫描并加载本地插件列表"""
        self.load_version_map()
        self.plugins = []

        if not plugins_path.exists():
            return self.plugins

        updated_versions = False

        for file in sorted(os.listdir(plugins_path), key=str.lower):
            if file.endswith(".py") or file.endswith(".py.disabled"):
                plugin_name = file.replace(".py.disabled", "").replace(".py", "")
                if plugin_name == "__init__":
                    continue

                # 从 version.json 读取已记录的版本
                cached_version = self.get_local_version(plugin_name)

                # 从插件源代码中解析实际 __version__
                parsed_version = None
                try:
                    file_path = plugins_path / file
                    with open(file_path, "r", encoding="utf-8") as pf:
                        source = pf.read()
                    # 使用 AST 安全解析顶层 __version__ 赋值
                    try:
                        tree = ast.parse(source, filename=str(file_path))
                        for node in tree.body:
                            if isinstance(node, ast.Assign):
                                target_names = [
                                    t.id
                                    for t in node.targets
                                    if isinstance(t, ast.Name)
                                ]
                                if "__version__" in target_names:
                                    value = node.value
                                    v = None
                                    if hasattr(ast, "Constant") and isinstance(
                                        value, ast.Constant
                                    ):
                                        v = value.value
                                    elif isinstance(value, ast.Num):
                                        v = value.n
                                    elif isinstance(value, ast.Str):
                                        v = value.s
                                    # 接受数字或字符串作为版本号
                                    if isinstance(v, (int, float)):
                                        parsed_version = str(float(v))
                                    elif isinstance(v, str):
                                        parsed_version = v.strip()
                                    break
                    except Exception:
                        parsed_version = None
                except Exception:
                    parsed_version = None

                # 检测版本不匹配并更新
                final_version = parsed_version
                if parsed_version is not None:
                    if cached_version is None:
                        # 首次记录版本
                        self.version_map[plugin_name] = parsed_version
                        updated_versions = True
                        logger.debug(
                            f"📝 插件 {plugin_name} 首次记录版本: {parsed_version}"
                        )
                    elif cached_version != parsed_version:
                        # 检测到版本更新
                        self.version_map[plugin_name] = parsed_version
                        updated_versions = True
                        logger.info(
                            f"🔄 插件 {plugin_name} 版本更新: {cached_version} -> {parsed_version}"
                        )
                    final_version = parsed_version
                elif cached_version is not None:
                    # 源码中没有版本但缓存中有，使用缓存版本
                    final_version = cached_version

                self.plugins.append(
                    LocalPlugin(
                        name=plugin_name,
                        installed=plugin_name in self.version_map,
                        status=file.endswith(".py"),
                        version=final_version,
                    )
                )

        # 批量保存版本更新
        if updated_versions:
            self.save_version_map()

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

                # 检测并更新插件版本（处理运行时版本变化）
                try:
                    if getattr(module, "__version__", None) is not None:
                        v = getattr(module, "__version__")
                        ver = None
                        if isinstance(v, (int, float)):
                            ver = str(float(v))
                        elif isinstance(v, str):
                            ver = v.strip()

                        if ver is not None:
                            cached_ver = self.version_map.get(plugin.name)
                            if cached_ver != ver:
                                # 版本不匹配，更新到最新版本
                                self.set_local_version(plugin.name, ver)
                                plugin.version = ver
                                if cached_ver is None:
                                    logger.debug(
                                        f"📝 插件 {plugin.name} 记录版本: {ver}"
                                    )
                                else:
                                    logger.info(
                                        f"🔄 插件 {plugin.name} 版本同步: {cached_ver} -> {ver}"
                                    )
                except Exception as e:
                    logger.debug(f"版本检测失败 {plugin.name}: {e}")

                # 若插件支持开关，确保 setting 表中存在对应列，并标记为可切换
                try:
                    if getattr(module, "__toggleable__", False):
                        await BotDatabase.ensure_plugin_column(plugin.name)
                        display_name = getattr(module, "__display_name__", plugin.name)
                        if not isinstance(display_name, str):
                            display_name = plugin.name
                        self.middleware.mark_toggleable(plugin.name, display_name)
                        logger.info(
                            f"🔧 插件 {plugin.name} 已注册为可开关，并确保 settings 列存在"
                        )
                except Exception as e:
                    logger.error(f"初始化插件开关列失败: {plugin.name}: {e}")

                # 新方式：通过中间件注册
                if hasattr(module, "register_handlers"):
                    # 检查函数签名，支持新旧两种方式
                    import inspect

                    sig = inspect.signature(module.register_handlers)
                    if len(sig.parameters) == 3:
                        # 新方式：register_handlers(bot, middleware, plugin_name)
                        await module.register_handlers(
                            bot, self.middleware, plugin.name
                        )
                    else:
                        # 旧方式：register_handlers(bot)
                        await module.register_handlers(bot)
                    loaded_count += 1
                    logger.success(f"✅ 插件 {plugin.name} 加载成功")

                # 支持插件声明定时任务
                if hasattr(module, "__scheduled_jobs__"):
                    try:
                        jobs = getattr(module, "__scheduled_jobs__") or []
                        for job in jobs:
                            job_id = job.get("job_id")
                            callback = job.get("callback")
                            if not job_id or callback is None:
                                continue
                            cron_expr = job.get("cron", "0 4 * * *")
                            timezone = job.get("timezone", "Asia/Shanghai")
                            display_name = job.get("display_name")
                            self.middleware.register_cron_job(
                                plugin.name,
                                job_id,
                                cron_expr,
                                timezone,
                                callback,
                                display_name=display_name,
                            )
                        if jobs:
                            logger.info(
                                f"⏱️ 插件 {plugin.name} 已注册 {len(jobs)} 个定时任务"
                            )
                    except Exception as e:
                        logger.error(f"注册插件定时任务失败: {plugin.name}: {e}")

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

    def get_plugin_commands_info(self, lang: str = "en"):
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
                if hasattr(module, "__commands__"):
                    plugin_commands = module.__commands__

                    # 获取命令描述映射
                    command_descriptions = {}
                    command_help_texts = {}
                    command_orders = {}

                    if hasattr(module, "__command_descriptions__"):
                        command_descriptions = module.__command_descriptions__

                    if hasattr(module, "__command_help__"):
                        command_help_texts = module.__command_help__

                    if hasattr(module, "__command_order__"):
                        command_orders = module.__command_order__

                    category = getattr(module, "__command_category__", None)
                    if not category:
                        category = "misc"
                    category = str(category).strip().lower()
                    if category not in COMMAND_CATEGORY_PRIORITY:
                        category = "misc"

                    # 为每个命令添加信息
                    for cmd in plugin_commands:
                        desc_key = f"command.description.{cmd}"
                        help_key = f"command.help.{cmd}"
                        i18n_desc = plugin_t(plugin.name, desc_key, lang)
                        i18n_help = plugin_t(plugin.name, help_key, lang)
                        description = (
                            i18n_desc
                            if i18n_desc != desc_key
                            else command_descriptions.get(cmd, "")
                        )
                        help_text = (
                            i18n_help
                            if i18n_help != help_key
                            else command_help_texts.get(cmd, "")
                        )
                        commands_info.append(
                            {
                                "command": cmd,
                                "description": description,
                                "help_text": help_text,
                                "plugin": plugin.name,
                                "category": category,
                                "category_priority": COMMAND_CATEGORY_PRIORITY[
                                    category
                                ],
                                "command_order": int(command_orders.get(cmd, 0)),
                            }
                        )

            except Exception as e:
                logger.error(f"收集插件 {plugin.name} 命令信息时出错: {e}")

        commands_info.sort(
            key=lambda item: (
                item["category_priority"],
                item["command_order"],
                item["command"],
                item["plugin"],
            )
        )
        return commands_info

    def get_inline_commands_info(self, lang: str = "en") -> List[dict]:
        """从所有已加载插件中收集 Inline 命令信息。

        规则：
        - 仅从插件模块的 `__command_help__` 中提取包含 `Inline:` 的条目
        - 允许条目不在 `__commands__` 中声明（用于隐藏命令/仅 inline 功能）

        返回: List[{ 'command': str, 'help_text': str, 'plugin': str }]
        """
        inline_info: List[dict] = []

        for plugin in self.plugins:
            if not plugin.status:
                continue

            module_name = f"plugins.{plugin.name}"
            if module_name not in sys.modules:
                continue

            try:
                module = sys.modules[module_name]
                help_map = getattr(module, "__command_help__", None)
                if not isinstance(help_map, dict):
                    continue

                for cmd, help_text in help_map.items():
                    if not isinstance(help_text, str):
                        continue
                    help_key = f"command.help.{cmd}"
                    i18n_help = plugin_t(plugin.name, help_key, lang)
                    if i18n_help != help_key:
                        help_text = i18n_help
                    if "Inline:" not in help_text:
                        continue

                    inline_info.append(
                        {
                            "command": str(cmd),
                            "help_text": help_text,
                            "plugin": plugin.name,
                        }
                    )
            except Exception as e:
                logger.error(f"收集插件 {plugin.name} Inline 命令信息时出错: {e}")

        return inline_info


# 全局插件管理器实例
plugin_manager = PluginManager()
