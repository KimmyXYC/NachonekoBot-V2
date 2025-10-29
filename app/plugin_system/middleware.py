# -*- coding: utf-8 -*-
# @Time    : 2025/10/29 20:24
# @Author  : KimmyXYC
# @File    : middleware.py
# @Software: PyCharm
"""
插件中间件系统 - 支持多 Handler 执行
"""
from typing import List, Callable, Awaitable, Dict, Any
from dataclasses import dataclass, field
from loguru import logger
from telebot import types
import asyncio


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
        }
        self._execution_stats = {}  # 统计信息

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
                await handler.callback(bot, message)
                executed_count += 1

                if handler.stop_propagation:
                    break

            except Exception as e:
                logger.error(f"❌ Handler {handler.plugin}.{handler.name} 执行失败: {e}")

        return executed_count

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

        return True

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
