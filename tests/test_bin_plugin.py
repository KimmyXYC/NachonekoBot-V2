import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import aiohttp
import pytest


ROOT = Path(__file__).resolve().parents[1]
MASTERCARD_RESULT = {
    "binNum": "223300",
    "acceptanceBrand": "DMC",
    "fundingSource": "DEBIT",
    "productDescription": "DEBIT STANDARD",
    "customerName": "Bank of China Limited",
    "country": {"name": "China"},
}


@pytest.fixture
def plugin(monkeypatch):
    # Load only this plugin, without reading local config or importing bot startup.
    config = ModuleType("utils.yaml")
    config.BotConfig = {}
    monkeypatch.setitem(sys.modules, "utils.yaml", config)
    locale = json.loads(
        (ROOT / "utils/i18n/zh-CN/plugins/bin.json").read_text(encoding="utf-8")
    )
    i18n = ModuleType("utils.i18n")
    i18n._t = lambda key, **kwargs: locale[key].format(**kwargs)
    monkeypatch.setitem(sys.modules, "utils.i18n", i18n)
    monkeypatch.delenv("HANDYAPI_API_KEY", raising=False)
    spec = importlib.util.spec_from_file_location(
        "bin_plugin_for_test", ROOT / "plugins/bin.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Response:
    def __init__(self, data=None, status=200):
        self.data = data
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self, **kwargs):
        if isinstance(self.data, Exception):
            raise self.data
        return self.data


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)


@pytest.fixture
def install_session(monkeypatch, plugin):
    def install(*responses):
        session = Session(responses)

        def client_session(*, timeout):
            assert timeout.total == 10
            return session

        monkeypatch.setattr(plugin.aiohttp, "ClientSession", client_session)
        return session

    # Any unexpected request fails rather than reaching the network.
    install()
    return install


def test_mastercard_success_stops_fallback(plugin, install_session, monkeypatch):
    monkeypatch.setenv("HANDYAPI_API_KEY", "test-key")
    session = install_session(Response(MASTERCARD_RESULT))

    result = asyncio.run(plugin.query_bin_text("22330000"))

    assert result == (
        "BIN：22330000\n卡品牌：Mastercard\n卡类型：DEBIT\n"
        "卡种类：DEBIT STANDARD\n发卡行：Bank of China Limited\n发卡国家：China"
    )
    assert session.calls == [
        (
            "POST",
            "https://btr-reference-app.herokuapp.com/bins",
            {"json": {"bin": "22330000"}},
        )
    ]


@pytest.mark.parametrize(
    "card_bin", ["2233", "22330", "223300", "2233000", "22330000", "001234"]
)
def test_valid_input_is_sent_unchanged(plugin, install_session, card_bin):
    session = install_session(
        Response({"scheme": "visa"} if card_bin == "001234" else MASTERCARD_RESULT)
    )
    result = asyncio.run(plugin.query_bin_text(card_bin))
    if card_bin == "001234":
        assert session.calls[0][1] == "https://lookup.binlist.net/001234"
    else:
        assert session.calls[0][2] == {"json": {"bin": card_bin}}
    assert result.startswith(f"BIN：{card_bin}\n")


@pytest.mark.parametrize(
    "data, expected",
    [
        ({"binNum": "223300"}, "BIN：223300"),
        (
            {"binNum": "223300", "acceptanceBrand": "OTHER", "country": "China"},
            "BIN：223300\n卡品牌：OTHER",
        ),
        (
            {
                "binNum": "223300",
                "fundingSource": None,
                "customerName": "",
                "country": {},
            },
            "BIN：223300",
        ),
    ],
)
def test_optional_fields_and_unknown_brand(plugin, data, expected):
    assert plugin._format_mastercard_bin("223300", data) == expected


