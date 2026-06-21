# -*- coding: utf-8 -*-

from utils.i18n.service import plugin_t, t as framework_t, normalize_language
from utils.telegram_guest import (
    answer_guest_photo,
    answer_guest_text,
    is_guest_message,
    make_guest_message_like,
    truncate_guest_text,
)


class LocalizedBot:
    """
    携带 i18n 上下文的 bot 包装器。

    不做任何隐式翻译 — 所有翻译必须通过 _t() / _ft() 或 bot.t() / bot.ft() 显式调用。
    bot 的所有方法（reply_to, send_message 等）直接透传到底层 bot 实例。
    """

    def __init__(self, bot, plugin_name: str, lang: str):
        self._bot = bot
        self.plugin_name = plugin_name
        self.lang = lang

    def t(self, key: str, **kwargs) -> str:
        """插件级别翻译 — 从 plugins/{plugin_name}.json 查找 key"""
        return plugin_t(self.plugin_name, key, self.lang, **kwargs)

    def ft(self, key: str, **kwargs) -> str:
        """Framework 级别翻译 — 从 framework.json 查找 key"""
        return framework_t(key, self.lang, **kwargs)

    def __getattr__(self, item):
        return getattr(self._bot, item)


class GuestLocalizedBot(LocalizedBot):
    """Guest Mode 专用 bot 包装器。

    pyTelegramBotAPI 的 Guest Mode 需要通过 ``answer_guest_query`` 回复。
    为了兼容现有插件中常见的 ``reply_to`` → ``edit_message_text`` 流程，
    这里把首次 ``reply_to`` 转换成 ``answer_guest_query``，并把后续针对
    返回 message-like 对象的 ``edit_message_text`` 转换成 inline message edit。
    """

    def __init__(self, bot, plugin_name: str, lang: str):
        super().__init__(bot, plugin_name, lang)
        self._answered = False
        self._inline_message_id: str | None = None
        self._last_text = ""
        self._fake_message_seq = 0
        self._message_map: dict[tuple[int, int], str] = {}

    async def reply_to(self, message, text, *args, **kwargs):
        if not is_guest_message(message):
            return await self._bot.reply_to(message, text, *args, **kwargs)

        return await self._answer_or_edit_guest(
            message,
            text,
            parse_mode=kwargs.get("parse_mode"),
            disable_web_page_preview=kwargs.get("disable_web_page_preview"),
            append=False,
        )

    async def send_message(self, chat_id, text, *args, **kwargs):
        guest_message = kwargs.pop("guest_message", None) or getattr(
            self, "_current_guest_message", None
        )
        if not guest_message or not is_guest_message(guest_message):
            return await self._bot.send_message(chat_id, text, *args, **kwargs)

        return await self._answer_or_edit_guest(
            guest_message,
            text,
            parse_mode=kwargs.get("parse_mode"),
            disable_web_page_preview=kwargs.get("disable_web_page_preview"),
            append=True,
        )

    async def send_photo(self, chat_id, photo, *args, **kwargs):
        guest_message = kwargs.pop("guest_message", None) or getattr(
            self, "_current_guest_message", None
        )
        if not guest_message or not is_guest_message(guest_message):
            return await self._bot.send_photo(chat_id, photo, *args, **kwargs)

        sent = await answer_guest_photo(
            self._bot,
            guest_message,
            photo,
            caption=kwargs.get("caption"),
            parse_mode=kwargs.get("parse_mode"),
        )
        self._answered = True
        self._inline_message_id = getattr(sent, "inline_message_id", None)
        self._fake_message_seq += 1
        return make_guest_message_like(
            int(getattr(guest_message.chat, "id", 0)),
            self._fake_message_seq,
            self._inline_message_id,
        )

    async def edit_message_text(self, *args, **kwargs):
        text = kwargs.pop("text", None)
        remaining_args = list(args)
        if text is None and remaining_args:
            text = remaining_args.pop(0)

        inline_message_id = kwargs.get("inline_message_id")
        chat_id = kwargs.get("chat_id")
        message_id = kwargs.get("message_id")

        if chat_id is None and remaining_args:
            chat_id = remaining_args.pop(0)
        if message_id is None and remaining_args:
            message_id = remaining_args.pop(0)

        if inline_message_id is None and chat_id is not None and message_id is not None:
            inline_message_id = self._message_map.get((int(chat_id), int(message_id)))

        if inline_message_id:
            kwargs.pop("chat_id", None)
            kwargs.pop("message_id", None)
            kwargs["inline_message_id"] = inline_message_id
            text = truncate_guest_text(text)
            self._last_text = text
            kwargs = {key: value for key, value in kwargs.items() if value is not None}
            return await self._bot.edit_message_text(text, *remaining_args, **kwargs)

        if chat_id is not None:
            kwargs["chat_id"] = chat_id
        if message_id is not None:
            kwargs["message_id"] = message_id
        return await self._bot.edit_message_text(text, *remaining_args, **kwargs)

    async def _answer_or_edit_guest(
        self,
        message,
        text,
        *,
        parse_mode: str | None = None,
        disable_web_page_preview: bool | None = None,
        append: bool = False,
    ):
        chat_id = int(getattr(message.chat, "id", 0))
        self._current_guest_message = message

        if self._answered and self._inline_message_id:
            next_text = str(text)
            if append and self._last_text:
                next_text = f"{self._last_text}\n\n{next_text}"
            next_text = truncate_guest_text(next_text)
            self._last_text = next_text
            edit_kwargs: dict[str, object] = {
                "inline_message_id": self._inline_message_id
            }
            if parse_mode is not None:
                edit_kwargs["parse_mode"] = parse_mode
            if disable_web_page_preview is not None:
                edit_kwargs["disable_web_page_preview"] = disable_web_page_preview
            await self._bot.edit_message_text(next_text, **edit_kwargs)
            return make_guest_message_like(
                chat_id, self._fake_message_seq, self._inline_message_id
            )

        sent = await answer_guest_text(
            self._bot,
            message,
            text,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )
        self._answered = True
        self._inline_message_id = getattr(sent, "inline_message_id", None)
        self._last_text = truncate_guest_text(text)
        self._fake_message_seq += 1
        fake_message_id = self._fake_message_seq
        if self._inline_message_id:
            self._message_map[(chat_id, fake_message_id)] = self._inline_message_id
        return make_guest_message_like(chat_id, fake_message_id, self._inline_message_id)


