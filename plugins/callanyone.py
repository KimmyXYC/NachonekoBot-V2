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
__version__ = "1.0.0"
__author__ = "KimmyXYC"
__description__ = "呼叫医生、MTF、警察等趣味功能"
__commands__ = ["calldoctor", "callmtf", "callpolice"]
__command_category__ = "fun"
__command_order__ = {"calldoctor": 430, "callmtf": 431, "callpolice": 432}
__command_descriptions__ = {
    "calldoctor": "呼叫医生",
    "callmtf": "呼叫 MTF",
    "callpolice": "呼叫警察",
}
__command_help__ = {
    "calldoctor": "/calldoctor - 呼叫医生\nInline: @NachoNekoX_bot calldoctor",
    "callmtf": "/callmtf - 呼叫 MTF\nInline: @NachoNekoX_bot callmtf",
    "callpolice": "/callpolice - 呼叫警察\nInline: @NachoNekoX_bot callpolice",
}


# ==================== 核心功能 ====================
def query_call_text(command: str) -> str:
    """生成与呼叫命令一致的随机表情串，用于命令与 Inline 复用。"""
    anyone_msg = ""
    cmd = (command or "").strip().lower()

    if cmd == "calldoctor":
        anyone_list = ["👨‍⚕️", "👩‍⚕️", "🚑", "🏥", "💊"]
    elif cmd == "callmtf":
        anyone_list = ["🏳️‍⚧️", "🍥"]
    elif cmd == "callpolice":
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

    return anyone_msg


async def handle_call_command(bot, message):
    """处理 /calldoctor /callmtf /callpolice 命令"""
    text = message.text or ""
    if "/calldoctor" in text:
        cmd = "calldoctor"
    elif "/callmtf" in text:
        cmd = "callmtf"
    elif "/callpolice" in text:
        cmd = "callpolice"
    else:
        cmd = ""

    anyone_msg = query_call_text(cmd)
    await bot.reply_to(message, anyone_msg)


async def handle_call_inline_query(bot, inline_query: types.InlineQuery):
    """处理 Inline Query：@Bot calldoctor/callmtf/callpolice"""
    query = (inline_query.query or "").strip()
    tokens = query.split()

    supported = {"calldoctor", "callmtf", "callpolice"}
    if not tokens:
        return

    cmd = tokens[0].lower()
    if cmd not in supported or len(tokens) != 1:
        text = "用法：\n- calldoctor\n- callmtf\n- callpolice"
        result = types.InlineQueryResultArticle(
            id="callanyone_usage",
            title="呼叫 (callanyone)",
            description="用法：calldoctor / callmtf / callpolice",
            input_message_content=types.InputTextMessageContent(text),
        )
        await bot.answer_inline_query(
            inline_query.id, [result], cache_time=1, is_personal=True
        )
        return

    anyone_msg = query_call_text(cmd)
    titles = {
        "calldoctor": "呼叫医生",
        "callmtf": "呼叫 MTF",
        "callpolice": "呼叫警察",
    }
    result = types.InlineQueryResultArticle(
        id=f"callanyone_{cmd}",
        title=titles.get(cmd, cmd),
        description="发送呼叫结果",
        input_message_content=types.InputTextMessageContent(anyone_msg),
    )
    await bot.answer_inline_query(
        inline_query.id, [result], cache_time=1, is_personal=True
    )


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
        commands=["calldoctor", "callmtf", "callpolice"],
        callback=call_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["private", "group", "supergroup"],
    )

    middleware.register_inline_handler(
        callback=handle_call_inline_query,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        func=lambda q: (
            bool(getattr(q, "query", None))
            and (
                q.query.strip().lower().split()[:1]
                and q.query.strip().lower().split()[0]
                in ("calldoctor", "callmtf", "callpolice")
            )
        ),
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