@pytest.mark.parametrize(
    "failure",
    [
        Response({}),
        Response(None),
        Response([]),
        Response({"error": "lookup unavailable"}),
        Response({"binNum": None}),
        Response({"binNum": 223300}),
        Response({"binNum": ""}),
        Response({"binNum": "abc123"}),
        Response({"binNum": "123"}),
        Response({"binNum": "123456789"}),
        Response({"binNum": "２２３３００"}),
        Response(status=404),
        Response(status=429),
        Response(status=500),
        Response(status=502),
        Response(ValueError("invalid JSON")),
        Response(TimeoutError()),
        aiohttp.ClientConnectionError(),
        TimeoutError(),
    ],
)
def test_mastercard_failure_falls_back_to_handyapi(
    plugin, install_session, monkeypatch, failure
):
    monkeypatch.setenv("HANDYAPI_API_KEY", "test-key")
    session = install_session(
        failure, Response({"Status": "SUCCESS", "Issuer": "Handy Bank"})
    )
    result = asyncio.run(plugin.query_bin_text("223300"))
    assert result == "BIN：223300\n发卡行：Handy Bank"
    assert [call[1] for call in session.calls] == [
        plugin.MASTERCARD_BIN_URL,
        "https://data.handyapi.com/bin/223300",
    ]
    assert session.calls[1][2] == {"headers": {"x-api-key": "test-key"}}


def test_no_key_skips_handyapi(plugin, install_session):
    session = install_session(Response({"scheme": "visa"}))
    assert asyncio.run(plugin.query_bin_text("411111")) == "BIN：411111\n卡品牌：visa"
    assert [call[1] for call in session.calls] == [
        "https://lookup.binlist.net/411111",
    ]


@pytest.mark.parametrize(
    "failure", [TimeoutError(), Response(TimeoutError()), Response(status=429)]
)
def test_handyapi_failure_reaches_binlist(
    plugin, install_session, monkeypatch, failure
):
    monkeypatch.setenv("HANDYAPI_API_KEY", "test-key")
    session = install_session(
        Response({}), failure, Response({"bank": {"name": "Last Bank"}})
    )
    assert (
        asyncio.run(plugin.query_bin_text("223300")) == "BIN：223300\n发卡行：Last Bank"
    )
    assert [call[1] for call in session.calls] == [
        plugin.MASTERCARD_BIN_URL,
        "https://data.handyapi.com/bin/223300",
        "https://lookup.binlist.net/223300",
    ]


@pytest.mark.parametrize(
    "failure, expected",
    [
        (Response(status=404), "出错了呜呜呜 ~ 目标卡头不存在"),
        (Response(status=429), "出错了呜呜呜 ~ 每分钟限额超过，请等待一分钟再试"),
        (Response(status=503), "出错了呜呜呜 ~ 请求失败，状态码: 503"),
        (aiohttp.ClientConnectionError(), "出错了呜呜呜 ~ 无法访问到binlist。"),
        (Response(ValueError()), "出错了呜呜呜 ~ 无效的参数。"),
    ],
)
def test_all_sources_fail_preserves_final_error(
    plugin, install_session, monkeypatch, failure, expected
):
    monkeypatch.setenv("HANDYAPI_API_KEY", "test-key")
    session = install_session(Response(status=502), TimeoutError(), failure)
    assert asyncio.run(plugin.query_bin_text("223300")) == expected
    assert len(session.calls) == 3


@pytest.mark.parametrize(
    "card_bin", ["", "123", "123456789", "abcdef", "223 300", "-223300"]
)
def test_invalid_input_makes_no_request(plugin, install_session, card_bin):
    session = install_session()
    assert (
        asyncio.run(plugin.query_bin_text(card_bin))
        == "参数无效，请提供 4 到 8 位数字的 BIN 号。"
    )
    assert session.calls == []


@pytest.mark.parametrize("api_key, button_count", [(None, 2), ("test-key", 3)])
def test_command_and_inline_use_shared_query(
    plugin, monkeypatch, api_key, button_count
):
    if api_key:
        monkeypatch.setenv("HANDYAPI_API_KEY", api_key)
    query = AsyncMock(return_value=("shared result", "binlist"))
    monkeypatch.setattr(plugin, "_query_bin_result", query)
    bot = SimpleNamespace(
        reply_to=AsyncMock(return_value=SimpleNamespace(message_id=9)),
        edit_message_text=AsyncMock(),
        answer_inline_query=AsyncMock(),
    )
    message = SimpleNamespace(text="/bin 223300", chat=SimpleNamespace(id=7))
    asyncio.run(plugin.handle_bin_command(bot, message))
    query.assert_awaited_once_with("223300")
    assert bot.edit_message_text.call_args.args == ("shared result", 7, 9)
    assert (
        len(bot.edit_message_text.call_args.kwargs["reply_markup"].keyboard[0])
        == button_count
    )

    query.reset_mock()
    asyncio.run(
        plugin.handle_bin_inline_query(
            bot, SimpleNamespace(query="bin 223300", id="inline-id")
        )
    )
    query.assert_awaited_once_with("223300")
    call = bot.answer_inline_query.call_args
    assert call.args[0] == "inline-id"
    assert call.args[1][0].input_message_content.message_text == "shared result"
    assert len(call.args[1][0].reply_markup.keyboard[0]) == button_count
    assert call.args[1][0].reply_markup.keyboard[0][-1].text == "✓ binlist"


