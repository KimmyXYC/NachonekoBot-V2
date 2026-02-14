# -*- coding: utf-8 -*-
# @Time    : 2026/1/19 20:05
# @Author  : KimmyXYC
# @File    : mcstatus.py
# @Software: PyCharm
import asyncio
from mcstatus import JavaServer, BedrockServer
from telebot import types
from loguru import logger

# ==================== 插件元数据 ====================
__plugin_name__ = "mcstatus"
__version__ = "1.0.0"
__author__ = "KimmyXYC"
__description__ = "Minecraft 服务器状态查询"
__commands__ = ["mc", "mcje", "mcbe"]
__command_descriptions__ = {
    "mc": "查询 Minecraft 服务器状态（自动识别 Java 版/基岩版）",
    "mcje": "查询 Minecraft Java 版服务器状态",
    "mcbe": "查询 Minecraft 基岩版服务器状态",
}
__command_help__ = {
    "mc": "/mcstatus [服务器地址:端口] - 查询 Minecraft 服务器状态（自动识别 Java 版/基岩版）\nInline: @NachoNekoX_bot mc [服务器地址:端口]",
    "mcje": "/mcje [服务器地址:端口] - 查询 Minecraft Java 版服务器状态\nInline: @NachoNekoX_bot mcje [服务器地址:端口]",
    "mcbe": "/mcbe [服务器地址:端口] - 查询 Minecraft 基岩版服务器状态\nInline: @NachoNekoX_bot mcbe [服务器地址:端口]",
}


# ==================== 核心功能 ====================
async def query_java_server(address: str) -> str:
    """查询 Minecraft Java 版服务器状态"""
    try:
        # 在异步环境中运行同步的 mcstatus 代码
        loop = asyncio.get_event_loop()
        server = await loop.run_in_executor(None, JavaServer.lookup, address)
        status = await loop.run_in_executor(None, server.status)

        msg_out = []
        msg_out.append("🎮 Minecraft Java 版服务器状态")
        msg_out.append("━━━━━━━━━━━━━━━━━━━━")
        msg_out.append(f"📍 服务器地址：{address}")
        msg_out.append(f"👥 在线玩家：{status.players.online}/{status.players.max}")
        msg_out.append(f"📊 版本：{status.version.name}")
        msg_out.append(f"⏱️ 延迟：{status.latency:.2f} ms")

        # MOTD (服务器描述)
        if hasattr(status, "description") and status.description:
            motd = status.description
            if isinstance(motd, dict):
                motd_text = motd.get("text", "") or motd.get("extra", "")
            else:
                motd_text = str(motd)
            if motd_text:
                msg_out.append(f"📝 MOTD：{motd_text[:100]}")

        # 在线玩家列表
        if status.players.sample:
            player_names = [player.name for player in status.players.sample[:10]]
            msg_out.append(f"🎯 在线玩家：{', '.join(player_names)}")
            if len(status.players.sample) > 10:
                msg_out.append(f"   ... 还有 {len(status.players.sample) - 10} 位玩家")

        return "\n".join(msg_out)

    except asyncio.TimeoutError:
        return f"出错了呜呜呜 ~ 连接服务器 {address} 超时"
    except ConnectionRefusedError:
        return f"出错了呜呜呜 ~ 无法连接到服务器 {address}，连接被拒绝"
    except Exception as e:
        error_msg = str(e)
        if "timed out" in error_msg.lower():
            return f"出错了呜呜呜 ~ 连接服务器 {address} 超时"
        elif (
            "name or service not known" in error_msg.lower()
            or "nodename nor servname provided" in error_msg.lower()
        ):
            return f"出错了呜呜呜 ~ 无法解析服务器地址 {address}"
        else:
            return f"出错了呜呜呜 ~ 查询失败: {error_msg}"


