import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

from setting.telegrambot import BotSetting

MODULE_PATH = Path(__file__).resolve().parents[1] / "plugins" / "memory.py"
SPEC = importlib.util.spec_from_file_location("memory_plugin_for_test", MODULE_PATH)
memory_module = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(memory_module)

IntentParseResult = memory_module.IntentParseResult
MemoryEntry = memory_module.MemoryEntry


class DummyBot:
    def __init__(self):
        self.replies = []
        self.sent_messages = []
        self.edits = []

    async def reply_to(self, message, text, **kwargs):
        self.replies.append((text, kwargs))
        return SimpleNamespace(chat=SimpleNamespace(id=message.chat.id), message_id=len(self.replies))

    async def send_message(self, chat_id, text, **kwargs):
        self.sent_messages.append((chat_id, text, kwargs))

    async def edit_message_text(self, text, chat_id, message_id, **kwargs):
        self.edits.append((text, chat_id, message_id, kwargs))


def _sample_entries():
    return [
        MemoryEntry("MEM-0001", "值班安排", "周三晚上由 Alice 值班，处理群内反馈。", ["值班", "Alice", "反馈"], "2026-03-17 10:00:00 UTC", "Alice"),
        MemoryEntry("MEM-0002", "服务器信息", "生产服务器位于 hk-1，维护窗口为每周日 02:00。", ["服务器", "hk-1", "维护"], "2026-03-17 11:00:00 UTC", "Bob"),
    ]


def _make_message(text: str):
    return SimpleNamespace(
        text=text,
        entities=[],
        chat=SimpleNamespace(id=-100123, type="supergroup", title="Test Group"),
        from_user=SimpleNamespace(id=42, first_name="Alice", last_name="", username="alice"),
    )


def test_render_and_parse_roundtrip():
    content = memory_module._render_memory_file("Test Group", _sample_entries())
    parsed = memory_module._parse_memory_entries(content)
    assert [item.memory_id for item in parsed] == ["MEM-0001", "MEM-0002"]
    assert parsed[0].title == "值班安排"
    assert "hk-1" in parsed[1].body


def test_extract_message_question_strips_bot_mention(monkeypatch):
    monkeypatch.setattr(BotSetting, "bot_username", "NachoNekoX_bot")
    question = memory_module._extract_message_question("@NachoNekoX_bot 帮我找一下服务器维护时间")
    assert question == "帮我找一下服务器维护时间"


def test_fallback_parse_intent_detects_update():
    parsed = memory_module._fallback_parse_intent("修改 MEM-0002 改成：维护时间改到周六 03:00")
    assert parsed.intent == "update_memory"
    assert parsed.memory_id == "MEM-0002"
    assert "周六 03:00" in parsed.updated_text


def test_find_candidates_supports_exact_memory_id():
    candidates = memory_module._find_candidates("MEM-0002", _sample_entries(), 0.88)
    assert len(candidates) == 1
    assert candidates[0][0].memory_id == "MEM-0002"


def test_find_candidates_returns_fuzzy_matches():
    candidates = memory_module._find_candidates("服务器维护", _sample_entries(), 0.88)
    assert candidates
    assert candidates[0][0].memory_id == "MEM-0002"


def test_dispatch_non_admin_cannot_modify():
    bot = DummyBot()
    msg = _make_message("@bot 记一下：测试")
    parsed = IntentParseResult("add_memory", "测试", None, "", 0.9, "test")
    asyncio.run(memory_module._dispatch_intent(bot, msg, parsed, is_admin=False))
    assert bot.replies


def test_dispatch_list_is_allowed_for_non_admin(monkeypatch):
    bot = DummyBot()
    msg = _make_message("@bot 列出群备忘")
    monkeypatch.setattr(memory_module, "_load_entries", lambda chat_id: _sample_entries())
    parsed = IntentParseResult("list_memory", "", None, "", 0.9, "test")
    asyncio.run(memory_module._dispatch_intent(bot, msg, parsed, is_admin=False))
    assert bot.sent_messages
    assert "MEM-0002" in bot.sent_messages[0][1]


def test_execute_update_memory_updates_entry(monkeypatch):
    bot = DummyBot()
    msg = _make_message("@bot 修改 MEM-0002 改成：维护时间改到周六 03:00")
    entries = _sample_entries()
    saved = {}

    async def always_true(*args, **kwargs):
        return True

    async def optimized(*args, **kwargs):
        return {"title": "服务器信息", "body": "维护时间改到周六 03:00。", "keywords": ["服务器", "维护", "周六"]}

    monkeypatch.setattr(memory_module, "_require_group_admin", always_true)
    monkeypatch.setattr(memory_module, "_load_entries", lambda chat_id: entries)
    monkeypatch.setattr(memory_module, "_save_entries", lambda chat_id, chat_title, updated_entries: saved.setdefault("entries", updated_entries))
    monkeypatch.setattr(memory_module, "_optimize_memory_text", optimized)

    asyncio.run(memory_module._execute_update_memory(bot, msg, "MEM-0002", "维护时间改到周六 03:00", "MEM-0002"))
    assert saved["entries"][1].updated_at
    assert "周六 03:00" in saved["entries"][1].body


def test_parse_intent_falls_back_when_ai_fails(monkeypatch):
    async def raise_error(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(memory_module, "_parse_intent_with_ai", raise_error)
    parsed = asyncio.run(memory_module._parse_intent("删掉关于服务器维护的备忘", True, True))
    assert parsed.intent == "delete_memory"
