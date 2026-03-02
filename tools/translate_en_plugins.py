# -*- coding: utf-8 -*-

import glob
import json
import os


BASE = r"C:\Users\Kimmy\PycharmProjects\NachonekoBot-V2\utils\i18n\en\plugins"


META_AND_COMMAND = {
    "bc": {
        "meta.description": "Currency converter (supports multiple fiat rate sources and crypto)",
        "command.description.bc": "Convert currencies (multiple fiat rate sources + crypto)",
        "command.help.bc": "/bc [Amount] [Currency_From] [Currency_To] - Convert currencies (fiat supports multiple rate sources: EU/UnionPay/Mastercard/Visa)\nInline: @NachoNekoX_bot bc [Amount] [Currency_From] [Currency_To]",
    },
    "bin": {
        "meta.description": "BIN lookup",
        "command.description.bin": "Query bank card BIN information",
        "command.help.bin": "/bin [Card_BIN] - Query bank card BIN information\nInline: @NachoNekoX_bot bin [Card_BIN]",
    },
    "callanyone": {
        "meta.description": "Fun commands to call doctor, MTF, police, etc.",
        "command.description.calldoctor": "Call doctor",
        "command.description.callmtf": "Call MTF",
        "command.description.callpolice": "Call police",
        "command.help.calldoctor": "/calldoctor - Call doctor\nInline: @NachoNekoX_bot calldoctor",
        "command.help.callmtf": "/callmtf - Call MTF\nInline: @NachoNekoX_bot callmtf",
        "command.help.callpolice": "/callpolice - Call police\nInline: @NachoNekoX_bot callpolice",
    },
    "dns": {
        "meta.description": "DNS record lookup",
        "command.description.dns": "Query DNS records",
        "command.help.dns": "/dns [Domain] [Record_Type] - Query DNS records\nInline: @NachoNekoX_bot dns [Domain] [Record_Type]",
    },
    "icp": {
        "meta.description": "ICP record lookup",
        "command.description.icp": "Query domain ICP registration information",
        "command.help.icp": "/icp [Domain] - Query domain ICP registration information\nInline: @NachoNekoX_bot icp [Domain]",
    },
    "ip": {
        "meta.description": "IP address lookup",
        "command.description.ip": "Query IP/domain information",
        "command.help.ip": "/ip [IP/Domain] - Query IP/domain information\nInline: @NachoNekoX_bot ip [IP/Domain]",
    },
    "keybox": {
        "meta.description": "Keybox checker tool",
        "command.description.check": "Check keybox.xml file",
        "command.help.check": "/check - Check keybox.xml file",
    },
    "lock": {
        "meta.description": "Group command lock management",
        "command.description.lock": "Lock commands in this group",
        "command.description.unlock": "Unlock commands in this group",
        "command.description.list": "List locked commands in this group",
        "command.help.lock": "/lock [Command] - Lock commands in this group",
        "command.help.unlock": "/unlock [Command] - Unlock commands in this group",
        "command.help.list": "/list - List locked commands in this group",
    },
    "long_image_cutter": {
        "meta.description": "Automatically cut long images into multiple 19.5:9 slices with 3:19.5 overlap; slice height follows a 19.5:9 baseline with fine tuning to keep all slices uniform (only effective for images sent as files).",
        "meta.display_name": "Long Image Cutter",
    },
    "lottery": {
        "meta.description": "Lottery system",
        "command.description.lottery": "Lottery",
        "command.help.lottery": "/lottery [Winners]/[Participants] [Keyword] [Title] - Lottery",
    },
    "mcstatus": {
        "meta.description": "Minecraft server status lookup",
        "command.description.mc": "Query Minecraft server status (auto-detect Java/Bedrock)",
        "command.description.mcje": "Query Minecraft Java server status",
        "command.description.mcbe": "Query Minecraft Bedrock server status",
        "command.help.mc": "/mcstatus [Server:Port] - Query Minecraft server status (auto-detect Java/Bedrock)\nInline: @NachoNekoX_bot mc [Server:Port]",
        "command.help.mcje": "/mcje [Server:Port] - Query Minecraft Java server status\nInline: @NachoNekoX_bot mcje [Server:Port]",
        "command.help.mcbe": "/mcbe [Server:Port] - Query Minecraft Bedrock server status\nInline: @NachoNekoX_bot mcbe [Server:Port]",
    },
    "ocr": {
        "meta.description": "OCR text recognition (Alibaba qwen-vl-ocr)",
        "command.description.ocr": "Recognize text in images via OCR",
        "command.help.ocr": "/ocr [Custom Prompt] - OCR image text; reply to an image/image file, or use in image caption",
    },
    "ping": {
        "meta.description": "Ping network connectivity test",
        "command.description.ping": "Ping test",
        "command.help.ping": "/ping [IP/Domain] - Ping test",
    },
    "quote_reply": {
        "meta.description": "Action quote plugin starting with /$ and \\$",
        "meta.display_name": "Quote Reply",
    },
    "rdap": {
        "meta.description": "RDAP lookup for domains, IPs, and ASNs",
        "command.description.rdap": "Query RDAP information",
        "command.help.rdap": "/rdap [Domain/IP/ASN] - Query RDAP information\nInline: @NachoNekoX_bot rdap [Domain/IP/ASN]\nSupported formats: domain(example.com), IP(1.1.1.1), ASN(AS13335 or 13335)",
    },
    "remake": {
        "meta.description": "Reincarnation system",
        "command.description.remake": "Reincarnate",
        "command.description.remake_data": "View reincarnation data",
        "command.help.remake": "/remake - Reincarnate",
        "command.help.remake_data": "/remake_data - View reincarnation data",
    },
    "shorturl": {
        "meta.description": "Short URL generator",
        "command.description.short": "Generate short URLs",
        "command.help.short": "/short [URL] - Generate short URL",
    },
    "stats": {
        "meta.description": "Group message statistics ranking (supports day/week/month/year and custom ranges)",
        "meta.display_name": "Message Statistics Recorder",
        "command.description.stats": "View group message leaderboard",
        "command.description.dragon": "View Dragon King leaderboard",
        "command.help.stats": "/stats - Today\n/stats 5h - Last 5 hours\n/stats 4d - Last 4 days\n/stats 3w - Last 3 weeks\n/stats 2m - Last 2 months\n/stats 1y - Last 1 year\n/stats 2026-02-25 - Specific date\n/stats 2026/02/25 - Specific date\n/stats 20260225 - Specific date\n",
        "command.help.dragon": "/dragon - Dragon King leaderboard\n",
    },
    "status": {
        "meta.description": "System status query (admin only)",
        "command.description.status": "Get bot status information",
        "command.help.status": "/status - Get bot status information",
    },
    "tcping": {
        "meta.description": "TCP port connectivity test",
        "command.description.tcping": "TCP ping test",
        "command.help.tcping": "/tcping [IP/Domain]:[Port] - TCP ping test",
    },
    "trace": {
        "meta.description": "Traceroute tool (using nexttrace)",
        "command.description.trace": "Trace route",
        "command.help.trace": "/trace [IP/Domain] [Protocol(T/U)] [Port] - Trace route",
    },
    "weather": {
        "meta.description": "Weather query",
        "command.description.weather": "Query weather information",
        "command.help.weather": "/weather [City_Name] - Query weather information",
    },
    "whois": {
        "meta.description": "Whois domain lookup",
        "command.description.whois": "Query Whois information",
        "command.help.whois": "/whois [Domain] - Query Whois information\nInline: @NachoNekoX_bot whois [Domain]",
    },
    "xiatou": {
        "meta.description": "Lower-head detection system (only effective for configured users)",
        "command.help.inb": "Inline: @NachoNekoX_bot inb",
    },
    "xibao": {
        "meta.description": "Xibao/Beibao/Tongbao/Jingbao image generator",
        "meta.display_name": "Report Image Generator",
    },
}


