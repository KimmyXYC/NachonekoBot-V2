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
    build_language_keyboard,
    get_toggleable_plugins,
    get_toggleable_jobs,
)
from app.security.permissions import is_bot_admin
from app.scheduler import scheduler
from utils.i18n import get_message_language, language_name, normalize_language, t

StepCache = StateMemoryStorage()


class BotRunner:
    def __init__(self):
        # 检查是否启用自定义 Bot API 服务器
        botapi_config = BotConfig.get("botapi", {})
        if botapi_config.get("enable", False):
            api_server = botapi_config.get("api_server", "")
            if api_server:
                from telebot import apihelper, asyncio_helper

                # 设置自定义 Bot API URL
                apihelper.API_URL = f"{api_server}/bot{{0}}/{{1}}"
                apihelper.FILE_URL = f"{api_server}/file/bot{{0}}/{{1}}"
                # AsyncTeleBot 使用 asyncio_helper.API_URL
                asyncio_helper.API_URL = apihelper.API_URL
                asyncio_helper.FILE_URL = apihelper.FILE_URL
                logger.info(f"🌐 使用自定义 Bot API 服务器: {api_server}")
            else:
                logger.warning(
                    "⚠️ 自定义 Bot API 已启用但未配置 api_server，使用官方服务器"
                )
        else:
            logger.info("🌐 使用官方 Bot API 服务器")

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

        # ==================== 启动定时任务调度器 ====================
        scheduler.attach_bot(bot)
        scheduler.start()

        # ==================== 设置机器人命令（在插件加载后） ====================
        await event.set_bot_commands(bot, plugin_manager)

        # ==================== 核心命令(保留在这里) ====================
        @bot.message_handler(commands=["start", "help"], chat_types=["private"])
        async def listen_help_command(message: types.Message):
            lang = await get_message_language(message)
            await event.listen_help_command(bot, message, plugin_manager, lang)

        async def build_settings_items(chat_id: int):
            plugin_list = await get_toggleable_plugins(plugin_manager.middleware)
            job_list = await get_toggleable_jobs(plugin_manager.middleware)
            items = []

            for name, display_name in plugin_list:
                enabled = await BotDatabase.get_plugin_enabled(chat_id, name)
                items.append(
                    {
                        "kind": "plugin",
                        "key": name,
                        "label": display_name,
                        "enabled": enabled,
                    }
                )

            for job_name, display_name in job_list:
                enabled = await BotDatabase.get_scheduled_job_enabled(chat_id, job_name)
                items.append(
                    {
                        "kind": "job",
                        "key": job_name,
                        "label": display_name,
                        "enabled": enabled,
                    }
                )

            return items

        # ==================== 插件管理命令 ====================
        @bot.message_handler(
            func=lambda m: (
                bool(getattr(m, "from_user", None)) and is_bot_admin(m.from_user.id)
            ),
            commands=["plugin"],
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
                    await bot.reply_to(
                        message,
                        f"✅ 插件 `{plugin_name}` 已启用",
                        parse_mode="Markdown",
                    )
                    await plugin_manager.reload_all_plugins(bot)
                else:
                    await bot.reply_to(message, "❌ 启用失败", parse_mode="Markdown")

            elif action == "disable" and len(args) == 3:
                plugin_name = args[2]
                if plugin_manager.disable_plugin(plugin_name):
                    await bot.reply_to(
                        message,
                        f"✅ 插件 `{plugin_name}` 已禁用",
                        parse_mode="Markdown",
                    )
                    await plugin_manager.reload_all_plugins(bot)
                else:
                    await bot.reply_to(message, "❌ 禁用失败", parse_mode="Markdown")

            elif action == "reload":
                msg = await bot.reply_to(message, "🔄 正在重载插件...")
                await plugin_manager.reload_all_plugins(bot)
                await bot.edit_message_text(
                    "✅ 插件重载完成", msg.chat.id, msg.message_id
                )

            elif action == "remove" and len(args) == 3:
                plugin_name = args[2]
                if plugin_manager.remove_plugin(plugin_name):
                    await bot.reply_to(
                        message,
                        f"✅ 插件 `{plugin_name}` 已删除",
                        parse_mode="Markdown",
                    )
                else:
                    await bot.reply_to(message, "❌ 删除失败", parse_mode="Markdown")

        # ==================== 插件设置面板（核心命令） ====================
        @bot.message_handler(
            commands=["plugin_settings"], chat_types=["group", "supergroup"]
        )
        async def core_plugin_settings(message: types.Message):
            try:
                user_id = message.from_user.id
                chat_id = message.chat.id
                lang = normalize_language(await BotDatabase.get_group_language(chat_id))

                if not await has_change_info_permission(bot, chat_id, user_id):
                    await bot.reply_to(
                        message, t("plugin_settings.permission_required", lang)
                    )
                    return

                items = await build_settings_items(chat_id)

                if not items:
                    await bot.reply_to(message, t("plugin_settings.empty", lang))
                    return

                await BotDatabase.ensure_group_row(chat_id)
                text, kb = build_keyboard_and_text(items, lang)
                await bot.reply_to(message, text, reply_markup=kb)
            except Exception as e:
                logger.error(f"/plugin_settings 处理失败: {e}")
                try:
                    lang = await get_message_language(message)
                    await bot.reply_to(
                        message, t("plugin_settings.fetch_failed", lang, error=e)
                    )
                except Exception:
                    pass

        # ==================== 语言设置命令（私聊和群组） ====================
        @bot.message_handler(commands=["language"], chat_types=["private"])
        async def core_private_language(message: types.Message):
            user_id = message.from_user.id
            current = normalize_language(await BotDatabase.get_user_language(user_id))
            text, kb = build_language_keyboard(
                lang=current,
                callback_prefix="lang_set_user",
                include_back=False,
                include_close=True,
                close_callback_data="lang_close",
            )
            await bot.reply_to(message, text, reply_markup=kb)

        @bot.message_handler(commands=["language"], chat_types=["group", "supergroup"])
        async def core_group_language(message: types.Message):
            user_id = message.from_user.id
            chat_id = message.chat.id
            current = normalize_language(await BotDatabase.get_group_language(chat_id))

            if not await has_change_info_permission(bot, chat_id, user_id):
                await bot.reply_to(message, t("language.group_admin_required", current))
                return

            text, kb = build_language_keyboard(
                lang=current,
                callback_prefix="lang_set_group",
                include_back=False,
                include_close=True,
                close_callback_data="lang_close",
            )
            await bot.reply_to(message, text, reply_markup=kb)

        # 回调：处理插件开关切换（核心处理，不经中间件）
        @bot.callback_query_handler(
            func=lambda c: c.data and c.data.startswith("plg_toggle:")
        )
        async def core_handle_toggle_callback(call: types.CallbackQuery):
            try:
                chat = call.message.chat
                chat_id = chat.id
                user_id = call.from_user.id
                lang = normalize_language(await BotDatabase.get_group_language(chat_id))

                if not await has_change_info_permission(bot, chat_id, user_id):
                    await bot.answer_callback_query(
                        call.id, t("common.no_permission", lang)
                    )
                    return

                parts = call.data.split(":", 2)
                if len(parts) < 3:
                    await bot.answer_callback_query(
                        call.id, t("common.invalid_action", lang)
                    )
                    return
                target_kind = parts[1]
                target_key = parts[2]

                if target_kind == "plugin":
                    current = await BotDatabase.get_plugin_enabled(chat_id, target_key)
                    new_state = not current
                    ok = await BotDatabase.set_plugin_enabled(
                        chat_id, target_key, new_state
                    )
                elif target_kind == "job":
                    current = await BotDatabase.get_scheduled_job_enabled(
                        chat_id, target_key
                    )
                    new_state = not current
                    ok = await BotDatabase.set_scheduled_job_enabled(
                        chat_id, target_key, new_state
                    )
                else:
                    await bot.answer_callback_query(
                        call.id, t("common.invalid_action", lang)
                    )
                    return
                if not ok:
                    await bot.answer_callback_query(
                        call.id, t("common.update_failed", lang)
                    )
                    return

                items = await build_settings_items(chat_id)
                text, kb = build_keyboard_and_text(items, lang)

                await bot.edit_message_text(
                    text=text,
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    reply_markup=kb,
                )
                await bot.answer_callback_query(call.id, t("common.updated", lang))
            except Exception as e:
                logger.error(f"切换插件失败: {e}")
                try:
                    chat_id = call.message.chat.id
                    lang = normalize_language(
                        await BotDatabase.get_group_language(chat_id)
                    )
                    await bot.answer_callback_query(
                        call.id, t("plugin_settings.toggle_failed", lang, error=e)
                    )
                except Exception:
                    pass

        # 回调：打开 plugin_settings 语言二级菜单
        @bot.callback_query_handler(func=lambda c: c.data and c.data == "plg_lang_menu")
        async def core_handle_plugin_language_menu(call: types.CallbackQuery):
            chat_id = call.message.chat.id
            user_id = call.from_user.id
            lang = normalize_language(await BotDatabase.get_group_language(chat_id))

            if not await has_change_info_permission(bot, chat_id, user_id):
                await bot.answer_callback_query(
                    call.id, t("common.no_permission", lang)
                )
                return

            text, kb = build_language_keyboard(
                lang=lang,
                callback_prefix="plg_lang_set",
                include_back=True,
                back_callback_data="plg_lang_back",
                include_close=False,
            )
            await bot.edit_message_text(
                text=t("plugin_settings.lang_title", lang) + "\n\n" + text,
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=kb,
            )
            await bot.answer_callback_query(call.id)

        # 回调：plugin_settings 内设置群语言
        @bot.callback_query_handler(
            func=lambda c: c.data and c.data.startswith("plg_lang_set:")
        )
        async def core_handle_plugin_language_set(call: types.CallbackQuery):
            chat_id = call.message.chat.id
            user_id = call.from_user.id
            old_lang = normalize_language(await BotDatabase.get_group_language(chat_id))

            if not await has_change_info_permission(bot, chat_id, user_id):
                await bot.answer_callback_query(
                    call.id, t("common.no_permission", old_lang)
                )
                return

            selected = normalize_language(call.data.split(":", 1)[1])
            await BotDatabase.set_group_language(chat_id, selected)
            lang = normalize_language(await BotDatabase.get_group_language(chat_id))
            items = await build_settings_items(chat_id)
            text, kb = build_keyboard_and_text(items, lang)
            await bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=kb,
            )
            await bot.answer_callback_query(
                call.id,
                t(
                    "language.set_success_group",
                    lang,
                    language=language_name(lang),
                ),
            )

        # 回调：plugin_settings 语言二级菜单返回主菜单
        @bot.callback_query_handler(func=lambda c: c.data and c.data == "plg_lang_back")
        async def core_handle_plugin_language_back(call: types.CallbackQuery):
            chat_id = call.message.chat.id
            user_id = call.from_user.id
            lang = normalize_language(await BotDatabase.get_group_language(chat_id))

            if not await has_change_info_permission(bot, chat_id, user_id):
                await bot.answer_callback_query(
                    call.id, t("common.no_permission", lang)
                )
                return

            items = await build_settings_items(chat_id)
            text, kb = build_keyboard_and_text(items, lang)
            await bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=kb,
            )
            await bot.answer_callback_query(call.id)

        # 回调：/language 快速设置（私聊用户）
        @bot.callback_query_handler(
            func=lambda c: c.data and c.data.startswith("lang_set_user:")
        )
        async def core_handle_user_language_set(call: types.CallbackQuery):
            if call.message.chat.type != "private":
                lang = normalize_language(
                    await BotDatabase.get_group_language(call.message.chat.id)
                )
                await bot.answer_callback_query(
                    call.id, t("language.private_only", lang)
                )
                return

            user_id = call.from_user.id
            selected = normalize_language(call.data.split(":", 1)[1])
            await BotDatabase.set_user_language(user_id, selected)
            lang = normalize_language(await BotDatabase.get_user_language(user_id))
            text, kb = build_language_keyboard(
                lang=lang,
                callback_prefix="lang_set_user",
                include_back=False,
                include_close=True,
                close_callback_data="lang_close",
            )
            await bot.edit_message_text(
                text=text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=kb,
            )
            await bot.answer_callback_query(
                call.id,
                t("language.set_success_user", lang, language=language_name(lang)),
            )

        # 回调：/language 快速设置（群语言）
        @bot.callback_query_handler(
            func=lambda c: c.data and c.data.startswith("lang_set_group:")
        )
        async def core_handle_group_language_set(call: types.CallbackQuery):
            chat_id = call.message.chat.id
            user_id = call.from_user.id
            current = normalize_language(await BotDatabase.get_group_language(chat_id))

            if not await has_change_info_permission(bot, chat_id, user_id):
                await bot.answer_callback_query(
                    call.id, t("language.group_admin_required", current)
                )
                return

            selected = normalize_language(call.data.split(":", 1)[1])
            await BotDatabase.set_group_language(chat_id, selected)
            lang = normalize_language(await BotDatabase.get_group_language(chat_id))
            text, kb = build_language_keyboard(
                lang=lang,
                callback_prefix="lang_set_group",
                include_back=False,
                include_close=True,
                close_callback_data="lang_close",
            )
            await bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=kb,
            )
            await bot.answer_callback_query(
                call.id,
                t(
                    "language.set_success_group",
                    lang,
                    language=language_name(lang),
                ),
            )

        # 回调：处理关闭按钮（删除消息）
        @bot.callback_query_handler(func=lambda c: c.data and c.data == "plg_close")
        async def core_handle_close_callback(call: types.CallbackQuery):
            try:
                chat_id = call.message.chat.id
                message_id = call.message.message_id
                user_id = call.from_user.id
                lang = normalize_language(await BotDatabase.get_group_language(chat_id))

                # 检查权限
                if not await has_change_info_permission(bot, chat_id, user_id):
                    await bot.answer_callback_query(
                        call.id, t("common.no_permission", lang)
                    )
                    return

                # 删除消息
                await bot.delete_message(chat_id, message_id)
                await bot.answer_callback_query(call.id, t("common.closed", lang))
            except Exception as e:
                logger.error(f"关闭插件面板失败: {e}")
                try:
                    chat_id = call.message.chat.id
                    lang = normalize_language(
                        await BotDatabase.get_group_language(chat_id)
                    )
                    await bot.answer_callback_query(
                        call.id, t("plugin_settings.close_failed", lang, error=e)
                    )
                except Exception:
                    pass

        @bot.callback_query_handler(func=lambda c: c.data and c.data == "lang_close")
        async def core_handle_language_close_callback(call: types.CallbackQuery):
            try:
                chat_id = call.message.chat.id
                message_id = call.message.message_id
                chat_type = call.message.chat.type
                user_id = call.from_user.id

                if chat_type in ("group", "supergroup"):
                    lang = normalize_language(
                        await BotDatabase.get_group_language(chat_id)
                    )
                    if not await has_change_info_permission(bot, chat_id, user_id):
                        await bot.answer_callback_query(
                            call.id, t("common.no_permission", lang)
                        )
                        return
                else:
                    lang = normalize_language(
                        await BotDatabase.get_user_language(user_id)
                    )

                await bot.delete_message(chat_id, message_id)
                await bot.answer_callback_query(call.id, t("common.closed", lang))
            except Exception as e:
                logger.error(f"关闭语言面板失败: {e}")
                try:
                    await bot.answer_callback_query(call.id)
                except Exception:
                    pass

        # ==================== 中间件分发器 ====================
        @bot.message_handler(func=lambda m: m.text and m.text.startswith("/"))
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

        @bot.message_handler(
            content_types=[
                "text",
                "photo",
                "video",
                "document",
                "sticker",
                "animation",
                "audio",
                "voice",
                "video_note",
            ]
        )
        async def message_dispatcher(message: types.Message):
            """统一消息分发器"""
            await plugin_manager.middleware.dispatch_message(bot, message)

        # 回调分发器（除核心前缀外，其余交由中间件处理）
        @bot.callback_query_handler(
            func=lambda c: not (
                c.data
                and (
                    c.data.startswith("plg_toggle:")
                    or c.data == "plg_close"
                    or c.data == "plg_lang_menu"
                    or c.data == "plg_lang_back"
                    or c.data.startswith("plg_lang_set:")
                    or c.data.startswith("lang_set_user:")
                    or c.data.startswith("lang_set_group:")
                    or c.data == "lang_close"
                )
            )
        )
        async def callback_dispatcher(call: types.CallbackQuery):
            executed = await plugin_manager.middleware.dispatch_callback(bot, call)
            if executed > 0:
                logger.info(f"✨ 回调处理完成，执行了 {executed} 个处理器")

        # Inline Query 分发器（交由中间件处理）
        @bot.inline_handler(func=lambda q: True)
        async def inline_dispatcher(inline_query: types.InlineQuery):
            query = (inline_query.query or "").strip()

            # 用户仅输入 @Bot（query 为空）时，返回占位图片
            if not query:
                logger.debug("Received empty inline query, returning placeholder image")
                placeholder_url = BotConfig.get("inline", {}).get(
                    "empty_placeholder_image",
                    "https://pbs.twimg.com/media/HAckcxubgAARphg?format=jpg&name=4096x4096",
                )
                result = types.InlineQueryResultPhoto(
                    id="1",
                    photo_url=placeholder_url,
                    thumbnail_url=placeholder_url,
                    caption="inline 命令请查阅 /help",
                )
                await bot.answer_inline_query(
                    inline_query.id, [result], cache_time=1, is_personal=True
                )
                return

            executed = await plugin_manager.middleware.dispatch_inline(
                bot, inline_query
            )
            if executed > 0:
                logger.info(f"✨ InlineQuery 处理完成，执行了 {executed} 个处理器")

        # ==================== 启动 Bot ====================
        try:
            logger.success("✨ Bot 启动成功,开始轮询...")
            await bot.polling(
                non_stop=True, allowed_updates=util.update_types, skip_pending=True
            )
        except ApiTelegramException as e:
            logger.opt(exception=e).exception("ApiTelegramException")
        except Exception as e:
            logger.exception(e)


# 自定义过滤器（仅保留内部使用的）
class CommandInChatFilter(SimpleCustomFilter):
    key = "command_in_group"

    async def check(self, message):
        return message.chat.type in ["group", "supergroup"] and message.text.startswith(
            "/"
        )
