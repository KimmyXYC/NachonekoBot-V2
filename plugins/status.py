# -*- coding: utf-8 -*-
# @Time    : 2025/5/1 12:49
# @Author  : KimmyXYC
# @File    : status.py
# @Software: PyCharm

import psutil
import platform
from telebot import types
from loguru import logger
from utils.yaml import BotConfig

# ==================== 插件元数据 ====================
__plugin_name__ = "status"
__version__ = "1.0.0"
__author__ = "KimmyXYC"
__description__ = "系统状态查询（仅限管理员）"
__commands__ = ["status"]
__command_descriptions__ = {"status": "获取机器人状态信息"}
__command_help__ = {"status": "/status - 获取机器人状态信息"}


# ==================== 核心功能 ====================
async def handle_status_command(bot, message: types.Message):
    """
    处理 /status 命令
    :param bot: Bot 对象
    :param message: 消息对象
    :return:
    """
    os_info = platform.platform()
    cpu_usage = psutil.cpu_percent(interval=1)
    memory_info = psutil.virtual_memory()
    swap_info = psutil.swap_memory()
    disk_info = psutil.disk_usage("/")
    net_io = psutil.net_io_counters()
    load_avg = psutil.getloadavg()

    info_message = (
        f"*Operating System:* `{os_info}`\n"
        f"*CPU Usage:* `{cpu_usage}%`\n"
        f"*Memory Usage:* `{memory_info.percent}% (Total: {memory_info.total / (1024**3):.2f} GB, "
        f"Used: {memory_info.used / (1024**3):.2f} GB)`\n"
        f"*Swap Usage:* `{swap_info.percent}% (Total: {swap_info.total / (1024**3):.2f} GB, "
        f"Used: {swap_info.used / (1024**3):.2f} GB)`\n"
        f"*Disk Usage:* `{disk_info.percent}% (Total: {disk_info.total / (1024**3):.2f} GB, "
        f"Used: {disk_info.used / (1024**3):.2f} GB)`\n"
        f"*Network I/O:* `Sent: {net_io.bytes_sent / (1024**2):.2f} MB, "
        f"Received: {net_io.bytes_recv / (1024**2):.2f} MB`\n"
        f"*Load Average:* `1 min: {load_avg[0]:.2f}, 5 min: {load_avg[1]:.2f}, 15 min: {load_avg[2]:.2f}`"
    )

    await bot.reply_to(message, info_message, parse_mode="Markdown")


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    async def status_handler(bot, message: types.Message):
        await handle_status_command(bot, message)

    middleware.register_command_handler(
        commands=["status"],
        callback=status_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["private", "group", "supergroup"],
        func=lambda m: m.from_user.id in BotConfig["admin"]["id"],
    )

    logger.info(
        f"✅ {__plugin_name__} 插件已注册 - 支持命令: {', '.join(__commands__)}"
    )


# ==================== 插件信息 ====================
def get_plugin_info() -> dict:
    """
    获取插件信息
    """
    return {
        "name": __plugin_name__,
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "commands": __commands__,
    }


# 保持全局 bot 引用
bot_instance = None
