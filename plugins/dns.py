# -*- coding: utf-8 -*-
# @Time    : 2025/7/1 15:21
# @Author  : KimmyXYC
# @File    : dns.py
# @Software: PyCharm

import dns.resolver
import dns.reversename
import dns.exception
from telebot import types
from loguru import logger
from app.utils import command_error_msg

# ==================== 插件元数据 ====================
__plugin_name__ = "dns"
__version__ = "1.0.0"
__author__ = "KimmyXYC"
__description__ = "DNS 记录查询"
__commands__ = ["dns"]
__command_descriptions__ = {"dns": "查询 DNS 记录"}
__command_help__ = {
    "dns": "/dns [Domain] [Record_Type] - 查询 DNS 记录\nInline: @NachoNekoX_bot dns [Domain] [Record_Type]"
}


# ==================== 核心功能 ====================
async def query_dns_text(domain: str, record_type: str) -> str:
    """生成与 `/dns` 命令一致的输出文本，用于命令与 Inline 复用（HTML）。"""
    return await dns_lookup(domain, record_type)


async def handle_dns_command(bot, message: types.Message, record_type):
    """
    处理 DNS 查询命令
    :param bot: Bot 对象
    :param message: 消息对象
    :param record_type: DNS 记录类型
    :return:
    """
    command_args = message.text.split()
    domain = command_args[1]

    # 向用户发送处理中的消息
    msg = await bot.reply_to(
        message,
        f"正在查询 {domain} 的 {record_type.upper()} 记录...",
        disable_web_page_preview=True,
    )

    # 进行 DNS 查询
    result = await query_dns_text(domain, record_type)

    # 更新消息内容为查询结果
    await bot.edit_message_text(
        result, message.chat.id, msg.message_id, parse_mode="HTML"
    )


