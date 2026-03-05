# -*- coding: utf-8 -*-
# @Time    : 2025/5/1 12:49
# @Author  : KimmyXYC
# @File    : status.py
# @Software: PyCharm

import os
import time
import socket
import psutil
import platform
import subprocess
import aiohttp
from telebot import types
from loguru import logger
from app.security.permissions import is_bot_admin

# ==================== 插件元数据 ====================
__plugin_name__ = "status"
__version__ = "1.0.0"
__author__ = "KimmyXYC"
__description__ = "系统状态查询（仅限管理员）"
__commands__ = ["status"]
__command_category__ = "utility"
__command_order__ = {"status": 510}
__command_descriptions__ = {"status": "获取机器人状态信息"}
__command_help__ = {"status": "/status - 获取机器人状态信息"}


# ==================== 辅助函数 ====================


def _get_local_ip() -> str:
    """获取本机内网 IPv4 地址。"""
    # 优先从网卡地址中取非 loopback 的第一个 IPv4
    try:
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith(
                    "127."
                ):
                    return addr.address
    except Exception:
        pass
    # fallback：通过连接外部地址推断本机出口 IP（不实际发包）
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        pass
    return "unknown"


async def _get_public_ip() -> str:
    """通过外部 API 获取公网 IP，失败时 fallback 到第二个源。"""
    sources = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
    ]
    try:
        async with aiohttp.ClientSession() as session:
            for url in sources:
                try:
                    async with session.get(
                        url, timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        if resp.status == 200:
                            return (await resp.text()).strip()
                except Exception:
                    continue
    except Exception:
        pass
    return "unknown"


def _fmt_bytes(n: int) -> str:
    """自动将字节数格式化为 MB 或 GB。"""
    if n >= 1024**3:
        return f"{n / 1024**3:.2f} GB"
    return f"{n / 1024**2:.2f} MB"


def _get_uptime() -> str:
    """返回格式化的系统运行时间。"""
    seconds = int(time.time() - psutil.boot_time())
    d, r = divmod(seconds, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


def _get_packages() -> str:
    """尝试 dpkg / rpm / pacman 获取已安装包数量。"""
    checks = [
        (["dpkg", "--get-selections"], lambda out: str(len(out.strip().splitlines()))),
        (
            ["rpm", "-qa", "--qf", "%{NAME}\\n"],
            lambda out: str(len(out.strip().splitlines())),
        ),
        (["pacman", "-Qq"], lambda out: str(len(out.strip().splitlines()))),
    ]
    for cmd, parse in checks:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                return parse(r.stdout) + f" ({cmd[0]})"
        except Exception:
            continue
    return "unknown"


def _get_shell() -> str:
    """获取当前 Shell。"""
    shell = os.environ.get("SHELL", "")
    if shell:
        return os.path.basename(shell)
    try:
        r = subprocess.run(
            ["ps", "-p", str(os.getppid()), "-o", "comm="],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _get_locale() -> str:
    """获取系统 Locale。"""
    for var in ("LANG", "LC_ALL", "LC_MESSAGES"):
        val = os.environ.get(var, "")
        if val:
            return val
    try:
        r = subprocess.run(["locale"], capture_output=True, text=True, timeout=3)
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                if line.startswith("LANG="):
                    val = line.split("=", 1)[1].strip().strip('"')
                    if val:
                        return val
    except Exception:
        pass
    return "unknown"


def _get_timezone() -> str:
    """获取系统时区。"""
    # 优先读文件
    for path in ("/etc/timezone",):
        try:
            with open(path) as f:
                val = f.read().strip()
                if val:
                    return val
        except Exception:
            pass
    # 通过 /etc/localtime 软链接推断
    try:
        link = os.readlink("/etc/localtime")
        marker = "zoneinfo/"
        idx = link.find(marker)
        if idx != -1:
            return link[idx + len(marker) :]
    except Exception:
        pass
    # timedatectl fallback
    try:
        r = subprocess.run(
            ["timedatectl", "show", "--property=Timezone", "--value"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    # Python time module fallback（可能乱码，仅作兜底）
    return time.tzname[0] if time.tzname else "unknown"


def _get_cpu_model() -> str:
    """获取 CPU 型号。"""
    # Linux /proc/cpuinfo
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line:
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    # macOS / Windows fallback via platform
    cpu = platform.processor()
    return cpu if cpu else "unknown"


def _get_gpu() -> str:
    """尝试 nvidia-smi 后 lspci 获取 GPU 型号，均失败返回 unknown。"""
    # nvidia-smi
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            return ", ".join(line.strip() for line in r.stdout.strip().splitlines())
    except Exception:
        pass
    # lspci
    try:
        r = subprocess.run(["lspci"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            gpus = []
            for line in r.stdout.splitlines():
                lower = line.lower()
                if any(
                    k in lower for k in ("vga", "3d controller", "display controller")
                ):
                    # 取冒号后的描述部分
                    gpus.append(line.split(":", 2)[-1].strip())
            if gpus:
                return ", ".join(gpus)
    except Exception:
        pass
    return "unknown"


# ==================== 核心功能 ====================
async def handle_status_command(bot, message: types.Message):
    """
    处理 /status 命令
    :param bot: Bot 对象
    :param message: 消息对象
    :return:
    """
    os_info = platform.platform()
    cpu_usage = psutil.cpu_percent(interval=1)
    memory_info = psutil.virtual_memory()
    swap_info = psutil.swap_memory()
    disk_info = psutil.disk_usage("/")
    net_io = psutil.net_io_counters()
    load_avg = psutil.getloadavg()

    uptime = _get_uptime()
    packages = _get_packages()
    shell = _get_shell()
    locale = _get_locale()
    timezone = _get_timezone()
    cpu_model = _get_cpu_model()
    gpu_model = _get_gpu()
    local_ip = _get_local_ip()
    public_ip = await _get_public_ip()

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
        )
        git_hash = result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        git_hash = "unknown"

    info_message = (
        f"*Operating System:* `{os_info}`\n"
        f"*Uptime:* `{uptime}`\n"
        f"*Packages:* `{packages}`\n"
        f"*Shell:* `{shell}`\n"
        f"*Locale:* `{locale}`\n"
        f"*Timezone:* `{timezone}`\n"
        f"*Local IP:* `{local_ip}`\n"
        f"*Public IP:* `{public_ip}`\n"
        f"*CPU Model:* `{cpu_model}`\n"
        f"*CPU Usage:* `{cpu_usage}%`\n"
        f"*GPU:* `{gpu_model}`\n"
        f"*Memory Usage:* `{memory_info.percent}% (Total: {memory_info.total / (1024**3):.2f} GB, "
        f"Used: {memory_info.used / (1024**3):.2f} GB)`\n"
        f"*Swap Usage:* `{swap_info.percent}% (Total: {swap_info.total / (1024**3):.2f} GB, "
        f"Used: {swap_info.used / (1024**3):.2f} GB)`\n"
        f"*Disk Usage:* `{disk_info.percent}% (Total: {disk_info.total / (1024**3):.2f} GB, "
        f"Used: {disk_info.used / (1024**3):.2f} GB)`\n"
        f"*Network I/O:* `Sent: {_fmt_bytes(net_io.bytes_sent)}, "
        f"Received: {_fmt_bytes(net_io.bytes_recv)}`\n"
        f"*Load Average:* `1 min: {load_avg[0]:.2f}, 5 min: {load_avg[1]:.2f}, 15 min: {load_avg[2]:.2f}`\n"
        f"*Git Commit:* `{git_hash}`"
    )

    await bot.reply_to(message, info_message, parse_mode="Markdown")


# ==================== 插件注册 ====================
async def register_handlers(bot, middleware, plugin_name):
    """注册插件处理器"""

    global bot_instance
    bot_instance = bot

    async def status_handler(bot, message: types.Message):
        await handle_status_command(bot, message)

    middleware.register_command_handler(
        commands=["status"],
        callback=status_handler,
        plugin_name=plugin_name,
        priority=50,
        stop_propagation=True,
        chat_types=["private", "group", "supergroup"],
        func=lambda m: (
            bool(getattr(m, "from_user", None)) and is_bot_admin(m.from_user.id)
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
