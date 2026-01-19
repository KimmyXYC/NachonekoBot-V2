# -*- coding: utf-8 -*-
# @Time    : 2025/7/1 17:41
# @Author  : KimmyXYC
# @File    : trace.py
# @Software: PyCharm

import asyncio
import re
import shutil
from telebot import types
from telebot.async_telebot import AsyncTeleBot
from loguru import logger

# ==================== 插件元数据 ====================
__plugin_name__ = "trace"
__version__ = "2.0.0"
__author__ = "KimmyXYC"
__description__ = "路由追踪工具 (使用 nexttrace)"
__commands__ = ["trace"]
__command_descriptions__ = {
    "trace": "追踪路由"
}
__command_help__ = {
    "trace": "/trace [IP/Domain] [协议类型(T/U)] [端口] - 追踪路由"
}

# ==================== 核心功能 ====================
MAX_TOTAL_TIMEOUT = 180  # 整个跟踪的最大超时时间（秒）

# 支持的协议类型映射到 nexttrace 参数
PROTOCOL_MAP = {
    "icmp": None,  # 默认协议
    "tcp": "T",
    "udp": "U",
}


def validate_target(target: str) -> bool:
    """
    验证目标地址是否合法，防止命令注入
    允许：域名、IPv4、IPv6
    """
    # IPv4 地址验证
    ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    # IPv6 地址验证 (简化版)
    ipv6_pattern = r'^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$'
    # 域名验证 (允许字母、数字、连字符、点)
    domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'

    # 检查是否包含危险字符
    dangerous_chars = [';', '&', '|', '$', '`', '(', ')', '<', '>', '\n', '\r', '\\']
    if any(char in target for char in dangerous_chars):
        return False

    # 验证格式
    if re.match(ipv4_pattern, target) or re.match(ipv6_pattern, target) or re.match(domain_pattern, target):
        return True

    return False


def validate_port(port: int) -> bool:
    """验证端口号是否合法"""
    return 1 <= port <= 65535


async def handle_trace_command(bot: AsyncTeleBot, message: types.Message):
    """处理 trace 命令"""
    command_args = message.text.split()

    if len(command_args) < 2:
        await bot.reply_to(message, "用法: /trace <目标地址> [T/U] [端口]\n"
                                    "T = TCP, U = UDP, 不指定则使用 ICMP\n"
                                    "示例: /trace 1.1.1.1\n"
                                    "      /trace example.com T 443")
        return

    target = command_args[1]

    # 验证目标地址，防止注入
    if not validate_target(target):
        await bot.reply_to(message, "❌ 无效的目标地址，请输入有效的 IP 地址或域名")
        return

    protocol = None  # 默认使用ICMP
    port = None

    # 解析协议参数
    if len(command_args) >= 3:
        protocol_arg = command_args[2].upper()
        if protocol_arg in ['T', 'TCP']:
            protocol = 'T'
        elif protocol_arg in ['U', 'UDP']:
            protocol = 'U'
        else:
            await bot.reply_to(message, "❌ 无效的协议类型，请使用 T (TCP) 或 U (UDP)")
            return

    # 解析端口参数
    if len(command_args) >= 4:
        if not command_args[3].isdigit():
            await bot.reply_to(message, "❌ 端口必须是数字")
            return
        port = int(command_args[3])
        if not validate_port(port):
            await bot.reply_to(message, "❌ 端口号必须在 1-65535 之间")
            return

    # 检查 nexttrace 是否安装
    if not shutil.which("nexttrace"):
        await bot.reply_to(message, "❌ 未找到 nexttrace 命令，请先安装 nexttrace")
        return

    # 发送初始消息
    protocol_name = "ICMP"
    if protocol == 'T':
        protocol_name = "TCP"
    elif protocol == 'U':
        protocol_name = "UDP"

    status_message = await bot.reply_to(message, f"⏳ 正在使用 {protocol_name} 跟踪路由到 {target}...")

    try:
        # 执行跟踪路由
        result = await asyncio.wait_for(
            run_nexttrace(target, protocol, port),
            timeout=MAX_TOTAL_TIMEOUT
        )

        # 格式化并发送结果
        formatted_result = format_nexttrace_output(target, protocol_name, port, result)

        # Telegram 消息长度限制为 4096 字符
        if len(formatted_result) > 4000:
            formatted_result = formatted_result[:4000] + "\n\n... (输出过长已截断)"

        await bot.edit_message_text(
            formatted_result,
            message.chat.id,
            status_message.message_id,
            parse_mode="Markdown"
        )

    except asyncio.TimeoutError:
        await bot.edit_message_text(
            f"❌ 跟踪路由到 {target} 超时，已执行 {MAX_TOTAL_TIMEOUT} 秒",
            message.chat.id,
            status_message.message_id
        )
    except Exception as e:
        logger.error(f"Traceroute error: {str(e)}")
        await bot.edit_message_text(
            f"❌ 跟踪路由失败: {str(e)}",
            message.chat.id,
            status_message.message_id
        )


