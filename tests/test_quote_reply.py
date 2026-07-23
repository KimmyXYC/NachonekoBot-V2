import asyncio
from types import SimpleNamespace

import pytest

from plugins import quote_reply


@pytest.mark.parametrize(
    "text",
    [
        "/$like",
        "/ like",
        "\\$like",
        "\\ like",
    ],
)
def test_ascii_action_accepts_dollar_or_space_separator(text):
    assert quote_reply._is_trigger(text) is True
    assert quote_reply._parse_keywords(text) == ["like"]


def test_plain_ascii_bot_command_is_not_a_quote_trigger():
    assert quote_reply._is_trigger("/like") is False


@pytest.mark.parametrize("text", ["/$like", "/ like"])
def test_dollar_and_space_syntax_build_the_same_reply(text):
    message = SimpleNamespace(
        text=text,
        sender_chat=None,
        from_user=SimpleNamespace(id=1, first_name="Alice", last_name=""),
        reply_to_message=SimpleNamespace(
            message_id=10,
            sender_chat=None,
            from_user=SimpleNamespace(
                id=2,
                first_name="Bob",
                last_name="",
                is_bot=False,
            ),
            entities=[],
        ),
        is_topic_message=False,
    )

    reply_text = asyncio.run(quote_reply._build_reply_text(message))

    assert reply_text == "[Alice](tg://user?id=1) like了 [Bob](tg://user?id=2)！"
