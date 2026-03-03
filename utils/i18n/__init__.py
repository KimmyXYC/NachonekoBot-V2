# -*- coding: utf-8 -*-

from utils.i18n.service import (
    get_callback_language,
    get_inline_query_language,
    get_message_language,
    language_button_label,
    language_name,
    normalize_language,
    plugin_t,
    supported_languages,
    t,
)
from utils.i18n.runtime import (
    LocalizedBot,
    make_localized_bot,
    make_localized_bot_for_chat,
)
from utils.i18n.context import (
    _t,
    _ft,
    _current_lang,
    _current_plugin,
)

__all__ = [
    "get_message_language",
    "get_callback_language",
    "get_inline_query_language",
    "language_button_label",
    "language_name",
    "normalize_language",
    "plugin_t",
    "supported_languages",
    "t",
    "LocalizedBot",
    "make_localized_bot",
    "make_localized_bot_for_chat",
    "_t",
    "_ft",
    "_current_lang",
    "_current_plugin",
]
