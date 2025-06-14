# -*- coding: utf-8 -*-
# @Time    : 2025/6/14 15:22
# @Author  : KimmyXYC
# @File    : icp.py
# @Software: PyCharm
import aiohttp
from telebot import types
from loguru import logger

from app.utils import markdown_to_telegram_html
from utils.yaml import BotConfig

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


async def icp_record_check(domain, retries=3):
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
                        else:
                            return False, data["msg"]
                    else:
                        logger.warning(f"Attempt {attempt + 1} failed with status {response.status}")
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed with exception: {e}")

    return False, "All retry attempts failed"
