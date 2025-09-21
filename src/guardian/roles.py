from __future__ import annotations
from typing import Optional

LEGENDS = "Legends"
PRO = "pro"
GUILDSTER = "Guildster"
NOOB = "Noob"

ROLE_ORDER = [LEGENDS, PRO, GUILDSTER, NOOB]


def role_for_hearts(hearts: int) -> str:
    if hearts >= 500:
        return LEGENDS
    if hearts >= 250:
        return PRO
    if hearts >= 100:
        return GUILDSTER
    return NOOB


def ordered_roles() -> list[str]:
    return ROLE_ORDER.copy()
