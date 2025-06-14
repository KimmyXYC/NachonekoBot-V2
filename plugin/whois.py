# -*- coding: utf-8 -*-
# @Time    : 2025/6/14 15:50
# @Author  : KimmyXYC
# @File    : whois.py
# @Software: PyCharm
import aiohttp
from telebot import types


async def handle_whois_command(bot, message: types.Message, req_type):
    """
    处理 Whois 命令
    :param bot: Bot 对象
    :param message: 消息对象
    :param req_type: 请求类型
    :return:
    """
    data = message.text.split()[1]
    msg = await bot.reply_to(message, f"正在查询 {message.text.split()[1]} Whois 信息...", disable_web_page_preview=True)
    status, result = await whois_check(data, req_type)
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
                filtered_result = [line for line in lines if
                                   'REDACTED FOR PRIVACY' not in line and 'Please query the' not in line
                                   and not line.strip().endswith(':')]
                return True, "\n".join(filtered_result).split("For more information")[0]
            else:
                return False, f"Request failed with status {response.status}"
