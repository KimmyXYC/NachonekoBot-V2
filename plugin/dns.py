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
    msg = await bot.reply_to(message, f"正在查询 {domain} 的 {record_type.upper()} 记录...", disable_web_page_preview=True)

    # 进行 DNS 查询
    result = await dns_lookup(domain, record_type)

    # 更新消息内容为查询结果
    await bot.edit_message_text(result, message.chat.id, msg.message_id, parse_mode="HTML")

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
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }
    return ''.join(html_escape_table.get(c, c) for c in text)
