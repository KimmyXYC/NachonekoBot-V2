# -*- coding: utf-8 -*-
# @Time    : 2025/7/1 21:59
# @Author  : KimmyXYC
# @File    : bin.py
# @Software: PyCharm
import os
from collections import OrderedDict
from time import monotonic
from typing import Any

import aiohttp
from telebot import types
from telebot.asyncio_helper import ApiTelegramException
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

MASTERCARD_BIN_URL = "https://btr-reference-app.herokuapp.com/bins"
HANDYAPI_BIN_URL = "https://data.handyapi.com/bin/{card_bin}"
BINLIST_BIN_URL = "https://lookup.binlist.net/{card_bin}"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)
BIN_SOURCES = {
    "mastercard": "Mastercard",
    "handyapi": "HandyAPI",
    "binlist": "binlist",
}
BIN_CACHE_TTL = 24 * 60 * 60
BIN_CACHE_MAX_ENTRIES = 4096
# 仅缓存成功响应的原始数据；不缓存语言相关文本或错误。
_bin_cache: OrderedDict[tuple[str, str], tuple[float, dict[str, Any]]] = OrderedDict()


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


def _is_mastercard_bin(card_bin: str) -> bool:
    return (
        4 <= len(card_bin) <= 8
        and card_bin.isascii()
        and card_bin.isdigit()
        and ("51" <= card_bin[:2] <= "55" or "2221" <= card_bin[:4] <= "2720")
    )


def _available_sources(card_bin: str) -> list[str]:
    return [
        source
        for source in BIN_SOURCES
        if (source != "mastercard" or _is_mastercard_bin(card_bin))
        and (source != "handyapi" or _get_handyapi_api_key())
    ]


def _get_cached_bin(source: str, card_bin: str) -> dict[str, Any] | None:
    key = (source, card_bin)
    cached = _bin_cache.get(key)
    if cached is None:
        return None
    expires_at, data = cached
    if monotonic() >= expires_at:
        del _bin_cache[key]
        return None
    return data


def _cache_bin(source: str, card_bin: str, data: dict[str, Any]) -> None:
    now = monotonic()
    _bin_cache.pop((source, card_bin), None)
    # 按写入时间排列，清理过期项并限制内存占用。
    while _bin_cache:
        expires_at, _ = next(iter(_bin_cache.values()))
        if expires_at > now and len(_bin_cache) < BIN_CACHE_MAX_ENTRIES:
            break
        _bin_cache.popitem(last=False)
    _bin_cache[(source, card_bin)] = (now + BIN_CACHE_TTL, data)


async def _query_mastercard_bin(
    session: aiohttp.ClientSession, card_bin: str
) -> dict[str, Any]:
    async with session.post(MASTERCARD_BIN_URL, json={"bin": card_bin}) as r:
        if r.status == 404:
            raise BinNotFoundError
        if r.status == 429:
            raise BinRateLimitError
        if r.status != 200:
            raise BinRequestError(r.status)

        bin_json = await r.json(content_type=None)

    if bin_json == {}:
        raise BinNotFoundError
    if not isinstance(bin_json, dict):
        raise ValueError("Invalid Mastercard BIN response")
    bin_num = bin_json.get("binNum")
    if (
        not isinstance(bin_num, str)
        or not bin_num.isascii()
        or not bin_num.isdigit()
        or not (4 <= len(bin_num) <= 8)
    ):
        raise ValueError("Invalid Mastercard BIN number")
    return bin_json


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
    if not bin_json:
        raise BinNotFoundError
    return bin_json


def _format_mastercard_bin(card_bin: str, bin_json: dict[str, Any]) -> str:
    msg_out = [_t("label.bin", value=card_bin)]
    scheme = bin_json.get("acceptanceBrand")
    _append_label(msg_out, "label.scheme", "Mastercard" if scheme == "DMC" else scheme)
    _append_label(msg_out, "label.card_type", bin_json.get("fundingSource"))
    _append_label(msg_out, "label.brand", bin_json.get("productDescription"))
    _append_label(msg_out, "label.bank_name", bin_json.get("customerName"))

    country = bin_json.get("country") or {}
    if isinstance(country, dict):
        _append_label(msg_out, "label.country_name", country.get("name"))

    return "\n".join(msg_out)


def _format_handyapi_bin(card_bin: str, bin_json: dict[str, Any]) -> str:
    msg_out = [_t("label.bin", value=card_bin)]
    _append_label(msg_out, "label.scheme", bin_json.get("Scheme"))
    _append_label(msg_out, "label.card_type", bin_json.get("Type"))
    _append_label(msg_out, "label.brand", bin_json.get("CardTier"))
    _append_label(msg_out, "label.bank_name", bin_json.get("Issuer"))

    country = bin_json.get("Country") or {}
    if isinstance(country, dict):
        _append_label(msg_out, "label.country_name", country.get("Name"))

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


def _build_source_keyboard(
    card_bin: str, selected_source: str | None = None
) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    keyboard.row(
        *[
            types.InlineKeyboardButton(
                text=f"✓ {BIN_SOURCES[source]}"
                if source == selected_source
                else BIN_SOURCES[source],
                callback_data=f"bin_source:{source}:{card_bin}",
            )
            for source in _available_sources(card_bin)
        ]
    )
    return keyboard


