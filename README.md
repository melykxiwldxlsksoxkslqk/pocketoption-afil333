# pocketafill-numb22

Telegram bot project.

## Configuration

Set environment variables in a `.env` file (loaded via `python-dotenv`):

- BOT_TOKEN=...
- TELEGRAM_API_ID=...
- TELEGRAM_API_HASH=...
- SECRET_UID=...  # optional privileged UID to bypass registration/deposit checks for testing

Never commit real secrets to the repo. Use `.env`, OS env vars, or your secret manager.
