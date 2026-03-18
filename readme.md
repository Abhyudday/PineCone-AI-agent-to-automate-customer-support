# Polycop Telegram Bot

A simple Telegram bot that forwards messages to the Pinecone "polycop" assistant and returns responses.

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   Then edit `.env` and fill in:
   - `TELEGRAM_BOT_TOKEN` — Get this from [@BotFather](https://t.me/BotFather) on Telegram
   - `PINECONE_API_KEY` — Your Pinecone API key

3. **Run the bot:**
   ```bash
   python bot.py
   ```

## Usage

- Send `/start` to get a welcome message.
- Send any text message and the bot will forward it to the Polycop assistant and reply with the response.
