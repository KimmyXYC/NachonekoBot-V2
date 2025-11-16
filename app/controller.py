# -*- coding: utf-8 -*-
# @Time    : 2023/11/18 上午12:18
# @File    : controller.py
# @Software: PyCharm
from loguru import logger
from telebot import types, util
from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_helper import ApiTelegramException
from telebot.asyncio_storage import StateMemoryStorage
from telebot.asyncio_filters import SimpleCustomFilter

from setting.telegrambot import BotSetting
from utils.yaml import BotConfig
from utils.postgres import BotDatabase
from app import event
from app.plugin_system.manager import plugin_manager
from app.plugin_system.plugin_settings import (
    has_change_info_permission,
    build_keyboard_and_text,
    get_toggleable_plugins,
)

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

        # 注册自定义过滤器（仅保留内部使用的）
        bot.add_custom_filter(CommandInChatFilter())

        # ==================== 动态加载插件 ====================
        logger.info("🔌 开始加载插件...")
        plugin_manager.load_local_plugins()
        await plugin_manager.load_plugin_handlers(bot)

        # ==================== 设置机器人命令（在插件加载后） ====================
        await event.set_bot_commands(bot, plugin_manager)

        # ==================== 核心命令(保留在这里) ====================
        @bot.message_handler(commands=['start', 'help'], chat_types=["private"])
        async def listen_help_command(message: types.Message):
            await event.listen_help_command(bot, message, plugin_manager)

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
                    await bot.reply_to(message, "❌ 启用失败", parse_mode="Markdown")

            elif action == "disable" and len(args) == 3:
                plugin_name = args[2]
                if plugin_manager.disable_plugin(plugin_name):
                    await bot.reply_to(message, f"✅ 插件 `{plugin_name}` 已禁用", parse_mode="Markdown")
                    await plugin_manager.reload_all_plugins(bot)
                else:
                    await bot.reply_to(message, "❌ 禁用失败", parse_mode="Markdown")

            elif action == "reload":
                msg = await bot.reply_to(message, "🔄 正在重载插件...")
                await plugin_manager.reload_all_plugins(bot)
                await bot.edit_message_text("✅ 插件重载完成", msg.chat.id, msg.message_id)

            elif action == "remove" and len(args) == 3:
                plugin_name = args[2]
                if plugin_manager.remove_plugin(plugin_name):
                    await bot.reply_to(message, f"✅ 插件 `{plugin_name}` 已删除", parse_mode="Markdown")
                else:
                    await bot.reply_to(message, "❌ 删除失败", parse_mode="Markdown")

        # ==================== 插件设置面板（核心命令） ====================
        @bot.message_handler(commands=['plugin_settings'], chat_types=['group', 'supergroup'])
        async def core_plugin_settings(message: types.Message):
            try:
                user_id = message.from_user.id
                chat_id = message.chat.id

                if not await has_change_info_permission(bot, chat_id, user_id):
                    await bot.reply_to(message, "你没有权限使用该功能（需要“更改群信息”权限）。")
                    return

                plugin_list = await get_toggleable_plugins(plugin_manager.middleware)
                if not plugin_list:
                    await bot.reply_to(message, "当前没有支持开关的插件。")
                    return

                await BotDatabase.ensure_group_row(chat_id)
                states = [await BotDatabase.get_plugin_enabled(chat_id, name) for name in plugin_list]

                text, kb = build_keyboard_and_text(plugin_list, states)
                await bot.reply_to(message, text, reply_markup=kb)
            except Exception as e:
                logger.error(f"/plugin_settings 处理失败: {e}")
                try:
                    await bot.reply_to(message, f"获取插件设置失败：{e}")
                except Exception:
                    pass

        # 回调：处理插件开关切换（核心处理，不经中间件）
        @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith('plg_toggle:'))
        async def core_handle_toggle_callback(call: types.CallbackQuery):
            try:
                chat = call.message.chat
                chat_id = chat.id
                user_id = call.from_user.id

                if not await has_change_info_permission(bot, chat_id, user_id):
                    await bot.answer_callback_query(call.id, "无权限")
                    return

                plugin_name_clicked = call.data.split(':', 1)[1]

                current = await BotDatabase.get_plugin_enabled(chat_id, plugin_name_clicked)
                new_state = not current
                ok = await BotDatabase.set_plugin_enabled(chat_id, plugin_name_clicked, new_state)
                if not ok:
                    await bot.answer_callback_query(call.id, "更新失败")
                    return

                plugin_list = await get_toggleable_plugins(plugin_manager.middleware)
                states = [await BotDatabase.get_plugin_enabled(chat_id, name) for name in plugin_list]
                text, kb = build_keyboard_and_text(plugin_list, states)

                await bot.edit_message_text(
                    text=text,
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    reply_markup=kb
                )
                await bot.answer_callback_query(call.id, "已更新")
            except Exception as e:
                logger.error(f"切换插件失败: {e}")
                try:
                    await bot.answer_callback_query(call.id, f"失败: {e}")
                except Exception:
                    pass

        # 回调：处理关闭按钮（删除消息）
        @bot.callback_query_handler(func=lambda c: c.data and c.data == 'plg_close')
        async def core_handle_close_callback(call: types.CallbackQuery):
            try:
                chat_id = call.message.chat.id
                message_id = call.message.message_id
                user_id = call.from_user.id

                # 检查权限
                if not await has_change_info_permission(bot, chat_id, user_id):
                    await bot.answer_callback_query(call.id, "无权限")
                    return

                # 删除消息
                await bot.delete_message(chat_id, message_id)
                await bot.answer_callback_query(call.id, "已关闭")
            except Exception as e:
                logger.error(f"关闭插件面板失败: {e}")
                try:
                    await bot.answer_callback_query(call.id, f"关闭失败: {e}")
                except Exception:
                    pass

        # ==================== 中间件分发器 ====================
        @bot.message_handler(func=lambda m: m.text and m.text.startswith('/'))
        async def middleware_dispatcher(message: types.Message):
            """统一命令分发器：优先分发命令；若无命中，则继续走普通消息分发，
            以便处理像 '/$' 这类非标准命令前缀的消息（由插件自行解析）。"""
            executed = await plugin_manager.middleware.dispatch_command(bot, message)
            if executed > 0:
                logger.info(f"✨ 命令处理完成，执行了 {executed} 个处理器")
            else:
                # 没有任何命令处理器命中，则转交给通用消息中间件，
                # 允许像 quote 这类通过 message handler 解析 '/$' 的插件生效。
                await plugin_manager.middleware.dispatch_message(bot, message)

        @bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
        async def message_dispatcher(message: types.Message):
            """统一消息分发器"""
            await plugin_manager.middleware.dispatch_message(bot, message)

        # 回调分发器（除核心前缀外，其余交由中间件处理）
        @bot.callback_query_handler(func=lambda c: not (c.data and c.data.startswith('plg_toggle:')))
        async def callback_dispatcher(call: types.CallbackQuery):
            executed = await plugin_manager.middleware.dispatch_callback(bot, call)
            if executed > 0:
                logger.info(f"✨ 回调处理完成，执行了 {executed} 个处理器")

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


# 自定义过滤器（仅保留内部使用的）
class CommandInChatFilter(SimpleCustomFilter):
    key = 'command_in_group'

    async def check(self, message):
        return message.chat.type in ['group', 'supergroup'] and message.text.startswith('/')