async def run_nexttrace(target: str, protocol: str = None, port: int = None) -> str:
    """
    执行 nexttrace 命令
    使用 subprocess 安全地调用命令，防止注入
    """
    # 构建命令参数列表（使用列表方式防止 shell 注入）
    cmd = ["nexttrace"]

    # 添加协议参数
    if protocol:
        cmd.extend(["-M", protocol])

    # 添加端口参数
    if port:
        cmd.extend(["-p", str(port)])

    # 添加目标地址
    cmd.append(target)

    logger.info(f"执行命令: {' '.join(cmd)}")

    try:
        # 使用 asyncio.create_subprocess_exec 安全地执行命令
        # 不使用 shell=True，避免命令注入风险
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # 等待命令执行完成
        stdout, stderr = await process.communicate()

        # 解码输出
        output = stdout.decode('utf-8', errors='ignore')
        error_output = stderr.decode('utf-8', errors='ignore')

        if process.returncode != 0:
            logger.error(f"nexttrace 执行失败，返回码: {process.returncode}")
            logger.error(f"错误输出: {error_output}")
            if error_output:
                raise Exception(f"nexttrace 执行失败: {error_output}")
            else:
                raise Exception(f"nexttrace 执行失败，返回码: {process.returncode}")

        logger.debug(f"nexttrace 输出长度: {len(output)} 字符")
        return output

    except FileNotFoundError:
        raise Exception("未找到 nexttrace 命令")
    except Exception as e:
        logger.error(f"执行 nexttrace 时发生错误: {str(e)}")
        raise


def format_nexttrace_output(target: str, protocol: str, port: int, output: str) -> str:
    """格式化 nexttrace 输出"""
    header = f"📡 *路由追踪结果*\n\n"
    header += f"目标: `{target}`\n"
    header += f"协议: {protocol}"

    if port:
        header += f" 端口: {port}"

    header += "\n\n```\n"

    # 清理输出中的 ANSI 转义序列
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    clean_output = ansi_escape.sub('', output)

    # 提取 MapTrace URL
    maptrace_url = None
    url_pattern = r'MapTrace URL:\s*(https?://[^\s]+)'
    url_match = re.search(url_pattern, clean_output)

    if url_match:
        maptrace_url = url_match.group(1)
        # 从输出中移除 MapTrace URL 行，避免重复显示
        clean_output = re.sub(r'MapTrace URL:.*\n?', '', clean_output)

    # 移除末尾多余的空行
    clean_output = clean_output.rstrip()

    footer = "\n```"

    # 如果找到 MapTrace URL，添加到代码块后面
    if maptrace_url:
        footer += f"\n\n🗺️ [查看可视化路由图]({maptrace_url})"

    return header + clean_output + footer


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    async def trace_handler(bot, message: types.Message):
        await handle_trace_command(bot, message)

    middleware.register_command_handler(
        commands=['trace'],
        callback=trace_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=['private', 'group', 'supergroup']
    )

    logger.info(f"✅ {__plugin_name__} 插件已注册 - 支持命令: {', '.join(__commands__)}")

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
