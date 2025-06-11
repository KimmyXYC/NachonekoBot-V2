# -*- coding: utf-8 -*-
# @Time    : 2025/5/1 12:42
# @Author  : KimmyXYC
# @File    : ping.py
# @Software: PyCharm

import re

from telebot import types

from utils.ip import *
from app.utils import markdown_to_telegram_html, escape_md_v2_text
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


async def handle_ipali_command(bot, message: types.Message):
    """
    处理 IP 查询命令
    :param bot: Bot 对象
    :param message: 消息对象
    :return:
    """
    msg = await bot.reply_to(message, f"正在查询 {message.text.split()[1]} ...", disable_web_page_preview=True)
    if not BotConfig["aliyun"]["appcode"]:
        await bot.edit_message_text("未配置阿里云 AppCode", message.chat.id, msg.message_id, parse_mode="MarkdownV2")
        return
    ip_addr, ip_type = check_url(message.text.split()[1])
    _is_url = False
    if ip_type is None:
        ip_addr, ip_type = check_url(ip_addr)
        _is_url = True
    if ip_addr is None:
        await bot.edit_message_text("非法的 IP 地址或域名", message.chat.id, msg.message_id, parse_mode="MarkdownV2")
        return
    elif ip_type == "v4" or ip_type == "v6":
        if ip_type == "v4":
            status, data = await ali_ipcity_ip(ip_addr, BotConfig["aliyun"]["appcode"])
        else:
            status, data = await ali_ipcity_ip(ip_addr, BotConfig["aliyun"]["appcode"], True)
        if not status:
            await bot.edit_message_text(f"请求失败: `{data}`", message.chat.id, msg.message_id, parse_mode="MarkdownV2")
            return
        ip_info = f"""查询目标:  `{message.text.split()[1]}`\n"""
        if _is_url:
            ip_info += f"""解析地址:  `{ip_addr}`\n"""
        if not data["country"]:
            ip_info += f"""地区:  `未知`\n"""
        else:
            if ip_type == "v4":
                if data["prov"]:
                    ip_info += f"""地区:  `{data["country"]} - {data["prov"]} - {data["city"]}`\n"""
                else:
                    ip_info += f"""地区:  `{data["country"]}`\n"""
            else:
                if data["province"]:
                    ip_info += f"""地区:  `{data["country"]} - {data["province"]} - {data["city"]}`\n"""
                else:
                    ip_info += f"""地区:  `{data["country"]}`\n"""
            ip_info += f"""经纬度:  `{data["lng"]}, {data["lat"]}`\nISP:  `{data["isp"]}`\n组织:  `{data["owner"]}`\n"""
            if data["asnumber"]:
                ip_info += f"""ASN:  [AS{data["asnumber"]}](https://bgp.he.net/AS{data["asnumber"]})"""
        await bot.edit_message_text(ip_info, message.chat.id, msg.message_id, parse_mode="MarkdownV2", disable_web_page_preview=True)
    else:
        await bot.edit_message_text("非法的 IP 地址或域名", message.chat.id, msg.message_id, parse_mode="MarkdownV2")


async def handle_ip_command(bot, message: types.Message):
    """
    处理 IP 查询命令
    :param bot: Bot 对象
    :param message: 消息对象
    :return:
    """
    msg = await bot.reply_to(message, f"正在查询 {message.text.split()[1]} ...", disable_web_page_preview=True)
    url = message.text.split()[1]
    url = convert_to_punycode(url)
    try:
        status, data = await ipapi_ip(url)
    except Exception as e:
        await bot.edit_message_text(f"请求失败: `{e}`", message.chat.id, msg.message_id, parse_mode="MarkdownV2")
        return
    if not status:
        await bot.edit_message_text(f"请求失败: `{data['message']}`", message.chat.id, msg.message_id, parse_mode="MarkdownV2")
        return

    _is_url = url != data["query"]
    if not data["country"]:
        ip_info = f"""查询目标:  `{url}`\n"""
        if _is_url:
            ip_info += f"""解析地址:  `{data["query"]}`\n"""
        ip_info += f"""地区:  `未知`\n"""
    else:
        ip_info = f"""查询目标:  `{url}`\n"""
        if _is_url:
            ip_info += f"""解析地址:  `{data["query"]}`\n"""
        region = (
            f"{data['regionName']} - {data['city']}"
            if data["regionName"] and data["city"]
            else data["regionName"] or data["city"] or data["country"]
        )
        ip_info += f"""地区:  `{data["country"]} - {region}`\n"""
        ip_info += f"""经纬度:  `{data["lon"]}, {data["lat"]}`\nISP:  `{data["isp"]}`\n组织:  `{data["org"]}`\n"""
        re_match = re.search(r'(AS\d+)', data["as"])
        if re_match:
            as_number = re_match.group(1)
            ip_info += f"""[{escape_md_v2_text(data["as"])}](https://bgp.he.net/{as_number})"""
        else:
            ip_info += f"""`{data["as"]}`"""
    if data["mobile"]:
        ip_info += f"""\n此 IP 可能为 *蜂窝移动数据 IP*"""
    if data["proxy"]:
        ip_info += f"""\n此 IP 可能为 *代理 IP*"""
    if data["hosting"]:
        ip_info += f"""\n此 IP 可能为 *数据中心 IP*"""
    await bot.edit_message_text(ip_info, message.chat.id, msg.message_id, parse_mode="MarkdownV2", disable_web_page_preview=True)
