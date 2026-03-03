# i18n Layout

Framework text keys are stored in language folders:

- `utils/i18n/en/framework.json`
- `utils/i18n/zh-CN/framework.json`
- New language template: `utils/i18n/template/framework.template.json`

Plugin language files are reserved under:

- `utils/i18n/{lang}/plugins/<plugin_name>.json`

Supported languages: `en`, `zh-CN`, `zh-TW`, `ja`

## Core API — `_t` and `_ft`

The recommended way to do translations in plugin code is via the global `_t()` and `_ft()` functions, powered by `contextvars`:

```python
from utils.i18n import _t, _ft

async def handle_command(bot, message):
    # Plugin-level translation (from plugins/{plugin_name}.json)
    await bot.reply_to(message, _t("error.invalid_target"))
    await bot.reply_to(message, _t("status.querying", target=target))

    # Framework-level translation (from framework.json)
    msg = _ft("error.command_format_with_args", command="ip", args="target")
```

### How it works

The middleware automatically sets `ContextVar` values (language + plugin name) before calling any handler. `_t()` and `_ft()` read from these `ContextVar`s, so they always know the current request's language and plugin — no parameter passing needed.

### `LocalizedBot` (still available)

Plugins receive a `LocalizedBot` wrapper as their `bot` parameter. It still provides `bot.t()`, `bot.ft()`, `bot.lang`, and `bot.plugin_name` — but `_t()` / `_ft()` are the preferred shorthand:

```python
# These are equivalent:
_t("error.invalid_target")
bot.t("error.invalid_target")

# These are equivalent:
_ft("error.command_format")
bot.ft("error.command_format")

# Access language code
lang = bot.lang  # e.g. "zh-CN"
```

### Sub-functions don't need `_t` as a parameter

Since `_t` reads from `ContextVar`, deeply nested functions can use it directly:

```python
from utils.i18n import _t

async def query_ip_text(target: str) -> str:
    # No need to receive _t as a parameter — just import and use
    return _t("error.request_failed")

async def handle_ip_command(bot, message):
    result = await query_ip_text(target)  # Clean — no _t passing
```

### For scheduled jobs / non-handler contexts

```python
from utils.i18n import _t
from utils.i18n.runtime import make_localized_bot_for_chat

lbot = await make_localized_bot_for_chat(bot, plugin_name, chat_id)
# ContextVar is set automatically — _t() works
await bot.send_message(chat_id, _t("result.some_key", arg=val))
```

### For framework code (controller.py, event.py)

Code that is NOT dispatched through the middleware (e.g., `controller.py`, `event.py`) should use the explicit `t(key, lang)` function since `ContextVar` is not set:

```python
from utils.i18n import t

lang = await get_message_language(message)
text = t("plugin.command.help", lang)
```

## Translation key conventions

- `command.description.<command>` / `command.help.<command>` — command metadata
- `meta.description` / `meta.display_name` — plugin metadata
- `error.*` — error messages
- `prompt.*` — user prompts
- `status.*` — processing status
- `result.*` — results
- `label.*` — labels

JSON format:

```json
{
  "error.invalid_target": "Invalid target address",
  "status.querying": "Querying {target}..."
}
```

## Fallback behavior

1. Look up key in requested language
2. Fall back to `en` (default language)
3. Return the raw key string (with a `logger.warning`)

## Startup validation

Call `validate_translations()` from `utils/i18n/validator.py` at startup to check:
- Missing keys compared to the `en` baseline
- Placeholder (`{var}`) mismatches between languages

## Add a new language

```bash
python tools/add_i18n_language.py --code ja --label "日本語"
```

## Scaffold plugin locale files

```bash
python tools/scaffold_plugin_locales.py
```

Generates locale skeletons for every plugin across all supported languages.
