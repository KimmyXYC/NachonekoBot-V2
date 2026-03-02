# -*- coding: utf-8 -*-
# @Time    : 2025/7/1 16:43
# @Author  : KimmyXYC
# @File    : ping.py
# @Software: PyCharm

import re
import asyncio
import platform
import ipaddress
from telebot import types
from loguru import logger

# ==================== 插件元数据 ====================
__plugin_name__ = "ping"
__version__ = "1.0.0"
__author__ = "KimmyXYC"
__description__ = "Ping 网络连通性测试"
__commands__ = ["ping"]
__command_category__ = "network"
__command_order__ = {"ping": 10}
__command_descriptions__ = {"ping": "Ping 测试"}
__command_help__ = {"ping": "/ping [IP/Domain] - Ping 测试"}


# ==================== 核心功能 ====================
def is_valid_hostname(hostname):
    """
    验证主机名是否合法
    :param hostname: 要验证的主机名
    :return: 是否合法
    """
    if len(hostname) > 255:
        return False

    # 检查主机名格式
    if hostname[-1] == ".":  # 允许末尾的点，但不作为检查的一部分
        hostname = hostname[:-1]

    # 主机名规则: 字母数字和连字符，段落之间用点分隔
    allowed = re.compile(
        r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63}(?<!-))*$"
    )
    return allowed.match(hostname) is not None


def is_valid_ip(ip):
    """
    验证IP地址是否合法
    :param ip: 要验证的IP地址
    :return: 是否合法
    """
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def is_valid_target(target):
    """
    验证目标地址是否为有效的主机名或IP地址
    :param target: 目标地址
    :return: 是否合法
    """
    return is_valid_hostname(target) or is_valid_ip(target)