async def query_bedrock_server(address: str) -> str:
    """查询 Minecraft 基岩版服务器状态"""
    try:
        # 在异步环境中运行同步的 mcstatus 代码
        loop = asyncio.get_event_loop()
        server = await loop.run_in_executor(None, BedrockServer.lookup, address)
        status = await loop.run_in_executor(None, server.status)

        msg_out = []
        msg_out.append("🎮 Minecraft 基岩版服务器状态")
        msg_out.append("━━━━━━━━━━━━━━━━━━━━")
        msg_out.append(f"📍 服务器地址：{address}")
        msg_out.append(f"👥 在线玩家：{status.players_online}/{status.players_max}")
        msg_out.append(f"📊 版本：{status.version.version}")
        msg_out.append(f"⏱️ 延迟：{status.latency:.2f} ms")

        # MOTD
        if hasattr(status, "motd") and status.motd:
            msg_out.append(f"📝 MOTD：{status.motd[:100]}")

        # 游戏模式
        if hasattr(status, "gamemode") and status.gamemode:
            msg_out.append(f"🎯 游戏模式：{status.gamemode}")

        # 地图名称
        if hasattr(status, "map") and status.map:
            msg_out.append(f"🗺️ 地图：{status.map}")

        return "\n".join(msg_out)

    except asyncio.TimeoutError:
        return f"出错了呜呜呜 ~ 连接服务器 {address} 超时"
    except ConnectionRefusedError:
        return f"出错了呜呜呜 ~ 无法连接到服务器 {address}，连接被拒绝"
    except Exception as e:
        error_msg = str(e)
        if "timed out" in error_msg.lower():
            return f"出错了呜呜呜 ~ 连接服务器 {address} 超时"
        elif (
            "name or service not known" in error_msg.lower()
            or "nodename nor servname provided" in error_msg.lower()
        ):
            return f"出错了呜呜呜 ~ 无法解析服务器地址 {address}"
        else:
            return f"出错了呜呜呜 ~ 查询失败: {error_msg}"


async def query_auto_server(address: str) -> str:
    """自动识别并查询 Minecraft 服务器状态（先尝试 Java 版，失败后尝试基岩版）"""
    try:
        # 先尝试 Java 版查询
        loop = asyncio.get_event_loop()
        server = await loop.run_in_executor(None, JavaServer.lookup, address)
        status = await loop.run_in_executor(None, server.status)

        msg_out = []
        msg_out.append("🎮 Minecraft Java 版服务器状态")
        msg_out.append("━━━━━━━━━━━━━━━━━━━━")
        msg_out.append(f"📍 服务器地址：{address}")
        msg_out.append(f"👥 在线玩家：{status.players.online}/{status.players.max}")
        msg_out.append(f"📊 版本：{status.version.name}")
        msg_out.append(f"⏱️ 延迟：{status.latency:.2f} ms")

        # MOTD (服务器描述)
        if hasattr(status, "description") and status.description:
            motd = status.description
            if isinstance(motd, dict):
                motd_text = motd.get("text", "") or motd.get("extra", "")
            else:
                motd_text = str(motd)
            if motd_text:
                msg_out.append(f"📝 MOTD：{motd_text[:100]}")

        # 在线玩家列表
        if status.players.sample:
            player_names = [player.name for player in status.players.sample[:10]]
            msg_out.append(f"🎯 在线玩家：{', '.join(player_names)}")
            if len(status.players.sample) > 10:
                msg_out.append(f"   ... 还有 {len(status.players.sample) - 10} 位玩家")

        return "\n".join(msg_out)

    except Exception as java_error:
        # Java 版查询失败，尝试基岩版
        try:
            loop = asyncio.get_event_loop()
            server = await loop.run_in_executor(None, BedrockServer.lookup, address)
            status = await loop.run_in_executor(None, server.status)

            msg_out = []
            msg_out.append("🎮 Minecraft 基岩版服务器状态")
            msg_out.append("━━━━━━━━━━━━━━━━━━━━")
            msg_out.append(f"📍 服务器地址：{address}")
            msg_out.append(f"👥 在线玩家：{status.players_online}/{status.players_max}")
            msg_out.append(f"📊 版本：{status.version.version}")
            msg_out.append(f"⏱️ 延迟：{status.latency:.2f} ms")

            # MOTD
            if hasattr(status, "motd") and status.motd:
                msg_out.append(f"📝 MOTD：{status.motd[:100]}")

            # 游戏模式
            if hasattr(status, "gamemode") and status.gamemode:
                msg_out.append(f"🎯 游戏模式：{status.gamemode}")

            # 地图名称
            if hasattr(status, "map") and status.map:
                msg_out.append(f"🗺️ 地图：{status.map}")

            return "\n".join(msg_out)

        except Exception:
            # 两种方式都失败，返回错误信息
            error_msg = str(java_error)
            if "timed out" in error_msg.lower():
                return f"出错了呜呜呜 ~ 连接服务器 {address} 超时"
            elif (
                "name or service not known" in error_msg.lower()
                or "nodename nor servname provided" in error_msg.lower()
            ):
                return f"出错了呜呜呜 ~ 无法解析服务器地址 {address}"
            else:
                return f"出错了呜呜呜 ~ 无法连接到服务器 {address}（已尝试 Java 版和基岩版）"