async def handle_dns_inline_query(bot, inline_query: types.InlineQuery):
    """处理 Inline Query：@Bot dns [Domain] [Record_Type]"""
    query = (inline_query.query or "").strip()
    tokens = query.split()

    record_types = ["A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "PTR"]
    if not tokens or tokens[0].lower() != "dns":
        usage = "用法：dns [Domain] [Record_Type]（Record_Type 可选，默认 A）"
        result = types.InlineQueryResultArticle(
            id="dns_usage",
            title="DNS 查询",
            description="用法：dns [Domain] [Record_Type]",
            input_message_content=types.InputTextMessageContent(usage),
        )
        await bot.answer_inline_query(
            inline_query.id, [result], cache_time=1, is_personal=True
        )
        return

    args = tokens[1:]
    if len(args) == 1:
        domain = args[0]
        record_type = "A"
    elif len(args) == 2:
        domain = args[0]
        record_type = args[1].upper()
        if record_type not in record_types:
            usage = "用法：dns [Domain] [Record_Type]（Record_Type: A/AAAA/CNAME/MX/NS/TXT/SOA/PTR）"
            result = types.InlineQueryResultArticle(
                id="dns_usage",
                title="DNS 查询",
                description="Record_Type 无效",
                input_message_content=types.InputTextMessageContent(usage),
            )
            await bot.answer_inline_query(
                inline_query.id, [result], cache_time=1, is_personal=True
            )
            return
    else:
        usage = "用法：dns [Domain] [Record_Type]（Record_Type 可选，默认 A）"
        result = types.InlineQueryResultArticle(
            id="dns_usage",
            title="DNS 查询",
            description="参数不正确",
            input_message_content=types.InputTextMessageContent(usage),
        )
        await bot.answer_inline_query(
            inline_query.id, [result], cache_time=1, is_personal=True
        )
        return

    result_text = await query_dns_text(domain, record_type)
    result = types.InlineQueryResultArticle(
        id=f"dns_{domain}_{record_type}",
        title=f"DNS {domain} {record_type}",
        description="发送查询结果",
        input_message_content=types.InputTextMessageContent(
            result_text, parse_mode="HTML"
        ),
    )
    await bot.answer_inline_query(
        inline_query.id, [result], cache_time=1, is_personal=True
    )


async def dns_lookup(domain, record_type):
    """
    使用 dnspython 执行 DNS 查询
    :param domain: 要查询的域名或 IP
    :param record_type: 记录类型 (A, AAAA, CNAME, MX, NS, TXT, PTR)
    :return: 查询结果文本
    """
    try:
        # 处理反向 DNS 查询（PTR 记录）
        if record_type.upper() == "PTR":
            if ":" in domain:  # IPv6
                rev_name = dns.reversename.from_address(domain)
                answers = dns.resolver.resolve(rev_name, "PTR")
            else:  # IPv4
                rev_name = dns.reversename.from_address(domain)
                answers = dns.resolver.resolve(rev_name, "PTR")

            result = f"<b>域名查询结果 ({escape_html(domain)})</b>\n\n"
            for rdata in answers:
                result += f"- {escape_html(str(rdata.target))}\n"
        else:
            # 标准 DNS 查询
            answers = dns.resolver.resolve(domain, record_type.upper())

            result = f"<b>DNS 查询结果 ({escape_html(domain)}, {record_type.upper()})</b>\n\n"

            # 根据不同记录类型处理结果
            if record_type.upper() == "MX":
                for rdata in answers:
                    result += f"- 优先级: {rdata.preference}, 服务器: {escape_html(str(rdata.exchange))}\n"
            elif record_type.upper() == "SOA":
                for rdata in answers:
                    result += f"- 主域名服务器: {escape_html(str(rdata.mname))}\n"
                    result += f"- 管理员邮箱: {escape_html(str(rdata.rname))}\n"
                    result += f"- 序列号: {rdata.serial}\n"
                    result += f"- 刷新时间: {rdata.refresh}秒\n"
                    result += f"- 重试时间: {rdata.retry}秒\n"
                    result += f"- 过期时间: {rdata.expire}秒\n"
                    result += f"- 最小TTL: {rdata.minimum}秒\n"
            else:
                for rdata in answers:
                    result += f"- {escape_html(str(rdata))}\n"

            # 添加 TTL 信息
            result += f"\n<b>TTL</b>: {answers.rrset.ttl}秒"

        return result

    except dns.resolver.NoAnswer:
        return f"<b>错误</b>: <code>{escape_html(domain)}</code> 没有 {record_type.upper()} 类型的记录"
    except dns.resolver.NXDOMAIN:
        return f"<b>错误</b>: <code>{escape_html(domain)}</code> 不存在"
    except dns.exception.DNSException as e:
        logger.error(f"DNS查询错误: {str(e)}")
        return f"<b>DNS查询错误</b>: <code>{escape_html(str(e))}</code>"
    except Exception as e:
        logger.error(f"查询过程中发生未知错误: {str(e)}")
        return f"<b>发生未知错误</b>: <code>{escape_html(str(e))}</code>"


def escape_html(text):
    """
    转义 HTML 特殊字符以便在 HTML 模式中正确显示
    """
    html_escape_table = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    }
    return "".join(html_escape_table.get(c, c) for c in text)


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    async def dns_handler(bot, message: types.Message):
        command_args = message.text.split()
        record_types = ["A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "PTR"]
        if len(command_args) == 2:
            await handle_dns_command(bot, message, "A")
        elif len(command_args) == 3:
            if command_args[2].upper() not in record_types:
                await bot.reply_to(message, command_error_msg(reason="invalid_type"))
                return
            await handle_dns_command(bot, message, command_args[2])
        else:
            await bot.reply_to(
                message, command_error_msg("dns", "Domain", "Record_Type")
            )

    middleware.register_command_handler(
        commands=["dns"],
        callback=dns_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["private", "group", "supergroup"],
    )

    middleware.register_inline_handler(
        callback=handle_dns_inline_query,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        func=lambda q: (
            bool(getattr(q, "query", None))
            and q.query.strip().lower().startswith("dns")
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
