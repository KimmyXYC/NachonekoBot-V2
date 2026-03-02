# -*- coding: utf-8 -*-

import argparse
import ast
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
I18N_DIR = ROOT / "utils" / "i18n"
CONFIG_FILE = I18N_DIR / "config.py"
TEMPLATE_FILE = I18N_DIR / "template" / "framework.template.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scaffold a new i18n language")
    parser.add_argument("--code", required=True, help="Language code, e.g. ja")
    parser.add_argument("--label", required=True, help="Language display name")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite framework.json if it already exists",
    )
    return parser.parse_args()


def update_supported_languages(code: str, label: str) -> None:
    content = CONFIG_FILE.read_text(encoding="utf-8")
    pattern = r"SUPPORTED_LANGUAGES\s*=\s*\{(?P<body>[\s\S]*?)\}\s*"
    match = re.search(pattern, content)
    if not match:
        raise RuntimeError("Cannot find SUPPORTED_LANGUAGES in utils/i18n/config.py")

    body = "{" + match.group("body") + "}"
    mapping = ast.literal_eval(body)
    if not isinstance(mapping, dict):
        raise RuntimeError("SUPPORTED_LANGUAGES is not a dict")

    mapping[code] = label

    lines = ["SUPPORTED_LANGUAGES = {"]
    ordered_keys = ["en"] + sorted(k for k in mapping if k != "en")
    for key in ordered_keys:
        value = mapping[key]
        lines.append(f'    "{key}": "{value}",')
    lines.append("}")
    new_block = "\n".join(lines)

    updated = re.sub(pattern, new_block + "\n", content)
    CONFIG_FILE.write_text(updated, encoding="utf-8")


def ensure_framework_template(code: str, force: bool) -> Path:
    lang_dir = I18N_DIR / code
    plugins_dir = lang_dir / "plugins"
    framework_file = lang_dir / "framework.json"

    plugins_dir.mkdir(parents=True, exist_ok=True)
    (plugins_dir / ".gitkeep").touch(exist_ok=True)

    if framework_file.exists() and not force:
        return framework_file

    if TEMPLATE_FILE.exists():
        template = json.loads(TEMPLATE_FILE.read_text(encoding="utf-8"))
    else:
        template = {}

    framework_file.write_text(
        json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return framework_file


def main() -> None:
    args = parse_args()
    code = args.code.strip()
    label = args.label.strip()

    if not code or not label:
        raise RuntimeError("--code and --label must be non-empty")

    update_supported_languages(code, label)
    framework_file = ensure_framework_template(code, args.force)

    print(f"Added/updated language '{code}' in {CONFIG_FILE}")
    print(f"Scaffolded framework file: {framework_file}")
    print(f"Scaffolded plugin folder: {framework_file.parent / 'plugins'}")
    print("Next: edit framework.json translations and commit changes.")


if __name__ == "__main__":
    main()