async def handle_mcstatus_command(
    bot, message: types.Message, server_type: str = "java"
):
    """
    处理 MC 服务器状态查询命令
    :param bot: Bot 对象
    :param message: 消息对象
    :param server_type: 服务器类型 (java/bedrock)
    :return:
    """
    command_args = message.text.split()
    if len(command_args) < 2:
        await bot.reply_to(
            message,
            "请提供服务器地址，格式：/mc 服务器地址:端口\n例如：/mc mc.hypixel.net",
        )
        return

    server_address = command_args[1]

    msg = await bot.reply_to(message, f"正在查询服务器: {server_address} ...")

    if server_type == "bedrock":
        result_text = await query_bedrock_server(server_address)
    else:
        result_text = await query_java_server(server_address)

    await bot.edit_message_text(result_text, message.chat.id, msg.message_id)


async def handle_mcje_command(bot, message: types.Message):
    """处理 Java 版服务器查询命令"""
    await handle_mcstatus_command(bot, message, server_type="java")


async def handle_mcbe_command(bot, message: types.Message):
    """处理基岩版服务器查询命令"""
    await handle_mcstatus_command(bot, message, server_type="bedrock")


async def handle_mcstatus_auto_command(bot, message: types.Message):
    """处理自动识别服务器类型的查询命令"""
    command_args = message.text.split()
    if len(command_args) < 2:
        await bot.reply_to(
            message,
            "请提供服务器地址，格式：/mc 服务器地址:端口\n例如：/mc mc.hypixel.net",
        )
        return

    server_address = command_args[1]

    msg = await bot.reply_to(message, f"正在查询服务器: {server_address} ...")

    result_text = await query_auto_server(server_address)

    await bot.edit_message_text(result_text, message.chat.id, msg.message_id)


async def handle_mcstatus_inline_query(bot, inline_query: types.InlineQuery):
    """处理 Inline Query：@Bot mcstatus/mcje/mcbe [服务器地址]"""
    query = (inline_query.query or "").strip()
    args = query.split()

    if len(args) < 2:
        text = "请提供服务器地址\n用法：mc [服务器地址:端口] (自动识别) 或 mcje/mcbe [服务器地址:端口] (指定版本)"
        result = types.InlineQueryResultArticle(
            id="mcstatus_usage",
            title="MC 服务器状态查询",
            description="用法：mc/mcje/mcbe [服务器地址:端口]",
            input_message_content=types.InputTextMessageContent(text),
        )
        await bot.answer_inline_query(
            inline_query.id, [result], cache_time=1, is_personal=True
        )
        return

    command = args[0].lower()
    server_address = args[1]

    # 确定服务器类型和查询方式
    if command == "mcbe":
        result_text = await query_bedrock_server(server_address)
        title_prefix = "基岩版"
    elif command == "mcje":
        result_text = await query_java_server(server_address)
        title_prefix = "Java版"
    else:  # mcstatus - 自动识别
        result_text = await query_auto_server(server_address)
        title_prefix = "自动识别"

    result = types.InlineQueryResultArticle(
        id=f"mcstatus_{server_address}",
        title=f"MC {title_prefix}：{server_address}",
        description="发送查询结果",
        input_message_content=types.InputTextMessageContent(result_text),
    )
    await bot.answer_inline_query(
        inline_query.id, [result], cache_time=1, is_personal=True
    )


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    # 注册 mcstatus 命令（自动识别版本）
    middleware.register_command_handler(
        commands=["mc"],
        callback=handle_mcstatus_auto_command,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["private", "group", "supergroup"],
    )

    # 注册 mcje 命令（Java 版）
    middleware.register_command_handler(
        commands=["mcje"],
        callback=handle_mcje_command,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["private", "group", "supergroup"],
    )

    # 注册 mcbe 命令（基岩版）
    middleware.register_command_handler(
        commands=["mcbe"],
        callback=handle_mcbe_command,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["private", "group", "supergroup"],
    )

    # 注册 Inline Query 处理器
    middleware.register_inline_handler(
        callback=handle_mcstatus_inline_query,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        func=lambda q: (
            bool(getattr(q, "query", None))
            and q.query.strip().lower().split()[0] in ["mc", "mcje", "mcbe"]
        ),
    )

    logger.info(
        f"✅ {__plugin_name__} 插件已注册 - 支持命令: {', '.join(__commands__)}"
    )


# ==================== 插件信息 ====================
def get_plugin_info() -> dict:
    """
    获取插件信息
    """
    return {
        "name": __plugin_name__,
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "commands": __commands__,
    }


# 保持全局 bot 引用
bot_instance = None
