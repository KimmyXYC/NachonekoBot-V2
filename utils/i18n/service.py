# -*- coding: utf-8 -*-

import json
from pathlib import Path
from typing import Dict, Optional

from loguru import logger

from utils.i18n.config import DEFAULT_LANGUAGE, LANGUAGE_FLAGS, SUPPORTED_LANGUAGES


_BASE_DIR = Path(__file__).resolve().parent
_PLUGIN_CACHE: Dict[str, Dict[str, str]] = {}
_FRAMEWORK_CACHE: Dict[str, Dict[str, str]] = {}


def normalize_language(lang: Optional[str]) -> str:
    if not lang:
        return DEFAULT_LANGUAGE
    lang = str(lang).strip()
    if lang in SUPPORTED_LANGUAGES:
        return lang
    return DEFAULT_LANGUAGE


def language_name(lang: str) -> str:
    return SUPPORTED_LANGUAGES.get(
        normalize_language(lang), SUPPORTED_LANGUAGES[DEFAULT_LANGUAGE]
    )


def supported_languages() -> Dict[str, str]:
    return dict(SUPPORTED_LANGUAGES)


def language_button_label(lang: str) -> str:
    code = normalize_language(lang)
    flag = LANGUAGE_FLAGS.get(code, "🌐")
    return f"{flag} {language_name(code)}"


def t(key: str, lang: Optional[str] = None, **kwargs) -> str:
    resolved = normalize_language(lang)
    framework_map = _load_framework_locale(resolved)
    value = framework_map.get(key)
    if value is None:
        value = _load_framework_locale(DEFAULT_LANGUAGE).get(key)
    if value is None:
        logger.warning(f"i18n: Missing framework key '{key}' for lang '{resolved}'")
        value = key
    if kwargs:
        try:
            return value.format(**kwargs)
        except Exception:
            return value
    return value


def _load_framework_locale(lang: str) -> Dict[str, str]:
    if lang in _FRAMEWORK_CACHE:
        return _FRAMEWORK_CACHE[lang]

    locale_path = _BASE_DIR / lang / "framework.json"
    if not locale_path.exists():
        _FRAMEWORK_CACHE[lang] = {}
        return _FRAMEWORK_CACHE[lang]

    try:
        data = json.loads(locale_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            normalized = {str(k): str(v) for k, v in data.items()}
        else:
            normalized = {}
        _FRAMEWORK_CACHE[lang] = normalized
        return normalized
    except Exception:
        _FRAMEWORK_CACHE[lang] = {}
        return _FRAMEWORK_CACHE[lang]


async def get_message_language(message) -> str:
    from utils.postgres import BotDatabase

    if not message or not getattr(message, "chat", None):
        return DEFAULT_LANGUAGE

    chat = message.chat
    if chat.type == "private":
        user_id = getattr(getattr(message, "from_user", None), "id", None)
        if not user_id:
            return DEFAULT_LANGUAGE
        return normalize_language(await BotDatabase.get_user_language(user_id))

    return normalize_language(await BotDatabase.get_group_language(chat.id))


async def get_callback_language(call) -> str:
    from utils.postgres import BotDatabase

    if not call or not getattr(call, "message", None):
        return DEFAULT_LANGUAGE

    chat = call.message.chat
    if chat.type == "private":
        user_id = getattr(getattr(call, "from_user", None), "id", None)
        if not user_id:
            return DEFAULT_LANGUAGE
        return normalize_language(await BotDatabase.get_user_language(user_id))

    return normalize_language(await BotDatabase.get_group_language(chat.id))


async def get_inline_query_language(inline_query) -> str:
    from utils.postgres import BotDatabase

    user_id = getattr(getattr(inline_query, "from_user", None), "id", None)
    if not user_id:
        return DEFAULT_LANGUAGE
    return normalize_language(await BotDatabase.get_user_language(user_id))


def _load_plugin_locale(lang: str, plugin_name: str) -> Dict[str, str]:
    cache_key = f"{lang}:{plugin_name}"
    if cache_key in _PLUGIN_CACHE:
        return _PLUGIN_CACHE[cache_key]

    locale_path = _BASE_DIR / lang / "plugins" / f"{plugin_name}.json"
    if not locale_path.exists():
        _PLUGIN_CACHE[cache_key] = {}
        return _PLUGIN_CACHE[cache_key]

    try:
        data = json.loads(locale_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            normalized = {str(k): str(v) for k, v in data.items()}
        else:
            normalized = {}
        _PLUGIN_CACHE[cache_key] = normalized
        return normalized
    except Exception:
        _PLUGIN_CACHE[cache_key] = {}
        return _PLUGIN_CACHE[cache_key]


def plugin_t(plugin_name: str, key: str, lang: Optional[str] = None, **kwargs) -> str:
    resolved = normalize_language(lang)
    mapping = _load_plugin_locale(resolved, plugin_name)
    value = mapping.get(key)

    if value is None and resolved != DEFAULT_LANGUAGE:
        mapping = _load_plugin_locale(DEFAULT_LANGUAGE, plugin_name)
        value = mapping.get(key)

    if value is None:
        logger.warning(
            f"i18n: Missing plugin key '{key}' for plugin '{plugin_name}' in lang '{resolved}'"
        )
        value = key

    if kwargs:
        try:
            return value.format(**kwargs)
        except Exception:
            return value
    return value
