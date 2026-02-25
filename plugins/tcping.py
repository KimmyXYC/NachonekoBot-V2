# -*- coding: utf-8 -*-
# @Time    : 2025/7/1 17:05
# @Author  : KimmyXYC
# @File    : tcping.py
# @Software: PyCharm

import re
import asyncio
import ipaddress
from telebot import types
from loguru import logger

__plugin_name__ = "tcping"
__version__ = "1.1.0"
__author__ = "KimmyXYC"
__description__ = "TCP 端口连通性测试"
__commands__ = ["tcping"]
__command_category__ = "network"
__command_order__ = {"tcping": 20}
__command_descriptions__ = {"tcping": "TCP Ping 测试"}
__command_help__ = {"tcping": "/tcping [IP/Domain]:[Port] - TCP Ping 测试"}


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


def is_valid_port(port):
    """
    验证端口号是否合法
    :param port: 要验证的端口号
    :return: 是否合法
    """
    try:
        port = int(port)
        return 1 <= port <= 65535
    except (ValueError, TypeError):
        return False


def is_valid_target(target):
    """
    验证目标地址是否为有效的主机名或IP地址
    :param target: 目标地址
    :return: 是否合法
    """
    return is_valid_hostname(target) or is_valid_ip(target)


async def execute_tcping_command(target, port, count=4, timeout=3):
    """
    执行 tcping 命令并返回结果
    :param target: 目标地址（IP 或域名）
    :param port: 目标端口
    :param count: tcping 次数
    :param timeout: 超时时间（秒）
    :return: tcping 命令输出结果
    """
    try:
        # 验证目标是否合法
        if not is_valid_target(target):
            return "❌ 无效的目标地址。请提供有效的域名或IP地址。"

        # 验证端口是否合法
        if not is_valid_port(port):
            return "❌ 无效的端口号。端口号应为1-65535之间的整数。"

        # 验证tcping次数，避免过大的数值
        if not isinstance(count, int) or count <= 0 or count > 10:
            count = 4  # 使用默认值

        # 验证超时时间
        if not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > 10:
            timeout = 3  # 使用默认值

        # 构建 tcping 命令参数列表，使用参数列表方式避免 shell 注入
        # tcping [-d] [-c] [-C] [-w sec] [-q num] [-x count] ipaddress [port]
        cmd_args = [
            "tcping",
            "-w",
            str(int(timeout)),  # 等待时间（秒）
            "-x",
            str(count),  # 重复次数
            target,  # 目标地址
            str(port),  # 端口
        ]

        # 执行命令，使用参数列表方式避免 shell 注入
        process = await asyncio.create_subprocess_exec(
            *cmd_args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        # 获取命令输出
        stdout, stderr = await process.communicate()

        if stderr:
            logger.error(f"TCPing error: {stderr.decode('utf-8', errors='replace')}")
            return (
                f"❌ 执行 tcping 命令出错: {stderr.decode('utf-8', errors='replace')}"
            )

        # 解码输出
        result = stdout.decode("utf-8", errors="replace")

        return result

    except FileNotFoundError:
        logger.error("tcping 命令未找到，请确保已安装 tcping")
        return "❌ 未找到 tcping 命令。请确保系统已安装 tcping 工具。\n\n安装方法：\nDebian/Ubuntu: apt-get install tcptraceroute\nCentOS/RHEL: yum install tcptraceroute\nmacOS: brew install tcping"
    except Exception as e:
        logger.exception(f"执行 tcping 命令异常: {str(e)}")
        return f"❌ 执行 tcping 命令异常: {str(e)}"


async def parse_tcping_result(result):
    """
    解析 tcping 结果，提取关键信息
    :param result: tcping 命令原始输出
    :return: 格式化后的结果摘要
    """
    summary = ""

    try:
        # 提取统计信息
        lines = result.strip().split("\n")

        # 统计成功和失败的连接
        successful = 0
        failed = 0
        times = []

        for line in lines:
            # 匹配成功的连接: "port 80 open" 或包含时间信息
            if "open" in line.lower() or "ms" in line.lower():
                successful += 1
                # 尝试提取时间
                time_match = re.search(r"(\d+\.?\d*)\s*ms", line)
                if time_match:
                    times.append(float(time_match.group(1)))
            elif (
                "closed" in line.lower()
                or "timeout" in line.lower()
                or "failed" in line.lower()
            ):
                failed += 1

        total = successful + failed

        if total > 0:
            loss_rate = (failed / total) * 100

            if successful > 0:
                avg_time = sum(times) / len(times) if times else 0
                min_time = min(times) if times else 0
                max_time = max(times) if times else 0

                summary += f"⏱ 延迟: 平均 {avg_time:.0f}ms"
                if times:
                    summary += f" (最小 {min_time:.0f}ms, 最大 {max_time:.0f}ms)"
                summary += "\n"

            summary += f"📊 丢包率: {loss_rate:.0f}%\n"
        else:
            summary = "⚠️ 无法解析 tcping 结果\n"

        # 添加原始结果
        if len(result) > 500:
            result = result[:500] + "..."
        summary += f"\n原始结果:\n```\n{result}\n```"

        return summary

    except Exception as e:
        logger.exception(f"解析 tcping 结果异常: {str(e)}")
        return f"⚠️ 解析 tcping 结果异常: {str(e)}\n\n原始结果:\n```\n{result[:300]}...\n```"


async def handle_tcping_command(bot, message: types.Message):
    """
    处理tcping命令
    :param bot: 机器人实例
    :param message: 消息对象
    """
    command_args = message.text.split()

    if len(command_args) < 2:
        await bot.reply_to(message, "❌ 请提供目标主机和端口，格式: /tcping 主机:端口")
        return

    # 解析目标和端口
    target_arg = command_args[1]
    if ":" in target_arg:
        target, port = target_arg.rsplit(":", 1)
        try:
            port = int(port)
        except ValueError:
            await bot.reply_to(
                message, "❌ 无效的端口号。端口号应为1-65535之间的整数。"
            )
            return
    else:
        target = target_arg
        port = 80  # 默认端口

    # 发送处理中消息
    processing_msg = await bot.reply_to(
        message, f"⏳ 正在测试 {target}:{port} 的TCP连接，请稍候..."
    )

    try:
        # 执行 tcping 命令
        result = await execute_tcping_command(target, port)

        # 解析结果
        summary = await parse_tcping_result(result)

        # 更新消息
        await bot.edit_message_text(
            summary,
            chat_id=processing_msg.chat.id,
            message_id=processing_msg.message_id,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(f"TCP Ping 执行错误: {e}")
        await bot.edit_message_text(
            f"❌ 执行 tcping 时出错: {str(e)}",
            chat_id=processing_msg.chat.id,
            message_id=processing_msg.message_id,
        )


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    async def tcping_handler(bot, message: types.Message):
        await handle_tcping_command(bot, message)

    middleware.register_command_handler(
        commands=["tcping"],
        callback=tcping_handler,
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
