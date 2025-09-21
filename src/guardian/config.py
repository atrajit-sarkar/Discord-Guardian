from dataclasses import dataclass
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


def get_config() -> Config:
    discord_token = os.getenv("DISCORD_TOKEN", "").strip()
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not discord_token:
        raise RuntimeError("DISCORD_TOKEN is not set in environment/.env")
    if not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in environment/.env")
    return Config(discord_token=discord_token, gemini_api_key=gemini_api_key)
