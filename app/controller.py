# -*- coding: utf-8 -*-
# @Time    : 2023/11/18 上午12:18
# @File    : controller.py
# @Software: PyCharm

import plugin

from asgiref.sync import sync_to_async
from loguru import logger
from telebot import types
from telebot import util, formatting
from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_helper import ApiTelegramException
from telebot.asyncio_storage import StateMemoryStorage

from setting.telegrambot import BotSetting
from utils.yaml import BotConfig
from app.utils import command_error_msg

StepCache = StateMemoryStorage()


@sync_to_async
def sync_to_async_func():
    pass


class BotRunner(object):
    def __init__(self):
        self.bot = AsyncTeleBot(BotSetting.token, state_storage=StepCache)

    async def run(self):
        logger.info("Bot Start")
        bot = self.bot
        if BotSetting.proxy_address:
            from telebot import asyncio_helper

            asyncio_helper.proxy = BotSetting.proxy_address
            logger.info("Proxy tunnels are being used!")

        @bot.message_handler(commands="help", chat_types=["private", "supergroup", "group"])
        async def listen_help_command(message: types.Message):
            _message = await bot.reply_to(
                message=message,
                text=formatting.format_text(
                    formatting.mbold("🥕 Help"),
                    formatting.mlink(
                        "🍀 Github", "https://github.com/KimmyXYC/NachonekoBot-V2"
                    ),
                ),
                parse_mode="MarkdownV2",
            )

        @bot.message_handler(func=lambda message: message.from_user.id in BotConfig["admin"]["id"], commands=['status'])
        async def listen_status_command(message: types.Message):
            await plugin.status.handle_status_command(bot, message)

        @bot.message_handler(commands=['calldoctor', 'callmtf', 'callpolice'])
        async def listen_call_command(message: types.Message):
            await plugin.callanyone.handle_call_command(bot, message)

        @bot.message_handler(commands=["short"])
        async def listen_short_command(message: types.Message):
            command_args = message.text.split()
            if len(command_args) == 2:
                url = command_args[1]
                await plugin.shorturl.handle_short_command(bot, message, url)
            else:
                await bot.reply_to(message, command_error_msg("short", "URL"))

        @bot.message_handler(commands=['ip'])
        async def listen_ip_command(message: types.Message):
            command_args = message.text.split()
            if len(command_args) == 2:
                await plugin.ping.handle_ip_command(bot, message)
            else:
                await bot.reply_to(message, command_error_msg("ip", "IP Address or Domain"))

        @bot.message_handler(commands=['ipali'])
        async def listen_ipali_command(message: types.Message):
            command_args = message.text.split()
            if len(command_args) == 2:
                await plugin.ping.handle_ipali_command(bot, message)
            else:
                await bot.reply_to(message, command_error_msg("ipali", "IP Address or Domain"))

        @bot.message_handler(commands=['icp'])
        async def listen_icp_command(message: types.Message):
            command_args = message.text.split()
            if len(command_args) == 2:
                await plugin.ping.handle_icp_command(bot, message)
            else:
                await bot.reply_to(message, command_error_msg("icp", "Domain"))

        @bot.message_handler(commands=['whois'])
        async def listen_whois_command(message: types.Message):
            command_args = message.text.split()
            available_types = ["domain", "ip", "asn", "entity"]
            if len(command_args) == 2:
                await plugin.ping.handle_whois_command(bot, message, "domain")
            elif len(command_args) == 3:
                if command_args[2] not in available_types:
                    await bot.reply_to(message, command_error_msg(reason="invalid_type"))
                    return
                await plugin.ping.handle_whois_command(bot, message, command_args[2])
            else:
                await bot.reply_to(message, command_error_msg("whois", "DATA", "TYPE"))

        @bot.message_handler(commands=['dns'])
        async def listen_dns_command(message: types.Message):
            command_args = message.text.split()
            record_types = ["A", "AAAA", "CNAME", "MX", "NS", "TXT"]
            if len(command_args) == 2:
                await plugin.ping.handle_dns_command(bot, message, "A")
            elif len(command_args) == 3:
                if command_args[2].upper() not in record_types:
                    await bot.reply_to(message, command_error_msg(reason="invalid_type"))
                    return
                await plugin.ping.handle_dns_command(bot, message, command_args[2])
            else:
                await bot.reply_to(message, command_error_msg("dns", "Domain", "Record_Type"))

        @bot.message_handler(commands=['lock'], chat_types=["group", "supergroup"])
        async def listen_lock_command(message: types.Message):
            command_args = message.text.split()
            if len(command_args) == 1:
                await bot.reply_to(message, command_error_msg("lock_cmd", "Command"))
            else:
                lock_list = command_args[1:]
                await plugin.lock.handle_lock_command(bot, message, lock_list)

        @bot.message_handler(commands=['unlock'], chat_types=["group", "supergroup"])
        async def listen_unlock_command(message: types.Message):
            command_args = message.text.split()
            if len(command_args) == 1:
                await bot.reply_to(message, command_error_msg("unlock_cmd", "Command"))
            else:
                unlock_list = command_args[1:]
                await plugin.lock.handle_unlock_command(bot, message, unlock_list)

        @bot.message_handler(commands=['list'], chat_types=["group", "supergroup"])
        async def listen_list_command(message: types.Message):
            await plugin.lock.handle_list_command(bot, message)

        try:
            await bot.polling(
                non_stop=True, allowed_updates=util.update_types, skip_pending=True
            )
        except ApiTelegramException as e:
            logger.opt(exception=e).exception("ApiTelegramException")
        except Exception as e:
            logger.exception(e)
