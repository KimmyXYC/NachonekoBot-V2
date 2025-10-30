# -*- coding: utf-8 -*-
# @Time    : 2025/7/1 17:41
# @Author  : KimmyXYC
# @File    : trace.py
# @Software: PyCharm

import asyncio
import time
import socket
import requests
from io import StringIO
from concurrent.futures import ThreadPoolExecutor
from scapy.layers.inet import IP, ICMP, TCP, UDP
from scapy.layers.inet6 import IPv6, ICMPv6EchoRequest
from scapy.sendrecv import sr1
from scapy.volatile import RandShort
from telebot import types
from telebot.async_telebot import AsyncTeleBot
from loguru import logger

# ==================== 插件元数据 ====================
__plugin_name__ = "trace"
__version__ = 1.0
__author__ = "KimmyXYC"
__description__ = "路由追踪工具"
__commands__ = ["trace"]
__command_descriptions__ = {
    "trace": "追踪路由"
}
__command_help__ = {
    "trace": "/trace [IP/Domain] - 追踪路由"
}


# ==================== 核心功能 ====================
# 主机名解析缓存
HOSTNAME_CACHE = {}

MAX_HOPS = 30
TIMEOUT = 3  # 减少每个包的超时时间
TRIES = 3    # 减少尝试次数，提高速度
MAX_TOTAL_TIMEOUT = 180  # 整个跟踪的最大超时时间（秒）

# 支持的协议类型
PROTOCOLS = {
    "icmp": "ICMP",
    "tcp": "TCP",
    "udp": "UDP",
    "icmp6": "ICMPv6"
}

