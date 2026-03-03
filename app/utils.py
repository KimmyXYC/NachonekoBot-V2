# -*- coding: utf-8 -*-
# @Time    : 2023/11/18 上午12:51
# @Author  : sudoskys
# @File    : utils.py
# @Software: PyCharm
import re

from utils.i18n.context import _ft


def parse_command(command):
    if not command:
        return None, None
    parts = command.split(" ", 1)
    if len(parts) > 1:
        return parts[0], parts[1]
    elif len(parts) == 1:
        return parts[0], None
    else:
        return None, None


def generate_uuid():
    import shortuuid

    return str(shortuuid.uuid())


def escape_md_v2_text(text):
    escape_chars = r"\*_{}\[\]()#+-.!"
    return re.sub(r"([" + escape_chars + "])", r"\\\1", text)


def markdown_to_telegram_html(markdown_text):
    html_text = re.sub(r"\*(.*?)\*", r"<b>\1</b>", markdown_text)
    html_text = re.sub(r"_(.*?)_", r"<i>\1</i>", html_text)
    html_text = re.sub(r"\[(.*?)]\((.*?)\)", r'<a href="\2">\1</a>', html_text)
    html_text = re.sub(r"`(.*?)`", r"<code>\1</code>", html_text)
    return html_text


def command_error_msg(command="", args="", optional_args="", reason=""):
    if not command:
        return _ft("error.command_format")

    if reason == "invalid_type":
        return _ft("error.invalid_query_type")

    if args:
        if optional_args:
            return _ft(
                "error.command_format_with_optional",
                command=command,
                args=args,
                optional_args=optional_args,
            )
        return _ft("error.command_format_with_args", command=command, args=args)
    else:
        return _ft("error.command_format_simple", command=command)
