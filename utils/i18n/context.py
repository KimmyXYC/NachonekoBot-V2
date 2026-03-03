# -*- coding: utf-8 -*-
"""
基于 contextvars 的请求级 i18n 上下文。

中间件在 dispatch 时自动设置 ContextVar，
插件代码通过 `from utils.i18n import _t, _ft` 直接使用。
"""

import contextvars

from utils.i18n.service import plugin_t, t as framework_t

_current_lang: contextvars.ContextVar[str] = contextvars.ContextVar(
    "i18n_lang", default="en"
)
_current_plugin: contextvars.ContextVar[str] = contextvars.ContextVar(
    "i18n_plugin", default=""
)


def _t(key: str, **kwargs) -> str:
    """插件级翻译 — 从 ContextVar 读取当前插件名和语言"""
    return plugin_t(_current_plugin.get(), key, _current_lang.get(), **kwargs)


def _ft(key: str, **kwargs) -> str:
    """Framework 级翻译 — 从 ContextVar 读取当前语言"""
    return framework_t(key, _current_lang.get(), **kwargs)
