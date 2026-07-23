import asyncio
import os
from types import SimpleNamespace

os.environ.setdefault("TELEGRAM_BOT_ID", "1")
os.environ.setdefault("TELEGRAM_BOT_USERNAME", "NachonekoBot")

from app.plugin_system import middleware as middleware_module
from app.plugin_system.middleware import PluginMiddleware
from setting.telegrambot import BotSetting


def _make_group_message(text: str):
    return SimpleNamespace(
        text=text,
        chat=SimpleNamespace(id=-100123, type="supergroup"),
    )


def test_extract_command_name_keeps_foreign_bot_commands(monkeypatch):
    monkeypatch.setattr(BotSetting, "bot_username", "NachonekoBot")

    assert PluginMiddleware._extract_command("/ping@OtherBot arg") is None
    assert PluginMiddleware._extract_command_name("/ping@OtherBot arg") == "ping"


def test_foreign_bot_command_only_runs_wildcard_guard(monkeypatch):
    monkeypatch.setattr(BotSetting, "bot_username", "NachonekoBot")

    async def get_language(message):
        return "en"

    monkeypatch.setattr(middleware_module, "get_message_language", get_language)
    monkeypatch.setattr(
        middleware_module, "make_localized_bot", lambda bot, plugin, lang: bot
    )

    calls = []
    middleware = PluginMiddleware()

    async def wildcard_guard(bot, message):
        calls.append("guard")
        return True

    async def ping_handler(bot, message):
        calls.append("ping")

    middleware.register_command_handler(
        commands=["*"],
        callback=wildcard_guard,
        plugin_name="lock",
        priority=100,
        chat_types=["group", "supergroup"],
    )
    middleware.register_command_handler(
        commands=["ping"],
        callback=ping_handler,
        plugin_name="ping",
        chat_types=["group", "supergroup"],
    )

    executed = asyncio.run(
        middleware.dispatch_command(
            object(), _make_group_message("/ping@OtherBot example")
        )
    )

    assert executed == 0
    assert calls == ["guard"]
