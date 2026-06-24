# -*- coding: utf-8 -*-
# @Time    : 2025/7/1 21:59
# @Author  : KimmyXYC
# @File    : bin.py
# @Software: PyCharm
import os
from typing import Any

import aiohttp
from telebot import types
from loguru import logger
from utils.i18n import _t
from utils.yaml import BotConfig

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

HANDYAPI_BIN_URL = "https://data.handyapi.com/bin/{card_bin}"
BINLIST_BIN_URL = "https://lookup.binlist.net/{card_bin}"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


class BinNotFoundError(Exception):
    """BIN 不存在。"""


class BinRateLimitError(Exception):
    """BIN 查询服务触发限流。"""


class BinRequestError(Exception):
    """BIN 查询服务返回非成功状态。"""

    def __init__(self, status: int):
        super().__init__(f"BIN lookup request failed with status {status}")
        self.status = status


# ==================== 核心功能 ====================
def _get_handyapi_api_key() -> str | None:
    """从环境变量或配置文件读取 HandyAPI Key。"""
    api_key = os.getenv("HANDYAPI_API_KEY")
    if not api_key:
        bin_config = BotConfig.get("bin") or {}
        api_key = bin_config.get("handyapi_api_key") or bin_config.get("api_key")

    if not api_key:
        return None

    api_key = str(api_key).strip()
    if api_key.lower() in {"undefined", "your_handyapi_api_key", "your key"}:
        return None
    return api_key


def _append_label(msg_out: list[str], key: str, value: Any) -> None:
    if value not in (None, ""):
        msg_out.append(_t(key, value=value))


async def _query_handyapi_bin(
    session: aiohttp.ClientSession, card_bin: str, api_key: str
) -> dict[str, Any]:
    headers = {"x-api-key": api_key}
    async with session.get(
        HANDYAPI_BIN_URL.format(card_bin=card_bin), headers=headers
    ) as r:
        if r.status == 404:
            raise BinNotFoundError
        if r.status == 429:
            raise BinRateLimitError
        if r.status != 200:
            raise BinRequestError(r.status)

        bin_json = await r.json(content_type=None)

    if not isinstance(bin_json, dict) or bin_json.get("Status") != "SUCCESS":
        raise BinNotFoundError
    return bin_json


async def _query_binlist_bin(
    session: aiohttp.ClientSession, card_bin: str
) -> dict[str, Any]:
    async with session.get(BINLIST_BIN_URL.format(card_bin=card_bin)) as r:
        if r.status == 404:
            raise BinNotFoundError
        if r.status == 429:
            raise BinRateLimitError
        if r.status != 200:
            raise BinRequestError(r.status)

        bin_json = await r.json(content_type=None)

    if not isinstance(bin_json, dict):
        raise ValueError("Invalid BIN response")
    return bin_json


def _format_handyapi_bin(card_bin: str, bin_json: dict[str, Any]) -> str:
    msg_out = [_t("label.bin", value=card_bin)]
    _append_label(msg_out, "label.scheme", bin_json.get("Scheme"))
    _append_label(msg_out, "label.card_type", bin_json.get("Type"))
    _append_label(msg_out, "label.brand", bin_json.get("CardTier"))
    _append_label(msg_out, "label.bank_name", bin_json.get("Issuer"))

    country = bin_json.get("Country") or {}
    if isinstance(country, dict):
        _append_label(msg_out, "label.country_name", country.get("Name"))

    luhn = bin_json.get("Luhn")
    if isinstance(luhn, bool):
        msg_out.append(_t("label.luhn_yes") if luhn else _t("label.luhn_no"))

    return "\n".join(msg_out)


def _format_binlist_bin(card_bin: str, bin_json: dict[str, Any]) -> str:
    msg_out = [_t("label.bin", value=card_bin)]
    _append_label(msg_out, "label.scheme", bin_json.get("scheme"))
    _append_label(msg_out, "label.card_type", bin_json.get("type"))
    _append_label(msg_out, "label.brand", bin_json.get("brand"))

    bank = bin_json.get("bank") or {}
    if isinstance(bank, dict):
        _append_label(msg_out, "label.bank_name", bank.get("name"))

    prepaid = bin_json.get("prepaid")
    if isinstance(prepaid, bool):
        msg_out.append(_t("label.prepaid_yes") if prepaid else _t("label.prepaid_no"))

    country = bin_json.get("country") or {}
    if isinstance(country, dict):
        _append_label(msg_out, "label.country_name", country.get("name"))

    return "\n".join(msg_out)


async def query_bin_text(card_bin: str) -> str:
    """查询 BIN"""
    if not card_bin.isdigit() or not (4 <= len(card_bin) <= 8):
        return _t("error.invalid_bin_parameter")

    try:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            handyapi_key = _get_handyapi_api_key()
            if handyapi_key:
                try:
                    bin_json = await _query_handyapi_bin(
                        session, card_bin, handyapi_key
                    )
                    return _format_handyapi_bin(card_bin, bin_json)
                except (aiohttp.ClientError, BinNotFoundError) as e:
                    logger.warning(f"HandyAPI BIN lookup failed, fallback: {e}")
                except (BinRateLimitError, BinRequestError, ValueError) as e:
                    logger.warning(f"HandyAPI BIN lookup failed, fallback: {e}")

            bin_json = await _query_binlist_bin(session, card_bin)
            return _format_binlist_bin(card_bin, bin_json)
    except BinNotFoundError:
        return _t("error.bin_not_found")
    except BinRateLimitError:
        return _t("error.rate_limit_exceeded")
    except BinRequestError as e:
        return _t("error.request_failed_with_status", status=e.status)
    except aiohttp.ClientError:
        return _t("error.binlist_unreachable")
    except ValueError:
        return _t("error.invalid_parameter")
    except Exception as e:
        return _t("error.exception_occurred", reason=str(e))


async def handle_bin_command(bot, message: types.Message):
    """
    处理 BIN 查询命令
    :param bot: Bot 对象
    :param message: 消息对象
    :return:
    """
    command_args = message.text.split()
    if len(command_args) != 2:
        await bot.reply_to(message, _t("prompt.valid_bin_required"))
        return

    card_bin = command_args[1]
    if not card_bin.isdigit() or not (4 <= len(card_bin) <= 8):
        await bot.reply_to(message, _t("error.invalid_bin_parameter"))
        return

    msg = await bot.reply_to(
        message,
        _t("status.querying_bin", card_bin=card_bin),
    )

    result_text = await query_bin_text(card_bin)
    await bot.edit_message_text(result_text, message.chat.id, msg.message_id)


async def handle_bin_inline_query(bot, inline_query: types.InlineQuery):
    """处理 Inline Query：@Bot bin [Card_BIN]"""
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
    result_text = await query_bin_text(card_bin)

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
        guest_supported=True,
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
