# 🎮 QilinMail Xbox Checker v3

**MADE BY @NUTFRR**

> Xbox / Microsoft account checker with full Telegram bot interface.

---

## 📁 Files

| File | Description |
|---|---|
| `checker_fixed.py` | QilinMail 6K-line checker (bug-fixed) |
| `tg_bot.py` | Telegram bot wrapper |
| `requirements.txt` | Python dependencies |

---

## ⚙️ Setup

```bash
pip install -r requirements.txt

# Set your bot token + admin ID
export BOT_TOKEN="your_telegram_bot_token"
export ADMIN_IDS="your_telegram_user_id"

python tg_bot.py
```

---

## 🤖 Bot Commands

| Command | Description |
|---|---|
| `/start` | Main menu with inline buttons |
| `/check email:pass` | Single account check |
| `/redeem KEY` | Redeem access key |
| `/stats` | View your stats |
| `/panel` | Admin panel |
| `/genkey [days\|lifetime]` | Generate key (admin) |
| `/auth user_id [days]` | Authorize user (admin) |
| `/revoke user_id` | Revoke user (admin) |
| `/broadcast message` | Message all users (admin) |

---

## 🔑 Key Format

```
NUTFRR-XXXXXXXXXXXX
```

---

## ✨ Features

- 🎮 **Single Check** — inline button flow, instant result
- 📂 **Bulk Check** — upload `.txt`, live progress bar `[████░░░░░░] 40%`
- 🛑 **Stop Button** — cancel bulk mid-run
- 🎯 **Hit Detection** — Xbox Live auth chain
- 📡 **Hits Channel** — auto-forward hits to Telegram channel
- 📁 **Result Files** — `hits.txt` + `bad.txt` sent after bulk
- 🔑 **Key System** — `1d / 7d / 30d / lifetime` keys
- 🛡️ **Admin Panel** — gen keys, auth/revoke users, broadcast, set channel
- 📊 **Stats** — per-user and global stats

---

## 🐛 Bugs Fixed in checker_fixed.py

1. **Line 198** — `p.get()` / `p['data']` → fixed to `pjson.get()` / `pjson['data']` (NameError: `p` was undefined)
2. **Line 5889** — `retries += 1` without `stats_lock` → thread-safe fix applied

---

**MADE BY @NUTFRR**
