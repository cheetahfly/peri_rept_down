# -*- coding: utf-8 -*-
"""
Rule applier - applies improvement suggestions to extraction config.py.
"""

import os
import re
import shutil
from typing import Dict, List


def apply_suggestions(
    config_path: str,
    suggestions: List[Dict],
    dry_run: bool = True,
) -> List[str]:
    changes = []

    if not dry_run:
        backup_path = config_path + ".bak"
        shutil.copy2(config_path, backup_path)
        changes.append(f"Backup created: {backup_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    for s in suggestions:
        if s["action"] == "add_alias" and s["category"] == "alias":
            change = _add_alias(content, s["key"], s["value"])
            if change:
                content = change
                changes.append(f"Added alias: {s['key']} -> {s['value']}")

        elif s["action"] == "add_standard_item" and s["category"] == "standard_items":
            change = _add_standard_item(content, s["key"])
            if change:
                content = change
                changes.append(f"Added standard item: {s['key']}")

    if not dry_run and changes:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(content)

    return changes


def _add_alias(content: str, standard_name: str, new_aliases: List[str]) -> str:
    # Find the standard name in ITEM_ALIAS_MAP and add new aliases
    pattern = re.compile(
        r'(\s*"' + re.escape(standard_name) + r'"\s*:\s*\[)([^\]]*?)(\])',
        re.DOTALL,
    )
    match = pattern.search(content)
    if not match:
        # Try to find it as a new entry
        insert_pattern = re.compile(r'(ITEM_ALIAS_MAP\s*=\s*\{)')
        insert_match = insert_pattern.search(content)
        if insert_match:
            pos = insert_match.end()
            new_entry = f'\n    "{standard_name}": {new_aliases},'
            content = content[:pos] + new_entry + content[pos:]
            return content
        return None

    existing = match.group(2)
    for alias in new_aliases:
        alias_escaped = alias.replace('"', '\\"')
        if alias_escaped not in existing:
            existing = existing.rstrip() + f',\n        "{alias_escaped}"'

    content = content[:match.start(2)] + existing + content[match.end(2):]
    return content


def _add_standard_item(content: str, item_name: str) -> str:
    # Find the last item in the appropriate list and add after it
    # This is a simple approach - find the most relevant statement type list
    for st_type in ["income_statement", "balance_sheet", "cash_flow"]:
        pattern = re.compile(
            r'(STATEMENT_TYPE_STANDARD_ITEMS\s*=\s*\{[^}]*?"' + st_type + r'"\s*:\s*\[)([^\]]*?)(\])',
            re.DOTALL,
        )
        match = pattern.search(content)
        if match:
            existing = match.group(2)
            if item_name not in existing:
                existing = existing.rstrip() + f',\n        "{item_name}"'
                content = content[:match.start(2)] + existing + content[match.end(2):]
                return content
    return None


def preview_changes(config_path: str, suggestions: List[Dict]) -> List[str]:
    return apply_suggestions(config_path, suggestions, dry_run=True)
