# -*- coding: utf-8 -*-
# @Time    : 2025/5/1 13:00
# @Author  : KimmyXYC
# @File    : shorturl.py
# @Software: PyCharm

import aiohttp
import json

from loguru import logger
from telebot import types

from utils.yaml import BotConfig
from app.utils import command_error_msg

# ==================== 插件元数据 ====================
__plugin_name__ = "shorturl"
__version__ = 1.0
__author__ = "KimmyXYC"
__description__ = "短链接生成工具"
__commands__ = ["short"]
__command_descriptions__ = {
    "short": "生成短链接"
}
__command_help__ = {
    "short": "/short [URL] - 生成短链接"
}


# ==================== 核心功能 ====================
async def handle_short_command(bot, message: types.Message, url):
    """
    处理短链接命令
    :param bot: Bot 对象
    :param message: 消息对象
    :param url: URL 地址
    :return:
    """
    server = BotConfig["shorturl"]["api"]
    reply = await bot.reply_to(
        message,
        f"正在生成短链接: `{url}`",
        disable_web_page_preview=True,
        parse_mode="Markdown",
    )
    if server == "":
        logger.error(f"[Short URL][{message.chat.id}]: Backend Address Not Set")
        await bot.edit_message_text(
            "生成失败, 后端地址未设置",
            message.chat.id,
            reply.message_id,
            disable_web_page_preview=True,
        )
    else:
        if not (url.startswith("https://") or url.startswith("http://")):
            url = "https://" + url
        params = {'url': url}
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(server, json=params) as response:
                    if response.status != 200:
                        logger.error(f"[Short URL][{message.chat.id}]: Can't Get Short URL: {response.status}")
                        await bot.edit_message_text(
                            f"生成失败, 请检查后端地址是否有效: `{response.status}`",
                            message.chat.id,
                            reply.message_id,
                            disable_web_page_preview=True,
                            parse_mode="Markdown",
                        )
                        return
                    if 'application/json' in response.headers['content-type']:
                        json_data = await response.json()
                    else:
                        json_data = json.loads(await response.text())
            if json_data["status"] == 200:
                _url = server + json_data['key']
                await bot.edit_message_text(
                    f"短链接: `{_url}`",
                    message.chat.id,
                    reply.message_id,
                    disable_web_page_preview=True,
                    parse_mode="Markdown",
                )
            else:
                logger.error(f"[Short URL][{message.chat.id}]: Can't Get Short URL: {json_data}")
                await bot.edit_message_text(
                    f"生成失败, 请检查 URL 是否有效: `{json_data}`",
                    message.chat.id,
                    reply.message_id,
                    disable_web_page_preview=True,
                    parse_mode="Markdown",
                )
        except Exception as e:
            logger.error(f"[Short URL][{message.chat.id}]: Can't Get Short URL: {e}")
            await bot.edit_message_text(
                f"生成失败, 请检查后端地址是否有效: `{e}`",
                message.chat.id,
                reply.message_id,
                disable_web_page_preview=True,
                parse_mode="Markdown",
            )


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    async def short_handler(bot, message: types.Message):
        command_args = message.text.split()
        if len(command_args) == 2:
            url = command_args[1]
            await handle_short_command(bot, message, url)
        else:
            await bot.reply_to(message, command_error_msg("short", "URL"))

    middleware.register_command_handler(
        commands=['short'],
        callback=short_handler,
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
