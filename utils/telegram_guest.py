"""pyTelegramBotAPI Guest Mode helpers.

Guest Mode replies are sent via ``answer_guest_query`` with an
``InlineQueryResult`` instead of normal ``sendMessage``/``reply_to`` calls.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

from telebot import types
from utils.yaml import BotConfig


MAX_GUEST_TEXT_LENGTH = 4096


def is_guest_message(message: Any) -> bool:
    return bool(getattr(message, "guest_query_id", None))


def truncate_guest_text(text: Any) -> str:
    text = str(text)
    if len(text) <= MAX_GUEST_TEXT_LENGTH:
        return text
    suffix = "\n\n…(Guest Mode 仅显示前 4096 字符)"
    return text[: MAX_GUEST_TEXT_LENGTH - len(suffix)] + suffix


def build_guest_text_result(
    text: Any,
    *,
    title: str = "Result",
    parse_mode: str | None = None,
    disable_web_page_preview: bool | None = None,
) -> types.InlineQueryResultArticle:
    kwargs: dict[str, Any] = {}
    if parse_mode:
        kwargs["parse_mode"] = parse_mode
    if disable_web_page_preview is not None:
        kwargs["disable_web_page_preview"] = disable_web_page_preview

    content = types.InputTextMessageContent(truncate_guest_text(text), **kwargs)
    return types.InlineQueryResultArticle(
        id=f"guest_{uuid.uuid4().hex}",
        title=title,
        input_message_content=content,
    )


async def answer_guest_text(
    bot: Any,
    message: Any,
    text: Any,
    *,
    title: str = "Result",
    parse_mode: str | None = None,
    disable_web_page_preview: bool | None = None,
) -> Any:
    guest_query_id = getattr(message, "guest_query_id", None)
    if not guest_query_id:
        raise ValueError("message.guest_query_id is required for Guest Mode replies")

    result = build_guest_text_result(
        text,
        title=title,
        parse_mode=parse_mode,
        disable_web_page_preview=disable_web_page_preview,
    )
    return await bot.answer_guest_query(guest_query_id, result)


def get_guest_media_cache_chat_id() -> int | str:
    guest_config = BotConfig.get("guest", {}) or {}
    chat_id = (
        guest_config.get("media_cache_chat_id")
        or guest_config.get("media_cache_channel_id")
        or guest_config.get("channel_id")
    )
    if not chat_id:
        raise RuntimeError(
            "Guest Mode 媒体缓存频道未配置，请在 conf_dir/config.yaml 中设置 "
            "guest.media_cache_chat_id"
        )
    return chat_id


def rewind_uploadable(uploadable: Any) -> None:
    seek = getattr(uploadable, "seek", None)
    if seek is not None:
        seek(0)


def get_uploadable_name(uploadable: Any, fallback: str) -> str:
    return getattr(uploadable, "name", None) or fallback


async def upload_photo_to_cache_chat(bot: Any, photo: Any) -> str:
    """Upload a local/generated photo to cache chat and return Telegram file_id."""
    seek = getattr(photo, "seek", None)
    if seek is not None:
        seek(0)

    cache_message = await bot.send_photo(
        get_guest_media_cache_chat_id(),
        photo,
        disable_notification=True,
    )
    photos = getattr(cache_message, "photo", None) or []
    if not photos:
        raise RuntimeError("上传 Guest Mode 图片到缓存频道后未获得 photo file_id")
    return photos[-1].file_id


async def upload_document_to_cache_chat(bot: Any, document: Any) -> str:
    """Upload a local/generated file to cache chat and return Telegram file_id."""
    rewind_uploadable(document)
    cache_message = await bot.send_document(
        get_guest_media_cache_chat_id(),
        document,
        disable_notification=True,
    )
    cached_document = getattr(cache_message, "document", None)
    file_id = getattr(cached_document, "file_id", None)
    if not file_id:
        raise RuntimeError("上传 Guest Mode 文件到缓存频道后未获得 document file_id")
    return file_id


async def answer_guest_photo(
    bot: Any,
    message: Any,
    photo: Any,
    *,
    title: str = "Image",
    caption: str | None = None,
    parse_mode: str | None = None,
) -> Any:
    guest_query_id = getattr(message, "guest_query_id", None)
    if not guest_query_id:
        raise ValueError("message.guest_query_id is required for Guest Mode replies")

    photo_file_id = await upload_photo_to_cache_chat(bot, photo)
    result = types.InlineQueryResultCachedPhoto(
        id=f"guest_photo_{uuid.uuid4().hex}",
        photo_file_id=photo_file_id,
        title=title,
        caption=caption,
        parse_mode=parse_mode,
    )
    return await bot.answer_guest_query(guest_query_id, result)


async def answer_guest_document(
    bot: Any,
    message: Any,
    document: Any,
    *,
    title: str | None = None,
    caption: str | None = None,
    parse_mode: str | None = None,
) -> Any:
    guest_query_id = getattr(message, "guest_query_id", None)
    if not guest_query_id:
        raise ValueError("message.guest_query_id is required for Guest Mode replies")

    document_file_id = await upload_document_to_cache_chat(bot, document)
    result = types.InlineQueryResultCachedDocument(
        id=f"guest_document_{uuid.uuid4().hex}",
        document_file_id=document_file_id,
        title=title or get_uploadable_name(document, "file"),
        caption=caption,
        parse_mode=parse_mode,
    )
    return await bot.answer_guest_query(guest_query_id, result)


def make_guest_message_like(chat_id: Any, message_id: int, inline_message_id: str | None):
    return SimpleNamespace(
        message_id=message_id,
        chat=SimpleNamespace(id=chat_id),
        inline_message_id=inline_message_id,
    )
