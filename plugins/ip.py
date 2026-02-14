# -*- coding: utf-8 -*-
# @Time    : 2025/6/14 15:52
# @Author  : KimmyXYC
# @File    : ip.py
# @Software: PyCharm
import re
import idna
import aiohttp
from telebot import types
from loguru import logger
from app.utils import escape_md_v2_text, command_error_msg

# ==================== 插件元数据 ====================
__plugin_name__ = "ip"
__version__ = "1.0.0"
__author__ = "KimmyXYC"
__description__ = "IP 地址查询"
__commands__ = ["ip"]
__command_descriptions__ = {"ip": "查询 IP 或域名信息"}
__command_help__ = {
    "ip": "/ip [IP/Domain] - 查询 IP 或域名信息\nInline: @NachoNekoX_bot ip [IP/Domain]"
}


# ==================== 核心功能 ====================
async def query_ip_text(raw_target: str) -> str:
    """生成与 `/ip` 命令一致的输出文本，用于命令与 Inline 复用（MarkdownV2）。"""
    url = convert_to_punycode(raw_target)

    try:
        status, data = await ipapi_ip(url)
    except Exception as e:
        return f"请求失败: `{e}`"

    if not status:
        # ip-api 的失败通常带 message 字段
        if isinstance(data, dict) and data.get("message"):
            return f"请求失败: `{data['message']}`"
        return f"请求失败: `{data}`"

    _is_url = url != data["query"]
    if not data["country"]:
        ip_info = f"""查询目标:  `{url}`\n"""
        if _is_url:
            ip_info += f"""解析地址:  `{data["query"]}`\n"""
        ip_info += """地区:  `未知`\n"""
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
        re_match = re.search(r"(AS\d+)", data["as"])
        if re_match:
            as_number = re_match.group(1)
            ip_info += (
                f"""[{escape_md_v2_text(data["as"])}](https://bgp.he.net/{as_number})"""
            )
        else:
            ip_info += f"""`{data["as"]}`"""
    if data["mobile"]:
        ip_info += """\n此 IP 可能为 *蜂窝移动数据 IP*"""
    if data["proxy"]:
        ip_info += """\n此 IP 可能为 *代理 IP*"""
    if data["hosting"]:
        ip_info += """\n此 IP 可能为 *数据中心 IP*"""
    return ip_info


async def handle_ip_command(bot, message: types.Message):
    """处理 IP 查询命令"""
    target = message.text.split()[1]
    msg = await bot.reply_to(
        message, f"正在查询 {target} ...", disable_web_page_preview=True
    )
    ip_info = await query_ip_text(target)
    await bot.edit_message_text(
        ip_info,
        message.chat.id,
        msg.message_id,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )


async def handle_ip_inline_query(bot, inline_query: types.InlineQuery):
    """处理 Inline Query：@Bot ip [IP/Domain]"""
    query = (inline_query.query or "").strip()
    tokens = query.split()

    if len(tokens) != 2 or tokens[0].lower() != "ip":
        usage = "用法：ip [IP/Domain]"
        result = types.InlineQueryResultArticle(
            id="ip_usage",
            title="IP 查询",
            description="用法：ip [IP/Domain]",
            input_message_content=types.InputTextMessageContent(usage),
        )
        await bot.answer_inline_query(
            inline_query.id, [result], cache_time=1, is_personal=True
        )
        return

    target = tokens[1]
    result_text = await query_ip_text(target)

    result = types.InlineQueryResultArticle(
        id=f"ip_{target}",
        title=f"IP：{target}",
        description="发送查询结果",
        input_message_content=types.InputTextMessageContent(
            result_text, parse_mode="MarkdownV2"
        ),
    )
    await bot.answer_inline_query(
        inline_query.id, [result], cache_time=1, is_personal=True
    )


async def ipapi_ip(ip_addr):
    """
    Query IP information using ip-api.com.
    :param ip_addr: The IP address to query.
    :return: A tuple containing the status and the result.
    """
    url = f"http://ip-api.com/json/{ip_addr}"
    params = {
        "fields": "status,message,country,regionName,city,lat,lon,isp,org,as,mobile,proxy,hosting,query"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if data["status"] == "success":
                    return True, data
                else:
                    return False, data
            else:
                return False, f"Request failed with status {response.status}"


def convert_to_punycode(domain):
    """
    Convert a domain name to Punycode format.
    :param domain: The domain name to convert.
    :return: The Punycode representation of the domain name.
    If the domain name is already in ASCII format, return it as is.
    """
    try:
        domain.encode("ascii")
    except UnicodeEncodeError:
        return idna.encode(domain).decode("ascii")
    else:
        return domain


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    async def ip_handler(bot, message: types.Message):
        command_args = message.text.split()
        if len(command_args) == 2:
            await handle_ip_command(bot, message)
        else:
            await bot.reply_to(message, command_error_msg("ip", "IP Address or Domain"))

    middleware.register_command_handler(
        commands=["ip"],
        callback=ip_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["private", "group", "supergroup"],
    )

    middleware.register_inline_handler(
        callback=handle_ip_inline_query,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        func=lambda q: (
            bool(getattr(q, "query", None)) and q.query.strip().lower().startswith("ip")
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
