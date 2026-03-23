# -*- coding: utf-8 -*-
import datetime as dt
import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import aiohttp
from loguru import logger
from telebot import types

from app.security.permissions import has_group_admin_permission
from setting.telegrambot import BotSetting
from utils.i18n import _t
from utils.yaml import BotConfig

__plugin_name__ = "memory"
__version__ = "1.2.0"
__author__ = "OpenCode"
__description__ = "Manage and query group memories through @bot"
__commands__ = []
__command_category__ = "admin"
__command_order__ = {}
__command_descriptions__ = {}
__command_help__ = {}
__extra_help__ = {"memory_mention": "command.help.memory_mention"}
__toggleable__ = True
__display_name__ = "memory"

MEMORY_ID_RE = re.compile(r"^MEM-(\d{4,})$", re.IGNORECASE)
MEMORY_ID_SEARCH_RE = re.compile(r"\bMEM-\d{4,}\b", re.IGNORECASE)
ENTRY_RE = re.compile(
    r"^##\s+(MEM-\d{4,})\s+\|\s+(.*?)\n"
    r"-\s+Created At:\s+(.*?)\n"
    r"-\s+Created By:\s+(.*?)\n"
    r"(?:-\s+Updated At:\s+(.*?)\n-\s+Updated By:\s+(.*?)\n)?"
    r"-\s+Keywords:\s*(.*?)\n\n"
    r"(.*?)(?=^##\s+MEM-\d{4,}\s+\||\Z)",
    re.MULTILINE | re.DOTALL,
)
JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)

ADD_HINTS = ["记一下", "记住", "添加备忘", "新增备忘", "加入备忘", "帮我记", "存成备忘"]
DELETE_HINTS = ["删除", "删掉", "移除", "去掉"]
UPDATE_HINTS = ["修改", "更新", "改成", "改为", "改一下", "编辑备忘"]
LIST_HINTS = ["列出", "查看", "看看", "显示", "所有备忘", "群备忘", "备忘列表"]


@dataclass
class MemoryEntry:
    memory_id: str
    title: str
    body: str
    keywords: list[str]
    created_at: str
    created_by: str
    updated_at: str = ""
    updated_by: str = ""

    @property
    def summary(self) -> str:
        text = self.body.replace("\n", " ").strip()
        return text[:100] + ("..." if len(text) > 100 else "")


@dataclass
class IntentParseResult:
    intent: str
    target_text: str
    memory_id: str | None
    updated_text: str
    confidence: float
    reason: str = ""


def _msg(key: str, fallback: str, **kwargs) -> str:
    value = _t(key, **kwargs)
    if value == key:
        try:
            return fallback.format(**kwargs) if kwargs else fallback
        except Exception:
            return fallback
    return value


def _language_name_for_prompt(lang: str) -> str:
    mapping = {
        "en": "English",
        "zh-CN": "Simplified Chinese",
        "zh-TW": "Traditional Chinese",
        "ja": "Japanese",
    }
    return mapping.get(lang, lang or "English")


def _get_memory_config() -> dict[str, Any]:
    conf = BotConfig.get("memory", {}) or {}
    return {
        "base_url": str(conf.get("base_url", "https://api.openai.com/v1")).rstrip("/"),
        "api_key": str(conf.get("api_key", "") or ""),
        "model": str(conf.get("model", "gpt-4o-mini")),
        "timeout": int(conf.get("timeout", 60)),
        "storage_dir": str(conf.get("storage_dir", "res/memory")),
        "max_context_items": int(conf.get("max_context_items", 5)),
        "dedupe_threshold": float(conf.get("dedupe_threshold", 0.84)),
        "delete_match_threshold": float(conf.get("delete_match_threshold", 0.88)),
        "intent_confidence_threshold": float(conf.get("intent_confidence_threshold", 0.68)),
    }


def _ensure_storage_dir() -> Path:
    path = Path(_get_memory_config()["storage_dir"])
    path.mkdir(parents=True, exist_ok=True)
    return path


def _get_memory_file(chat_id: int) -> Path:
    return _ensure_storage_dir() / f"{chat_id}.md"


def _normalize_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip().lower())
    return re.sub(r"[^\w\u4e00-\u9fff\s-]", "", cleaned)


