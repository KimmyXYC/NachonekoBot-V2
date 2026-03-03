# i18n Layout

Framework text keys are stored in language folders:

- `utils/i18n/en/framework.json`
- `utils/i18n/zh-CN/framework.json`
- New language template: `utils/i18n/template/framework.template.json`

Plugin language files are reserved under:

- `utils/i18n/{lang}/plugins/<plugin_name>.json`

Supported languages: `en`, `zh-CN`, `zh-TW`, `ja`

## Core API

### `LocalizedBot` (replaces `LocalizedBotProxy`)

Plugins receive a `LocalizedBot` wrapper as their `bot` parameter. It carries i18n context (language + plugin name) and provides explicit translation methods. **No implicit/automatic translation** is performed on `reply_to`, `send_message`, etc.

```python
# Plugin-level translation (from plugins/{plugin_name}.json)
text = bot.t("error.invalid_target")
text = bot.t("status.querying", target=target)

# Framework-level translation (from framework.json)
text = bot.ft("error.command_format_with_args", command="ip", args="target")

# Access language code directly
lang = bot.lang           # e.g. "zh-CN"
plugin = bot.plugin_name  # e.g. "ping"
```

All bot methods (`reply_to`, `send_message`, `edit_message_text`, etc.) are transparently proxied to the underlying bot instance.

### Service functions

- `t(key, lang, **kwargs)` for framework keys
- `plugin_t(plugin_name, key, lang, **kwargs)` for plugin keys

### For scheduled jobs / non-handler contexts

```python
from utils.i18n.runtime import make_localized_bot_for_chat

lbot = await make_localized_bot_for_chat(bot, plugin_name, chat_id)
await bot.send_message(chat_id, lbot.t("result.some_key", arg=val))
```

## Translation key conventions

Plugin locale value behavior:

- For command metadata, use keys like:
  - `command.description.<command>`
  - `command.help.<command>`
  - `meta.description`, `meta.display_name`
- For runtime message text, use semantic keys:
  - `error.*` for error messages
  - `prompt.*` for user prompts
  - `status.*` for processing status
  - `result.*` for results
  - `label.*` for labels

JSON format example:

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

## Language config

- `utils/i18n/config.py` (`DEFAULT_LANGUAGE`, `SUPPORTED_LANGUAGES`)

## Add a new language (fixed template flow)

1. Run scaffold command:

```bash
python tools/add_i18n_language.py --code ja --label "日本語"
```

2. Edit generated file:

- `utils/i18n/ja/framework.json`

3. (Optional) add plugin locales:

- `utils/i18n/ja/plugins/<plugin_name>.json`

Notes:

- Use `--force` to overwrite existing `framework.json` from template.
- The command also updates `utils/i18n/config.py` automatically.

## Scaffold all plugin locale files

Generate locale skeletons for every plugin:

```bash
python tools/scaffold_plugin_locales.py
```

This script scans `plugins/*.py` and merges extracted metadata and static outbound texts into locale files for all supported languages (`en`, `zh-CN`, `zh-TW`, `ja`).
