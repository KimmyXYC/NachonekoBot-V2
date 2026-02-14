# -*- coding: utf-8 -*-
# @Time    : 2025/6/14 15:22
# @Author  : KimmyXYC
# @File    : icp.py
# @Software: PyCharm
import aiohttp
from telebot import types
from loguru import logger

from app.utils import markdown_to_telegram_html, command_error_msg
from utils.yaml import BotConfig

# ==================== 插件元数据 ====================
__plugin_name__ = "icp"
__version__ = "1.0.0"
__author__ = "KimmyXYC"
__description__ = "ICP 备案查询"
__commands__ = ["icp"]
__command_descriptions__ = {"icp": "查询域名 ICP 备案信息"}
__command_help__ = {
    "icp": "/icp [Domain] - 查询域名 ICP 备案信息\nInline: @NachoNekoX_bot icp [Domain]"
}


# ==================== 核心功能 ====================
async def query_icp_text(domain: str) -> str:
    """生成与 `/icp` 命令一致的输出文本，用于命令与 Inline 复用（HTML）。"""
    status, data = await icp_record_check(domain)
    if not status:
        return markdown_to_telegram_html(f"请求失败: `{data}`")

    if not data:
        icp_info = f"""查询目标:  `{domain}`\n备案状态:  `未备案`"""
    else:
        icp_info = ""
        for item in data:
            icp_info += (
                f"域名:  `{item['domain']}`\n"
                f"备案号:  `{item['mainLicence']}`\n"
                f"备案主体:  `{item['unitName']}`\n"
                f"备案性质:  `{item['natureName']}`\n"
                f"备案时间:  `{item['updateRecordTime']}`\n\n"
            )

    return markdown_to_telegram_html(icp_info)


async def handle_icp_command(bot, message: types.Message):
    """
    处理 ICP 命令
    :param bot: Bot 对象
    :param message: 消息对象
    :return:
    """
    domain = message.text.split()[1]
    msg = await bot.reply_to(
        message, f"正在查询域名 {domain} 备案信息...", disable_web_page_preview=True
    )
    text = await query_icp_text(domain)
    await bot.edit_message_text(
        text, message.chat.id, msg.message_id, parse_mode="HTML"
    )


async def handle_icp_inline_query(bot, inline_query: types.InlineQuery):
    """处理 Inline Query：@Bot icp [Domain]"""
    query = (inline_query.query or "").strip()
    tokens = query.split()

    if len(tokens) != 2 or tokens[0].lower() != "icp":
        usage = "用法：icp [Domain]"
        result = types.InlineQueryResultArticle(
            id="icp_usage",
            title="ICP 备案查询",
            description="用法：icp [Domain]",
            input_message_content=types.InputTextMessageContent(usage),
        )
        await bot.answer_inline_query(
            inline_query.id, [result], cache_time=1, is_personal=True
        )
        return

    domain = tokens[1]
    result_text = await query_icp_text(domain)
    result = types.InlineQueryResultArticle(
        id=f"icp_{domain}",
        title=f"ICP：{domain}",
        description="发送查询结果",
        input_message_content=types.InputTextMessageContent(
            result_text, parse_mode="HTML"
        ),
    )
    await bot.answer_inline_query(
        inline_query.id, [result], cache_time=1, is_personal=True
    )


async def icp_record_check(domain, retries=5):
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
                        elif data["code"] == 122:
                            pass
                        else:
                            return False, data["msg"]
                    else:
                        logger.warning(
                            f"Attempt {attempt + 1} failed with status {response.status}"
                        )
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed with exception: {e}")

    return False, "All retry attempts failed"


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    async def icp_handler(bot, message: types.Message):
        command_args = message.text.split()
        if len(command_args) == 2:
            await handle_icp_command(bot, message)
        else:
            await bot.reply_to(message, command_error_msg("icp", "Domain"))

    middleware.register_command_handler(
        commands=["icp"],
        callback=icp_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["private", "group", "supergroup"],
    )

    middleware.register_inline_handler(
        callback=handle_icp_inline_query,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        func=lambda q: (
            bool(getattr(q, "query", None))
            and q.query.strip().lower().startswith("icp")
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
