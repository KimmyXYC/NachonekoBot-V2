# -*- coding: utf-8 -*-
# @Time    : 2025/6/22 17:27
# @Author  : KimmyXYC
# @File    : event.py
# @Software: PyCharm
import re
from loguru import logger
from telebot import types, formatting
from utils.i18n import t

# Telegram bot command: 1-32 lowercase letters, digits, underscores
_VALID_BOT_COMMAND_RE = re.compile(r"^[a-z0-9_]{1,32}$")

# 我们的 i18n 语言代码 → Telegram language_code (ISO 639-1) 映射
# en 作为默认（不带 language_code），不在此映射中
# zh-TW 与 zh-CN 共用 "zh"（Telegram 不支持区分简繁），优先使用 zh-CN
_LANG_TO_TELEGRAM = {
    "zh-CN": "zh",
    "ja": "ja",
}


CATEGORY_KEYS = {
    "network": "category.title.network",
    "query": "category.title.query",
    "tool": "category.title.tool",
    "admin": "category.title.admin",
    "fun": "category.title.fun",
    "utility": "category.title.utility",
    "misc": "category.title.misc",
}


async def set_bot_commands(bot, plugin_manager):
    """
    动态构建并设置机器人命令。
    默认（无 language_code）使用 en，
    然后为 _LANG_TO_TELEGRAM 中的每种语言额外注册本地化的命令描述。
    """

    async def _register_commands_for_lang(lang: str, language_code: str = None):
        """为指定语言构建命令列表并注册到 Telegram (3 个 scope)。"""
        all_cmds = [
            types.BotCommand("help", t("core.command.help", lang)),
            types.BotCommand("plugin", t("core.command.plugin", lang)),
            types.BotCommand(
                "plugin_settings", t("core.command.plugin_settings", lang)
            ),
            types.BotCommand("language", t("core.command.language", lang)),
        ]
        private_cmds = [
            types.BotCommand("help", t("core.command.help", lang)),
            types.BotCommand("plugin", t("core.command.plugin", lang)),
            types.BotCommand("language", t("core.command.language", lang)),
        ]
        group_cmds = [
            types.BotCommand("help", t("core.command.help", lang)),
            types.BotCommand("plugin", t("core.command.plugin", lang)),
            types.BotCommand(
                "plugin_settings", t("core.command.plugin_settings", lang)
            ),
            types.BotCommand("language", t("core.command.language", lang)),
        ]

        plugin_commands_info = plugin_manager.get_plugin_commands_info(lang)
        for cmd_info in plugin_commands_info:
            if cmd_info["description"] and _VALID_BOT_COMMAND_RE.match(
                cmd_info["command"]
            ):
                bot_cmd = types.BotCommand(cmd_info["command"], cmd_info["description"])
                all_cmds.append(bot_cmd)
                private_cmds.append(bot_cmd)
                group_cmds.append(bot_cmd)

        await bot.set_my_commands(
            all_cmds,
            scope=types.BotCommandScopeDefault(),
            language_code=language_code,
        )
        await bot.set_my_commands(
            private_cmds,
            scope=types.BotCommandScopeAllPrivateChats(),
            language_code=language_code,
        )
        await bot.set_my_commands(
            group_cmds,
            scope=types.BotCommandScopeAllGroupChats(),
            language_code=language_code,
        )

    # 默认（en）— 不带 language_code，作为 fallback
    await _register_commands_for_lang("en")

    # 为每种支持的语言额外注册
    for our_lang, tg_lang_code in _LANG_TO_TELEGRAM.items():
        try:
            await _register_commands_for_lang(our_lang, tg_lang_code)
        except Exception as e:
            logger.warning(
                f"Failed to set bot commands for language {our_lang} "
                f"(telegram code: {tg_lang_code}): {e}"
            )


async def listen_help_command(bot, message: types.Message, plugin_manager, lang: str):
    """
    动态构建并显示帮助信息
    从插件管理器收集所有插件的帮助文本
    """
    # 构建帮助文本列表
    help_lines = [formatting.mbold(t("help.title", lang))]

    # 核心命令帮助
    help_lines.append(formatting.mcite(t("help.line.help", lang)))
    help_lines.append(formatting.mcite(""))  # 添加空行分隔
    help_lines.append(formatting.mcite(t("help.line.plugin", lang)))
    help_lines.append(formatting.mcite(t("help.line.language", lang)))
    help_lines.append(formatting.mcite(""))  # 添加空行分隔

    # 从插件收集帮助信息
    plugin_commands_info = plugin_manager.get_plugin_commands_info(lang)

    # 按类别分组添加插件命令帮助
    last_category = None
    for cmd_info in plugin_commands_info:
        if not cmd_info["help_text"]:
            continue

        category = cmd_info.get("category", "misc")
        if category != last_category:
            title_key = CATEGORY_KEYS.get(category, f"category.title.{category}")
            title = t(title_key, lang)
            if title == title_key:
                title = category.title()
            help_lines.append(formatting.mitalic(f"{title}:"))
            last_category = category

        help_lines.append(formatting.mcite(cmd_info["help_text"]))
        help_lines.append(formatting.mcite(""))  # 添加空行分隔

    # 添加 GitHub 链接
    help_lines.append("")
    help_lines.append(
        formatting.mlink(
            t("help.github", lang), "https://github.com/KimmyXYC/NachonekoBot-V2"
        )
    )

    _message = await bot.reply_to(
        message=message,
        text=formatting.format_text(*help_lines),
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )
