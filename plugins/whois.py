# -*- coding: utf-8 -*-
# @Time    : 2025/6/14 15:50
# @Author  : KimmyXYC
# @File    : whois.py
# @Software: PyCharm
import asyncio
from telebot import types
from loguru import logger
from app.utils import command_error_msg

# ==================== 插件元数据 ====================
__plugin_name__ = "whois"
__version__ = "1.2.0"
__author__ = "KimmyXYC"
__description__ = "Whois 域名查询"
__commands__ = ["whois"]
__command_descriptions__ = {
    "whois": "查询 Whois 信息"
}
__command_help__ = {
    "whois": "/whois [Domain] - 查询 Whois 信息\nInline: @NachoNekoX_bot whois [Domain]"
}


# ==================== 核心功能 ====================
async def query_whois_text(data: str) -> str:
    """生成与 `/whois` 命令一致的输出文本，用于命令与 Inline 复用（MarkdownV2）。"""
    status, result = await whois_check(data)
    if not status:
        return f"请求失败: `{result}`"
    return f"`{result}`"


async def handle_whois_command(bot, message: types.Message):
    """
    处理 Whois 命令
    :param bot: Bot 对象
    :param message: 消息对象
    :return:
    """
    data = message.text.split()[1]
    msg = await bot.reply_to(message, f"正在查询 {data} Whois 信息...", disable_web_page_preview=True)
    text = await query_whois_text(data)
    await bot.edit_message_text(text, message.chat.id, msg.message_id, parse_mode="MarkdownV2")


async def handle_whois_inline_query(bot, inline_query: types.InlineQuery):
    """处理 Inline Query：@Bot whois [Domain]"""
    query = (inline_query.query or "").strip()
    tokens = query.split()

    if len(tokens) != 2 or tokens[0].lower() != 'whois':
        usage = "用法：whois [Domain]"
        result = types.InlineQueryResultArticle(
            id="whois_usage",
            title="Whois 查询",
            description="用法：whois [Domain]",
            input_message_content=types.InputTextMessageContent(usage)
        )
        await bot.answer_inline_query(inline_query.id, [result], cache_time=1, is_personal=True)
        return

    domain = tokens[1]
    result_text = await query_whois_text(domain)
    result = types.InlineQueryResultArticle(
        id=f"whois_{domain}",
        title=f"Whois：{domain}",
        description="发送查询结果",
        input_message_content=types.InputTextMessageContent(result_text, parse_mode="MarkdownV2")
    )
    await bot.answer_inline_query(inline_query.id, [result], cache_time=1, is_personal=True)


async def whois_check(data):
    """
    Perform a WHOIS check on a domain or IP address using command-line whois.
    :param data: The domain or IP address to check.
    :return: A tuple containing the status and the result.
    """
    try:
        # Run whois command asynchronously
        process = await asyncio.create_subprocess_exec(
            'whois', data,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode('utf-8', errors='ignore').strip()
            return False, f"Whois command failed: {error_msg if error_msg else 'Unknown error'}"

        result = stdout.decode('utf-8', errors='ignore').strip()

        if not result or "No match" in result or "NOT FOUND" in result:
            return False, "No WHOIS data found."

        # Clean up the result - remove redacted info and common footer text
        lines = result.splitlines()
        filtered_result = [line for line in lines
                           if 'REDACTED' not in line
                           and 'Please query the' not in line
                           and not (line.strip().endswith(':') and not line.strip()[:-1])]
        cleaned = "\n".join(filtered_result)

        # Remove common footer sections
        cleaned = cleaned.split("For more information")[0]
        cleaned = cleaned.split("RDAP TERMS OF SERVICE:")[0]
        cleaned = cleaned.split("TERMS OF SERVICE:")[0]
        cleaned = cleaned.split(">>> Last update of")[0]
        cleaned = cleaned.split("% This is the")[0]

        return True, cleaned.strip()

    except FileNotFoundError:
        return False, "Whois command not found. Please install whois tool."
    except Exception as e:
        logger.error(f"Whois query error: {e}")
        return False, f"Error executing whois: {str(e)}"


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    async def whois_handler(bot, message: types.Message):
        command_args = message.text.split()
        if len(command_args) == 2:
            await handle_whois_command(bot, message)
        else:
            await bot.reply_to(message, command_error_msg("whois", "Domain"))

    middleware.register_command_handler(
        commands=['whois'],
        callback=whois_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=['private', 'group', 'supergroup']
    )

    middleware.register_inline_handler(
        callback=handle_whois_inline_query,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        func=lambda q: bool(getattr(q, 'query', None)) and q.query.strip().lower().startswith('whois')
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
