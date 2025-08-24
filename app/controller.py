# -*- coding: utf-8 -*-
# @Time    : 2023/11/18 上午12:18
# @File    : controller.py
# @Software: PyCharm
import re
import plugin

from asgiref.sync import sync_to_async
from loguru import logger
from telebot import types
from telebot import util
from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_helper import ApiTelegramException
from telebot.asyncio_storage import StateMemoryStorage
from telebot.asyncio_filters import SimpleCustomFilter

from setting.telegrambot import BotSetting
from utils.yaml import BotConfig
from utils.elaradb import BotElara
from app import event
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

        await event.set_bot_commands(bot)

        # 注册自定义过滤器
        bot.add_custom_filter(StartsWithFilter())
        bot.add_custom_filter(CommandInChatFilter())
        bot.add_custom_filter(LotteryJoinFilter())

        @bot.message_handler(commands=['start', 'help'], chat_types=["private", "supergroup", "group"])
        async def listen_help_command(message: types.Message):
            await event.listen_help_command(bot, message)

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
                await plugin.ip.handle_ip_command(bot, message)
            else:
                await bot.reply_to(message, command_error_msg("ip", "IP Address or Domain"))

        @bot.message_handler(commands=['ipali'])
        async def listen_ipali_command(message: types.Message):
            command_args = message.text.split()
            if len(command_args) == 2:
                await plugin.ipali.handle_ipali_command(bot, message)
            else:
                await bot.reply_to(message, command_error_msg("ipali", "IP Address or Domain"))

        @bot.message_handler(commands=['icp'])
        async def listen_icp_command(message: types.Message):
            command_args = message.text.split()
            if len(command_args) == 2:
                await plugin.icp.handle_icp_command(bot, message)
            else:
                await bot.reply_to(message, command_error_msg("icp", "Domain"))

        @bot.message_handler(commands=['whois'])
        async def listen_whois_command(message: types.Message):
            command_args = message.text.split()
            if len(command_args) == 2:
                await plugin.whois.handle_whois_command(bot, message)
            else:
                await bot.reply_to(message, command_error_msg("whois", "Domain"))

        @bot.message_handler(commands=['dns'])
        async def listen_dns_command(message: types.Message):
            command_args = message.text.split()
            record_types = ["A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "PTR"]
            if len(command_args) == 2:
                await plugin.dns.handle_dns_command(bot, message, "A")
            elif len(command_args) == 3:
                if command_args[2].upper() not in record_types:
                    await bot.reply_to(message, command_error_msg(reason="invalid_type"))
                    return
                await plugin.dns.handle_dns_command(bot, message, command_args[2])
            else:
                await bot.reply_to(message, command_error_msg("dns", "Domain", "Record_Type"))

        @bot.message_handler(commands=['dnsapi'])
        async def listen_dnsapi_command(message: types.Message):
            command_args = message.text.split()
            record_types = ["A", "AAAA", "CNAME", "MX", "NS", "TXT"]
            if len(command_args) == 2:
                await plugin.dnsapi.handle_dns_command(bot, message, "A")
            elif len(command_args) == 3:
                if command_args[2].upper() not in record_types:
                    await bot.reply_to(message, command_error_msg(reason="invalid_type"))
                    return
                await plugin.dnsapi.handle_dns_command(bot, message, command_args[2])
            else:
                await bot.reply_to(message, command_error_msg("dns", "Domain", "Record_Type"))

        @bot.message_handler(commands=['lock'], chat_types=["group", "supergroup"])
        async def listen_lock_command(message: types.Message):
            command_args = message.text.split()
            if len(command_args) == 1:
                await bot.reply_to(message, command_error_msg("lock", "Command"))
            else:
                lock_list = command_args[1:]
                await plugin.lock.handle_lock_command(bot, message, lock_list)

        @bot.message_handler(commands=['unlock'], chat_types=["group", "supergroup"])
        async def listen_unlock_command(message: types.Message):
            command_args = message.text.split()
            if len(command_args) == 1:
                await bot.reply_to(message, command_error_msg("unlock", "Command"))
            else:
                unlock_list = command_args[1:]
                await plugin.lock.handle_unlock_command(bot, message, unlock_list)

        @bot.message_handler(commands=['list'], chat_types=["group", "supergroup"])
        async def listen_list_command(message: types.Message):
            await plugin.lock.handle_list_command(bot, message)

        @bot.message_handler(commands=['remake'])
        async def listen_remake_command(message: types.Message):
            await plugin.remake.handle_remake_command(bot, message)

        @bot.message_handler(commands=['remake_data'])
        async def listen_remake_data_command(message: types.Message):
            await plugin.remake.handle_remake_data_command(bot, message)

        @bot.message_handler(commands=['check'])
        async def handle_keybox_check(message: types.Message):
            if not (message.reply_to_message and message.reply_to_message.document):
                await bot.reply_to(message, "Please reply to a keybox.xml file.")
                return
            document = message.reply_to_message.document
            await plugin.keybox.handle_keybox_check(bot, message, document)

        @bot.message_handler(commands=['weather'])
        async def listen_weather_command(message: types.Message):
            command_args = message.text.split()
            if len(command_args) == 1:
                await bot.reply_to(message, command_error_msg("weather", "City_Name"))
            else:
                city = " ".join(command_args[1:])
                await plugin.weather.handle_weather_command(bot, message, city)

        @bot.message_handler(commands=['bin'])
        async def listen_bin_command(message: types.Message):
            await plugin.bin.handle_bin_command(bot, message)

        @bot.message_handler(commands=['bc'])
        async def listen_bc_command(message: types.Message):
            await plugin.bc.handle_bc_command(bot, message)

        @bot.message_handler(commands=['ping'])
        async def listen_ping_command(message: types.Message):
            command_args = message.text.split()
            if len(command_args) == 2:
                await plugin.ping.handle_ping_command(bot, message)
            else:
                await bot.reply_to(message, command_error_msg("ping", "Domain_or_IP"))

        @bot.message_handler(commands=['tcping'])
        async def listen_tcping_command(message: types.Message):
            await plugin.tcping.handle_tcping_command(bot, message)

        @bot.message_handler(commands=['trace'])
        async def listen_trace_command(message: types.Message):
            await plugin.trace.handle_trace_command(bot, message)

        @bot.message_handler(commands=['ocr'])
        async def listen_ocr_command(message: types.Message):
            await plugin.ocr.handle_ocr_command(bot, message)

        @bot.message_handler(starts_with_alarm=True)
        async def handle_specific_start(message: types.Message):
            type_dict = {"喜报": 0, "悲报": 1, "通报": 2, "警报": 3}
            await plugin.xibao.good_news(bot, message, type_dict[message.text[:2]])

        @bot.message_handler(content_types=['document'], chat_types=['private'])
        async def handle_keybox_file(message: types.Message):
            document = message.document
            await plugin.keybox.handle_keybox_check(bot, message, document)

        @bot.message_handler(content_types=['photo'], chat_types=['private'])
        async def handle_photo_ocr(message: types.Message):
            await plugin.ocr.process_photo(bot, message)

        @bot.message_handler(commands=['lottery'], chat_types=["group", "supergroup"])
        async def listen_lottery_command(message: types.Message):
            await plugin.lottery.handle_lottery_command(bot, message)

        @bot.message_handler(lottery_join=True, content_types=['text'], chat_types=['group', 'supergroup'])
        async def handle_lottery_join(message: types.Message):
            await plugin.lottery.process_lottery_message(bot, message)

        @bot.message_handler(func=lambda message: message.from_user.id in BotConfig["xiatou"]["id"],
                             content_types=['text', 'photo', 'video', 'document'], starts_with_alarm=False)
        async def handle_xiatou(message: types.Message):
            logger.debug(f"[XiaTou][{message.from_user.id}]: {message.text}")
            await plugin.xiatou.handle_xiatou(bot, message)

        @bot.message_handler(command_in_group=True, content_types=['text'])
        async def handle_commands(message: types.Message):
            if BotElara.exists(str(message.chat.id)):
                command = re.split(r'[@\s]+', message.text.lower())[0]
                command = command[1:]
                lock_cmd_list = BotElara.get(str(message.chat.id), [])
                if command in lock_cmd_list:
                    await bot.delete_message(message.chat.id, message.message_id)

        try:
            await bot.polling(
                non_stop=True, allowed_updates=util.update_types, skip_pending=True
            )
        except ApiTelegramException as e:
            logger.opt(exception=e).exception("ApiTelegramException")
        except Exception as e:
            logger.exception(e)

class StartsWithFilter(SimpleCustomFilter):
    key = 'starts_with_alarm'

    async def check(self, message):
        return message.text.startswith(('喜报', '悲报', '通报', '警报'))


class CommandInChatFilter(SimpleCustomFilter):
    key = 'command_in_group'

    async def check(self, message):
        return message.chat.type in ['group', 'supergroup'] and message.text.startswith('/')



class LotteryJoinFilter(SimpleCustomFilter):
    key = 'lottery_join'

    async def check(self, message):
        try:
            return plugin.lottery.should_pass_lottery_filter(message)
        except Exception:
            return False
