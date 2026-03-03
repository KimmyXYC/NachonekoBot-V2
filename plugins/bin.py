# -*- coding: utf-8 -*-
# @Time    : 2025/7/1 21:59
# @Author  : KimmyXYC
# @File    : bin.py
# @Software: PyCharm
import json
import aiohttp
from json.decoder import JSONDecodeError
from telebot import types
from loguru import logger

# ==================== 插件元数据 ====================
__plugin_name__ = "bin"
__version__ = "1.0.0"
__author__ = "KimmyXYC"
__description__ = "BIN 号码查询"
__commands__ = ["bin"]
__command_category__ = "query"
__command_order__ = {"bin": 120}
__command_descriptions__ = {"bin": "查询银行卡 BIN 信息"}
__command_help__ = {
    "bin": "/bin [Card_BIN] - 查询银行卡 BIN 信息\nInline: @NachoNekoX_bot bin [Card_BIN]"
}


# ==================== 核心功能 ====================
async def query_bin_text(card_bin: str, _t) -> str:
    """查询 BIN"""
    if not card_bin.isdigit() or not (4 <= len(card_bin) <= 8):
        return _t("error.invalid_bin_parameter")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://lookup.binlist.net/{card_bin}") as r:
                if r.status == 404:
                    return _t("error.bin_not_found")
                if r.status == 429:
                    return _t("error.rate_limit_exceeded")
                if r.status != 200:
                    return _t("error.request_failed_with_status", status=r.status)

                content = await r.text()
                bin_json = json.loads(content)
    except aiohttp.ClientError:
        return _t("error.binlist_unreachable")
    except JSONDecodeError:
        return _t("error.invalid_parameter")
    except Exception as e:
        return _t("error.exception_occurred", reason=str(e))

    msg_out = []
    msg_out.extend([_t("label.bin", value=card_bin)])
    try:
        msg_out.extend([_t("label.scheme", value=bin_json["scheme"])])
    except (KeyError, TypeError):
        pass
    try:
        msg_out.extend([_t("label.card_type", value=bin_json["type"])])
    except (KeyError, TypeError):
        pass
    try:
        msg_out.extend([_t("label.brand", value=bin_json["brand"])])
    except (KeyError, TypeError):
        pass
    try:
        msg_out.extend([_t("label.bank_name", value=bin_json["bank"]["name"])])
    except (KeyError, TypeError):
        pass
    try:
        if bin_json["prepaid"]:
            msg_out.extend([_t("label.prepaid_yes")])
        else:
            msg_out.extend([_t("label.prepaid_no")])
    except (KeyError, TypeError):
        pass
    try:
        msg_out.extend([_t("label.country_name", value=bin_json["country"]["name"])])
    except (KeyError, TypeError):
        pass

    return "\n".join(msg_out)


async def handle_bin_command(bot, message: types.Message):
    """
    处理 BIN 查询命令
    :param bot: Bot 对象
    :param message: 消息对象
    :return:
    """
    command_args = message.text.split()
    _t = bot.t
    if len(command_args) != 2:
        await bot.reply_to(message, bot.t("prompt.valid_bin_required"))
        return

    card_bin = command_args[1]
    if not card_bin.isdigit() or not (4 <= len(card_bin) <= 8):
        await bot.reply_to(message, bot.t("error.invalid_bin_parameter"))
        return

    msg = await bot.reply_to(
        message,
        _t("status.querying_bin", card_bin=card_bin),
    )

    result_text = await query_bin_text(card_bin, _t)
    await bot.edit_message_text(result_text, message.chat.id, msg.message_id)


async def handle_bin_inline_query(bot, inline_query: types.InlineQuery):
    """处理 Inline Query：@Bot bin [Card_BIN]"""
    _t = bot.t
    query = (inline_query.query or "").strip()
    args = query.split()

    # 仅在 middleware 过滤后进来；此处再做一次兜底
    if len(args) != 2 or args[0].lower() != "bin":
        text = _t("prompt.valid_bin_required")
        result = types.InlineQueryResultArticle(
            id="bin_usage",
            title=_t("inline.usage_title"),
            description=_t("inline.usage_description"),
            input_message_content=types.InputTextMessageContent(text),
        )
        await bot.answer_inline_query(
            inline_query.id, [result], cache_time=1, is_personal=True
        )
        return

    card_bin = args[1]
    result_text = await query_bin_text(card_bin, _t)

    result = types.InlineQueryResultArticle(
        id=f"bin_{card_bin}",
        title=_t("inline.result_title", card_bin=card_bin),
        description=_t("inline.send_result_description"),
        input_message_content=types.InputTextMessageContent(result_text),
    )
    await bot.answer_inline_query(
        inline_query.id, [result], cache_time=1, is_personal=True
    )


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot
    middleware.register_command_handler(
        commands=["bin"],
        callback=handle_bin_command,
        plugin_name=plugin_name,
        priority=50,  # 优先级
        stop_propagation=True,  # 阻止后续处理器
        chat_types=["private", "group", "supergroup"],  # 过滤器
    )

    middleware.register_inline_handler(
        callback=handle_bin_inline_query,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        func=lambda q: (
            bool(getattr(q, "query", None))
            and q.query.strip().lower().startswith("bin")
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
