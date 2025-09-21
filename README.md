# Discord Guardian (父)

A Discord moderation and encouragement bot that analyzes messages with Google Gemini to detect harmful content and reward positive behavior. It tracks user hearts, promotes/demotes roles, and stores only flagged message details in Firestore for privacy.

## Features
- Starts each user at `50❤️` when they first chat
- Deducts `10❤️` per flagged harmful/abusive/profane message
- Daily bonus: `+5❤️` per day the user chats
- Rewards `+5❤️` for good advice and `+10❤️` for solving problems (detected via Gemini)
- Auto-kicks at `0❤️`
- Auto-assigns roles based on hearts: `Legends (>=500)`, `Pro (>=250)`, `Guildster (>=100)`, `Noob (<100)`
- Stores only flagged messages (content + reasons) in Firestore under `discord-guardian`; other events update counters without storing message content

## Prerequisites
- Python 3.10+
- A Discord Bot in the Developer Portal
- A Google Cloud project with Firestore enabled and a service account key JSON
- A Gemini API key

## Setup
1. Clone the repo and create a virtual environment:
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Create `.env` from the example and fill values:
```env
DISCORD_TOKEN=your_discord_bot_token
GEMINI_API_KEY=your_gemini_api_key
GOOGLE_APPLICATION_CREDENTIALS=C:\\path\\to\\service-account.json
FIRESTORE_COLLECTION=discord-guardian
# Optional tunings
HEART_START=50
HEART_PENALTY_FLAG=10
HEART_DAILY_BONUS=5
HEART_ADVICE=5
HEART_PROBLEM_SOLVED=10
LOG_LEVEL=INFO
# Restrict bot to a single server (guild) ID
ALLOWED_GUILD_ID=123456789012345678
```

3. Discord Developer Portal configuration
- In https://discord.com/developers/applications -> Your App:
  - Bot tab: Add a Bot if not created
  - Privileged Gateway Intents: enable `MESSAGE CONTENT INTENT` and `SERVER MEMBERS INTENT`
  - Reset and copy the Bot Token -> set `DISCORD_TOKEN` in `.env`
  - OAuth2 -> URL Generator: scopes `bot` and `applications.commands`; Bot Permissions:
    - Read Messages/View Channels
    - Send Messages, Send Messages in Threads
    - Manage Roles
    - Kick Members
    - Read Message History
  - Invite the bot using the generated URL
- In your server:
  - Create or ensure roles: `Legends`, `Pro`, `Guildster`, `Noob` (bot will try to create them if missing)
  - Move the bot's highest role ABOVE these roles so it can assign them

4. Firestore
- Enable Firestore in Native mode in your Google Cloud project
- Create a service account with `Cloud Datastore User` role
- Download the JSON key and set `GOOGLE_APPLICATION_CREDENTIALS` to its absolute path
- The collection defaults to `discord-guardian`

## Run
- Easiest:
```powershell
. .venv\Scripts\Activate.ps1
python run.py
```
- Or as a module:
```powershell
. .venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src"
python -m guardian.main
```

## How it works
- On each message, the bot asks Gemini to classify it as harmful/abusive/profane and/or positive (good advice, problem solved)
- If harmful, the bot replies with a warning, deducts hearts, stores the flagged message content and reasons in Firestore
- For positive signals, hearts are increased without storing message content
- Daily first message triggers a daily bonus once per user per day
- The bot then adjusts the user's level role

## Privacy
- Only flagged message content is stored
- Non-flagged messages are never persisted; only counters are updated
- When a member is kicked (0 hearts), their user document and stored flags are deleted from Firestore for privacy.

## Troubleshooting
- Ensure `MESSAGE CONTENT INTENT` is enabled in the Developer Portal
- Ensure the bot role is above `Legends/Pro/Guildster/Noob`
- Check that `GOOGLE_APPLICATION_CREDENTIALS` path is correct and readable
- If Firestore permission errors occur, verify service account roles
- Set `LOG_LEVEL=DEBUG` to see more logs

## Commands
- `/hearts [member]` – Show current hearts (defaults to yourself if member not provided)
- `/leaderboard` – Show top hearts in the current server
- `/award <member> <amount>` – Admin only: add hearts
- `/penalize <member> <amount>` – Admin only: deduct hearts

Troubleshooting slash commands
- Make sure the invite URL includes the `applications.commands` scope.
- Wait up to 1–5 minutes after the first run; commands can take time to propagate.
- We sync per-guild on startup, but you can kick/re-invite the bot to force refresh.
- Ensure the bot can view the channel and `Use Application Commands` permission is not blocked by channel overrides.
- If `ALLOWED_GUILD_ID` is set, commands will only work in that server.

## Notes
- Gemini prompts are best-effort; adjust phrasing in `gemini_client.py` if needed
- Rate limits may apply on Discord and Gemini; consider adding caching or backoff for large servers