def _tokenize(text: str) -> set[str]:
    normalized = _normalize_text(text)
    latin_parts = re.findall(r"[a-z0-9_-]+", normalized)
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", normalized)
    cjk_bigrams = ["".join(cjk_chars[i : i + 2]) for i in range(len(cjk_chars) - 1)]
    return {part for part in [*latin_parts, *cjk_chars, *cjk_bigrams] if part}


def _score_match(query: str, entry: MemoryEntry) -> float:
    normalized_query = _normalize_text(query)
    haystack = " ".join([entry.memory_id, entry.title, entry.body, " ".join(entry.keywords)])
    normalized_haystack = _normalize_text(haystack)
    ratio = SequenceMatcher(None, normalized_query, normalized_haystack).ratio()
    if not normalized_query:
        return 0.0
    overlap = len(_tokenize(normalized_query) & _tokenize(normalized_haystack)) / max(len(_tokenize(normalized_query)), 1)
    substring_bonus = 0.25 if normalized_query in normalized_haystack else 0.0
    prefix_bonus = 0.15 if entry.memory_id.lower() == normalized_query else 0.0
    return min(1.0, ratio * 0.55 + overlap * 0.45 + substring_bonus + prefix_bonus)


def _parse_memory_entries(content: str) -> list[MemoryEntry]:
    entries: list[MemoryEntry] = []
    for match in ENTRY_RE.finditer(content or ""):
        keywords = [item.strip() for item in (match.group(7) or "").split(",") if item.strip()]
        entries.append(
            MemoryEntry(
                memory_id=match.group(1).strip(),
                title=match.group(2).strip(),
                created_at=match.group(3).strip(),
                created_by=match.group(4).strip(),
                updated_at=(match.group(5) or "").strip(),
                updated_by=(match.group(6) or "").strip(),
                keywords=keywords,
                body=match.group(8).strip(),
            )
        )
    return entries