RUNTIME_TEXT = {
    "\u6570\u91cf\u5fc5\u987b\u662f\u6709\u6548\u7684\u6570\u5b57": "The amount must be a valid number",
    "\u51fa\u9519\u4e86\u545c\u545c\u545c ~ \u65e0\u6548\u7684\u53c2\u6570\u3002\u8bf7\u63d0\u4f9b4\u52308\u4f4d\u6570\u5b57\u7684BIN\u53f7\u7801\u3002": "Oops, invalid parameter. Please provide a 4 to 8 digit BIN.",
    "\u8bf7\u63d0\u4f9b\u6709\u6548\u7684BIN\u53f7\u7801\uff084\u52308\u4f4d\u6570\u5b57\uff09": "Please provide a valid BIN (4 to 8 digits)",
    "\u60a8\u65e0\u6743\u4f7f\u7528\u6b64\u529f\u80fd": "You do not have permission to use this feature",
    "\u65e0\u6cd5\u8bc6\u522b\u6d88\u606f\u53d1\u9001\u8005": "Unable to identify message sender",
    "\u672c\u7fa4\u672a\u9501\u5b9a\u4efb\u4f55\u547d\u4ee4": "No commands are locked in this group",
    "\u673a\u5668\u4eba\u914d\u7f6e\u9519\u8bef\uff1abot_id \u65e0\u6548": "Bot configuration error: bot_id is invalid",
    "\u8bf7\u5148\u5c06\u673a\u5668\u4eba\u8bbe\u7f6e\u4e3a\u7ba1\u7406\u5458\u5e76\u8d4b\u4e88\u5220\u9664\u6d88\u606f\u6743\u9650": "Please make the bot an admin and grant delete message permission first",
    "\u4eba\u6570\u5fc5\u987b\u662f\u6574\u6570": "Participant count must be an integer",
    "\u53ea\u6709\u7fa4\u7ba1\u7406\u5458\u53ef\u4ee5\u4f7f\u7528\u6b64\u547d\u4ee4\u3002": "Only group admins can use this command.",
    "\u5956\u54c1\u6570\u3001\u4eba\u6570\u3001\u5173\u952e\u5b57\u548c\u6807\u9898\u4e0d\u80fd\u4e3a\u7a7a": "Prize count, participant count, keyword, and title cannot be empty",
    "\u5956\u54c1\u6570\u3001\u4eba\u6570\u4e0d\u80fd\u4e3a\u7a7a": "Prize count and participant count cannot be empty",
    "\u5956\u54c1\u6570\u4e0d\u80fd\u8d85\u8fc7\u4eba\u6570": "Prize count cannot exceed participant count",
    "\u5f3a\u5236\u5f00\u5956\u6210\u529f\u3002": "Force draw completed successfully.",
    "\u6709\u62bd\u5956\u6d3b\u52a8\u6b63\u5728\u8fdb\u884c\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5": "A lottery is currently running, please try again later",
    "\u672c\u7fa4\u6682\u65e0\u6b63\u5728\u8fdb\u884c\u7684\u62bd\u5956\u6d3b\u52a8\u3002": "No ongoing lottery in this group.",
    "\u8bf7\u5728\u7fa4\u7ec4\u4e2d\u4f7f\u7528\u8be5\u547d\u4ee4\u3002": "Please use this command in a group.",
    "\u8bf7\u8f93\u5165 \u5956\u54c1\u6570\u3001\u4eba\u6570\u7b49\u53c2\u6570 \u6216\u8005 \u5f3a\u5236\u5f00\u5956\n\n\u4f8b\u5982 `/lottery 1/10 \u53c2\u52a0 \u6d4b\u8bd5`": "Please enter parameters like prize count/participants, or use force draw\n\nExample: `/lottery 1/10 join test`",
    "\u8bf7\u63d0\u4f9b\u670d\u52a1\u5668\u5730\u5740\uff0c\u683c\u5f0f\uff1a/mc \u670d\u52a1\u5668\u5730\u5740:\u7aef\u53e3\n\u4f8b\u5982\uff1a/mc mc.hypixel.net": "Please provide a server address in this format: /mc server:port\nExample: /mc mc.hypixel.net",
    "OCR\u8bc6\u522b\u4e2d...": "Running OCR...",
    "\u683c\u5f0f\u9519\u8bef\uff0c\u683c\u5f0f\u5e94\u4e3a /ocr [\u81ea\u5b9a\u4e49\u63d0\u793a\u8bcd]": "Invalid format. Use: /ocr [Custom Prompt]",
    "\u8bf7\u56de\u590d\u4e00\u5f20\u56fe\u7247\u6216\u56fe\u7247\u6587\u4ef6\u540e\u518d\u4f7f\u7528 /ocr [\u81ea\u5b9a\u4e49\u63d0\u793a\u8bcd]\u3002": "Please reply to an image or image file, then use /ocr [Custom Prompt].",
    "\u274c \u65e0\u6548\u7684\u76ee\u6807\u5730\u5740\u3002\u8bf7\u63d0\u4f9b\u6709\u6548\u7684\u57df\u540d\u6216IP\u5730\u5740\u3002": "❌ Invalid target address. Please provide a valid domain or IP address.",
    "\u8bf7\u63d0\u4f9b\u8981 ping \u7684\u76ee\u6807\u5730\u5740\uff0c\u4f8b\u5982: /ping example.com": "Please provide a target to ping, for example: /ping example.com",
    "\u60a8\u8fd8\u6ca1\u6709 remake \u8fc7\u5462\uff0c\u5feb /remake \u5427": "You haven't done a remake yet, try /remake",
    "\u67e5\u8be2\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5\u3002": "Query failed, please try again later.",
    "\u751f\u6210\u5931\u8d25, \u540e\u7aef\u5730\u5740\u672a\u8bbe\u7f6e": "Generation failed, backend URL is not configured",
    "\u7528\u6cd5\uff1a/stats [Nh|Nd|Nw|Nm|Ny|YYYY-MM-DD|YYYY/MM/DD|YYYYMMDD] \u4f8b\u5982 /stats 1h /stats 4d /stats 3w /stats 2m /stats 4y /stats 2026-02-25 /stats 2026/02/25 /stats 20260225": "Usage: /stats [Nh|Nd|Nw|Nm|Ny|YYYY-MM-DD|YYYY/MM/DD|YYYYMMDD] e.g. /stats 1h /stats 4d /stats 3w /stats 2m /stats 4y /stats 2026-02-25 /stats 2026/02/25 /stats 20260225",
    "\u8be5\u7edf\u8ba1\u4ec5\u652f\u6301\u7fa4\u7ec4\u4f7f\u7528\u3002": "This statistics command is only available in groups.",
    "\u9f99\u738b\u603b\u699c\n\n\u6682\u65e0\u9f99\u738b\u7edf\u8ba1\u6570\u636e": "Dragon King Leaderboard\n\nNo Dragon King statistics yet",
    "\u274c \u65e0\u6548\u7684\u7aef\u53e3\u53f7\u3002\u7aef\u53e3\u53f7\u5e94\u4e3a1-65535\u4e4b\u95f4\u7684\u6574\u6570\u3002": "❌ Invalid port number. Port must be an integer between 1 and 65535.",
    "\u274c \u8bf7\u63d0\u4f9b\u76ee\u6807\u4e3b\u673a\u548c\u7aef\u53e3\uff0c\u683c\u5f0f: /tcping \u4e3b\u673a:\u7aef\u53e3": "❌ Please provide target host and port in this format: /tcping host:port",
    "\u274c \u65e0\u6548\u7684\u534f\u8bae\u7c7b\u578b\uff0c\u8bf7\u4f7f\u7528 T (TCP) \u6216 U (UDP)": "❌ Invalid protocol type. Use T (TCP) or U (UDP)",
    "\u274c \u65e0\u6548\u7684\u76ee\u6807\u5730\u5740\uff0c\u8bf7\u8f93\u5165\u6709\u6548\u7684 IP \u5730\u5740\u6216\u57df\u540d": "❌ Invalid target address. Please enter a valid IP address or domain",
    "\u274c \u672a\u627e\u5230 nexttrace \u547d\u4ee4\uff0c\u8bf7\u5148\u5b89\u88c5 nexttrace": "❌ nexttrace command not found, please install nexttrace first",
    "\u274c \u7aef\u53e3\u53f7\u5fc5\u987b\u5728 1-65535 \u4e4b\u95f4": "❌ Port number must be between 1 and 65535",
    "\u274c \u7aef\u53e3\u5fc5\u987b\u662f\u6570\u5b57": "❌ Port must be numeric",
    "\u7528\u6cd5: /trace <\u76ee\u6807\u5730\u5740> [T/U] [\u7aef\u53e3]\nT = TCP, U = UDP, \u4e0d\u6307\u5b9a\u5219\u4f7f\u7528 ICMP\n\u793a\u4f8b: /trace 1.1.1.1\n      /trace example.com T 443": "Usage: /trace <target> [T/U] [port]\nT = TCP, U = UDP, ICMP is used if omitted\nExample: /trace 1.1.1.1\n      /trace example.com T 443",
    "\u53d1\u751f\u672a\u77e5\u9519\u8bef": "An unknown error occurred",
}


def main():
    for path in sorted(glob.glob(os.path.join(BASE, "*.json"))):
        plugin = os.path.basename(path)[:-5]
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for key, value in META_AND_COMMAND.get(plugin, {}).items():
            if key in data:
                data[key] = value

        for key, value in RUNTIME_TEXT.items():
            if key in data:
                data[key] = value

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")

    print("English plugin locale files translated.")


if __name__ == "__main__":
    main()
