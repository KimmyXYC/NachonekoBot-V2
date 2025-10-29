# -*- coding: utf-8 -*-
# @Time    : 2025/5/1 12:58
# @Author  : KimmyXYC
# @File    : callanyone.py
# @Software: PyCharm

import random
from telebot import types
from loguru import logger

# ==================== 插件元数据 ====================
__plugin_name__ = "callanyone"
__version__ = 1.0
__author__ = "KimmyXYC"
__description__ = "呼叫医生、MTF、警察等趣味功能"
__commands__ = ["calldoctor", "callmtf", "callpolice"]


# ==================== 核心功能 ====================
async def handle_call_command(bot, message):
    """
    处理 /callanyone 命令
    :param bot: Bot 对象
    :param message: 消息对象
    :return:
    """
    anyone_msg = ""
    if "/calldoctor" in message.text:
        anyone_list = ["👨‍⚕️", "👩‍⚕️", "🚑", "🏥", "💊"]
    elif "/callmtf" in message.text:
        anyone_list = ["🏳️‍⚧️", "🍥"]
    elif "/callpolice" in message.text:
        anyone_list = ["🚨", "👮", "🚔", "🚓"]
    else:
        anyone_list = ["🔧"]
    max_repeats = 5
    consecutive_count = 0
    count = 0
    while count <= random.randint(20, 80):
        emoji = random.choice(anyone_list)
        if emoji == anyone_msg[-1:]:
            consecutive_count += 1
            if consecutive_count > max_repeats:
                continue
        else:
            consecutive_count = 1
        anyone_msg += emoji
        count += 1
    await bot.reply_to(message, anyone_msg)


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """
    注册插件的消息处理器
    """

    global bot_instance
    bot_instance = bot

    async def call_handler(bot, message: types.Message):
        """处理所有呼叫命令"""
        await handle_call_command(bot, message)

    middleware.register_command_handler(
        commands=['calldoctor', 'callmtf', 'callpolice'],
        callback=call_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=['private', 'group', 'supergroup']
    )

    logger.info(f"✅ {__plugin_name__} 插件已注册 - 支持命令: {', '.join(__commands__)}")


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
