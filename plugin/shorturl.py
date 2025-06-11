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
            f"生成失败, 后端地址未设置",
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
