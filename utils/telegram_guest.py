"""pyTelegramBotAPI Guest Mode helpers.

Guest Mode replies are sent via ``answer_guest_query`` with an
``InlineQueryResult`` instead of normal ``sendMessage``/``reply_to`` calls.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import aiohttp
from telebot import types


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


async def upload_image_to_telegraph(photo: Any, filename: str = "image.png") -> str:
    """Upload an in-memory image to Telegraph and return a public HTTPS URL."""
    seek = getattr(photo, "seek", None)
    if seek is not None:
        seek(0)

    if hasattr(photo, "read"):
        data = photo.read()
    elif isinstance(photo, bytes):
        data = photo
    else:
        raise TypeError("Guest Mode photo must be bytes or a file-like object")

    form = aiohttp.FormData()
    form.add_field(
        "file",
        data,
        filename=getattr(photo, "name", filename) or filename,
        content_type="image/png",
    )
    async with aiohttp.ClientSession() as session:
        async with session.post("https://telegra.ph/upload", data=form, timeout=30) as resp:
            payload = await resp.json(content_type=None)
            if resp.status != 200:
                raise RuntimeError(f"Telegraph upload failed: HTTP {resp.status} {payload}")

    if not isinstance(payload, list) or not payload or "src" not in payload[0]:
        raise RuntimeError(f"Telegraph upload returned unexpected payload: {payload}")

    return f"https://telegra.ph{payload[0]['src']}"


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

    photo_url = await upload_image_to_telegraph(photo)
    result = types.InlineQueryResultPhoto(
        id=f"guest_photo_{uuid.uuid4().hex}",
        photo_url=photo_url,
        thumbnail_url=photo_url,
        title=title,
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
