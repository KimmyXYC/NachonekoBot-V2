"""pyTelegramBotAPI Guest Mode helpers.

Guest Mode replies are sent via ``answer_guest_query`` with an
``InlineQueryResult`` instead of normal ``sendMessage``/``reply_to`` calls.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

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


def make_guest_message_like(chat_id: Any, message_id: int, inline_message_id: str | None):
    return SimpleNamespace(
        message_id=message_id,
        chat=SimpleNamespace(id=chat_id),
        inline_message_id=inline_message_id,
    )
