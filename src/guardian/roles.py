from __future__ import annotations
import json
import os
from typing import List, Dict

_ROLES_SPEC_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "roles.json")
_ROLES_CACHE: List[Dict] | None = None


def _load_roles() -> List[Dict]:
    global _ROLES_CACHE
    if _ROLES_CACHE is not None:
        return _ROLES_CACHE
    try:
        with open(_ROLES_SPEC_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            roles = data.get("roles", [])
            # Sort by minHearts descending so we can pick the first match
            roles_sorted = sorted(roles, key=lambda r: int(r.get("minHearts", 0)), reverse=True)
            _ROLES_CACHE = roles_sorted
            return roles_sorted
    except Exception:
        # Fallback to defaults
        defaults = [
            {"name": "Legends", "minHearts": 500, "color": "#E5C233"},
            {"name": "pro", "minHearts": 250, "color": "#1ABC9C"},
            {"name": "Guildster", "minHearts": 100, "color": "#9B59B6"},
            {"name": "Noob", "minHearts": 0, "color": "#95A5A6"},
        ]
        _ROLES_CACHE = defaults
        return defaults


def role_for_hearts(hearts: int) -> str:
    for spec in _load_roles():
        if hearts >= int(spec.get("minHearts", 0)):
            return spec.get("name")
    return _load_roles()[-1].get("name")


def ordered_roles() -> list[str]:
    return [spec.get("name") for spec in _load_roles()]


def role_color(name: str):
    for spec in _load_roles():
        if spec.get("name") == name:
            color_hex = spec.get("color")
            if isinstance(color_hex, str) and color_hex.startswith("#") and len(color_hex) == 7:
                try:
                    return int(color_hex[1:], 16)
                except Exception:
                    return None
    return None
