# -*- coding: utf-8 -*-
# @Time    : 2025/6/22 17:27
# @Author  : KimmyXYC
# @File    : event.py
# @Software: PyCharm
from telebot import types, formatting
from utils.i18n import t


CATEGORY_TITLES = {
    "network": "Network",
    "query": "Query",
    "tool": "Tools",
    "admin": "Admin",
    "fun": "Fun",
    "utility": "Utility",
    "misc": "Misc",
}


async def set_bot_commands(bot, plugin_manager):
    """
    动态构建并设置机器人命令
    从插件管理器收集所有插件的命令信息
    """
    # 核心命令（不属于任何插件）
    commands = [
        types.BotCommand("help", t("core.command.help", "en")),
        types.BotCommand("plugin", t("core.command.plugin", "en")),
        types.BotCommand("plugin_settings", t("core.command.plugin_settings", "en")),
        types.BotCommand("language", t("core.command.language", "en")),
    ]
    private_commands = [
        types.BotCommand("help", t("core.command.help", "en")),
        types.BotCommand("plugin", t("core.command.plugin", "en")),
        types.BotCommand("language", t("core.command.language", "en")),
    ]
    group_commands = [
        types.BotCommand("help", t("core.command.help", "en")),
        types.BotCommand("plugin", t("core.command.plugin", "en")),
        types.BotCommand("plugin_settings", t("core.command.plugin_settings", "en")),
        types.BotCommand("language", t("core.command.language", "en")),
    ]

    # 从插件收集命令
    plugin_commands_info = plugin_manager.get_plugin_commands_info()

    # 添加插件命令
    for cmd_info in plugin_commands_info:
        if cmd_info["description"]:
            commands.append(
                types.BotCommand(cmd_info["command"], cmd_info["description"])
            )
            private_commands.append(
                types.BotCommand(cmd_info["command"], cmd_info["description"])
            )
            group_commands.append(
                types.BotCommand(cmd_info["command"], cmd_info["description"])
            )

    await bot.set_my_commands(commands, scope=types.BotCommandScopeDefault())
    await bot.set_my_commands(
        private_commands, scope=types.BotCommandScopeAllPrivateChats()
    )
    await bot.set_my_commands(
        group_commands, scope=types.BotCommandScopeAllGroupChats()
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
    plugin_commands_info = plugin_manager.get_plugin_commands_info()

    # 按类别分组添加插件命令帮助
    last_category = None
    for cmd_info in plugin_commands_info:
        if not cmd_info["help_text"]:
            continue

        category = cmd_info.get("category", "misc")
        if category != last_category:
            title = CATEGORY_TITLES.get(category, category.title())
            help_lines.append(formatting.mitalic(f"{title}:"))
            last_category = category

        help_lines.append(formatting.mcite(cmd_info["help_text"]))
        help_lines.append(formatting.mcite(""))  # 添加空行分隔

    # 添加特殊功能说明
    help_lines.append("")
    help_lines.append(formatting.mitalic(t("help.special", lang)))
    help_lines.append(formatting.mcite(t("help.special.report", lang)))

    # 添加 GitHub 链接
    help_lines.append("")
    help_lines.append(
        formatting.mlink("🍀 Github", "https://github.com/KimmyXYC/NachonekoBot-V2")
    )

    _message = await bot.reply_to(
        message=message,
        text=formatting.format_text(*help_lines),
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )
