# -*- coding: utf-8 -*-
# @Time    : 2025/6/14 15:22
# @Author  : KimmyXYC
# @File    : icp.py
# @Software: PyCharm
import aiohttp
from telebot import types
from loguru import logger

from app.utils import markdown_to_telegram_html, command_error_msg
from utils.yaml import BotConfig

# ==================== 插件元数据 ====================
__plugin_name__ = "icp"
__version__ = 1.0
__author__ = "KimmyXYC"
__description__ = "ICP 备案查询"
__commands__ = ["icp"]


# ==================== 核心功能 ====================
async def handle_icp_command(bot, message: types.Message):
    """
    处理 ICP 命令
    :param bot: Bot 对象
    :param message: 消息对象
    :return:
    """
    msg = await bot.reply_to(message, f"正在查询域名 {message.text.split()[1]} 备案信息...", disable_web_page_preview=True)
    status, data = await icp_record_check(message.text.split()[1])
    if not status:
        await bot.edit_message_text(message, f"请求失败: `{data}`", message.chat.id, msg.message_id, parse_mode="MarkdownV2")
        return
    if not data:
        icp_info = f"""查询目标:  `{message.text.split()[1]}`\n备案状态:  `未备案`"""
    else:
        icp_info = ""
        for item in data:
            icp_info += f"""域名:  `{item["domain"]}`\n备案号:  `{item["mainLicence"]}`\n备案主体:  `{item["unitName"]}`\n备案性质:  `{item["natureName"]}`\n备案时间:  `{item["updateRecordTime"]}`\n\n"""
    await bot.edit_message_text(markdown_to_telegram_html(icp_info), message.chat.id, msg.message_id, parse_mode="HTML")


async def icp_record_check(domain, retries=5):
    """
    Check if a domain has an ICP record.
    :param domain: The domain name to check.
    :param retries: The number of retry attempts.
    :return: A tuple containing the status and the result.
    """
    url = BotConfig["icp"]["url"]
    params = {"search": domain}

    for attempt in range(retries):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params, timeout=20) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data["code"] == 200:
                            return True, data["params"]["list"]
                        elif data["code"] == 122:
                            pass
                        else:
                            return False, data["msg"]
                    else:
                        logger.warning(f"Attempt {attempt + 1} failed with status {response.status}")
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed with exception: {e}")

    return False, "All retry attempts failed"


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    async def icp_handler(bot, message: types.Message):
        command_args = message.text.split()
        if len(command_args) == 2:
            await handle_icp_command(bot, message)
        else:
            await bot.reply_to(message, command_error_msg("icp", "Domain"))

    middleware.register_command_handler(
        commands=['icp'],
        callback=icp_handler,
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
