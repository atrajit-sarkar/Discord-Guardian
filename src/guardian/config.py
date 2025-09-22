from dataclasses import dataclass
from typing import List, Optional
import json
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    discord_token: str
    gemini_api_key: str
    firestore_collection: str = os.getenv("FIRESTORE_COLLECTION", "discord-guardian")
    heart_start: int = int(os.getenv("HEART_START", "50"))
    heart_penalty_flag: int = int(os.getenv("HEART_PENALTY_FLAG", "10"))
    heart_daily_bonus: int = int(os.getenv("HEART_DAILY_BONUS", "5"))
    heart_advice: int = int(os.getenv("HEART_ADVICE", "5"))
    heart_problem_solved: int = int(os.getenv("HEART_PROBLEM_SOLVED", "10"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    allowed_guild_id: str | None = os.getenv("ALLOWED_GUILD_ID")
    admin_role_ids: List[str] = None  # populated below
    # Special users: list of dicts with keys id (str), optional hearts (int), optional roles (list[str])
    special_users: List[dict] = None  # populated below


def get_config() -> Config:
    discord_token = os.getenv("DISCORD_TOKEN", "").strip()
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not discord_token:
        raise RuntimeError("DISCORD_TOKEN is not set in environment/.env")
    if not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in environment/.env")
    cfg = Config(discord_token=discord_token, gemini_api_key=gemini_api_key)
    # Parse admin role IDs (comma or space separated)
    raw = os.getenv("ADMIN_ROLE_IDS", "").strip()
    ids: List[str] = []
    if raw:
        for part in raw.replace("\n", ",").replace(" ", ",").split(","):
            p = part.strip()
            if p:
                ids.append(p)
    cfg.admin_role_ids = ids
    # Load special users from JSON file (default: specialuser.json)
    special_users: List[dict] = []
    file_path = os.getenv("SPECIAL_USERS_FILE", "specialuser.json").strip()
    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    uid = str(item.get("id") or item.get("user_id") or "").strip()
                    rid = str(item.get("roleId") or item.get("role_id") or "").strip()
                    entry: dict = {}
                    if uid:
                        entry["id"] = uid
                    elif rid:
                        entry["roleId"] = rid
                    else:
                        continue
                    if "hearts" in item and isinstance(item.get("hearts"), (int, float)):
                        entry["hearts"] = int(item["hearts"])  # minimum hearts to ensure
                    roles = item.get("roles")
                    if isinstance(roles, list):
                        entry["roles"] = [str(r) for r in roles if r is not None]
                    special_users.append(entry)
        except FileNotFoundError:
            # no special users file, leave empty
            pass
        except Exception:
            # invalid file, leave empty
            pass
    cfg.special_users = special_users
    return cfg
