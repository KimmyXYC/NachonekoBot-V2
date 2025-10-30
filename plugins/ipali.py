# -*- coding: utf-8 -*-
# @Time    : 2025/6/14 16:06
# @Author  : KimmyXYC
# @File    : ipali.py
# @Software: PyCharm
import ipaddress
import socket
import aiohttp

from telebot import types
from loguru import logger

from utils.yaml import BotConfig
from app.utils import command_error_msg

# ==================== 插件元数据 ====================
__plugin_name__ = "ipali"
__version__ = 1.0
__author__ = "KimmyXYC"
__description__ = "阿里云 IP 地址查询"
__commands__ = ["ipali"]
__command_descriptions__ = {
    "ipali": "使用阿里 API 查询 IP 或域名"
}
__command_help__ = {
    "ipali": "/ipali [IP/Domain] - 使用阿里 API 查询 IP 或域名"
}


# ==================== 核心功能 ====================
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
            ip_info += """地区:  `未知`\n"""
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


async def ali_ipcity_ip(ip_addr, appcode, is_v6=False):
    """
    Query IP information using Aliyun's IP City API.
    :param ip_addr: The IP address to query.
    :param appcode: The AppCode for authentication.
    :param is_v6: Boolean indicating if the IP address is IPv6.
    :return: A tuple containing the status and the result.
    """
    if is_v6:
        url = "https://ipv6city.market.alicloudapi.com/ip/ipv6/query"
    else:
        url = "https://ipcity.market.alicloudapi.com/ip/city/query"
    headers = {"Authorization": f"APPCODE {appcode}"}
    params = {"ip": ip_addr}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if data["code"] == 200:
                    return True, data["data"]["result"]
                else:
                    return False, data["msg"]
            else:
                return False, f"Request failed with status {response.status}"


def check_url(url):
    """
    Check if the URL is an IP address or a domain name.
    If it's an IP address, return it with its version (v4 or v6).
    If it's a domain name, resolve it to an IP address.
    :param url: The URL to check.
    :return: A tuple containing the IP address and its version (v4 or v6) or None if it's a domain name.
    """
    try:
        ip = ipaddress.ip_address(url)
        if ip.version == 4:
            return url, "v4"
        elif ip.version == 6:
            return url, "v6"
    except ValueError:
        return get_ip_address(url), None


def get_ip_address(domain):
    """
    Resolve a domain name to its IP address.
    :param domain: The domain name to resolve.
    :return: The first resolved IP address or None if the resolution fails.
    """
    try:
        addr_info = socket.getaddrinfo(domain, None, socket.AF_UNSPEC)
        ip_addresses = []
        for info in addr_info:
            ip_address = info[4][0]
            ip_addresses.append(ip_address)
        return ip_addresses[0]
    except socket.gaierror as e:
        logger.error(f"Domain name resolution failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unknown error: {e}")
        return None


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    async def ipali_handler(bot, message: types.Message):
        command_args = message.text.split()
        if len(command_args) == 2:
            await handle_ipali_command(bot, message)
        else:
            await bot.reply_to(message, command_error_msg("ipali", "IP Address or Domain"))

    middleware.register_command_handler(
        commands=['ipali'],
        callback=ipali_handler,
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
