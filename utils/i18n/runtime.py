# -*- coding: utf-8 -*-

from utils.i18n.service import plugin_t


class LocalizedBotProxy:
    def __init__(self, bot, plugin_name: str, lang: str):
        self._bot = bot
        self._plugin_name = plugin_name
        self._lang = lang

    def _translate(self, text):
        if not isinstance(text, str):
            return text
        return plugin_t(self._plugin_name, text, self._lang)

    def t(self, key: str, **kwargs):
        return plugin_t(self._plugin_name, key, self._lang, **kwargs)

    async def reply_to(self, message, text=None, *args, **kwargs):
        if text is not None:
            text = self._translate(text)
        elif "text" in kwargs:
            kwargs["text"] = self._translate(kwargs.get("text"))
        return await self._bot.reply_to(message, text, *args, **kwargs)

    async def send_message(self, chat_id, text=None, *args, **kwargs):
        if text is not None:
            text = self._translate(text)
        elif "text" in kwargs:
            kwargs["text"] = self._translate(kwargs.get("text"))
        return await self._bot.send_message(chat_id, text, *args, **kwargs)

    async def edit_message_text(self, text=None, *args, **kwargs):
        if text is not None:
            text = self._translate(text)
        elif "text" in kwargs:
            kwargs["text"] = self._translate(kwargs.get("text"))
        return await self._bot.edit_message_text(text, *args, **kwargs)

    async def answer_callback_query(
        self, callback_query_id, text=None, *args, **kwargs
    ):
        if text is not None:
            text = self._translate(text)
        elif "text" in kwargs:
            kwargs["text"] = self._translate(kwargs.get("text"))
        return await self._bot.answer_callback_query(
            callback_query_id, text, *args, **kwargs
        )

    async def send_photo(self, chat_id, photo, *args, **kwargs):
        if "caption" in kwargs:
            kwargs["caption"] = self._translate(kwargs.get("caption"))
        return await self._bot.send_photo(chat_id, photo, *args, **kwargs)

    async def send_document(self, chat_id, document, *args, **kwargs):
        if "caption" in kwargs:
            kwargs["caption"] = self._translate(kwargs.get("caption"))
        return await self._bot.send_document(chat_id, document, *args, **kwargs)

    async def send_video(self, chat_id, data, *args, **kwargs):
        if "caption" in kwargs:
            kwargs["caption"] = self._translate(kwargs.get("caption"))
        return await self._bot.send_video(chat_id, data, *args, **kwargs)

    async def send_animation(self, chat_id, animation, *args, **kwargs):
        if "caption" in kwargs:
            kwargs["caption"] = self._translate(kwargs.get("caption"))
        return await self._bot.send_animation(chat_id, animation, *args, **kwargs)

    def __getattr__(self, item):
        return getattr(self._bot, item)


def make_localized_bot(bot, plugin_name: str, lang: str):
    return LocalizedBotProxy(bot, plugin_name, lang)
