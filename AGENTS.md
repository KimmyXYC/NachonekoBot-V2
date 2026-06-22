# AGENTS.md

## Project facts
- Python 3.12 Telegram bot framework; real entrypoint is `main.py`.
- Startup loads `.env`, Dynaconf `conf_dir/settings.toml`, YAML `conf_dir/config.yaml`, connects PostgreSQL, then runs `app.controller.BotRunner`.
- Main boundaries: `app/controller.py` wires Telegram handlers, plugin loading, scheduler, and polling; `app/plugin_system/` owns plugin scan/load/middleware; `plugins/*.py` are runtime plugins; `utils/postgres.py` owns the asyncpg pool and framework tables; `utils/i18n/` owns translations.
- Enabled plugins are `plugins/<name>.py`; disabled plugins use `plugins/<name>.py.disabled`. `plugins/version.json` is runtime-managed and gitignored.

## Commands
- Install app deps: `pdm install` or `uv sync`.
- Install dev tools too: `pdm install -G dev` or `uv sync --extra dev` (`pytest` and `ruff` are only in the `dev` extra).
- Run locally: `pdm run python main.py` or `uv run python main.py`.
- Docker run/log/stop: `docker-compose up -d`, `docker-compose logs -f app`, `docker-compose down`.
- Lint/format explicitly: `pdm run ruff check .` and `pdm run ruff format .` (or the same under `uv run`). Pre-commit runs `ruff --fix` then `ruff-format`.
- Focused tests: `pdm run pytest tests/test_memory_plugin.py` or `pdm run pytest tests/test_memory_plugin.py::test_name`.

## Configuration and secrets
- Initial local config is `cp .env.exp .env` and `cp conf_dir/config.yaml.exp conf_dir/config.yaml`.
- README mentions `conf_dir/settings.toml.example`, but this repo only has `conf_dir/settings.toml`; do not assume the example file exists.
- Do not print or copy values from local `.env` or `conf_dir/config.yaml`; the checked-in example files are safe references.
- PostgreSQL is required. Docker Compose uses `postgres:15-alpine`, mounts `database_setup.sql`, and expects app DB settings under `database:` in `conf_dir/config.yaml`.
- `setting/telegrambot.py` may call Telegram `get_me()` at import time if `.env` has a token but no `TELEGRAM_BOT_ID`; tests/offline scripts should monkeypatch or set bot id/username to avoid unexpected network calls.

## Plugin conventions
- New-style plugins implement `async register_handlers(bot, middleware, plugin_name)`; the loader still accepts legacy `register_handlers(bot)`.
- Common metadata: `__plugin_name__`, `__version__`, `__commands__`, `__command_category__`, `__command_descriptions__`, `__command_help__`.
- Optional hooks/flags: `__toggleable__` registers a per-group setting column; `__display_name__` names toggleable plugins; `setup_database(conn_pool)` runs before handler registration; `__scheduled_jobs__` registers cron jobs.
- Middleware handler priority is higher-first; command/message/callback/inline handlers can set `stop_propagation` and `guest_supported`.
- Scheduler cron support is intentionally limited to five fields where day/month/weekday must be `*`; only minute/hour are parsed.

## i18n
- Plugin handlers should import and use `utils.i18n._t()` / `_ft()`; middleware sets language/plugin contextvars before handler execution.
- Framework code not dispatched through middleware, such as controller/event code, should call explicit `t(key, lang)`.
- Locale files live at `utils/i18n/{lang}/framework.json` and `utils/i18n/{lang}/plugins/<plugin_name>.json`; supported languages are `en`, `zh-CN`, `zh-TW`, `ja`.
- Helpers: `python tools/add_i18n_language.py --code ja --label "日本語"` and `python tools/scaffold_plugin_locales.py`.

## Known verification gotchas
- Current `tests/test_memory_plugin.py` imports `plugins/memory.py`, but that file is absent in this checkout; plain `pytest` is expected to fail until the plugin is restored or the test is skipped/updated.
- `pyproject.toml` requires Python `>=3.12` but Ruff `target-version` is `py38`; do not “fix” that mismatch unless asked.
- Dockerfile installs `whois` and nexttrace, but local runs may still need OS commands used by network plugins (`ping`, `whois`, trace tools, etc.).
