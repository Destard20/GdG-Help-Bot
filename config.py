"""
Configuration loader for GdG-Help-Bot.
Loads environment variables from .env file.
"""

import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

# Bot Username (e.g., @GdG_Help_Bot)
BOT_USERNAME = os.getenv("BOT_USERNAME", "@GdG_Help_Bot").strip()
if BOT_USERNAME and not BOT_USERNAME.startswith("@"):
    BOT_USERNAME = f"@{BOT_USERNAME}"

# Ticket Admin Chat ID (supergroup or channel)
_ticket_chat_id_raw = os.getenv("TICKET_CHAT_ID", "0").strip()
try:
    TICKET_CHAT_ID = int(_ticket_chat_id_raw)
except ValueError:
    TICKET_CHAT_ID = 0

# GitHub Repository Configuration
GITHUB_REPO = os.getenv("GITHUB_REPO", "Destard20/GdG-Help-Bot").strip()
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()

# Custom Raw Base URL or default GitHub raw content URL
_default_raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}" if GITHUB_REPO else ""
GITHUB_RAW_BASE_URL = os.getenv("GITHUB_RAW_BASE_URL", _default_raw_url).rstrip("/")

# Database file path
DATABASE_PATH = os.getenv("DATABASE_PATH", "tickets.db").strip()

# Fallback & caching settings
USE_LOCAL_FILES = os.getenv("USE_LOCAL_FILES", "false").lower() in ("true", "1", "yes")
USE_LOCAL_FALLBACK = os.getenv("USE_LOCAL_FALLBACK", "true").lower() in ("true", "1", "yes")
FAQ_CACHE_TTL = int(os.getenv("FAQ_CACHE_TTL", "300"))


def get_raw_url(relative_path: str) -> str:
    """Returns the full raw GitHub URL for a given relative repository path."""
    clean_path = relative_path.lstrip("/")
    if GITHUB_RAW_BASE_URL:
        return f"{GITHUB_RAW_BASE_URL}/{clean_path}"
    return ""


def validate_config() -> list[str]:
    """Validates configuration and returns a list of warnings or errors."""
    warnings = []
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        warnings.append("TELEGRAM_BOT_TOKEN is not configured! The bot will not be able to connect to Telegram.")
    if TICKET_CHAT_ID == 0:
        warnings.append("TICKET_CHAT_ID is not configured! Admin ticket notifications will fail.")
    if not GITHUB_REPO and not USE_LOCAL_FALLBACK and not USE_LOCAL_FILES:
        warnings.append("Neither GITHUB_REPO nor USE_LOCAL_FILES/USE_LOCAL_FALLBACK is set! Bot will not be able to load FAQs.")
    return warnings
