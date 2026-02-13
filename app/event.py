# -*- coding: utf-8 -*-
# @Time    : 2025/6/22 17:27
# @Author  : KimmyXYC
# @File    : event.py
# @Software: PyCharm
from telebot import types, formatting


async def set_bot_commands(bot, plugin_manager):
    """
    动态构建并设置机器人命令
    从插件管理器收集所有插件的命令信息
    """
    # 核心命令（不属于任何插件）
    commands = [
        types.BotCommand("help", "获取帮助信息"),
        types.BotCommand("plugin", "全局插件管理（仅 Bot 管理员）"),
        types.BotCommand("plugin_settings", "群组插件设置（仅群组管理员）"),
    ]
    
    # 从插件收集命令
    plugin_commands_info = plugin_manager.get_plugin_commands_info()
    
    # 添加插件命令
    for cmd_info in plugin_commands_info:
        if cmd_info['description']:
            commands.append(
                types.BotCommand(cmd_info['command'], cmd_info['description'])
            )
    
    await bot.set_my_commands(commands, scope=types.BotCommandScopeDefault())
    await bot.set_my_commands(commands, scope=types.BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(commands, scope=types.BotCommandScopeAllGroupChats())


async def listen_help_command(bot, message: types.Message, plugin_manager):
    """
    动态构建并显示帮助信息
    从插件管理器收集所有插件的帮助文本
    """
    # 构建帮助文本列表
    help_lines = [formatting.mbold("🥕 Help")]
    
    # 核心命令帮助
    help_lines.append(formatting.mcite("/help - 获取帮助信息"))
    help_lines.append(formatting.mcite(""))  # 添加空行分隔
    help_lines.append(formatting.mcite("/plugin - 全局插件管理（仅 Bot 管理员）"))
    help_lines.append(formatting.mcite("/plugin_settings - 群组插件设置（仅群组管理员）"))
    help_lines.append(formatting.mcite(""))  # 添加空行分隔
    
    # 从插件收集帮助信息
    plugin_commands_info = plugin_manager.get_plugin_commands_info()
    
    # 添加插件命令的帮助文本
    for cmd_info in plugin_commands_info:
        if cmd_info['help_text']:
            help_lines.append(formatting.mcite(cmd_info['help_text']))
            help_lines.append(formatting.mcite(""))  # 添加空行分隔
    
    # 添加特殊功能说明
    help_lines.append("")
    help_lines.append(formatting.mitalic("特殊功能："))
    help_lines.append(formatting.mcite("喜报/悲报/通报/警报 [内容] - 生成对应类型的报告图片"))
    
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
