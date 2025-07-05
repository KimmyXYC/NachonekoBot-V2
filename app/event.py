# -*- coding: utf-8 -*-
# @Time    : 2025/6/22 17:27
# @Author  : KimmyXYC
# @File    : event.py
# @Software: PyCharm
from telebot import types, formatting


async def set_bot_commands(bot):
    commands = [
        types.BotCommand("help", "获取帮助信息"),
        types.BotCommand("status", "获取机器人状态信息"),
        types.BotCommand("calldoctor", "呼叫医生"),
        types.BotCommand("callmtf", "呼叫 MTF"),
        types.BotCommand("callpolice", "呼叫警察"),
        types.BotCommand("short", "生成短链接"),
        types.BotCommand("ping", "Ping 测试"),
        types.BotCommand("tcping", "TCP Ping 测试"),
        types.BotCommand("ip", "查询 IP 或域名信息"),
        types.BotCommand("ipali", "使用阿里 API 查询 IP 或域名"),
        types.BotCommand("icp", "查询域名 ICP 备案信息"),
        types.BotCommand("whois", "查询 Whois 信息"),
        types.BotCommand("dns", "查询 DNS 记录"),
        types.BotCommand("dnsapi", "使用 API 查询 DNS 记录"),
        types.BotCommand("trace", "追踪路由"),
        types.BotCommand("lock", "锁定群组中的命令"),
        types.BotCommand("unlock", "解锁群组中的命令"),
        types.BotCommand("list", "列出群组中被锁定的命令"),
        types.BotCommand("remake", "转生"),
        types.BotCommand("remake_data", "查看转生数据"),
        types.BotCommand("check", "检查 keybox.xml 文件"),
        types.BotCommand("weather", "查询天气信息"),
        types.BotCommand("bin", "银行卡 bin 查询"),
        types.BotCommand("ocr", "OCR 识别图片中的文字"),
        types.BotCommand("bin", "查询银行卡 BIN 信息"),
        types.BotCommand("bc", "货币转换")
    ]
    await bot.set_my_commands(commands, scope=types.BotCommandScopeDefault())
    await bot.set_my_commands(commands, scope=types.BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(commands, scope=types.BotCommandScopeAllGroupChats())


async def listen_help_command(bot, message: types.Message):
    _message = await bot.reply_to(
        message=message,
        text=formatting.format_text(
            formatting.mbold("🥕 Help"),
            formatting.mcode("/help - 获取帮助信息"),
            formatting.mcode("/status - 获取机器人状态信息"),
            formatting.mcode("/calldoctor - 呼叫医生"),
            formatting.mcode("/callmtf - 呼叫 MTF"),
            formatting.mcode("/callpolice - 呼叫警察"),
            formatting.mcode("/short [URL] - 生成短链接"),
            formatting.mcode("/ping [IP/Domain] - Ping 测试"),
            formatting.mcode("/tcping [IP/Domain]:[Port] - TCP Ping 测试"),
            formatting.mcode("/ip [IP/Domain] - 查询 IP 或域名信息"),
            formatting.mcode("/ipali [IP/Domain] - 使用阿里 API 查询 IP 或域名"),
            formatting.mcode("/icp [Domain] - 查询域名 ICP 备案信息"),
            formatting.mcode("/whois [Domain] - 查询 Whois 信息"),
            formatting.mcode("/dns [Domain] [Record_Type] - 查询 DNS 记录"),
            formatting.mcode("/dnsapi [Domain] [Record_Type] - 使用 API 查询 DNS 记录"),
            formatting.mcode("/trace [IP/Domain] - 追踪路由"),
            formatting.mcode("/lock [Command] - 锁定群组中的命令"),
            formatting.mcode("/unlock [Command] - 解锁群组中的命令"),
            formatting.mcode("/list - 列出群组中被锁定的命令"),
            formatting.mcode("/remake - 转生"),
            formatting.mcode("/remake_data - 查看转生数据"),
            formatting.mcode("/check - 检查 keybox.xml 文件"),
            formatting.mcode("/weather [City_Name] - 查询天气信息"),
            formatting.mcode("/bin - 银行卡 bin 查询"),
            formatting.mcode("/ocr - OCR 识别图片中的文字"),
            formatting.mcode("/bin [Card_BIN] - 查询银行卡 BIN 信息"),
            formatting.mcode("/bc [Amount] [Currency_From] [Currency_To] - 货币转换"),
            "",
            formatting.mitalic("特殊功能："),
            formatting.mcode("喜报/悲报/通报/警报 [内容] - 生成对应类型的报告图片"),
            "",
            formatting.mlink(
                "🍀 Github", "https://github.com/KimmyXYC/NachonekoBot-V2"
            ),
        ),
        parse_mode="MarkdownV2",
    )