def make_localized_bot(bot, plugin_name: str, lang: str) -> LocalizedBot:
    """为 handler 调度创建 LocalizedBot 实例（同时设置 ContextVar）"""
    from utils.i18n.context import _current_lang, _current_plugin

    _current_lang.set(lang)
    _current_plugin.set(plugin_name)
    return LocalizedBot(bot, plugin_name, lang)


def make_guest_localized_bot(bot, plugin_name: str, lang: str) -> GuestLocalizedBot:
    """为 Guest Mode handler 创建 LocalizedBot 实例。"""
    from utils.i18n.context import _current_lang, _current_plugin

    _current_lang.set(lang)
    _current_plugin.set(plugin_name)
    return GuestLocalizedBot(bot, plugin_name, lang)


async def make_localized_bot_for_chat(
    bot, plugin_name: str, chat_id: int
) -> LocalizedBot:
    """
    为定时任务等非 handler 场景创建 LocalizedBot。

    自动从数据库查询 chat 的语言偏好，同时设置 ContextVar。
    """
    from utils.postgres import BotDatabase
    from utils.i18n.context import _current_lang, _current_plugin

    lang = normalize_language(await BotDatabase.get_group_language(chat_id))
    _current_lang.set(lang)
    _current_plugin.set(plugin_name)
    return LocalizedBot(bot, plugin_name, lang)
