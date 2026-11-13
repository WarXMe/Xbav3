# 🎮 Xbox Checker Pro

**MADE BY @NUTFRR**

Premium Xbox / Microsoft account checker Telegram bot.

## Features

- ✅ **Single account check** — validates email:pass via Xbox API
- 📂 **Bulk check** — upload `.txt` file (up to 10,000 accounts)  
- 🎮 **Rich data** — gamertag, gamerscore, tier, tenure, friends, subscriptions
- 🎯 **Game Pass / Xbox Gold** detection
- 📊 **Live progress bar** during bulk checks
- 🛑 **Stop button** — cancel bulk check mid-run
- 📡 **Hits channel** — auto-forward hits to a Telegram channel
- 📁 **Result files** — hits.txt + bad.txt sent after bulk check
- 🔑 **Key-based access** — `NUTFRR-XXXXXXXXXXXX` format keys
- 🛡️ **Admin panel** — auth users, gen keys, stats, broadcast

## Setup

```bash
pip install -r requirements.txt
export BOT_TOKEN="your_telegram_bot_token"
export ADMIN_ID="your_telegram_user_id"
python bot.py
```

## Commands

| Command | Description |
|---|---|
| `/start` | Main menu |
| `/check email:pass` | Single account check |
| `/redeem KEY` | Redeem access key |
| `/stats` | View your stats |
| `/panel` | Admin panel |
| `/genkey [days\|lifetime]` | Generate key (admin) |
| `/auth user_id [days]` | Authorize user (admin) |
| `/revoke user_id` | Revoke user (admin) |
| `/broadcast msg` | Message all users (admin) |

## Bot Flow

```
/start → main menu
  ├── 🎮 Check Single → send email:pass → result
  ├── 📂 Check File  → upload .txt → live progress → hits.txt + bad.txt
  ├── 📊 My Stats
  ├── 📋 Last Hits
  ├── 🔑 Redeem Key  → /redeem CODE
  └── 🛡️ Admin Panel → manage users, keys, stats
```

## Credits

**MADE BY @NUTFRR**