@pytest.mark.parametrize("inline", [False, True])
@pytest.mark.parametrize(
    "api_key, responses, selected_source",
    [
        (None, [Response(MASTERCARD_RESULT)], "mastercard"),
        (
            "test-key",
            [Response({}), Response({"Status": "SUCCESS", "Issuer": "Handy Bank"})],
            "handyapi",
        ),
        (None, [Response({}), Response({"scheme": "visa"})], "binlist"),
        (
            "test-key",
            [Response({}), TimeoutError(), Response({"scheme": "visa"})],
            "binlist",
        ),
        (None, [Response({}), Response(status=404)], None),
    ],
)
def test_initial_message_checks_actual_successful_source(
    plugin, install_session, monkeypatch, inline, api_key, responses, selected_source
):
    if api_key:
        monkeypatch.setenv("HANDYAPI_API_KEY", api_key)
    session = install_session(*responses)
    bot = SimpleNamespace(
        reply_to=AsyncMock(return_value=SimpleNamespace(message_id=9)),
        edit_message_text=AsyncMock(),
        answer_inline_query=AsyncMock(),
    )
    if inline:
        asyncio.run(
            plugin.handle_bin_inline_query(
                bot, SimpleNamespace(query="bin 223300", id="inline-id")
            )
        )
        keyboard = bot.answer_inline_query.call_args.args[1][0].reply_markup
    else:
        asyncio.run(
            plugin.handle_bin_command(
                bot, SimpleNamespace(text="/bin 223300", chat=SimpleNamespace(id=7))
            )
        )
        keyboard = bot.edit_message_text.call_args.kwargs["reply_markup"]
    checked = [
        button.callback_data
        for button in keyboard.keyboard[0]
        if button.text.startswith("✓ ")
    ]
    assert checked == (
        [f"bin_source:{selected_source}:223300"] if selected_source else []
    )
    assert len(session.calls) == len(responses)


@pytest.mark.parametrize("config_key", ["handyapi_api_key", "api_key"])
def test_source_keyboard_is_one_row_and_preserves_bin(plugin, config_key):
    plugin.BotConfig["bin"] = {config_key: "test-key"}
    rows = plugin._build_source_keyboard("001234", "handyapi").to_dict()[
        "inline_keyboard"
    ]
    assert len(rows) == 1
    assert [button["text"] for button in rows[0]] == [
        "✓ HandyAPI",
        "binlist",
    ]
    assert [button["callback_data"] for button in rows[0]] == [
        "bin_source:handyapi:001234",
        "bin_source:binlist:001234",
    ]


@pytest.mark.parametrize(
    "source, data, expected_url, expected_text",
    [
        (
            "mastercard",
            MASTERCARD_RESULT,
            "https://btr-reference-app.herokuapp.com/bins",
            "卡品牌：Mastercard",
        ),
        (
            "handyapi",
            {"Status": "SUCCESS", "Issuer": "Handy Bank"},
            "https://data.handyapi.com/bin/223300",
            "发卡行：Handy Bank",
        ),
        (
            "binlist",
            {"bank": {"name": "Last Bank"}},
            "https://lookup.binlist.net/223300",
            "发卡行：Last Bank",
        ),
    ],
)
def test_manual_source_queries_only_selected_provider(
    plugin, install_session, monkeypatch, source, data, expected_url, expected_text
):
    monkeypatch.setenv("HANDYAPI_API_KEY", "test-key")
    session = install_session(Response(data))
    assert expected_text in asyncio.run(plugin.query_bin_text("223300", source=source))
    assert [call[1] for call in session.calls] == [expected_url]


