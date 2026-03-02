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
    "error.amount_invalid": "The amount must be a valid number",
    "error.invalid_bin_parameter": "Oops, invalid parameter. Please provide a 4 to 8 digit BIN.",
    "prompt.valid_bin_required": "Please provide a valid BIN (4 to 8 digits)",
    "error.permission_denied": "You do not have permission to use this feature",
    "error.sender_unrecognized": "Unable to identify message sender",
    "lock.list.empty": "No commands are locked in this group",
    "error.bot_id_invalid": "Bot configuration error: bot_id is invalid",
    "error.bot_delete_permission_required": "Please make the bot an admin and grant delete message permission first",
    "error.participant_count_invalid": "Participant count must be an integer",
    "error.group_admin_required": "Only group admins can use this command.",
    "error.required_args_missing": "Prize count, participant count, keyword, and title cannot be empty",
    "error.prize_or_participant_missing": "Prize count and participant count cannot be empty",
    "error.prize_count_exceeds_participants": "Prize count cannot exceed participant count",
    "status.force_draw_success": "Force draw completed successfully.",
    "error.lottery_in_progress": "A lottery is currently running, please try again later",
    "error.no_active_lottery": "No ongoing lottery in this group.",
    "error.group_only": "Please use this command in a group.",
    "prompt.lottery_usage": "Please enter parameters like prize count/participants, or use force draw\n\nExample: `/lottery 1/10 join test`",
    "prompt.server_address_required": "Please provide a server address in this format: /mc server:port\nExample: /mc mc.hypixel.net",
    "status.ocr_processing": "Running OCR...",
    "error.ocr_invalid_format": "Invalid format. Use: /ocr [Custom Prompt]",
    "prompt.ocr_reply_image_first": "Please reply to an image or image file, then use /ocr [Custom Prompt].",
    "error.invalid_target_address": "❌ Invalid target address. Please provide a valid domain or IP address.",
    "prompt.ping_target_required": "Please provide a target to ping, for example: /ping example.com",
    "prompt.remake_not_started": "You haven't done a remake yet, try /remake",
    "error.query_failed_retry": "Query failed, please try again later.",
    "error.backend_url_not_configured": "Generation failed, backend URL is not configured",
    "prompt.stats_usage": "Usage: /stats [Nh|Nd|Nw|Nm|Ny|YYYY-MM-DD|YYYY/MM/DD|YYYYMMDD] e.g. /stats 1h /stats 4d /stats 3w /stats 2m /stats 4y /stats 2026-02-25 /stats 2026/02/25 /stats 20260225",
    "error.stats_group_only": "This statistics command is only available in groups.",
    "dragon.empty": "Dragon King Leaderboard\n\nNo Dragon King statistics yet",
    "error.invalid_port_number": "❌ Invalid port number. Port must be an integer between 1 and 65535.",
    "prompt.tcping_host_port_required": "❌ Please provide target host and port in this format: /tcping host:port",
    "error.invalid_protocol_type": "❌ Invalid protocol type. Use T (TCP) or U (UDP)",
    "error.trace_invalid_target": "❌ Invalid target address. Please enter a valid IP address or domain",
    "error.nexttrace_not_found": "❌ nexttrace command not found, please install nexttrace first",
    "error.port_out_of_range": "❌ Port number must be between 1 and 65535",
    "error.port_not_numeric": "❌ Port must be numeric",
    "prompt.trace_usage": "Usage: /trace <target> [T/U] [port]\nT = TCP, U = UDP, ICMP is used if omitted\nExample: /trace 1.1.1.1\n      /trace example.com T 443",
    "error.unknown": "An unknown error occurred",
    "keybox.ban.success": "Banned successfully.",
    "error.file_too_large": "File size is too large",
    "error.local_botapi_path_inaccessible": "Local Bot API enabled but file path is not accessible.",
    "keybox.ban.empty": "No keybox has been banned.",
    "prompt.reply_keybox_xml": "Please reply to a keybox.xml file.",
    "keybox.ban.already_banned": "This keybox has been banned.",
    "keybox.ban.not_found": "This keybox has not been banned.",
    "keybox.unban.success": "Unbanned successfully.",
    "prompt.ban_keybox_usage": "Usage: /ban_keybox <serial_number>\nExample: /ban_keybox 1a2b3c4d5e6f",
    "prompt.unban_keybox_usage": "Usage: /unban_keybox <serial_number>\nExample: /unban_keybox 1a2b3c4d5e6f",
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
