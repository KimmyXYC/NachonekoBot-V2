# -*- coding: utf-8 -*-
# @Time    : 2025/6/14 15:31
# @Author  : KimmyXYC
# @File    : dnsapi.py
# @Software: PyCharm
import aiohttp
from telebot import types

async def handle_dns_command(bot, message: types.Message, record_type):
    """
    处理 DNS 命令
    :param bot: Bot 对象
    :param message: 消息对象
    :param record_type: 记录类型
    :return:
    """
    msg = await bot.reply_to(message, f"DNS lookup {message.text.split()[1]} as {record_type.upper()} ...", disable_web_page_preview=True)
    status, result = await get_dns_info(message.text.split()[1], record_type)
    if not status:
        await bot.edit_message_text(f"请求失败: `{result}`", message.chat.id, msg.message_id, parse_mode="MarkdownV2")
        return
    dns_info = f"CN:\nTime Consume: {result['86'][0]['answer']['time_consume']}\n"
    dns_info += f"Records: {result['86'][0]['answer']['records']}\n\n"
    dns_info = f"`{dns_info}`"
    await bot.edit_message_text(dns_info, message.chat.id, msg.message_id, parse_mode="MarkdownV2")

async def get_dns_info(domain, record_type):
    """
    Perform a DNS lookup for a given domain and record type.
    :param domain: The domain name to look up.
    :param record_type: The type of DNS record to look up (A, NS, CNAME, MX, TXT, AAAA).
    :return: A tuple containing the status and the result.
    """
    qtype = {
        "A": 1,
        "NS": 2,
        "CNAME": 5,
        "MX": 15,
        "TXT": 16,
        "AAAA": 28,
    }
    record_type = record_type.upper()
    if record_type not in qtype.keys():
        return False, "record_type error"

    url = "https://myssl.com/api/v1/tools/dns_query"
    params = {
        "qtype": qtype[record_type],
        "host": domain,
        "qmode": -1
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if data["code"] == 0:
                    return True, data["data"]
                else:
                    return False, data["error"]
            else:
                return False, f"Request failed with status {response.status}"
