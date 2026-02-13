# -*- coding: utf-8 -*-
# @Time    : 2025/10/29 20:24
# @Author  : KimmyXYC
# @File    : middleware.py
# @Software: PyCharm
"""
插件中间件系统 - 支持多 Handler 执行
"""
from typing import List, Callable, Dict, Any
from dataclasses import dataclass, field
from loguru import logger
from telebot import types
from utils.postgres import BotDatabase


@dataclass
class HandlerMetadata:
    """Handler 元数据"""
    name: str  # handler 名称
    plugin: str  # 所属插件
    callback: Callable  # 回调函数
    priority: int = 50  # 优先级(越大越先执行)
    stop_propagation: bool = False  # 是否停止传播
    filters: Dict[str, Any] = field(default_factory=dict)


class PluginMiddleware:
    """插件中间件 - 支持链式 Handler 调用"""

    def __init__(self):
        self.handlers: Dict[str, List[HandlerMetadata]] = {
            'command': [],  # 命令 handlers
            'message': [],  # 消息 handlers
            'callback': [],  # 回调 handlers
            'inline': [],  # inline_query handlers
        }
        self._execution_stats = {}  # 统计信息
        # 可切换开关的插件集合（由插件管理器在加载时标记）
        self.toggleable_plugins = set()
        # 可切换的定时任务（job_name -> display_name）
        self.scheduled_jobs: Dict[str, str] = {}

    def mark_toggleable(self, plugin_name: str):
        self.toggleable_plugins.add(plugin_name)

    def is_toggleable(self, plugin_name: str) -> bool:
        return plugin_name in self.toggleable_plugins

    def register_cron_job(
            self,
            plugin_name: str,
            job_id: str,
            cron_expr: str,
            timezone: str,
            callback: Callable,
            display_name: str = None,
            toggleable: bool = True,
    ) -> str:
        job_name = f"{plugin_name}.{job_id}"
        from app.scheduler import scheduler
        scheduler.register_cron_job(plugin_name, job_id, cron_expr, timezone, callback)
        if toggleable:
            self.scheduled_jobs[job_name] = display_name or job_name
        return job_name

    def register_schedule_handler(self, *args, **kwargs) -> str:
        return self.register_cron_job(*args, **kwargs)

    def get_toggleable_jobs(self):
        return list(self.scheduled_jobs.items())

    def register_command_handler(
            self,
            commands: List[str],
            callback: Callable,
            plugin_name: str,
            priority: int = 50,
            stop_propagation: bool = False,
            **filters
    ):
        """
        注册命令处理器

        :param commands: 命令列表 ['ping', 'test']
        :param callback: 回调函数
        :param plugin_name: 插件名称
        :param priority: 优先级 (0-100, 越大越先执行)
        :param stop_propagation: 是否阻止后续 handler 执行
        :param filters: 额外的过滤器 (chat_types, func 等)
        """
        for cmd in commands:
            handler = HandlerMetadata(
                name=cmd,
                plugin=plugin_name,
                callback=callback,
                priority=priority,
                stop_propagation=stop_propagation,
                filters=filters
            )
            self.handlers['command'].append(handler)
            logger.debug(f"注册命令 /{cmd} -> {plugin_name} (优先级: {priority})")

        # 按优先级排序
        self.handlers['command'].sort(key=lambda h: h.priority, reverse=True)

    def register_message_handler(
            self,
            callback: Callable,
            plugin_name: str,
            handler_name: str = None,
            priority: int = 50,
            stop_propagation: bool = False,
            **filters
    ):
        """注册通用消息处理器"""
        handler = HandlerMetadata(
            name=handler_name or f"{plugin_name}_handler",
            plugin=plugin_name,
            callback=callback,
            priority=priority,
            stop_propagation=stop_propagation,
            filters=filters
        )
        self.handlers['message'].append(handler)
        self.handlers['message'].sort(key=lambda h: h.priority, reverse=True)

    async def dispatch_command(self, bot, message: types.Message):
        """
        分发命令消息到所有匹配的 handlers

        :return: 执行的 handler 数量
        """
        if not message.text or not message.text.startswith('/'):
            return 0

        # 提取命令
        command = message.text.split()[0][1:].split('@')[0].lower()

        # 查找所有匹配的 handlers
        matched_handlers = [
            h for h in self.handlers['command']
            if h.name == command and self._check_filters(h, message)
        ]

        if not matched_handlers:
            return 0

        logger.info(f"🎯 命令 /{command} 匹配到 {len(matched_handlers)} 个处理器")

        executed_count = 0
        for handler in matched_handlers:
            try:
                # 插件开关检查（仅群组）
                if message.chat.type in ('group', 'supergroup') and self.is_toggleable(handler.plugin):
                    enabled = await BotDatabase.get_plugin_enabled(message.chat.id, handler.plugin)
                    if not enabled:
                        logger.info(f"⏭️ 跳过插件 {handler.plugin}（群 {message.chat.id} 已关闭）")
                        continue
                logger.debug(f"  → 执行 {handler.plugin}.{handler.name}")
                await handler.callback(bot, message)
                executed_count += 1

                # 记录统计
                key = f"{handler.plugin}.{handler.name}"
                self._execution_stats[key] = self._execution_stats.get(key, 0) + 1

                # 检查是否停止传播
                if handler.stop_propagation:
                    logger.debug(f"  ⛔ {handler.plugin} 阻止了后续处理器")
                    break

            except Exception as e:
                logger.error(f"❌ Handler {handler.plugin}.{handler.name} 执行失败: {e}")

        return executed_count

    async def dispatch_message(self, bot, message: types.Message):
        """分发普通消息"""
        matched_handlers = [
            h for h in self.handlers['message']
            if self._check_filters(h, message)
        ]

        executed_count = 0
        for handler in matched_handlers:
            try:
                # 插件开关检查（仅群组）
                if getattr(message, 'chat', None) and message.chat.type in ('group', 'supergroup') and self.is_toggleable(handler.plugin):
                    enabled = await BotDatabase.get_plugin_enabled(message.chat.id, handler.plugin)
                    if not enabled:
                        logger.info(f"⏭️ 跳过插件 {handler.plugin}（群 {message.chat.id} 已关闭）")
                        continue
                await handler.callback(bot, message)
                executed_count += 1

                if handler.stop_propagation:
                    break

            except Exception as e:
                logger.error(f"❌ Handler {handler.plugin}.{handler.name} 执行失败: {e}")

        return executed_count

    def register_callback_handler(
            self,
            callback: Callable,
            plugin_name: str,
            handler_name: str = None,
            priority: int = 50,
            stop_propagation: bool = False,
            **filters
    ):
        """注册回调查询处理器 (CallbackQuery)
        过滤器支持：
        - data_startswith: str | list[str] 回调 data 前缀匹配
        - chat_types: ['group','supergroup','private']
        - func: 自定义过滤函数，接收 CallbackQuery
        """
        handler = HandlerMetadata(
            name=handler_name or f"{plugin_name}_callback",
            plugin=plugin_name,
            callback=callback,
            priority=priority,
            stop_propagation=stop_propagation,
            filters=filters
        )
        self.handlers['callback'].append(handler)
        self.handlers['callback'].sort(key=lambda h: h.priority, reverse=True)

    def register_inline_handler(
            self,
            callback: Callable,
            plugin_name: str,
            handler_name: str = None,
            priority: int = 50,
            stop_propagation: bool = False,
            **filters
    ):
        """注册 InlineQuery 处理器

        过滤器支持：
        - func: 自定义过滤函数，接收 InlineQuery
        """
        handler = HandlerMetadata(
            name=handler_name or f"{plugin_name}_inline",
            plugin=plugin_name,
            callback=callback,
            priority=priority,
            stop_propagation=stop_propagation,
            filters=filters
        )
        self.handlers['inline'].append(handler)
        self.handlers['inline'].sort(key=lambda h: h.priority, reverse=True)

    def _check_filters(self, handler: HandlerMetadata, message: types.Message) -> bool:
        """检查消息是否符合 handler 的过滤条件"""
        filters = handler.filters

        # 检查 chat_types
        if 'chat_types' in filters:
            if message.chat.type not in filters['chat_types']:
                return False

        # 检查 func 过滤器
        if 'func' in filters:
            try:
                if not filters['func'](message):
                    return False
            except Exception:
                return False

        # 检查 content_types
        if 'content_types' in filters:
            if message.content_type not in filters['content_types']:
                return False

        # 检查 starts_with 过滤器（用于喜报/悲报等）
        if 'starts_with' in filters:
            if not message.text:
                return False
            starts_with_list = filters['starts_with']
            if not isinstance(starts_with_list, (list, tuple)):
                starts_with_list = [starts_with_list]
            if not message.text.startswith(tuple(starts_with_list)):
                return False

        return True

    def _check_callback_filters(self, handler: HandlerMetadata, call: types.CallbackQuery) -> bool:
        """检查回调查询是否符合 handler 的过滤条件"""
        filters = handler.filters

        # chat_types 依据回调所属消息的 chat 类型
        if 'chat_types' in filters:
            if not getattr(call, 'message', None):
                return False
            chat_type = getattr(call.message.chat, 'type', None)
            if chat_type not in filters['chat_types']:
                return False

        # func 自定义过滤
        if 'func' in filters:
            try:
                if not filters['func'](call):
                    return False
            except Exception:
                return False

        # data_startswith 过滤
        if 'data_startswith' in filters:
            if not getattr(call, 'data', None):
                return False
            starts = filters['data_startswith']
            if not isinstance(starts, (list, tuple)):
                starts = [starts]
            if not any(call.data.startswith(s) for s in starts):
                return False

        return True

    def _check_inline_filters(self, handler: HandlerMetadata, inline_query: types.InlineQuery) -> bool:
        """检查 inline query 是否符合 handler 的过滤条件"""
        filters = handler.filters

        if 'func' in filters:
            try:
                if not filters['func'](inline_query):
                    return False
            except Exception:
                return False

        return True

    async def dispatch_inline(self, bot, inline_query: types.InlineQuery) -> int:
        """分发 InlineQuery 到匹配的 handlers，返回执行数量"""
        matched_handlers = [
            h for h in self.handlers['inline']
            if self._check_inline_filters(h, inline_query)
        ]

        if not matched_handlers:
            return 0

        executed_count = 0
        for handler in matched_handlers:
            try:
                await handler.callback(bot, inline_query)
                executed_count += 1

                key = f"{handler.plugin}.{handler.name}"
                self._execution_stats[key] = self._execution_stats.get(key, 0) + 1

                if handler.stop_propagation:
                    break
            except Exception as e:
                logger.error(f"❌ Inline Handler {handler.plugin}.{handler.name} 执行失败: {e}")

        return executed_count

    async def dispatch_callback(self, bot, call: types.CallbackQuery) -> int:
        """分发回调查询到匹配的 handlers，返回执行数量"""
        matched_handlers = [
            h for h in self.handlers['callback']
            if self._check_callback_filters(h, call)
        ]

        if not matched_handlers:
            return 0

        executed_count = 0
        for handler in matched_handlers:
            try:
                # 插件开关检查（仅群组）
                chat = getattr(call, 'message', None) and call.message.chat
                if chat and getattr(chat, 'type', None) in ('group', 'supergroup') and self.is_toggleable(handler.plugin):
                    enabled = await BotDatabase.get_plugin_enabled(chat.id, handler.plugin)
                    if not enabled:
                        logger.info(f"⏭️ 跳过插件 {handler.plugin}（群 {chat.id} 已关闭）")
                        continue

                await handler.callback(bot, call)
                executed_count += 1

                if handler.stop_propagation:
                    break

            except Exception as e:
                logger.error(f"❌ Callback Handler {handler.plugin}.{handler.name} 执行失败: {e}")

        return executed_count

    def get_stats(self) -> Dict[str, int]:
        """获取执行统计"""
        return self._execution_stats.copy()

    def clear_handlers(self, plugin_name: str = None):
        """清除 handlers"""
        if plugin_name:
            for handler_type in self.handlers:
                self.handlers[handler_type] = [
                    h for h in self.handlers[handler_type]
                    if h.plugin != plugin_name
                ]
        else:
            for handler_type in self.handlers:
                self.handlers[handler_type].clear()


# 全局中间件实例
middleware = PluginMiddleware()
