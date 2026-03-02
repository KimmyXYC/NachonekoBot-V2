# -*- coding: utf-8 -*-

import ast
import json
from pathlib import Path
from typing import Dict, Set


ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = ROOT / "plugins"
I18N_DIR = ROOT / "utils" / "i18n"
LANGS = ("en", "zh-CN")


TARGET_CALLS = {
    "reply_to": {"pos": 1, "kw": ("text",)},
    "send_message": {"pos": 1, "kw": ("text",)},
    "edit_message_text": {"pos": 0, "kw": ("text",)},
    "answer_callback_query": {"pos": 1, "kw": ("text",)},
    "send_photo": {"pos": None, "kw": ("caption",)},
    "send_document": {"pos": None, "kw": ("caption",)},
    "send_video": {"pos": None, "kw": ("caption",)},
    "send_animation": {"pos": None, "kw": ("caption",)},
}


def _const_str(node) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def _collect_assign_map(tree, name: str) -> Dict[str, str]:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        target_names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if name not in target_names:
            continue
        if isinstance(node.value, ast.Dict):
            result = {}
            for k, v in zip(node.value.keys, node.value.values):
                ks = _const_str(k)
                vs = _const_str(v)
                if ks:
                    result[ks] = vs
            return result
    return {}


def _collect_assign_str(tree, name: str) -> str:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        target_names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if name in target_names:
            return _const_str(node.value)
    return ""


class StringCollector(ast.NodeVisitor):
    def __init__(self):
        self.values: Set[str] = set()

    def visit_Call(self, node: ast.Call):
        attr = None
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
        if not attr or attr not in TARGET_CALLS:
            self.generic_visit(node)
            return

        spec = TARGET_CALLS[attr]
        pos = spec["pos"]
        if pos is not None and len(node.args) > pos:
            s = _const_str(node.args[pos])
            if s:
                self.values.add(s)

        kw_names = set(spec["kw"])
        for kw in node.keywords:
            if kw.arg in kw_names:
                s = _const_str(kw.value)
                if s:
                    self.values.add(s)

        self.generic_visit(node)


def build_locale_for_plugin(plugin_file: Path):
    source = plugin_file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(plugin_file))

    data: Dict[str, str] = {}

    description = _collect_assign_str(tree, "__description__")
    if description:
        data["meta.description"] = description

    display_name = _collect_assign_str(tree, "__display_name__")
    if display_name:
        data["meta.display_name"] = display_name

    desc_map = _collect_assign_map(tree, "__command_descriptions__")
    for cmd, text in desc_map.items():
        data[f"command.description.{cmd}"] = text

    help_map = _collect_assign_map(tree, "__command_help__")
    for cmd, text in help_map.items():
        data[f"command.help.{cmd}"] = text

    collector = StringCollector()
    collector.visit(tree)
    for text in sorted(collector.values):
        data[text] = text

    return data


def merge_and_write(path: Path, generated: Dict[str, str]):
    existing: Dict[str, str] = {}
    if path.exists():
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                existing = {str(k): str(v) for k, v in parsed.items()}
        except Exception:
            existing = {}

    merged = dict(existing)
    for key, value in generated.items():
        if key not in merged:
            merged[key] = value

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main():
    plugin_files = sorted(
        [p for p in PLUGINS_DIR.glob("*.py") if p.name != "__init__.py"],
        key=lambda p: p.name.lower(),
    )

    for plugin_file in plugin_files:
        plugin_name = plugin_file.stem
        generated = build_locale_for_plugin(plugin_file)

        for lang in LANGS:
            out_file = I18N_DIR / lang / "plugins" / f"{plugin_name}.json"
            merge_and_write(out_file, generated)

    print(f"Scaffolded locale files for {len(plugin_files)} plugins.")


if __name__ == "__main__":
    main()