@pytest.mark.parametrize("source", ["mastercard", "handyapi", "binlist"])
@pytest.mark.parametrize(
    "failure, error_key",
    [
        (Response(status=404), "error.bin_not_found"),
        (Response(status=429), "error.rate_limit_exceeded"),
        (TimeoutError(), "error.source_unreachable"),
        (aiohttp.ClientConnectionError(), "error.source_unreachable"),
        (Response(ValueError()), "error.invalid_parameter"),
    ],
)
def test_manual_source_failures_do_not_fallback(
    plugin, install_session, monkeypatch, source, failure, error_key
):
    monkeypatch.setenv("HANDYAPI_API_KEY", "test-key")
    session = install_session(failure)
    assert asyncio.run(plugin.query_bin_text("223300", source=source)) == plugin._t(
        error_key, source=plugin.BIN_SOURCES[source]
    )
    assert len(session.calls) == 1


def test_manual_handyapi_without_key_makes_no_request(plugin, install_session):
    session = install_session()
    assert asyncio.run(plugin.query_bin_text("223300", source="handyapi")) == plugin._t(
        "error.handyapi_key_missing"
    )
    assert session.calls == []


@pytest.mark.parametrize("inline", [False, True])
@pytest.mark.parametrize(
    "api_key, button_count", [(None, 2), ("test-key", 3), ("your_handyapi_api_key", 2)]
)
def test_callback_acknowledges_before_query_and_edits_original(
    plugin, monkeypatch, inline, api_key, button_count
):
    if api_key:
        monkeypatch.setenv("HANDYAPI_API_KEY", api_key)
    bot = SimpleNamespace(
        answer_callback_query=AsyncMock(), edit_message_text=AsyncMock()
    )

    async def query(card_bin, source=None):
        bot.answer_callback_query.assert_awaited_once_with("callback-id")
        assert (card_bin, source) == ("223300", "binlist")
        return "selected result"

    monkeypatch.setattr(plugin, "query_bin_text", query)
    call = SimpleNamespace(
        id="callback-id",
        data="bin_source:binlist:223300",
        inline_message_id="inline-message-id" if inline else None,
        message=None
        if inline
        else SimpleNamespace(chat=SimpleNamespace(id=7), message_id=9),
    )
    asyncio.run(plugin.handle_bin_source_callback(bot, call))
    edit = bot.edit_message_text.call_args
    assert edit.args == ("selected result",)
    kwargs = dict(edit.kwargs)
    rows = kwargs.pop("reply_markup").to_dict()["inline_keyboard"]
    assert len(rows) == 1 and len(rows[0]) == button_count
    assert rows[0][-1]["text"] == "✓ binlist"
    assert [button["text"] for button in rows[0]] == (
        ["Mastercard", "HandyAPI", "✓ binlist"]
        if button_count == 3
        else ["Mastercard", "✓ binlist"]
    )
    assert kwargs == (
        {"inline_message_id": "inline-message-id"}
        if inline
        else {"chat_id": 7, "message_id": 9}
    )


@pytest.mark.parametrize(
    "data",
    [
        None,
        "bin_source",
        "bin_source:unknown:223300",
        "bin_source:binlist:123",
        "bin_source:binlist:abcdef",
        "bin_source:binlist:223300:extra",
        "other:binlist:223300",
    ],
)
def test_malformed_callback_does_not_query_or_edit(plugin, monkeypatch, data):
    query = AsyncMock()
    monkeypatch.setattr(plugin, "query_bin_text", query)
    bot = SimpleNamespace(
        answer_callback_query=AsyncMock(), edit_message_text=AsyncMock()
    )
    asyncio.run(
        plugin.handle_bin_source_callback(
            bot, SimpleNamespace(id="callback-id", data=data)
        )
    )
    bot.answer_callback_query.assert_awaited_once()
    query.assert_not_awaited()
    bot.edit_message_text.assert_not_awaited()


