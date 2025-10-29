# -*- coding: utf-8 -*-
# @Time    : 2023/11/18 上午12:18
# @File    : controller.py
# @Software: PyCharm
import re
from loguru import logger
from telebot import types, util
from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_helper import ApiTelegramException
from telebot.asyncio_storage import StateMemoryStorage
from telebot.asyncio_filters import SimpleCustomFilter

from setting.telegrambot import BotSetting
from utils.yaml import BotConfig
from utils.elaradb import BotElara
from app import event
from app.plugin_system.manager import plugin_manager

StepCache = StateMemoryStorage()


class BotRunner:
    def __init__(self):
        self.bot = AsyncTeleBot(BotSetting.token, state_storage=StepCache)

    async def run(self):
        logger.info("🤖 Bot Start")
        bot = self.bot

        if BotSetting.proxy_address:
            from telebot import asyncio_helper
            asyncio_helper.proxy = BotSetting.proxy_address
            logger.info("🌐 Proxy tunnels are being used!")

        await event.set_bot_commands(bot)

        # 注册自定义过滤器
        bot.add_custom_filter(StartsWithFilter())
        bot.add_custom_filter(CommandInChatFilter())
        bot.add_custom_filter(LotteryJoinFilter())

        # ==================== 核心命令(保留在这里) ====================
        @bot.message_handler(commands=['start', 'help'], chat_types=["private"])
        async def listen_help_command(message: types.Message):
            await event.listen_help_command(bot, message)

        # ==================== 插件管理命令 ====================
        @bot.message_handler(
            func=lambda m: m.from_user.id in BotConfig["admin"]["id"],
            commands=['plugin']
        )
        async def handle_plugin_command(message: types.Message):
            """插件管理命令"""
            args = message.text.split()

            if len(args) < 2:
                help_text = (
                    "📦 *插件管理命令*\n\n"
                    "`/plugin list` - 列出所有插件\n"
                    "`/plugin enable <name>` - 启用插件\n"
                    "`/plugin disable <name>` - 禁用插件\n"
                    "`/plugin reload` - 重载所有插件\n"
                    "`/plugin remove <name>` - 删除插件\n"
                )
                await bot.reply_to(message, help_text, parse_mode="Markdown")
                return

            action = args[1].lower()

            if action == "list":
                plugin_manager.load_local_plugins()
                plugins_text = "📋 *已安装的插件:*\n\n"
                for p in plugin_manager.plugins:
                    status = "✅ 启用" if p.status else "❌ 禁用"
                    version = f"v{p.version}" if p.version else "未知版本"
                    plugins_text += f"• `{p.name}` - {status} ({version})\n"
                await bot.reply_to(message, plugins_text, parse_mode="Markdown")

            elif action == "enable" and len(args) == 3:
                plugin_name = args[2]
                if plugin_manager.enable_plugin(plugin_name):
                    await bot.reply_to(message, f"✅ 插件 `{plugin_name}` 已启用", parse_mode="Markdown")
                    await plugin_manager.reload_all_plugins(bot)
                else:
                    await bot.reply_to(message, f"❌ 启用失败", parse_mode="Markdown")

            elif action == "disable" and len(args) == 3:
                plugin_name = args[2]
                if plugin_manager.disable_plugin(plugin_name):
                    await bot.reply_to(message, f"✅ 插件 `{plugin_name}` 已禁用", parse_mode="Markdown")
                    await plugin_manager.reload_all_plugins(bot)
                else:
                    await bot.reply_to(message, f"❌ 禁用失败", parse_mode="Markdown")

            elif action == "reload":
                msg = await bot.reply_to(message, "🔄 正在重载插件...")
                await plugin_manager.reload_all_plugins(bot)
                await bot.edit_message_text("✅ 插件重载完成", msg.chat.id, msg.message_id)

            elif action == "remove" and len(args) == 3:
                plugin_name = args[2]
                if plugin_manager.remove_plugin(plugin_name):
                    await bot.reply_to(message, f"✅ 插件 `{plugin_name}` 已删除", parse_mode="Markdown")
                else:
                    await bot.reply_to(message, f"❌ 删除失败", parse_mode="Markdown")

        # ==================== 动态加载插件 ====================
        logger.info("🔌 开始加载插件...")
        plugin_manager.load_local_plugins()
        await plugin_manager.load_plugin_handlers(bot)

        # ==================== 启动 Bot ====================
        try:
            logger.success("✨ Bot 启动成功,开始轮询...")
            await bot.polling(
                non_stop=True,
                allowed_updates=util.update_types,
                skip_pending=True
            )
        except ApiTelegramException as e:
            logger.opt(exception=e).exception("ApiTelegramException")
        except Exception as e:
            logger.exception(e)


# 自定义过滤器保持不变
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
            import sys
            if 'plugins.lottery' in sys.modules:
                from plugins import lottery
                return lottery.should_pass_lottery_filter(message)
        except Exception:
            return False