async def handle_trace_command(bot: AsyncTeleBot, message: types.Message):
    """处理 trace 命令"""
    command_args = message.text.split()

    if len(command_args) < 2:
        await bot.reply_to(message, "用法: /trace <目标地址> [协议类型(icmp/tcp/udp/icmp6)] [端口(TCP/UDP)]")
        return

    target = command_args[1]
    protocol = "icmp"  # 默认使用ICMP
    port = 80  # 默认端口

    if len(command_args) >= 3 and command_args[2].lower() in PROTOCOLS:
        protocol = command_args[2].lower()

    if len(command_args) >= 4 and command_args[3].isdigit():
        port = int(command_args[3])

    # 发送初始消息
    status_message = await bot.reply_to(message, f"⏳ 正在启动 {PROTOCOLS[protocol]} 跟踪路由到 {target}...")

    # 为了确保网络操作不会阻塞整个机器人，我们需要创建一个线程池执行器
    with ThreadPoolExecutor():
        try:
            # 设置一个超时，防止跟踪永远不返回
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    perform_traceroute,
                    target=target,
                    protocol=protocol,
                    port=port
                ),
                timeout=MAX_TOTAL_TIMEOUT
            )

            # 更新消息，显示结果
            formatted_result = format_trace_results(target, protocol, port, result)
            await bot.edit_message_text(
                formatted_result,
                message.chat.id,
                status_message.message_id,
                parse_mode="Markdown"
            )

        except asyncio.TimeoutError:
            await bot.edit_message_text(
                f"❌ 跟踪路由到 {target} 超时，已执行 {MAX_TOTAL_TIMEOUT} 秒。请尝试使用不同的协议或确认目标是否可达。",
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

def perform_traceroute(target, protocol="icmp", port=80):
    """执行跟踪路由"""
    results = []
    start_time = time.time()

    logger.debug(f"开始执行跟踪路由: 目标={target}, 协议={protocol}, 端口={port}")

    # 解析目标主机
    try:
        target_ip = socket.gethostbyname(target)
        is_ipv6 = False
        logger.debug(f"解析目标主机成功: {target} -> {target_ip} (IPv4)")
    except socket.gaierror:
        # 尝试 IPv6 解析
        try:
            socket.getaddrinfo(target, None, socket.AF_INET6)
            target_ip = target
            is_ipv6 = True
            if protocol not in ["icmp6"]:
                protocol = "icmp6"  # 强制使用 ICMPv6
            logger.debug(f"解析目标主机成功: {target} (IPv6), 已自动切换协议为 {protocol}")
        except socket.gaierror:
            logger.error(f"无法解析主机: {target}")
            raise Exception(f"无法解析主机: {target}")

    # 根据协议类型选择不同的跟踪路由方法
    try:
        if is_ipv6:
            logger.debug("使用 ICMPv6 协议执行跟踪路由")
            results = icmpv6_traceroute(target_ip)
        elif protocol == "icmp":
            logger.debug("使用 ICMP 协议执行跟踪路由")
            results = icmp_traceroute(target_ip)
        elif protocol == "tcp":
            logger.debug(f"使用 TCP 协议执行跟踪路由，端口: {port}")
            results = tcp_traceroute(target_ip, port)
        elif protocol == "udp":
            logger.debug(f"使用 UDP 协议执行跟踪路由，端口: {port}")
            results = udp_traceroute(target_ip, port)
    except Exception as e:
        logger.error(f"跟踪路由协议错误: {str(e)}")
        # 如果当前协议失败，尝试使用 ICMP 协议（最可靠）
        if protocol != "icmp" and not is_ipv6:
            logger.info("尝试使用 ICMP 协议进行跟踪路由")
            results = icmp_traceroute(target_ip)

    total_time = time.time() - start_time
    logger.debug(f"跟踪路由完成，总用时: {total_time:.2f} 秒，共 {len(results)} 跳")

    # 添加总执行时间到结果
    results.append({
        "total_time": total_time
    })

    return results

def icmp_traceroute(target_ip):
    """ICMP 跟踪路由（并行版本，主机名解析与下一跃点并行）"""
    results = []
    previous_ip = None
    hostname_futures = {}  # 存储主机名解析的futures
    logger.debug(f"开始 ICMP 跟踪路由(并行版本): 目标={target_ip}")

    with ThreadPoolExecutor() as hostname_executor:
        for ttl in range(1, MAX_HOPS + 1):
            # 定义如何创建 ICMP 数据包
            def create_icmp_packet(ttl_value, _attempt):
                return IP(dst=target_ip, ttl=ttl_value) / ICMP()

            # 使用辅助函数处理当前跃点，同时传递前一个跃点的IP
            hop_result, reached_target = _process_parallel_hop(ttl, target_ip, "ICMP", create_icmp_packet, previous_ip)

            # 收集需要解析主机名的唯一IP地址
            unique_ips = set()
            for resp in hop_result["responses"]:
                if resp["ip"] != "*" and not resp["hostname"] and resp["ip"] not in hostname_futures:
                    unique_ips.add(resp["ip"])

            # 提交主机名解析任务（与下一跃点并行）
            for ip in unique_ips:
                if ip not in hostname_futures:
                    hostname_futures[ip] = hostname_executor.submit(resolve_hostname, ip)

            # 更新前一个跃点的IP地址（用于下一个跃点查询地理位置）
            valid_responses = [r for r in hop_result["responses"] if r["ip"] != "*"]
            if valid_responses:
                previous_ip = valid_responses[0]["ip"]

            # 将跃点结果添加到结果列表
            results.append(hop_result)

            if reached_target:
                logger.debug(f"ICMP 跟踪: 达到目标 IP={target_ip}, 跃点={ttl}, 提前结束")
                break

            logger.debug(f"ICMP 跟踪: 完成跃点={ttl}, 共收集 {len(hop_result['responses'])} 个响应")

        # 处理完所有跃点后，获取所有主机名解析结果并更新
        for result in results:
            for resp in result["responses"]:
                if resp["ip"] != "*" and resp["ip"] in hostname_futures:
                    try:
                        resp["hostname"] = hostname_futures[resp["ip"]].result()
                    except Exception as e:
                        logger.error(f"获取主机名解析结果失败: {resp['ip']} - {str(e)}")
                        resp["hostname"] = ""

    logger.debug(f"ICMP 跟踪路由完成: 共 {len(results)} 跳")
    return results

def icmpv6_traceroute(target_ip):
    """ICMPv6 跟踪路由（并行版本，主机名解析与下一跃点并行）"""
    results = []
    previous_ip = None
    hostname_futures = {}  # 存储主机名解析的futures
    logger.debug(f"开始 ICMPv6 跟踪路由(并行版本): 目标={target_ip}")

    with ThreadPoolExecutor() as hostname_executor:
        for ttl in range(1, MAX_HOPS + 1):
            # 定义如何创建 ICMPv6 数据包
            def create_icmpv6_packet(ttl_value, _attempt):
                return IPv6(dst=target_ip, hlim=ttl_value) / ICMPv6EchoRequest()

            # 使用辅助函数处理当前跃点，同时传递前一个跃点的IP
            hop_result, reached_target = _process_parallel_hop(ttl, target_ip, "ICMPv6", create_icmpv6_packet, previous_ip)

            # 收集需要解析主机名的唯一IP地址
            unique_ips = set()
            for resp in hop_result["responses"]:
                if resp["ip"] != "*" and not resp["hostname"] and resp["ip"] not in hostname_futures:
                    unique_ips.add(resp["ip"])

            # 提交主机名解析任务（与下一跃点并行）
            for ip in unique_ips:
                if ip not in hostname_futures:
                    hostname_futures[ip] = hostname_executor.submit(resolve_hostname, ip)

            # 更新前一个跃点的IP地址（用于下一个跃点查询地理位置）
            valid_responses = [r for r in hop_result["responses"] if r["ip"] != "*"]
            if valid_responses:
                previous_ip = valid_responses[0]["ip"]

            # 将跃点结果添加到结果列表
            results.append(hop_result)

            if reached_target:
                logger.debug(f"ICMPv6 跟踪: 达到目标 IP={target_ip}, 跃点={ttl}, 提前结束")
                break

            logger.debug(f"ICMPv6 跟踪: 完成跃点={ttl}, 共收集 {len(hop_result['responses'])} 个响应")

        # 处理完所有跃点后，获取所有主机名解析结果并更新
        for result in results:
            for resp in result["responses"]:
                if resp["ip"] != "*" and resp["ip"] in hostname_futures:
                    try:
                        resp["hostname"] = hostname_futures[resp["ip"]].result()
                    except Exception as e:
                        logger.error(f"获取主机名解析结果失败: {resp['ip']} - {str(e)}")
                        resp["hostname"] = ""

    logger.debug(f"ICMPv6 跟踪路由完成: 共 {len(results)} 跳")
    return results

def tcp_traceroute(target_ip, port=80):
    """TCP 跟踪路由（并行版本，主机名解析与下一跃点并行）"""
    results = []
    previous_ip = None
    hostname_futures = {}  # 存储主机名解析的futures
    logger.debug(f"开始 TCP 跟踪路由(并行版本): 目标={target_ip}, 端口={port}")

    with ThreadPoolExecutor() as hostname_executor:
        for ttl in range(1, MAX_HOPS + 1):
            # 定义如何创建 TCP 数据包
            def create_tcp_packet(ttl_value, _attempt):
                # 使用随机源端口
                sport = RandShort()
                return IP(dst=target_ip, ttl=ttl_value) / TCP(sport=sport, dport=port, flags="S")

            # 使用辅助函数处理当前跃点，同时传递前一个跃点的IP
            hop_result, reached_target = _process_parallel_hop(ttl, target_ip, "TCP", create_tcp_packet, previous_ip)

            # 收集需要解析主机名的唯一IP地址
            unique_ips = set()
            for resp in hop_result["responses"]:
                if resp["ip"] != "*" and not resp["hostname"] and resp["ip"] not in hostname_futures:
                    unique_ips.add(resp["ip"])

            # 提交主机名解析任务（与下一跃点并行）
            for ip in unique_ips:
                if ip not in hostname_futures:
                    hostname_futures[ip] = hostname_executor.submit(resolve_hostname, ip)

            # 更新前一个跃点的IP地址（用于下一个跃点查询地理位置）
            valid_responses = [r for r in hop_result["responses"] if r["ip"] != "*"]
            if valid_responses:
                previous_ip = valid_responses[0]["ip"]

            # 将跃点结果添加到结果列表
            results.append(hop_result)

            if reached_target:
                logger.debug(f"TCP 跟踪: 达到目标 IP={target_ip}, 跃点={ttl}, 提前结束")
                break

            logger.debug(f"TCP 跟踪: 完成跃点={ttl}, 共收集 {len(hop_result['responses'])} 个响应")

        # 处理完所有跃点后，获取所有主机名解析结果并更新
        for result in results:
            for resp in result["responses"]:
                if resp["ip"] != "*" and resp["ip"] in hostname_futures:
                    try:
                        resp["hostname"] = hostname_futures[resp["ip"]].result()
                    except Exception as e:
                        logger.error(f"获取主机名解析结果失败: {resp['ip']} - {str(e)}")
                        resp["hostname"] = ""

    logger.debug(f"TCP 跟踪路由完成: 共 {len(results)} 跳")
    return results

def udp_traceroute(target_ip, port=53):
    """UDP 跟踪路由（并行版本，主机名解析与下一跃点并行）"""
    results = []
    previous_ip = None
    hostname_futures = {}  # 存储主机名解析的futures
    logger.debug(f"开始 UDP 跟踪路由(并行版本): 目标={target_ip}, 端口={port}")

    with ThreadPoolExecutor() as hostname_executor:
        for ttl in range(1, MAX_HOPS + 1):
            # 定义如何创建 UDP 数据包
            def create_udp_packet(ttl_value, _attempt):
                # 使用随机源端口
                sport = RandShort()
                return IP(dst=target_ip, ttl=ttl_value) / UDP(sport=sport, dport=port)

            # 使用辅助函数处理当前跃点，同时传递前一个跃点的IP
            hop_result, reached_target = _process_parallel_hop(ttl, target_ip, "UDP", create_udp_packet, previous_ip)

            # 收集需要解析主机名的唯一IP地址
            unique_ips = set()
            for resp in hop_result["responses"]:
                if resp["ip"] != "*" and not resp["hostname"] and resp["ip"] not in hostname_futures:
                    unique_ips.add(resp["ip"])

            # 提交主机名解析任务（与下一跃点并行）
            for ip in unique_ips:
                if ip not in hostname_futures:
                    hostname_futures[ip] = hostname_executor.submit(resolve_hostname, ip)

            # 更新前一个跃点的IP地址（用于下一个跃点查询地理位置）
            valid_responses = [r for r in hop_result["responses"] if r["ip"] != "*"]
            if valid_responses:
                previous_ip = valid_responses[0]["ip"]

            # 将跃点结果添加到结果列表
            results.append(hop_result)

            if reached_target:
                logger.debug(f"UDP 跟踪: 达到目标 IP={target_ip}, 跃点={ttl}, 提前结束")
                break

            logger.debug(f"UDP 跟踪: 完成跃点={ttl}, 共收集 {len(hop_result['responses'])} 个响应")

        # 处理完所有跃点后，获取所有主机名解析结果并更新
        for result in results:
            for resp in result["responses"]:
                if resp["ip"] != "*" and resp["ip"] in hostname_futures:
                    try:
                        resp["hostname"] = hostname_futures[resp["ip"]].result()
                    except Exception as e:
                        logger.error(f"获取主机名解析结果失败: {resp['ip']} - {str(e)}")
                        resp["hostname"] = ""

    logger.debug(f"UDP 跟踪路由完成: 共 {len(results)} 跳")
    return results

# 添加并行处理相关的辅助函数
def _send_packet_and_process(packet_info):
    """发送数据包并处理响应（适用于并行处理）"""
    ttl, attempt, pkt, timeout, target_ip, protocol = packet_info

    start_time = time.time()
    reply = sr1(pkt, timeout=timeout, verbose=0)
    response_time = (time.time() - start_time) * 1000  # 转换为毫秒

    if reply is None:
        logger.debug(f"{protocol} 跟踪: 跃点={ttl}, 尝试={attempt+1}, 无响应 (超时)")
        return {
            "ip": "*",
            "hostname": "*",
            "rtt": None
        }
    else:
        # 获取响应 IP
        resp_ip = reply.src
        logger.debug(f"{protocol} 跟踪: 跃点={ttl}, 尝试={attempt+1}, 收到响应 IP={resp_ip}, RTT={response_time:.2f}ms")

        # 不在这里解析主机名，而是使用缓存或稍后并行解析
        return {
            "ip": resp_ip,
            "hostname": "",  # 主机名将在后续步骤中解析
            "rtt": response_time,
            "is_target": resp_ip == target_ip  # 添加标志以检查是否到达目标
        }

def resolve_hostname(ip):
    """解析主机名并缓存结果"""
    if ip == "*" or not ip:
        return ""

    # 检查缓存
    if ip in HOSTNAME_CACHE:
        logger.debug(f"从缓存获取主机名: {ip} -> {HOSTNAME_CACHE[ip]}")
        return HOSTNAME_CACHE[ip]

    # 尝试解析主机名，但设置短超时
    hostname = ""
    try:
        socket.setdefaulttimeout(1)
        hostname = socket.gethostbyaddr(ip)[0]
        logger.debug(f"解析主机名成功: {ip} -> {hostname}")
        # 缓存结果
        HOSTNAME_CACHE[ip] = hostname
    except (socket.herror, socket.gaierror, socket.timeout):
        logger.debug(f"解析主机名失败: {ip}")
        # 缓存空结果，避免重复查询
        HOSTNAME_CACHE[ip] = ""
    finally:
        socket.setdefaulttimeout(None)

    return hostname

def _process_parallel_hop(ttl, target_ip, protocol_name, packet_function, previous_ip=None):
    """处理单个跃点的并行尝试"""
    hop_result = {
        "hop": ttl,
        "responses": []
    }
    logger.debug(f"{protocol_name} 跟踪: 当前跃点={ttl}")

    # 准备数据包参数
    packets_info = []
    for attempt in range(TRIES):
        # 调用传入的函数创建特定的协议的数据包
        pkt = packet_function(ttl, attempt)
        packets_info.append((ttl, attempt, pkt, TIMEOUT, target_ip, protocol_name))

    # 并行处理：1. 获取前一个跃点的地理位置，2. 发送当前跃点的数据包
    geo_info = None
    # 只有当previous_ip有效且不是"*"时，才进行地理位置查询
    if previous_ip and previous_ip != "*":
        # 使用线程池并行执行地理位置查询和数据包发送
        with ThreadPoolExecutor(max_workers=TRIES+1) as executor:
            # 提交地理位置查询任务
            geo_future = executor.submit(get_ip_geolocation, previous_ip)

            # 提交所有数据包发送任务
            packet_futures = []
            for packet_info in packets_info:
                packet_futures.append(executor.submit(_send_packet_and_process, packet_info))

            # 获取地理位置信息结果
            geo_info = geo_future.result()

            # 获取数据包响应结果
            reached_target = False
            for future in packet_futures:
                response = future.result()
                hop_result["responses"].append(response)
                if response.get("is_target", False):
                    reached_target = True
    else:
        # 如果没有前一个跃点或前一个跃点是"*"，只执行数据包发送
        reached_target = False
        with ThreadPoolExecutor(max_workers=TRIES) as executor:
            for response in executor.map(_send_packet_and_process, packets_info):
                hop_result["responses"].append(response)
                if response.get("is_target", False):
                    reached_target = True

    # 不再在这里解析主机名，而是在各个traceroute函数中并行处理

    # 移除辅助字段
    for resp in hop_result["responses"]:
        if "is_target" in resp:
            del resp["is_target"]

    # 添加地理位置信息到结果中
    if geo_info:
        hop_result["geo_info"] = geo_info

    return hop_result, reached_target

def format_trace_results(target, protocol, port, results):
    """格式化跟踪路由结果"""
    output = StringIO()

    # 显示标题
    output.write(f"📡 *{PROTOCOLS[protocol]} 跟踪路由*\n\n")
    output.write(f"目标: `{target}`\n")
    output.write(f"协议: {PROTOCOLS[protocol]}")

    if protocol in ["tcp", "udp"]:
        output.write(f" 端口: {port}")

    output.write("\n\n")

    # 在结果数据前添加 ```
    output.write("```\n")

    # 显示每一跳的信息
    for hop in results[:-1]:  # 最后一个元素是总时间
        hop_num = hop["hop"]
        responses = hop["responses"]
        geo_info = hop.get("geo_info", None)  # 前一跳的地理位置信息

        # 检查是否所有尝试都超��
        if all(r["ip"] == "*" for r in responses):
            output.write(f"{hop_num}. */*/*\n")
            continue

        # 找出有效响应
        valid_responses = [r for r in responses if r["ip"] != "*"]
        if valid_responses:
            first_resp = valid_responses[0]
            ip = first_resp["ip"]
            hostname = first_resp["hostname"] if first_resp["hostname"] else ""

            # 使用 / 分隔三次尝试的RTT值
            rtts = []
            for i in range(TRIES):
                if i < len(responses) and responses[i]["rtt"] is not None:
                    rtts.append(f"{responses[i]['rtt']:.2f}")
                else:
                    rtts.append("*")
            rtt_str = "/".join(rtts) + " ms"

            # 显示IP和RTT
            if hostname:
                output.write(f"{hop_num}. {ip} ({hostname}) {rtt_str}")
            else:
                output.write(f"{hop_num}. {ip} {rtt_str}")

            # 如果有地理位置信息，显示在下一行
            if geo_info:
                output.write("\n    ")
                location_info = []

                if geo_info.get("location"):
                    location_info.append(geo_info["location"])

                if geo_info.get("asn"):
                    asn_info = geo_info["asn"]
                    if geo_info.get("org") and geo_info["org"] != geo_info.get("isp", ""):
                        asn_info += f" ({geo_info['org']})"
                    elif geo_info.get("isp"):
                        asn_info += f" ({geo_info['isp']})"
                    location_info.append(asn_info)
                elif geo_info.get("isp"):
                    location_info.append(geo_info["isp"])

                output.write(", ".join(location_info))

            output.write("\n")
        else:
            output.write(f"{hop_num}. */*/*\n")

    # 在结果数据后添加 ```
    output.write("```\n")

    # 显示总时间
    total_time = results[-1]["total_time"]
    output.write(f"\n跟踪完成，总用时: {total_time:.2f} 秒")

    return output.getvalue()

def get_ip_geolocation(ip):
    """从ip-api.com获取IP地址的地理位置信息"""
    if ip == "*" or not ip:
        return None

    try:
        # 使用ip-api.com的免费API
        response = requests.get(f"http://ip-api.com/json/{ip}?fields=country,regionName,city,isp,as,org", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success" or "country" in data:
                # 构建地理位置信息
                location = []

                # 添加城市、地区和国家
                city = data.get("city", "")
                region = data.get("regionName", "")
                country = data.get("country", "")

                if city:
                    location.append(city)
                if region and region != city:
                    location.append(region)
                if country:
                    location.append(country)

                # 添加ISP/ASN/组织信息
                isp = data.get("isp", "")
                asn = data.get("as", "")
                org = data.get("org", "")

                # 构建返回值
                result = {
                    "location": ", ".join(location) if location else "",
                    "isp": isp,
                    "asn": asn,
                    "org": org
                }

                return result
    except Exception as e:
        logger.debug(f"获取IP地理位置信息失败: {ip} - {str(e)}")

    return None


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