@pytest.mark.parametrize(
    "description, should_raise",
    [
        ("Bad Request: message is not modified", False),
        ("Bad Request: message to edit not found", True),
    ],
)
def test_callback_handles_only_unchanged_message_error(
    plugin, monkeypatch, description, should_raise
):
    monkeypatch.setattr(plugin, "query_bin_text", AsyncMock(return_value="same result"))
    error = plugin.ApiTelegramException(
        "editMessageText", None, {"error_code": 400, "description": description}
    )
    bot = SimpleNamespace(
        answer_callback_query=AsyncMock(),
        edit_message_text=AsyncMock(side_effect=error),
    )
    call = SimpleNamespace(
        id="callback-id",
        data="bin_source:binlist:223300",
        inline_message_id="inline-id",
    )
    if should_raise:
        with pytest.raises(plugin.ApiTelegramException):
            asyncio.run(plugin.handle_bin_source_callback(bot, call))
    else:
        asyncio.run(plugin.handle_bin_source_callback(bot, call))


def test_registers_callback_without_chat_filter_for_inline_messages(plugin):
    middleware = Mock()
    asyncio.run(plugin.register_handlers(object(), middleware, "bin"))
    kwargs = middleware.register_callback_handler.call_args.kwargs
    assert kwargs["callback"] is plugin.handle_bin_source_callback
    assert kwargs["data_startswith"] == "bin_source:"
    assert kwargs["stop_propagation"] is True
    assert "chat_types" not in kwargs


@pytest.mark.parametrize("lang", ["en", "zh-CN", "zh-TW", "ja"])
def test_source_errors_have_translations(lang):
    locale = json.loads(
        (ROOT / f"utils/i18n/{lang}/plugins/bin.json").read_text(encoding="utf-8")
    )
    assert locale["error.handyapi_key_missing"]
    assert "HandyAPI" in locale["error.source_unreachable"].format(source="HandyAPI")


@pytest.mark.parametrize(
    "card_bin, is_mastercard",
    [
        ("2220", False),
        ("22209999", False),
        ("2221", True),
        ("22210000", True),
        ("2720", True),
        ("27209999", True),
        ("2721", False),
        ("27210000", False),
        ("50999999", False),
        ("5100", True),
        ("51000000", True),
        ("55999999", True),
        ("5600", False),
        ("411111", False),
        ("378282", False),
        ("622202", False),
        ("５０１０", False),
        ("222", False),
    ],
)
def test_mastercard_range_controls_button(plugin, card_bin, is_mastercard):
    assert plugin._is_mastercard_bin(card_bin) is is_mastercard
    buttons = plugin._build_source_keyboard(card_bin).keyboard[0]
    assert any(button.text == "Mastercard" for button in buttons) is is_mastercard


@pytest.mark.parametrize("api_key", [None, "test-key"])
def test_non_mastercard_skips_mastercard_request(
    plugin, install_session, monkeypatch, api_key
):
    if api_key:
        monkeypatch.setenv("HANDYAPI_API_KEY", api_key)
    session = install_session(
        Response(
            {"Status": "SUCCESS", "Issuer": "Bank"}
            if api_key
            else {"bank": {"name": "Bank"}}
        )
    )
    text, source = asyncio.run(plugin._query_bin_result("411111"))
    assert "Bank" in text
    assert source == ("handyapi" if api_key else "binlist")
    assert len(session.calls) == 1
    assert session.calls[0][0] == "GET"


def test_manual_mastercard_rejects_other_ranges(plugin, install_session):
    session = install_session()
    assert asyncio.run(plugin.query_bin_text("411111", "mastercard")) == plugin._t(
        "error.invalid_parameter"
    )
    assert session.calls == []


@pytest.mark.parametrize(
    "source, data",
    [
        ("mastercard", MASTERCARD_RESULT),
        ("handyapi", {"Status": "SUCCESS", "Issuer": "Handy Bank"}),
        ("binlist", {"bank": {"name": "Last Bank"}}),
    ],
)
def test_cache_expires_after_24_hours_without_sliding(
    plugin, install_session, monkeypatch, source, data
):
    monkeypatch.setenv("HANDYAPI_API_KEY", "test-key")
    now = [100.0]
    monkeypatch.setattr(plugin, "monotonic", lambda: now[0])
    session = install_session(Response(data), Response(data))
    first = asyncio.run(plugin._query_bin_result("223300", source))
    assert first[1] == source
    now[0] += 86399
    assert asyncio.run(plugin._query_bin_result("223300", source)) == first
    assert len(session.calls) == 1
    now[0] += 1
    assert asyncio.run(plugin._query_bin_result("223300", source)) == first
    assert len(session.calls) == 2


