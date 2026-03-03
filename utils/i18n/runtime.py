# -*- coding: utf-8 -*-

from utils.i18n.service import plugin_t, t as framework_t, normalize_language


class LocalizedBot:
    """
    携带 i18n 上下文的 bot 包装器。

    不做任何隐式翻译 — 所有翻译必须通过 t() / ft() 显式调用。
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


def make_localized_bot(bot, plugin_name: str, lang: str) -> LocalizedBot:
    """为 handler 调度创建 LocalizedBot 实例"""
    return LocalizedBot(bot, plugin_name, lang)


async def make_localized_bot_for_chat(
    bot, plugin_name: str, chat_id: int
) -> LocalizedBot:
    """
    为定时任务等非 handler 场景创建 LocalizedBot。

    自动从数据库查询 chat 的语言偏好。
    """
    from utils.postgres import BotDatabase

    lang = normalize_language(await BotDatabase.get_group_language(chat_id))
    return LocalizedBot(bot, plugin_name, lang)
