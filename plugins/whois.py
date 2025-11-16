# -*- coding: utf-8 -*-
# @Time    : 2025/6/14 15:50
# @Author  : KimmyXYC
# @File    : whois.py
# @Software: PyCharm
import aiohttp
from telebot import types
from loguru import logger
from app.utils import command_error_msg

# ==================== 插件元数据 ====================
__plugin_name__ = "whois"
__version__ = 1.0
__author__ = "KimmyXYC"
__description__ = "Whois 域名查询"
__commands__ = ["whois"]
__command_descriptions__ = {
    "whois": "查询 Whois 信息"
}
__command_help__ = {
    "whois": "/whois [Domain] - 查询 Whois 信息"
}


# ==================== 核心功能 ====================
async def handle_whois_command(bot, message: types.Message):
    """
    处理 Whois 命令
    :param bot: Bot 对象
    :param message: 消息对象
    :return:
    """
    data = message.text.split()[1]
    msg = await bot.reply_to(message, f"正在查询 {message.text.split()[1]} Whois 信息...", disable_web_page_preview=True)
    status, result = await whois_check(data)
    if not status:
        await bot.edit_message_text(f"请求失败: `{result}`", message.chat.id, msg.message_id, parse_mode="MarkdownV2")
        return
    await bot.edit_message_text(f"`{result}`", message.chat.id, msg.message_id, parse_mode="MarkdownV2")


async def whois_check(data):
    """
    Perform a WHOIS check on a domain or IP address.
    :param data: The domain or IP address to check.
    :return: A tuple containing the status and the result.
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://namebeta.com/api/search/check?query={data}') as response:
            if response.status == 200:
                result = await response.json()
                if "whois" not in result:
                    return False, result
                result = result['whois']['whois']
                lines = result.splitlines()
                filtered_result = [line for line in lines
                                   if 'REDACTED' not in line
                                   and 'Please query the' not in line
                                   and not line.strip().endswith(':')]
                cleaned = "\n".join(filtered_result)
                cleaned = cleaned.split("For more information")[0]
                cleaned = cleaned.split("RDAP TERMS OF SERVICE:")[0]
                return True, cleaned
            else:
                return False, f"Request failed with status {response.status}"


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    async def whois_handler(bot, message: types.Message):
        command_args = message.text.split()
        if len(command_args) == 2:
            await handle_whois_command(bot, message)
        else:
            await bot.reply_to(message, command_error_msg("whois", "Domain"))

    middleware.register_command_handler(
        commands=['whois'],
        callback=whois_handler,
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