def test_cache_separates_sources_and_full_bin_strings(plugin, install_session):
    session = install_session(
        Response(MASTERCARD_RESULT),
        Response({"scheme": "mastercard"}),
        Response(MASTERCARD_RESULT),
    )
    mc = asyncio.run(plugin.query_bin_text("223300", "mastercard"))
    other = asyncio.run(plugin.query_bin_text("223300", "binlist"))
    longer = asyncio.run(plugin.query_bin_text("22330000", "mastercard"))
    assert mc != other
    assert longer.startswith("BIN：22330000\n")
    assert asyncio.run(plugin.query_bin_text("223300", "mastercard")) == mc
    assert len(session.calls) == 3


def test_cached_fallback_avoids_retrying_failed_provider(plugin, install_session):
    session = install_session(
        Response({}), Response({"scheme": "mastercard"}), Response(MASTERCARD_RESULT)
    )
    first = asyncio.run(plugin._query_bin_result("223300"))
    assert first[1] == "binlist"
    assert asyncio.run(plugin._query_bin_result("223300")) == first
    assert len(session.calls) == 2
    # 手动切换仍可单独查询此前失败的来源。
    assert (
        asyncio.run(plugin._query_bin_result("223300", "mastercard"))[1] == "mastercard"
    )
    assert len(session.calls) == 3


@pytest.mark.parametrize(
    "failure",
    [
        Response({}),
        Response(status=404),
        Response(status=429),
        Response(status=503),
        Response(ValueError()),
        TimeoutError(),
    ],
)
def test_failed_responses_are_not_cached(plugin, install_session, failure):
    session = install_session(failure, Response(MASTERCARD_RESULT))
    assert asyncio.run(plugin._query_bin_result("223300", "mastercard"))[1] is None
    assert (
        asyncio.run(plugin._query_bin_result("223300", "mastercard"))[1] == "mastercard"
    )
    assert len(session.calls) == 2


def test_empty_binlist_result_is_not_cached(plugin, install_session):
    session = install_session(Response({}), Response({"scheme": "visa"}))
    assert asyncio.run(plugin._query_bin_result("411111"))[1] is None
    assert asyncio.run(plugin._query_bin_result("411111"))[1] == "binlist"
    assert len(session.calls) == 2


def test_cached_data_uses_current_language(plugin, install_session, monkeypatch):
    session = install_session(Response(MASTERCARD_RESULT))
    assert "发卡行" in asyncio.run(plugin.query_bin_text("223300"))
    locale = json.loads(
        (ROOT / "utils/i18n/en/plugins/bin.json").read_text(encoding="utf-8")
    )
    monkeypatch.setattr(
        plugin, "_t", lambda key, **kwargs: locale[key].format(**kwargs)
    )
    text = asyncio.run(plugin.query_bin_text("223300"))
    assert "Bank: Bank of China Limited" in text
    assert "发卡行" not in text
    assert len(session.calls) == 1


def test_handyapi_cache_respects_removed_key(plugin, install_session, monkeypatch):
    monkeypatch.setenv("HANDYAPI_API_KEY", "test-key")
    session = install_session(
        Response({"Status": "SUCCESS", "Issuer": "Handy Bank"}),
        Response({"scheme": "visa"}),
    )
    assert asyncio.run(plugin._query_bin_result("411111"))[1] == "handyapi"
    monkeypatch.delenv("HANDYAPI_API_KEY")
    assert asyncio.run(plugin._query_bin_result("411111"))[1] == "binlist"
    assert len(session.calls) == 2


def test_cache_evicts_old_entries_at_capacity(plugin, install_session, monkeypatch):
    monkeypatch.setattr(plugin, "BIN_CACHE_MAX_ENTRIES", 2)
    session = install_session(*(Response({"scheme": "visa"}) for _ in range(4)))
    for card_bin in ("411111", "411112", "411113", "411111"):
        asyncio.run(plugin.query_bin_text(card_bin))
    assert len(session.calls) == 4
    assert len(plugin._bin_cache) == 2
