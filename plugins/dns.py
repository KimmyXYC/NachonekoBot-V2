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
from utils.i18n import get_inline_query_language, get_message_language, plugin_t

# ==================== 插件元数据 ====================
__plugin_name__ = "dns"
__version__ = "1.0.0"
__author__ = "KimmyXYC"
__description__ = "DNS 记录查询"
__commands__ = ["dns"]
__command_category__ = "network"
__command_order__ = {"dns": 40}
__command_descriptions__ = {"dns": "查询 DNS 记录"}
__command_help__ = {
    "dns": "/dns [Domain] [Record_Type] - 查询 DNS 记录\nInline: @NachoNekoX_bot dns [Domain] [Record_Type]"
}


# ==================== 核心功能 ====================
async def query_dns_text(domain: str, record_type: str, lang: str) -> str:
    """生成与 `/dns` 命令一致的输出文本，用于命令与 Inline 复用（HTML）。"""
    return await dns_lookup(domain, record_type, lang)


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
    lang = await get_message_language(message)

    # 向用户发送处理中的消息
    msg = await bot.reply_to(
        message,
        plugin_t(
            __plugin_name__,
            "status.dns_querying",
            lang,
            domain=domain,
            record_type=record_type.upper(),
        ),
        disable_web_page_preview=True,
    )

    # 进行 DNS 查询
    result = await query_dns_text(domain, record_type, lang)

    # 更新消息内容为查询结果
    await bot.edit_message_text(
        result, message.chat.id, msg.message_id, parse_mode="HTML"
    )


async def handle_dns_inline_query(bot, inline_query: types.InlineQuery):
    """处理 Inline Query：@Bot dns [Domain] [Record_Type]"""
    lang = await get_inline_query_language(inline_query)
    query = (inline_query.query or "").strip()
    tokens = query.split()

    record_types = ["A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "PTR"]
    if not tokens or tokens[0].lower() != "dns":
        usage = plugin_t(__plugin_name__, "inline.usage_text", lang)
        result = types.InlineQueryResultArticle(
            id="dns_usage",
            title=plugin_t(__plugin_name__, "inline.usage_title", lang),
            description=plugin_t(__plugin_name__, "inline.usage_description", lang),
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
            usage = plugin_t(__plugin_name__, "inline.record_type_invalid_text", lang)
            result = types.InlineQueryResultArticle(
                id="dns_usage",
                title=plugin_t(__plugin_name__, "inline.usage_title", lang),
                description=plugin_t(
                    __plugin_name__, "inline.record_type_invalid_description", lang
                ),
                input_message_content=types.InputTextMessageContent(usage),
            )
            await bot.answer_inline_query(
                inline_query.id, [result], cache_time=1, is_personal=True
            )
            return
    else:
        usage = plugin_t(__plugin_name__, "inline.usage_text", lang)
        result = types.InlineQueryResultArticle(
            id="dns_usage",
            title=plugin_t(__plugin_name__, "inline.usage_title", lang),
            description=plugin_t(
                __plugin_name__, "inline.invalid_arguments_description", lang
            ),
            input_message_content=types.InputTextMessageContent(usage),
        )
        await bot.answer_inline_query(
            inline_query.id, [result], cache_time=1, is_personal=True
        )
        return

    result_text = await query_dns_text(domain, record_type, lang)
    result = types.InlineQueryResultArticle(
        id=f"dns_{domain}_{record_type}",
        title=plugin_t(
            __plugin_name__,
            "inline.result_title",
            lang,
            domain=domain,
            record_type=record_type,
        ),
        description=plugin_t(__plugin_name__, "inline.send_result_description", lang),
        input_message_content=types.InputTextMessageContent(
            result_text, parse_mode="HTML"
        ),
    )
    await bot.answer_inline_query(
        inline_query.id, [result], cache_time=1, is_personal=True
    )


async def dns_lookup(domain, record_type, lang: str):
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

            result = plugin_t(
                __plugin_name__,
                "title.domain_query_result",
                lang,
                domain=escape_html(domain),
            )
            for rdata in answers:
                result += f"- {escape_html(str(rdata.target))}\n"
        else:
            # 标准 DNS 查询
            answers = dns.resolver.resolve(domain, record_type.upper())

            result = plugin_t(
                __plugin_name__,
                "title.dns_query_result",
                lang,
                domain=escape_html(domain),
                record_type=record_type.upper(),
            )

            # 根据不同记录类型处理结果
            if record_type.upper() == "MX":
                for rdata in answers:
                    result += plugin_t(
                        __plugin_name__,
                        "line.mx_record",
                        lang,
                        preference=rdata.preference,
                        exchange=escape_html(str(rdata.exchange)),
                    )
            elif record_type.upper() == "SOA":
                for rdata in answers:
                    result += plugin_t(
                        __plugin_name__,
                        "line.soa_mname",
                        lang,
                        mname=escape_html(str(rdata.mname)),
                    )
                    result += plugin_t(
                        __plugin_name__,
                        "line.soa_rname",
                        lang,
                        rname=escape_html(str(rdata.rname)),
                    )
                    result += plugin_t(
                        __plugin_name__, "line.soa_serial", lang, serial=rdata.serial
                    )
                    result += plugin_t(
                        __plugin_name__, "line.soa_refresh", lang, refresh=rdata.refresh
                    )
                    result += plugin_t(
                        __plugin_name__, "line.soa_retry", lang, retry=rdata.retry
                    )
                    result += plugin_t(
                        __plugin_name__, "line.soa_expire", lang, expire=rdata.expire
                    )
                    result += plugin_t(
                        __plugin_name__, "line.soa_min_ttl", lang, minimum=rdata.minimum
                    )
            else:
                for rdata in answers:
                    result += f"- {escape_html(str(rdata))}\n"

            # 添加 TTL 信息
            result += plugin_t(__plugin_name__, "line.ttl", lang, ttl=answers.rrset.ttl)

        return result

    except dns.resolver.NoAnswer:
        return plugin_t(
            __plugin_name__,
            "error.no_record_type",
            lang,
            domain=escape_html(domain),
            record_type=record_type.upper(),
        )
    except dns.resolver.NXDOMAIN:
        return plugin_t(
            __plugin_name__, "error.domain_not_exists", lang, domain=escape_html(domain)
        )
    except dns.exception.DNSException as e:
        logger.error(f"DNS查询错误: {str(e)}")
        return plugin_t(
            __plugin_name__, "error.dns_query_failed", lang, reason=escape_html(str(e))
        )
    except Exception as e:
        logger.error(f"查询过程中发生未知错误: {str(e)}")
        return plugin_t(
            __plugin_name__, "error.unknown", lang, reason=escape_html(str(e))
        )


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