async def _query_bin_result(
    card_bin: str, source: str | None = None
) -> tuple[str, str | None]:
    """返回查询文本及实际成功的来源；指定来源时不自动回退。"""
    if not card_bin.isdigit() or not (4 <= len(card_bin) <= 8):
        return _t("error.invalid_bin_parameter"), None
    if source is not None and source not in BIN_SOURCES:
        return _t("error.invalid_parameter"), None
    if source == "handyapi" and not _get_handyapi_api_key():
        return _t("error.handyapi_key_missing"), None

    if source == "mastercard" and not _is_mastercard_bin(card_bin):
        return _t("error.invalid_parameter"), None

    sources = [source] if source else _available_sources(card_bin)
    formatters = {
        "mastercard": _format_mastercard_bin,
        "handyapi": _format_handyapi_bin,
        "binlist": _format_binlist_bin,
    }
    try:
        # 自动查询优先复用已有成功结果，避免再次请求此前失败的来源。
        for candidate in sources:
            cached = _get_cached_bin(candidate, card_bin)
            if cached is not None:
                return formatters[candidate](card_bin, cached), candidate

        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            for candidate in sources:
                try:
                    if candidate == "mastercard":
                        bin_json = await _query_mastercard_bin(session, card_bin)
                    elif candidate == "handyapi":
                        bin_json = await _query_handyapi_bin(
                            session, card_bin, _get_handyapi_api_key()
                        )
                    else:
                        bin_json = await _query_binlist_bin(session, card_bin)
                    result_text = formatters[candidate](card_bin, bin_json)
                    _cache_bin(candidate, card_bin, bin_json)
                    return result_text, candidate
                except (
                    aiohttp.ClientError,
                    TimeoutError,
                    BinNotFoundError,
                    BinRateLimitError,
                    BinRequestError,
                    ValueError,
                ) as e:
                    if candidate == sources[-1]:
                        raise
                    logger.warning(
                        f"{BIN_SOURCES[candidate]} BIN lookup failed, fallback: {e}"
                    )
    except BinNotFoundError:
        return _t("error.bin_not_found"), None
    except BinRateLimitError:
        return _t("error.rate_limit_exceeded"), None
    except BinRequestError as e:
        return _t("error.request_failed_with_status", status=e.status), None
    except (aiohttp.ClientError, TimeoutError):
        if source is not None:
            return _t("error.source_unreachable", source=BIN_SOURCES[source]), None
        return _t("error.binlist_unreachable"), None
    except ValueError:
        return _t("error.invalid_parameter"), None
    except Exception as e:
        return _t("error.exception_occurred", reason=str(e)), None


async def query_bin_text(card_bin: str, source: str | None = None) -> str:
    """查询 BIN 文本，保留现有调用接口。"""
    text, _ = await _query_bin_result(card_bin, source)
    return text


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

    result_text, selected_source = await _query_bin_result(card_bin)
    await bot.edit_message_text(
        result_text,
        message.chat.id,
        msg.message_id,
        reply_markup=_build_source_keyboard(card_bin, selected_source),
    )


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
    result_text, selected_source = await _query_bin_result(card_bin)

    result = types.InlineQueryResultArticle(
        id=f"bin_{card_bin}",
        title=_t("inline.result_title", card_bin=card_bin),
        description=_t("inline.send_result_description"),
        input_message_content=types.InputTextMessageContent(result_text),
        reply_markup=(
            _build_source_keyboard(card_bin, selected_source)
            if card_bin.isdigit() and 4 <= len(card_bin) <= 8
            else None
        ),
    )
    await bot.answer_inline_query(
        inline_query.id, [result], cache_time=1, is_personal=True
    )


async def handle_bin_source_callback(bot, call: types.CallbackQuery):
    """切换普通消息或 Inline 消息的 BIN 查询来源。"""
    parts = (call.data or "").split(":")
    if (
        len(parts) != 3
        or parts[0] != "bin_source"
        or parts[1] not in BIN_SOURCES
        or not parts[2].isdigit()
        or not (4 <= len(parts[2]) <= 8)
    ):
        await bot.answer_callback_query(call.id, _t("error.invalid_parameter"))
        return

    inline_message_id = getattr(call, "inline_message_id", None)
    message = getattr(call, "message", None)
    if inline_message_id:
        target = {"inline_message_id": inline_message_id}
    elif message:
        target = {"chat_id": message.chat.id, "message_id": message.message_id}
    else:
        await bot.answer_callback_query(call.id, _t("error.invalid_parameter"))
        return

    _, source, card_bin = parts
    # 先应答回调，避免网络查询期间 Telegram 一直显示加载状态。
    await bot.answer_callback_query(call.id)
    result_text = await query_bin_text(card_bin, source=source)
    try:
        await bot.edit_message_text(
            result_text,
            **target,
            reply_markup=_build_source_keyboard(card_bin, source),
        )
    except ApiTelegramException as e:
        # 重复点击且结果未变化时，Telegram 会拒绝相同内容的编辑。
        if e.error_code != 400 or "message is not modified" not in e.description:
            raise


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

    middleware.register_callback_handler(
        callback=handle_bin_source_callback,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        data_startswith="bin_source:",
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