async def execute_ping_command(target, count=4, timeout=2):
    """
    执行 ping 命令并返回结果
    :param target: 目标地址（IP 或域名）
    :param count: ping 次数
    :param timeout: 超时时间（秒）
    :return: ping 命令输出结果
    """
    try:
        # 验证目标是否合法
        if not is_valid_target(target):
            return "error.invalid_target_address"

        # 验证ping次数，避免过大的数值
        if not isinstance(count, int) or count <= 0 or count > 10:
            count = 4  # 使用默认值

        # 验证超时时间
        if not isinstance(timeout, int) or timeout <= 0 or timeout > 10:
            timeout = 2  # 使用默认值

        # 根据操作系统构建不同的 ping 命令参数列表
        if platform.system().lower() == "windows":
            cmd_args = ["ping", "-n", str(count), "-w", str(timeout * 1000), target]
        else:  # Linux, macOS, etc.
            cmd_args = ["ping", "-c", str(count), "-W", str(timeout), target]

        # 执行命令，使用参数列表方式避免 shell 注入
        process = await asyncio.create_subprocess_exec(
            *cmd_args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        # 获取命令输出
        stdout, stderr = await process.communicate()

        if stderr:
            logger.error(f"Ping error: {stderr.decode('utf-8', errors='replace')}")
            return f"执行 ping 命令出错: {stderr.decode('utf-8', errors='replace')}"

        # 根据操作系统使用不同的编码解码
        if platform.system().lower() == "windows":
            # Windows中文版通常使用GBK/GB2312编码
            try:
                result = stdout.decode("gbk", errors="replace")
            except UnicodeDecodeError:
                # 如果GBK解码失败，尝试其他常见编码
                encodings = ["gb18030", "gb2312", "utf-8"]
                for encoding in encodings:
                    try:
                        result = stdout.decode(encoding, errors="replace")
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    # 所有尝试都失败，使用replace错误处理模式
                    result = stdout.decode("utf-8", errors="replace")
        else:  # Linux, macOS, etc.
            result = stdout.decode("utf-8", errors="replace")

        return result

    except Exception as e:
        logger.exception(f"执行 ping 命令异常: {str(e)}")
        return f"执行 ping 命令异常: {str(e)}"


async def parse_ping_result(result):
    """
    解析 ping 结果，提取关键信息
    :param result: ping 命令原始输出
    :return: 格式化后的结果摘要
    """
    summary = ""

    # 检查是否包含错误信息
    if (
        "请求找不到主机" in result
        or "请求超时" in result
        or "unknown host" in result
        or "100% packet loss" in result
    ):
        return "❌ Ping 失败：目标主机不可达或网络超时"

    try:
        # 提取 IP 地址
        ip_match = re.search(
            r"Pinging\s+([^\s]+)\s+\[([0-9.]+)]|PING\s+([^\s]+)\s+\(([0-9.]+)\)", result
        )
        if ip_match:
            groups = ip_match.groups()
            if groups[0] and groups[1]:  # Windows 格式
                hostname, ip = groups[0], groups[1]
            elif groups[2] and groups[3]:  # Unix 格式
                hostname, ip = groups[2], groups[3]
            else:
                hostname = ip = "未知"
            summary += f"🎯 目标: {hostname} ({ip})\n"

        # 提取往返时间
        if platform.system().lower() == "windows":
            time_match = re.search(
                r"最短\s*=\s*(\d+)ms，最长\s*=\s*(\d+)ms，平均\s*=\s*(\d+)ms", result
            )
            if time_match:
                min_time, max_time, avg_time = time_match.groups()
                summary += f"⏱ 延迟: 平均 {avg_time}ms (最小 {min_time}ms, 最大 {max_time}ms)\n"
        else:
            time_match = re.search(
                r"min/avg/max/mdev\s*=\s*([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)\s*ms",
                result,
            )
            if time_match:
                min_time, avg_time, max_time, mdev = time_match.groups()
                summary += f"⏱ 延迟: 平均 {avg_time}ms (最小 {min_time}ms, 最大 {max_time}ms)\n"

        # 提取丢包率
        loss_match = re.search(r"(\d+)%\s*(丢失|packet loss)", result)
        if loss_match:
            loss_rate = loss_match.group(1)
            summary += f"📊 丢包率: {loss_rate}%\n"

        if not summary:
            summary = "⚠️ 无法解析 ping 结果"

        # 添加原始结果的简短版本
        if len(result) > 300:
            result = result[:300] + "..."
        summary += f"\n原始结果:\n```\n{result}\n```"

        return summary

    except Exception as e:
        logger.exception(f"解析 ping 结果异常: {str(e)}")
        return f"解析 ping 结果异常: {str(e)}\n\n原始结果:\n```\n{result[:300]}...\n```"


async def handle_ping_command(bot, message: types.Message, target=None):
    """
    处理 ping 命令
    :param bot: Telegram 机器人实例
    :param message: 消息对象
    :param target: 目标地址，如果为 None 则从消息中提取
    """
    # 如果没有提供目标，提示用户
    if not target:
        command_args = message.text.split()
        if len(command_args) >= 2:
            target = command_args[1]
        else:
            await bot.reply_to(
                message, "prompt.ping_target_required"
            )
            return

    # 清理和验证目标地址，防止命令注入
    # 移除任何可能导致命令注入的字符
    target = target.strip()

    # 检查目标是否合法
    if not is_valid_target(target):
        await bot.reply_to(message, "error.invalid_target_address")
        return

    # 发送正在处理的消息
    processing_msg = await bot.reply_to(message, f"⏳ 正在 ping {target}...")

    # 执行 ping 命令
    result = await execute_ping_command(target)

    # 解析结果
    summary = await parse_ping_result(result)

    # 发送结果
    await bot.edit_message_text(
        chat_id=processing_msg.chat.id,
        message_id=processing_msg.message_id,
        text=summary,
        parse_mode="Markdown",
    )


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    async def ping_handler(bot, message: types.Message):
        await handle_ping_command(bot, message)

    middleware.register_command_handler(
        commands=["ping"],
        callback=ping_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["private", "group", "supergroup"],
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