def _render_memory_file(chat_title: str, entries: list[MemoryEntry]) -> str:
    lines = [
        "# Group Memory",
        "",
        f"- Chat Title: {(chat_title or 'Unknown Group').replace(chr(10), ' ').strip()}",
        f"- Updated At: {dt.datetime.now(dt.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"- Total Entries: {len(entries)}",
        "",
    ]
    for entry in entries:
        lines.extend(
            [
                f"## {entry.memory_id} | {entry.title}",
                f"- Created At: {entry.created_at}",
                f"- Created By: {entry.created_by}",
            ]
        )
        if entry.updated_at:
            lines.append(f"- Updated At: {entry.updated_at}")
            lines.append(f"- Updated By: {entry.updated_by}")
        lines.extend(
            [
                f"- Keywords: {', '.join(entry.keywords)}",
                "",
                entry.body.strip(),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _next_memory_id(entries: list[MemoryEntry]) -> str:
    current = 0
    for entry in entries:
        match = MEMORY_ID_RE.match(entry.memory_id)
        if match:
            current = max(current, int(match.group(1)))
    return f"MEM-{current + 1:04d}"


def _extract_message_question(text: str) -> str:
    username = (BotSetting.bot_username or "").lstrip("@")
    if not username or not text:
        return ""
    return re.sub(rf"@{re.escape(username)}\b", "", text, count=1, flags=re.IGNORECASE).strip(" \n\t:,-")


def _message_mentions_bot(message: types.Message) -> bool:
    text = getattr(message, "text", None)
    username = (BotSetting.bot_username or "").lstrip("@")
    if not text or not username:
        return False
    for ent in list(getattr(message, "entities", None) or []):
        if getattr(ent, "type", "") == "mention":
            start = getattr(ent, "offset", 0)
            end = start + getattr(ent, "length", 0)
            if text[start:end].lstrip("@").lower() == username.lower():
                return True
    return bool(re.search(rf"@{re.escape(username)}\b", text, re.IGNORECASE))


def _chunk_text(text: str, limit: int = 3500) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    remaining = text
    while remaining:
        cut = remaining[:limit]
        if len(remaining) > limit:
            split_at = cut.rfind("\n")
            if split_at > limit // 2:
                cut = cut[:split_at]
        chunks.append(cut)
        remaining = remaining[len(cut) :].lstrip("\n")
    return chunks


async def _reply_or_edit(bot, message: types.Message, text: str, progress_message=None, **kwargs):
    if progress_message is not None:
        try:
            await bot.edit_message_text(
                text, progress_message.chat.id, progress_message.message_id, **kwargs
            )
            return
        except Exception:
            pass
    await bot.reply_to(message, text, **kwargs)


def _extract_json_payload(raw_text: str) -> dict[str, Any]:
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("empty response")
    candidates = [text]
    block = JSON_BLOCK_RE.search(text)
    if block:
        candidates.insert(0, block.group(1).strip())
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise ValueError("response is not valid json")


async def _call_openai_compatible(messages: list[dict[str, Any]]) -> str:
    conf = _get_memory_config()
    if not conf["api_key"]:
        raise ValueError("memory.api_key missing")
    payload = {"model": conf["model"], "messages": messages, "temperature": 0.2}
    headers = {"Authorization": f"Bearer {conf['api_key']}", "Content-Type": "application/json"}
    timeout = aiohttp.ClientTimeout(total=conf["timeout"])
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(f"{conf['base_url']}/chat/completions", headers=headers, json=payload) as resp:
            body = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"AI request failed ({resp.status}): {body[:300]}")
            data = await resp.json()
    return data["choices"][0]["message"]["content"].strip()


def _extract_memory_id(text: str) -> str | None:
    match = MEMORY_ID_SEARCH_RE.search(text or "")
    return match.group(0).upper() if match else None


def _fallback_optimize_memory(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    return {"title": cleaned[:30] or "Untitled", "body": cleaned or "", "keywords": [item for item in _tokenize(cleaned) if len(item) >= 2][:6]}


def _split_update_text(text: str) -> tuple[str, str]:
    for token in ["改成", "改为", "更新为", "修改为", "内容改成", "内容改为"]:
        if token in text:
            before, after = text.split(token, 1)
            return before.strip(" ：:，,。"), after.strip(" ：:，,。")
    return text.strip(), ""


def _trim_after_prefix(text: str, prefixes: list[str]) -> str:
    cleaned = (text or "").strip()
    for prefix in prefixes:
        if prefix in cleaned:
            after = cleaned.split(prefix, 1)[1].strip(" ：:，,。")
            if after:
                return after
    return cleaned


def _fallback_parse_intent(text: str) -> IntentParseResult:
    memory_id = _extract_memory_id(text)
    if any(hint in text for hint in LIST_HINTS):
        return IntentParseResult("list_memory", "", None, "", 0.92, "rule:list")
    if any(hint in text for hint in UPDATE_HINTS):
        target, updated = _split_update_text(_trim_after_prefix(text, UPDATE_HINTS))
        return IntentParseResult("update_memory", target, memory_id, updated, 0.86, "rule:update")
    if any(hint in text for hint in DELETE_HINTS):
        return IntentParseResult("delete_memory", _trim_after_prefix(text, DELETE_HINTS), memory_id, "", 0.86, "rule:delete")
    if any(hint in text for hint in ADD_HINTS):
        return IntentParseResult("add_memory", _trim_after_prefix(text, ADD_HINTS), None, "", 0.86, "rule:add")
    if _normalize_text(text) in {"", "help", "帮助", "怎么用", "可以做什么"}:
        return IntentParseResult("unknown", "", None, "", 0.7, "rule:help")
    return IntentParseResult("qa", text.strip(), memory_id, "", 0.6, "rule:qa")


async def _parse_intent_with_ai(raw_text: str, is_admin: bool, has_entries: bool) -> IntentParseResult:
    messages = [
        {
            "role": "system",
            "content": (
                "Parse a group-memory bot request. "
                "Return JSON with keys intent,target_text,memory_id,updated_text,confidence,reason. "
                "Intent must be one of add_memory,delete_memory,update_memory,list_memory,qa,unknown."
            ),
        },
        {"role": "user", "content": f"text={raw_text}\nis_admin={is_admin}\nhas_entries={has_entries}"},
    ]
    payload = _extract_json_payload(await _call_openai_compatible(messages))
    intent = str(payload.get("intent", "")).strip()
    if intent not in {"add_memory", "delete_memory", "update_memory", "list_memory", "qa", "unknown"}:
        raise ValueError("invalid intent")
    memory_id = payload.get("memory_id")
    memory_id = str(memory_id).upper().strip() if memory_id else None
    return IntentParseResult(
        intent=intent,
        target_text=str(payload.get("target_text", "") or "").strip(),
        memory_id=memory_id if memory_id and MEMORY_ID_RE.match(memory_id) else None,
        updated_text=str(payload.get("updated_text", "") or "").strip(),
        confidence=float(payload.get("confidence", 0.0) or 0.0),
        reason=str(payload.get("reason", "") or "").strip(),
    )


async def _parse_intent(raw_text: str, is_admin: bool, has_entries: bool) -> IntentParseResult:
    threshold = _get_memory_config()["intent_confidence_threshold"]
    try:
        parsed = await _parse_intent_with_ai(raw_text, is_admin, has_entries)
        if parsed.confidence >= threshold:
            return parsed
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"[memory] fallback parse: {exc}")
    return _fallback_parse_intent(raw_text)


async def _optimize_memory_text(
    raw_text: str, existing_entries: list[MemoryEntry], target_lang: str = "en"
) -> dict[str, Any]:
    recent_context = "\n".join(f"- {entry.memory_id}: {entry.title} | {entry.summary}" for entry in existing_entries[-5:])
    messages = [
        {
            "role": "system",
            "content": (
                "Rewrite the user's text into a clean memory entry. "
                "Return JSON with title, body, keywords. "
                "The final title, body, and keywords must be written in the target group language. "
                "Do not mix languages unless the original content requires a proper noun or fixed term."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Target group language code: {target_lang}\n"
                f"Target group language name: {_language_name_for_prompt(target_lang)}\n"
                f"Existing memories:\n{recent_context or 'none'}\n\n"
                f"New text:\n{raw_text}"
            ),
        },
    ]
    try:
        payload = _extract_json_payload(await _call_openai_compatible(messages))
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[memory] optimize fallback: {exc}")
        return _fallback_optimize_memory(raw_text)
    fallback = _fallback_optimize_memory(raw_text)
    keywords = payload.get("keywords", [])
    normalized: list[str] = []
    if isinstance(keywords, list):
        for item in keywords:
            text = str(item).strip()
            if text and text not in normalized:
                normalized.append(text)
    return {
        "title": str(payload.get("title", "")).strip() or fallback["title"],
        "body": str(payload.get("body", "")).strip() or fallback["body"],
        "keywords": normalized[:8] or fallback["keywords"],
    }


def _find_duplicate_candidates(optimized: dict[str, Any], entries: list[MemoryEntry], threshold: float) -> list[tuple[MemoryEntry, float]]:
    query = " ".join([optimized.get("title", ""), optimized.get("body", ""), " ".join(optimized.get("keywords", []))])
    matches = [(entry, _score_match(query, entry)) for entry in entries]
    matches = [item for item in matches if item[1] >= threshold]
    matches.sort(key=lambda item: item[1], reverse=True)
    return matches[:3]


def _find_candidates(query: str, entries: list[MemoryEntry], threshold: float, limit: int = 5) -> list[tuple[MemoryEntry, float]]:
    exact_id = (query or "").strip().upper()
    if MEMORY_ID_RE.match(exact_id):
        exact = [entry for entry in entries if entry.memory_id.upper() == exact_id]
        return [(exact[0], 1.0)] if exact else []
    scored = [(entry, _score_match(query, entry)) for entry in entries]
    scored.sort(key=lambda item: item[1], reverse=True)
    return [item for item in scored if item[1] >= max(threshold * 0.55, 0.3)][:limit]


def _select_context_entries(query: str, entries: list[MemoryEntry], limit: int) -> list[MemoryEntry]:
    scored = [(entry, _score_match(query, entry)) for entry in entries]
    scored.sort(key=lambda item: item[1], reverse=True)
    return [entry for entry, score in scored[:limit] if score >= 0.2]


async def _answer_from_memory(question: str, entries: list[MemoryEntry]) -> str:
    context_entries = _select_context_entries(question, entries, _get_memory_config()["max_context_items"])
    if not context_entries:
        return _msg("qa.no_match", "No matching group memory was found, so I can't answer only from group memories.")
    context_text = "\n\n".join(
        f"[{entry.memory_id}] {entry.title}\nKeywords: {', '.join(entry.keywords)}\n{entry.body}"
        for entry in context_entries
    )
    messages = [
        {"role": "system", "content": "Answer only from the provided group memories. If the answer is missing, say so clearly."},
        {"role": "user", "content": f"Memories:\n{context_text}\n\nQuestion:\n{question}"},
    ]
    try:
        return await _call_openai_compatible(messages)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[memory] answer fallback: {exc}")
        bullets = "\n".join(f"- {entry.memory_id} {entry.title}: {entry.summary}" for entry in context_entries)
        return _msg("qa.ai_failed", "I found related memories, but AI failed:\n{bullets}", bullets=bullets)


def _load_entries(chat_id: int) -> list[MemoryEntry]:
    path = _get_memory_file(chat_id)
    if not path.exists():
        return []
    return _parse_memory_entries(path.read_text(encoding="utf-8"))


def _save_entries(chat_id: int, chat_title: str, entries: list[MemoryEntry]) -> None:
    _get_memory_file(chat_id).write_text(_render_memory_file(chat_title, entries), encoding="utf-8")


def _user_label(user: types.User | None) -> str:
    if not user:
        return "Unknown"
    full_name = " ".join(part for part in [getattr(user, "first_name", ""), getattr(user, "last_name", "")] if part).strip()
    if getattr(user, "username", None):
        username = f"@{user.username}"
        return f"{full_name} ({username})".strip() if full_name else username
    return full_name or str(getattr(user, "id", "Unknown"))


async def _is_group_admin(bot, message: types.Message) -> bool:
    sender = getattr(message, "from_user", None)
    if not sender or message.chat.type not in ("group", "supergroup"):
        return False
    return await has_group_admin_permission(bot, message.chat.id, sender.id, required_permission=None)


async def _require_group_admin(bot, message: types.Message) -> bool:
    if message.chat.type not in ("group", "supergroup"):
        await bot.reply_to(message, _msg("error.group_only", "This feature can only be used in groups."))
        return False
    if not await _is_group_admin(bot, message):
        await bot.reply_to(message, _msg("error.modify_denied", "You can ask questions or view memories, but you cannot modify group memories."))
        return False
    return True


async def _execute_add_memory(bot, message: types.Message, payload: str, progress_message=None):
    if not await _require_group_admin(bot, message):
        return
    if not payload.strip():
        await _reply_or_edit(bot, message, _msg("prompt.add_missing", "Please tell me what to save after mentioning me."), progress_message=progress_message)
        return
    if progress_message is not None:
        try:
            await bot.edit_message_text(
                _msg("status.adding", "Saving group memory..."),
                progress_message.chat.id,
                progress_message.message_id,
            )
        except Exception:
            progress_message = None
    progress = progress_message or await bot.reply_to(message, _msg("status.adding", "Saving group memory..."))
    entries = _load_entries(message.chat.id)
    optimized = await _optimize_memory_text(
        payload, entries, target_lang=getattr(bot, "lang", "en")
    )
    new_entry = MemoryEntry(
        memory_id=_next_memory_id(entries),
        title=optimized["title"],
        body=optimized["body"],
        keywords=optimized.get("keywords", []),
        created_at=dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        created_by=_user_label(message.from_user),
    )
    duplicates = _find_duplicate_candidates(optimized, entries, _get_memory_config()["dedupe_threshold"])
    entries.append(new_entry)
    _save_entries(message.chat.id, getattr(message.chat, "title", ""), entries)
    lines = [
        _msg("result.added", "Added memory `{memory_id}`", memory_id=new_entry.memory_id),
        _msg("label.title", "Title: {title}", title=new_entry.title),
        _msg("label.summary", "Summary: {summary}", summary=new_entry.summary),
    ]
    if duplicates:
        dup_text = "；".join(f"{item.memory_id}({score:.2f})" for item, score in duplicates)
        lines.append(_msg("result.duplicate_hint", "Possible duplicate memories: {items}", items=dup_text))
    text = "\n".join(lines)
    try:
        await bot.edit_message_text(text, progress.chat.id, progress.message_id, parse_mode="Markdown")
    except Exception:
        await bot.reply_to(message, text, parse_mode="Markdown")


async def _execute_list_memory(bot, message: types.Message, progress_message=None):
    entries = _load_entries(message.chat.id)
    if not entries:
        await _reply_or_edit(bot, message, _msg("result.list_empty", "There are no group memories yet."), progress_message=progress_message)
        return
    lines = [_msg("result.list_header", "There are {count} memories in this group:", count=len(entries)), ""]
    for entry in reversed(entries):
        lines.append(f"- `{entry.memory_id}` {entry.title}")
        lines.append(f"  {entry.summary}")
    chunks = _chunk_text("\n".join(lines))
    if progress_message is not None and chunks:
        try:
            await bot.edit_message_text(
                chunks[0], progress_message.chat.id, progress_message.message_id, parse_mode="Markdown"
            )
            chunks = chunks[1:]
        except Exception:
            pass
    for chunk in chunks:
        await bot.send_message(message.chat.id, chunk, parse_mode="Markdown")


async def _execute_delete_memory(bot, message: types.Message, target_text: str, memory_id: str | None = None, progress_message=None):
    if not await _require_group_admin(bot, message):
        return
    query = (memory_id or target_text or "").strip()
    if not query:
        await _reply_or_edit(bot, message, _msg("prompt.delete_missing", "Please tell me which memory to delete, or give a MEM-id directly."), progress_message=progress_message)
        return
    entries = _load_entries(message.chat.id)
    if not entries:
        await _reply_or_edit(bot, message, _msg("result.delete_empty", "There are no memories to delete."), progress_message=progress_message)
        return
    candidates = _find_candidates(query, entries, _get_memory_config()["delete_match_threshold"])
    if not candidates:
        await _reply_or_edit(bot, message, _msg("result.no_match", "No matching memory was found."), progress_message=progress_message)
        return
    if len(candidates) == 1 and (candidates[0][1] >= _get_memory_config()["delete_match_threshold"] or bool(memory_id and MEMORY_ID_RE.match(memory_id))):
        target = candidates[0][0]
        _save_entries(message.chat.id, getattr(message.chat, "title", ""), [entry for entry in entries if entry.memory_id != target.memory_id])
        await _reply_or_edit(bot, message, _msg("result.deleted", "Deleted memory `{memory_id}` {title}", memory_id=target.memory_id, title=target.title), progress_message=progress_message, parse_mode="Markdown")
        return
    lines = [_msg("result.multiple_matches", "Matched multiple memories. Please use a more specific keyword or a MEM-id:"), ""]
    for entry, score in candidates:
        lines.append(f"- `{entry.memory_id}` {entry.title} ({score:.2f})")
        lines.append(f"  {entry.summary}")
    await _reply_or_edit(bot, message, "\n".join(lines), progress_message=progress_message, parse_mode="Markdown")


async def _execute_update_memory(bot, message: types.Message, target_text: str, updated_text: str, memory_id: str | None = None, progress_message=None):
    if not await _require_group_admin(bot, message):
        return
    query = (memory_id or target_text or "").strip()
    if not query:
        await _reply_or_edit(bot, message, _msg("prompt.update_missing_target", "Please tell me which memory to modify, or give a MEM-id directly."), progress_message=progress_message)
        return
    if not updated_text.strip():
        await _reply_or_edit(bot, message, _msg("prompt.update_missing_content", "Please tell me what the memory should be updated to."), progress_message=progress_message)
        return
    entries = _load_entries(message.chat.id)
    if not entries:
        await _reply_or_edit(bot, message, _msg("result.update_empty", "There are no memories to update."), progress_message=progress_message)
        return
    candidates = _find_candidates(query, entries, _get_memory_config()["delete_match_threshold"])
    if not candidates:
        await _reply_or_edit(bot, message, _msg("result.no_match", "No matching memory was found."), progress_message=progress_message)
        return
    if len(candidates) != 1 and not (memory_id and MEMORY_ID_RE.match(memory_id)):
        lines = [_msg("result.multiple_matches_update", "Matched multiple memories. Please use a more specific keyword or a MEM-id for update:"), ""]
        for entry, score in candidates:
            lines.append(f"- `{entry.memory_id}` {entry.title} ({score:.2f})")
            lines.append(f"  {entry.summary}")
        await _reply_or_edit(bot, message, "\n".join(lines), progress_message=progress_message, parse_mode="Markdown")
        return
    target = candidates[0][0]
    if progress_message is not None:
        try:
            await bot.edit_message_text(
                _msg("status.adding", "Saving group memory..."),
                progress_message.chat.id,
                progress_message.message_id,
            )
        except Exception:
            progress_message = None
    optimized = await _optimize_memory_text(
        updated_text, entries, target_lang=getattr(bot, "lang", "en")
    )
    now = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    for index, entry in enumerate(entries):
        if entry.memory_id == target.memory_id:
            entries[index] = MemoryEntry(
                memory_id=entry.memory_id,
                title=optimized["title"],
                body=optimized["body"],
                keywords=optimized.get("keywords", []),
                created_at=entry.created_at,
                created_by=entry.created_by,
                updated_at=now,
                updated_by=_user_label(message.from_user),
            )
            break
    _save_entries(message.chat.id, getattr(message.chat, "title", ""), entries)
    await _reply_or_edit(bot, message, _msg("result.updated", "Updated memory `{memory_id}` {title}", memory_id=target.memory_id, title=optimized["title"]), progress_message=progress_message, parse_mode="Markdown")


async def _answer_qa(bot, message: types.Message, question: str, progress_message=None):
    entries = _load_entries(message.chat.id)
    if not entries:
        await _reply_or_edit(bot, message, _msg("qa.empty", "There are no group memories yet, so I can't answer from memory."), progress_message=progress_message)
        return
    if progress_message is not None:
        try:
            await bot.edit_message_text(
                _msg("status.answering", "Searching group memories and preparing an answer..."),
                progress_message.chat.id,
                progress_message.message_id,
            )
        except Exception:
            progress_message = None
    progress = progress_message or await bot.reply_to(message, _msg("status.answering", "Searching group memories and preparing an answer..."))
    answer = await _answer_from_memory(question, entries)
    try:
        await bot.edit_message_text(answer, progress.chat.id, progress.message_id)
    except Exception:
        for chunk in _chunk_text(answer):
            await bot.send_message(message.chat.id, chunk)


async def _dispatch_intent(bot, message: types.Message, parsed: IntentParseResult, is_admin: bool, progress_message=None):
    if parsed.intent == "add_memory":
        if not is_admin:
            await _reply_or_edit(bot, message, _msg("error.modify_denied", "You can ask questions or view memories, but you cannot modify group memories."), progress_message=progress_message)
            return
        await _execute_add_memory(bot, message, parsed.target_text, progress_message=progress_message)
        return
    if parsed.intent == "delete_memory":
        if not is_admin:
            await _reply_or_edit(bot, message, _msg("error.modify_denied", "You can ask questions or view memories, but you cannot modify group memories."), progress_message=progress_message)
            return
        await _execute_delete_memory(bot, message, parsed.target_text, parsed.memory_id, progress_message=progress_message)
        return
    if parsed.intent == "update_memory":
        if not is_admin:
            await _reply_or_edit(bot, message, _msg("error.modify_denied", "You can ask questions or view memories, but you cannot modify group memories."), progress_message=progress_message)
            return
        await _execute_update_memory(bot, message, parsed.target_text, parsed.updated_text, parsed.memory_id, progress_message=progress_message)
        return
    if parsed.intent == "list_memory":
        await _execute_list_memory(bot, message, progress_message=progress_message)
        return
    if parsed.intent == "qa":
        await _answer_qa(bot, message, parsed.target_text, progress_message=progress_message)
        return
    await _reply_or_edit(bot, message, _msg("prompt.usage", "You can say:\n@botusername remember this: Friday 8pm meeting\n@botusername update MEM-0001 to: Friday 9pm meeting\n@botusername delete the server maintenance memory\n@botusername list group memories\n@botusername when is server maintenance"), progress_message=progress_message)


async def _handle_memory_message(bot, message: types.Message):
    if message.chat.type not in ("group", "supergroup") or not _message_mentions_bot(message):
        return
    text = _extract_message_question(message.text or "")
    if not text:
        await bot.reply_to(message, _msg("prompt.empty_after_mention", "Please put a concrete request after mentioning me."))
        return
    progress_message = await bot.reply_to(
        message, _msg("status.thinking", "Thinking...")
    )
    entries = _load_entries(message.chat.id)
    is_admin = await _is_group_admin(bot, message)
    parsed = await _parse_intent(text, is_admin=is_admin, has_entries=bool(entries))
    await _dispatch_intent(bot, message, parsed, is_admin, progress_message=progress_message)


async def register_handlers(bot, middleware, plugin_name):
    async def memory_message_handler(bot, message: types.Message):
        await _handle_memory_message(bot, message)

    middleware.register_message_handler(
        callback=memory_message_handler,
        plugin_name=plugin_name,
        handler_name="memory_mention",
        priority=40,
        stop_propagation=False,
        chat_types=["group", "supergroup"],
        content_types=["text"],
        func=lambda m: bool(getattr(m, "text", None)) and _message_mentions_bot(m),
    )

    logger.info("memory plugin registered with mention-based memory management")


def get_plugin_info() -> dict[str, Any]:
    return {"name": __plugin_name__, "version": __version__, "author": __author__, "description": __description__, "commands": __commands__}
