# i18n Layout

Framework text keys are stored in language folders:

- `utils/i18n/en/framework.json`
- `utils/i18n/zh-CN/framework.json`
- New language template: `utils/i18n/template/framework.template.json`

Plugin language files are reserved under:

- `utils/i18n/en/plugins/<plugin_name>.json`
- `utils/i18n/zh-CN/plugins/<plugin_name>.json`

JSON format example:

```json
{
  "hello": "Hello",
  "bye": "Goodbye"
}
```

Runtime API:

- `t(key, lang, **kwargs)` for framework keys
- `plugin_t(plugin_name, key, lang, **kwargs)` for plugin keys

Language config:

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
