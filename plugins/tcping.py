# -*- coding: utf-8 -*-
# @Time    : 2025/7/1 17:05
# @Author  : KimmyXYC
# @File    : tcping.py
# @Software: PyCharm

import re
import asyncio
import socket
import time
import ipaddress
from telebot import types
from loguru import logger

__plugin_name__ = "tcping"
__version__ = 1.0
__author__ = "KimmyXYC"
__description__ = "TCP 端口连通性测试"
__commands__ = ["tcping"]


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
    allowed = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63}(?<!-))*$")
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


async def tcp_connect(host, port, timeout=2):
    """
    尝试TCP连接到指定主机和端口
    :param host: 目标主机
    :param port: 目标端口
    :param timeout: 连接超时时间(秒)
    :return: (是否成功, 响应时间, IP地址, TTL, 字节大小)
    """
    try:
        # 解析IP地址
        ip_address = None
        ttl = 0
        packet_size = 0

        # 获取目标的IP地址
        try:
            ip_info = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
            if ip_info and len(ip_info) > 0:
                ip_address = ip_info[0][4][0]  # 提取IP地址
        except socket.gaierror:
            ip_address = None

        start_time = time.time()
        # 创建TCP连接
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout
        )

        # 获取套接字
        sock = writer.get_extra_info('socket')
        if sock:
            # 尝试获取TTL值
            try:
                if ':' in ip_address:  # IPv6
                    ttl = sock.getsockopt(socket.IPPROTO_IPV6, socket.IPV6_UNICAST_HOPS)
                else:  # IPv4
                    ttl = sock.getsockopt(socket.IPPROTO_IP, socket.IP_TTL)
            except (socket.error, OSError):
                ttl = -1

            # 估算数据包大小 (SYN包大小 + IP头 + TCP头)
            if ':' in ip_address:  # IPv6
                packet_size = 40 + 20  # IPv6头(40字节) + TCP头(20字节)
            else:  # IPv4
                packet_size = 20 + 20  # IPv4头(20字节) + TCP头(20字节)

        end_time = time.time()
        response_time = (end_time - start_time) * 1000  # 转换为毫秒

        # 关闭连接
        writer.close()
        await writer.wait_closed()

        return True, response_time, ip_address, ttl, packet_size
    except asyncio.TimeoutError:
        return False, timeout * 1000, None, 0, 0
    except (socket.gaierror, ConnectionRefusedError, OSError) as e:
        logger.error(f"TCP连接错误: {e}")
        return False, 0, None, 0, 0


async def execute_tcping(target, port, count=4, timeout=2):
    """
    执行TCP ping并返回结果
    :param target: 目标主机
    :param port: 目标端口
    :param count: 测试次数
    :param timeout: 超时时间(秒)
    :return: TCP ping结果文本
    """
    # 验证目标是否合法
    if not is_valid_target(target):
        return "❌ 无效的目标地址。请提供有效的域名或IP地址。"

    # 验证端口是否合法
    if not is_valid_port(port):
        return "❌ 无效的端口号。端口号应为1-65535之间的整数。"

    # 验证ping次数，避免过大的数值
    if not isinstance(count, int) or count <= 0 or count > 10:
        count = 4  # 使用默认值

    # 验证超时时间
    if not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > 10:
        timeout = 2  # 使用默认值

    results = []
    successful = 0
    total_time = 0
    min_time = float('inf')
    max_time = 0

    # 获取目标主机的IP地址用于显示在标题
    ip_addr_title = None
    try:
        ip_info = socket.getaddrinfo(target, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if ip_info and len(ip_info) > 0:
            ip_addr_title = ip_info[0][4][0]  # 提取IP地址
    except socket.gaierror:
        ip_addr_title = "未知IP"

    orig_result = f"正在 Ping {target} [{ip_addr_title}:{port}]\n"

    for i in range(count):
        success, response_time, ip_address, ttl, packet_size = await tcp_connect(target, port, timeout)

        if success:
            if ip_address is None:
                ip_address = "未知IP"

            # 更新统计数据
            successful += 1
            total_time += response_time
            min_time = min(min_time, response_time)
            max_time = max(max_time, response_time)

            # 使用类似ping命令的格式
            results.append(f"来自 {ip_address} 的回复: 字节={packet_size} 时间={response_time:.2f}ms TTL={ttl}")
        else:
            if response_time > 0:
                results.append(f"请求超时 (>{timeout}秒)")
            else:
                results.append("连接失败: 目标主机拒绝连接")

    # 添加结果到原始结果文本
    orig_result += "\n".join(results)

    # 如果有成功的连接，添加统计信息
    if successful > 0:
        loss_rate = ((count - successful) / count) * 100
        avg_time = total_time / successful

        orig_result += f"\n\n{target} 的 Ping 统计信息:\n"
        orig_result += f"    数据包: 已发送 = {count}, 已接收 = {successful}, 丢失 = {count - successful} ({loss_rate:.0f}% 丢失)..."
    else:
        orig_result += f"\n\n{target}:{port} 无法访问。"

    # 创建简洁摘要
    summary = ""
    if successful > 0:
        # 添加延迟信息
        summary += f"⏱ 延迟: 平均 {avg_time:.0f}ms (最小 {min_time:.0f}ms, 最大 {max_time:.0f}ms)\n"
        # 添加丢包率
        summary += f"📊 丢包率: {loss_rate:.0f}%\n"
    else:
        summary += f"❌ 连接失败: 目标 {target}:{port} 不可达\n"
        summary += "📊 丢包率: 100%\n"

    # 组合摘要和原始结果，使用HTML格式
    final_result = f"{summary}\n原始结果:\n\n```{orig_result}```"

    return final_result


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
            await bot.reply_to(message, "❌ 无效的端口号。端口号应为1-65535之间的整数。")
            return
    else:
        target = target_arg
        port = 80  # 默认端口

    # 发送处理中消息
    processing_msg = await bot.reply_to(message, "⏳ 正在测试TCP连接，请稍候...")

    try:
        # 执行TCP Ping测试
        result = await execute_tcping(target, port)

        # 更新消息
        await bot.edit_message_text(
            result,
            chat_id=processing_msg.chat.id,
            message_id=processing_msg.message_id,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"TCP Ping 执行错误: {e}")
        await bot.edit_message_text(
            f"❌ 执行TCP Ping时出错: {str(e)}",
            chat_id=processing_msg.chat.id,
            message_id=processing_msg.message_id
        )


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    async def tcping_handler(bot, message: types.Message):
        await handle_tcping_command(bot, message)

    middleware.register_command_handler(
        commands=['tcping'],
        callback=tcping_handler,
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
