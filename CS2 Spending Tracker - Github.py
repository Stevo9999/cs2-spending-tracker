#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Counter Strike Spending Tracker
Run:  python "CS2 Spending Tracker - Github.py"
Needs only Python 3.9+, no other installs required.

DISCLAIMER: This application was created with help from Claude AI.
Every line of code is plain text and can be read in any text editor.
It does not access the internet, does not collect data, and does not
write any file other than the single HTML report you choose to save.
To verify this yourself: open this file in Notepad or any other
text editor of your choice and read it. It asks you to select saved
.txt/.json files, parses the information, and writes a single HTML file.

License: MIT (see the LICENSE file). Provided "as is", without warranty.
"""

import html as _html
import json
import os
import re
import sys
import webbrowser
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


DISCLAIMER = """
============================================================
 Counter Strike Spending Tracker
 Created with Claude AI

 HOW TO VERIFY THIS IS SAFE:
   1. Open this file (CS2 Spending Tracker - Github.py) in Notepad or your preferred text editor.
   2. Press Ctrl+F and search for: socket, requests, urllib, subprocess,
      exec, eval  -- the only place you will find them is this notice.
   3. Imports used:
        html, json, os, re, sys, webbrowser  (standard Python tools)
        collections, dataclasses, datetime, pathlib  (data structures)
        threading, time, shutil, csv  (spinner animation, terminal size, CSV files)
        select, tty, termios, msvcrt  (read single keypresses; standard Python)
        tkinter  (only for the file-picker popup; standard Python)
   4. The only file this script writes is the HTML report YOU choose
      to save. It reads only the files YOU point it to.

 STEAM:
   This tool only reads pages YOU save from your own Steam account. It does
   not use the Steam Web API, an API key, or your login. Your use of Steam
   is governed by the Steam Subscriber Agreement:
     https://store.steampowered.com/subscriber_agreement/
   Not affiliated with or endorsed by Valve Corporation. Steam® is a
   trademark of Valve Corporation. The report is for personal use and is
   provided "as is", with no guarantee of accuracy.
============================================================
"""

MARKET_URL        = "https://steamcommunity.com/market/myhistory/render/?query=&l=english&count=500&start={start}"
STEAM_HISTORY_URL = "https://store.steampowered.com/account/history/"
DEFAULT_KEY_PRICE = 2.49


@dataclass
class Tx:
    date:          date
    item:          str
    amount:        float
    type:          str
    source:        str
    estimated:     bool = False
    year_inferred: bool = False


CUR                = ["$"]
STEAM_MARKET_DATES = []
MARKET_FILES       = []
KEY_PRICE          = [DEFAULT_KEY_PRICE]


import threading as _threading
import time as _time
import shutil as _shutil

# ── Always-on spinner ──────────────────────────────────────────────────────────
# The spinner runs continuously from program start.
# It pauses (hidden) while the user is typing or while the block-bar is active,
# then resumes the instant control returns to idle.
# say() clears the spinner line before printing so output is never garbled.

_SP_FRAMES = ["|", "/", "─", "\\"]
_SP        = {"label": "", "running": False, "paused": False, "thread": None}
_sp_lock   = _threading.Lock()


def _sp_loop():
    i = 0
    while True:
        with _sp_lock:
            if not _SP["running"]:
                break
            if not _SP["paused"]:
                cols = _shutil.get_terminal_size((72, 24)).columns - 2
                print(f"\r{'  ' + _SP_FRAMES[i % 4] + '  ' + _SP['label']:<{cols}}", end="", flush=True)
                i += 1
        _time.sleep(0.10)
    _sp_clear_line()


def spinner_start(label="waiting..."):
    _sp_set(label=label, paused=False)
    _SP["running"] = True
    _SP["thread"] = _threading.Thread(target=_sp_loop, daemon=True)
    _SP["thread"].start()


def spinner_stop():
    with _sp_lock:
        _SP["running"] = False
    if _SP["thread"]:
        _SP["thread"].join(timeout=0.5)


def _sp_set(label=None, paused=None):
    with _sp_lock:
        if label is not None:
            _SP["label"] = label
        if paused is not None:
            _SP["paused"] = paused


def _sp_clear_line():
    cols = _shutil.get_terminal_size((72, 24)).columns - 2
    print(f"\r{' ' * cols}\r", end="", flush=True)


def say(msg=""):
    _sp_clear_line()
    print(msg)
    # resume spinner after printing
    _sp_set(paused=False)


class _Keys:
    """Read the keyboard one key at a time (Windows: msvcrt; Mac/Linux: termios + select)."""

    def __enter__(self):
        if os.name != "nt":
            import termios, tty
            self.fd = sys.stdin.fileno()
            self.old = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        return self

    def __exit__(self, *exc):
        if os.name != "nt":
            import termios
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)

    def get(self, wait):
        """One key; '' for keys that type nothing (arrows, F-keys); None if no key arrived in time."""
        if os.name == "nt":
            import msvcrt
            end = _time.time() + wait
            while _time.time() < end:
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ("\x00", "\xe0"):            # special key: swallow its second code
                        msvcrt.getwch()
                        return ""
                    return ch
                _time.sleep(0.01)
            return None
        import select
        if not select.select([self.fd], [], [], wait)[0]:
            return None
        first = os.read(self.fd, 1)
        if not first:
            raise EOFError
        size = 1 if first[0] < 0xC0 else 2 if first[0] < 0xE0 else 3 if first[0] < 0xF0 else 4
        ch = (first + b"".join(os.read(self.fd, 1) for _ in range(size - 1))).decode("utf-8", errors="replace")
        if ch == "\x1b":                                  # arrow keys etc. arrive as escape sequences
            while select.select([self.fd], [], [], 0.08)[0]:
                c = os.read(self.fd, 1)
                if not c or (0x40 <= c[0] <= 0x7E and c not in (b"[", b"O")):
                    break
            return ""
        return ch


def _spin_line(text, frame):
    lead = len(text) - len(text.lstrip())
    return " " * max(lead - 2, 0) + frame + " " + text.lstrip()


def _is_terminal():
    return bool(sys.stdin and sys.stdin.isatty() and sys.stdout.isatty())


def _read_line(prompt):
    """input() with a spinner that turns only while nothing is typed; the first key stops it."""
    _sp_set(paused=True)
    head, _, prompt = prompt.rpartition("\n")
    if head:
        print(head)                                       # earlier lines of the prompt, printed once
    if not _is_terminal():
        return input(prompt)
    blank = "\r" + " " * len(_spin_line(prompt, "|")) + "\r"
    typed, tick = [], 0
    with _Keys() as keys:
        while True:
            if not typed:
                print("\r" + _spin_line(prompt, _SP_FRAMES[tick % 4]), end="", flush=True)
                tick += 1
            ch = keys.get(0.12)
            if ch is None:
                continue
            if ch in ("\r", "\n"):
                print()
                return "".join(typed)
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch in ("\x04", "\x1a") and not typed:
                raise EOFError
            if ch in ("\x08", "\x7f"):
                if typed:
                    typed.pop()
                    print("\b \b", end="", flush=True)
                continue
            if not ch or ord(ch[0]) < 32:
                continue
            if not typed:
                print(blank + prompt, end="")             # spinner off, same row, nothing left behind
            typed.append(ch)
            print(ch, end="", flush=True)


def press_any_key(message):
    _sp_set(paused=True)
    _sp_clear_line()
    if not _is_terminal():
        input(message)
    else:
        with _Keys() as keys:
            tick = 0
            while True:
                print("\r" + _spin_line(message, _SP_FRAMES[tick % 4]), end="", flush=True)
                tick += 1
                if keys.get(0.12) is not None:
                    break
        print()
    _sp_set(label="waiting...", paused=False)


def ask(prompt, default=""):
    suffix = f" [{default}]" if default else ""
    full   = f"  {prompt}{suffix}: "
    _sp_set(paused=True)
    _sp_clear_line()
    val = _read_line(full).strip()
    _sp_set(label="waiting...", paused=False)
    return val or default


def yes_no(prompt, default=False):
    hint = "Y/n" if default else "y/N"
    full = f"  {prompt} [{hint}]: "
    while True:
        _sp_set(paused=True)
        _sp_clear_line()
        ans = _read_line(full).strip().lower()
        _sp_set(label="waiting...", paused=False)
        if not ans:
            return default
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False


def parse_price(text):
    if "-" in text:
        return None
    t = re.sub(r"[^\d.,]", "", text)
    t = t.replace(",", ".") if "," in t and "." not in t else t.replace(",", "")
    try:
        v = float(t)
    except ValueError:
        return None
    return v if 0 < v < 1000 else None


def ask_open(prompt):
    ans = ask(f"{prompt} [Y/N]").lower()
    if ans in ("y", "yes"):
        return True
    if ans not in ("n", "no"):
        say("  No input selected" if not ans else "  Input not recognized")
    return False


def choose_key_price():
    say("")
    say(f"  Default key price: ${DEFAULT_KEY_PRICE:.2f} USD")
    say("  Only used by the optional 'Estimate missing keys' feature (main menu option 5).")
    say("  If your Steam wallet is not in USD, choose 2 and enter the key price in your own currency.")
    if menu(["Keep the default price", "Modify price"]) == 1:
        say(f"  Using the default key price: ${DEFAULT_KEY_PRICE:.2f} USD")
        return
    while True:
        raw = ask("  Enter your key price (numbers only, for example 2.49)")
        price = parse_price(raw)
        if price:
            KEY_PRICE[0] = price
            say(f"  Key price set to {price:.2f} (replaces the {DEFAULT_KEY_PRICE:.2f} default).")
            return
        say("  No input selected" if not raw else "  Please enter a number greater than 0, for example 2.49")


def banner(title):
    say(f"\n{'='*60}\n {title}\n{'='*60}")


def money(v):
    return f"-{CUR[0]}{abs(v):,.2f}" if v < 0 else f"{CUR[0]}{v:,.2f}"


def read_file(path):
    path = Path(path).expanduser()
    if path.stat().st_size > 100_000_000:                # no real history is this big; refuse instead of filling memory
        return ""
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8-sig", errors="replace")


def pick_file(prompt, filetypes=None):
    """Show a native file-picker dialog. Spinner spins while the dialog is open."""
    _sp_set(label="file picker open — select your file...")
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.lift()
        root.attributes("-topmost", True)
        kwargs = {"title": prompt}
        if filetypes:
            kwargs["filetypes"] = filetypes + [("All files", "*.*")]
        path = filedialog.askopenfilename(**kwargs)
        root.destroy()
        _sp_set(label="waiting...")
        if path:
            say(f"  Selected: {path}")
            return Path(path)
        say("  (No file selected.)")
        return None
    except Exception:
        _sp_set(label="waiting...")
        say("  (File picker unavailable — type the path manually or drag the file here.)")
        while True:
            _sp_clear_line()
            _sp_set(paused=True)
            raw = _read_line(f"  {prompt} (Enter to skip): ").strip().strip('"').strip("'")
            _sp_set(label="waiting...", paused=False)
            if not raw:
                return None
            p = Path(raw).expanduser()
            if p.exists():
                return p
            say(f"  File not found: {p}")


MONTHS = {m: i+1 for i, m in enumerate(
    ["january","february","march","april","may","june",
     "july","august","september","october","november","december"]
)}
for _m, _i in list(MONTHS.items()):
    MONTHS[_m[:3]] = _i
MONTHS["sept"] = 9

_DATE_MDY = re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?(?!\d)")
_DATE_DMY = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?(?:,?\s+(\d{4}))?(?!\d)")
_DATE_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")

def _valid(month, day, year):
    return bool(month) and 1 <= month <= 12 and 1 <= day <= 31 and (year is None or 1990 <= year <= 2100)


def parse_date(text):
    m = _DATE_ISO.search(text)
    if m:
        found = int(m[2]), int(m[3]), int(m[1])
        return found if _valid(*found) else None
    for pat in (_DATE_MDY, _DATE_DMY):
        for mo in pat.finditer(text):
            if pat == _DATE_MDY:
                month = MONTHS.get(mo[1].lower())
                day, year = int(mo[2]), int(mo[3]) if mo[3] else None
            else:
                month = MONTHS.get(mo[2].lower())
                day, year = int(mo[1]), int(mo[3]) if mo[3] else None
            if _valid(month, day, year):
                return month, day, year
    return None

def safe_date(y, m, d):
    y = min(max(y, 1990), 2100)
    try:
        return date(y, m, d)
    except ValueError:
        return date(y, m, 28)

def day_of_year(m, d):
    return safe_date(2001, m, d).timetuple().tm_yday

def resolve_dates(tokens, today=None):
    today = today or date.today()
    years = [t[2] for t in tokens if t[2]]
    seq   = list(reversed(tokens)) if (len(years) >= 2 and years[0] < years[-1]) else list(tokens)
    out, cur_year, prev, started = [], today.year, None, False
    for mo, d, yr in seq:
        if yr is not None:
            cur_year, inferred = yr, False
        else:
            if not started and (mo, d) > (today.month, today.day):
                cur_year = today.year - 1
            elif prev is not None and day_of_year(mo, d) - day_of_year(*prev) > 90:
                cur_year -= 1
            inferred = True
        started, prev = True, (mo, d)
        out.append((safe_date(cur_year, mo, d), inferred))
    if len(years) >= 2 and years[0] < years[-1]:
        out.reverse()
    return out

_AMOUNT = re.compile(
    r"(?P<s1>[-+\u2212])?(?:[A-Za-z$€£¥₩]{1,3}\$?)?\s*(?P<s2>[-+\u2212])?\s*"
    r"(?P<n>\d{1,3}(?:[., ]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)\s*(?:[A-Za-z$€£¥₩]{1,3})?"
)
_MONEY_HINT = re.compile(r"[$€£¥₩]|\d+[.,]\d{2}\b")

def parse_amount(text):
    text = text.strip()
    if not _MONEY_HINT.search(text):
        return None
    m = _AMOUNT.fullmatch(text)
    if not m:
        return None
    raw  = re.sub(r"[\s\u00a0]", "", m["n"])
    last = max(raw.rfind("."), raw.rfind(","))
    try:
        if last == -1:
            val = float(raw)
        elif len(raw) - last - 1 in (1, 2):
            val = float(re.sub(r"[.,]", "", raw[:last]) + "." + raw[last+1:])
        else:
            val = float(re.sub(r"[.,]", "", raw))
    except ValueError:
        return None
    sign = m["s1"] or m["s2"] or ""
    return val, sign

_CUR_TOKEN = re.compile(
    r"(R\$|CDN\$|A\$|NZ\$|HK\$|S\$|NT\$|Mex\$|CHF|Rp|RM|[$€£¥₩₹₽₺₴₫₱฿])\s?\d"
    r"|\d\s?(€|£|¥|zł|kr(?![A-Za-z])|руб\.?|pуб\.?|₽|₺|₴|TL(?![A-Za-z]))"
)

def set_currency(text):
    found = Counter(m.group(1) or m.group(2) for m in _CUR_TOKEN.finditer(text))
    if found:
        CUR[0] = found.most_common(1)[0][0]

NON_CS     = ("(dota 2)", "dota 2", "team fortress 2")
NAME_FIXES = {}

def is_cs(name):
    low = name.lower()
    return not any(h in low for h in NON_CS)

def clean(name):
    name = " ".join(str(name).split())
    for wrong, right in NAME_FIXES.items():
        name = name.replace(wrong, right)
    return name

def is_case(name):
    return bool(re.search(r"\bcase(?:\s+\d+)?$", name, re.I)) and "key" not in name.lower()

def is_key(name):
    return bool(re.search(r"\bkey$", name, re.I))


_GAME_CELL   = re.compile(r"counter-strike(: global offensive| 2)?$", re.I)
_STEAM_TYPES = {"in-game purchase", "purchase", "gift purchase", "refund",
                "wallet funds", "wallet credit", "conversion"}


def _market_count(cells):
    for c in cells:
        m = re.match(r"(\d+) market transactions?$", c, re.I)
        if m:
            return int(m.group(1))
    return 1


def load_steam_history(path, today=None):
    return load_steam_history_text(read_file(path), today)


def load_steam_history_text(text, today=None):
    entries, cur = [], None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        tok = parse_date(line)
        if tok:
            cur = (tok, [])
            entries.append(cur)
        elif cur:
            cur[1].extend(c.strip() for c in line.split("\t") if c.strip())
    if not entries:
        return [], ["No dated rows found. Make sure you copied the full page with dates visible."]
    set_currency(text)
    resolved = resolve_dates([e[0] for e in entries], today)
    out, market_days, skipped = [], [], 0
    for (tok, cells), (dt, inferred) in zip(entries, resolved):
        if "market transaction" in " ".join(cells).lower():
            market_days += [dt] * _market_count(cells)
            skipped += 1
            continue
        if not any(_GAME_CELL.match(c) for c in cells):
            skipped += 1
            continue
        amounts = [a for a in (parse_amount(c) for c in cells) if a]
        neg     = [v for v, sign in amounts if sign in ("-", "\u2212")]
        plain   = [v for v, sign in amounts if sign == ""]
        cost    = neg[0] if neg else (max(plain[:3]) if plain else None)
        names   = []
        for c in cells:
            if c.lower() in _STEAM_TYPES:
                break
            if not _GAME_CELL.match(c) and not parse_amount(c) and re.search(r"\w", c):
                names.append(c)
        if cost is None or not names:
            continue
        units = []
        for n in names:
            m = re.match(r"^(\d+)\s+(.+)$", n)
            units += [clean(m.group(2) if m else n)] * (int(m.group(1)) if m else 1)
        for item in units:
            out.append(Tx(dt, item, -cost / len(units), "Purchase", "Steam History", year_inferred=inferred))
    STEAM_MARKET_DATES[:] = sorted(market_days, reverse=True)
    return out, ([f"Skipped {skipped} non-CS or market-transaction rows."] if skipped else [])


_ORDER_HEADER = re.compile(r"Order\s*#\d+\s*\((.+?)\)")
_ORDER_ITEM   = re.compile(r"^[-*]\s+(.+?):\s*\$([0-9.,]+)(?:\s*\(x(\d+)\s+individual items?\))?")
_MP_MONEY     = re.compile(r"^\$[\d,.]+$",   re.MULTILINE)
_MP_DATE      = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}", re.MULTILINE)
_MP_WEAR      = re.compile(r"^(Field-Tested|Factory New|Minimal Wear|Well-Worn|Battle-Scarred)(\s|$)", re.I)
_MP_FLOAT     = re.compile(r"^\d\.\d{3,4}$")
_MP_TOUR      = re.compile(
    r".+\|\s*(Paris|Antwerp|Rio|Copenhagen|Stockholm|Katowice|Cologne|Atlanta|"
    r"Krakow|Boston|London|Marseille|Bucharest|Berlin|Cluj|DreamHack|ESL)\s+\d{4}"
)
_MP_QUAL      = re.compile(r"^\(?(Holo|Foil|Gold|Glitter|Lenticular|Paper)\)?$", re.I)

_MP_NOISE = {
    "marketplace","market","sell","transactions","orders","seller account",
    "history of transactions","invoices","collapse all",
    "container","base grade container","base grade",
    "master agent","distinguished agent","superior agent","exceptional agent",
    "remarkable sticker","high grade sticker","shattered web","sticker",
    "covert rifle","covert pistol","covert smg","covert shotgun","covert sniper rifle",
    "mil-spec rifle","mil-spec pistol","mil-spec smg",
    "industrial grade","consumer grade","high grade","extraordinary gloves",
    "popular tags","payment methods","visa","mc","applepay","paypal","maestro","en",
    "about us","affiliate","blog","screenshot tool","api","faq","support","jobs",
    "privacy","imprint","terms of service","follow us",
}

def _mp_is_noise(line):
    low = line.lower().strip()
    if low in _MP_NOISE:                        return True
    if _MP_WEAR.match(line):                    return True
    if _MP_FLOAT.match(line):                   return True
    if _MP_TOUR.match(line):                    return True
    if _MP_QUAL.match(line):                    return True
    if re.match(r"^info@", low):                return True
    if re.match(r"^[©\xa9]", line):             return True
    if "powered by steam" in low:               return True
    if re.search(r"\bbase grade\b", low):       return True
    return False

def _mp_extract_items(after_lines):
    clean      = [l for l in after_lines if not _mp_is_noise(l)]
    full_names = [l for l in clean if "|" in l]
    plain      = [l for l in clean if "|" not in l]
    full_parts = set()
    for name in full_names:
        for part in re.split(r"\|", name):
            base = part.strip()
            # strip leading non-letter chars (e.g. ★, ♦) so a plain name still
            # matches its fragment when the full name starts with a symbol
            base_noprefix = re.sub(r"^[^\w]+", "", base).strip()
            full_parts.add(base)
            full_parts.add(base_noprefix)
            full_parts.add(re.sub(r"\s*\(.*?\)\s*", "", base).strip())
            full_parts.add(re.sub(r"\s*\(.*?\)\s*", "", base_noprefix).strip())
    counts = Counter(plain)
    result, seen_full, seen_plain = [], set(), set()
    for name in full_names:
        if name not in seen_full:
            seen_full.add(name)
            result.append((name, 1))
    for line, count in counts.items():
        if line in full_parts or line in seen_plain:
            continue
        seen_plain.add(line)
        result.append((line, max(1, count // 2)))
    return result

_ORDER_BLOCK  = re.compile(r"^Order\s+#\s*\d+", re.I | re.M)
_SKIP_STATUSES = {"cancelled", "canceled", "open", "pending", "refunded"}
_KEEP_STATUSES = {"paid", "completed"}
_ITEM_NOISE   = {
    "container", "base grade container", "need help?", "total",
    "master agent", "distinguished agent", "superior agent", "exceptional agent",
    "shattered web", "remarkable sticker", "high grade sticker",
}

def _parse_order_items(item_lines):
    """
    Walk the item content lines for one order block and return
    a list of (item_name, price) with one entry per physical unit.

    Pattern for named items (skin, gloves, agent with |):
        Full Name | Rest\nFragment\nFragment\n$price\nwear/type info

    Pattern for plain items (cases, containers):
        Name\nContainer\nName\n$price\nBase Grade Container  (repeats per unit)

    Rule: once a full | name is pending, ignore fragments until the price arrives.
    """
    items        = []
    pending      = None
    locked_full  = False

    for line in item_lines:
        low = line.lower()
        if low in _ITEM_NOISE:                          continue
        if _MP_WEAR.match(line):                        continue
        if _MP_FLOAT.match(line):                       continue
        if _MP_TOUR.match(line):                        continue
        if re.match(r"^info@", low):                    continue
        if re.match(r"^[©\xa9]", line):                 continue
        if "powered by steam" in low:                   continue

        if _MP_MONEY.match(line):
            if pending is not None:
                price = float(line.replace("$","").replace(",",""))
                items.append((pending, price))
                pending     = None
                locked_full = False
        elif "|" in line and not _MP_TOUR.match(line):
            pending     = line   # full name always wins
            locked_full = True
        elif not locked_full:
            pending = line       # plain name only if not locked

    return items


def load_marketplace_paste(text, source="Marketplace", today=None):
    """
    Parse a raw Ctrl+A Ctrl+C paste from a marketplace All Orders page.
    Handles per-item prices, skips Cancelled/Open orders, detects both
    'Order # XXXXXXXX' headers and 'Purchased/Completed' style pages.
    """
    # --- Format A: "Order # XXXXXXXX" header style (All Orders page) ---
    if _ORDER_BLOCK.search(text):
        blocks  = re.split(r"(?=^Order\s+#)", text, flags=re.M)
        entries = []
        skipped_status = 0
        for block in blocks:
            lines     = [l.strip() for l in block.splitlines() if l.strip()]
            if not lines:
                continue
            date_line = next((l for l in lines if _MP_DATE.match(l)), None)
            if not date_line:
                continue
            status_line = next(
                (l for l in lines if l.lower() in _KEEP_STATUSES | _SKIP_STATUSES),
                None
            )
            if status_line and status_line.lower() in _SKIP_STATUSES:
                skipped_status += 1
                continue
            try:
                start = lines.index(status_line) + 1 if status_line else 2
            except ValueError:
                start = 2
            end = next((i for i, l in enumerate(lines) if l == "Need help?"), len(lines))
            item_pairs = _parse_order_items(lines[start:end])
            if not item_pairs:
                continue
            tok = parse_date(date_line)
            if tok:
                entries.append((tok, item_pairs))

        if entries:
            notes = []
            if skipped_status:
                notes.append(f"Skipped {skipped_status} cancelled/open order(s).")
            resolved = resolve_dates([e[0] for e in entries], today)
            out = []
            for (tok, item_pairs), (dt, inferred) in zip(entries, resolved):
                for item_name, price in item_pairs:
                    if is_cs(item_name):
                        out.append(Tx(dt, clean(item_name), -price, "Purchase", source, year_inferred=inferred))
            n_orders = len(entries)
            n_items  = len(out)
            if n_orders != n_items:
                notes.append(f"{n_items} individual items across {n_orders} paid orders.")
            return out, notes

    # --- Format B: "Purchased / Completed / Canceled" style (older layout, no item prices) ---
    blocks  = [b.strip() for b in text.split("Purchased") if b.strip()]
    entries = []
    mixed   = 0
    for block in blocks:
        lines      = [l.strip() for l in block.splitlines() if l.strip()]
        date_line  = next((l for l in lines if _MP_DATE.match(l)), None)
        status     = next((l for l in lines if l in ("Completed","Canceled")), None)
        if not date_line or status != "Completed":
            continue
        # First try _parse_order_items (works if prices are present)
        try:
            after = lines[lines.index(status)+1:]
        except ValueError:
            after = lines[3:]
        item_pairs = _parse_order_items(after)
        if not item_pairs:
            # No per-item prices — use order total divided by item count
            price_line = next((l for l in lines if _MP_MONEY.match(l)), None)
            if not price_line:
                continue
            order_total = float(price_line.replace("$","").replace(",",""))
            named_items = _mp_extract_items(after)   # (name, qty) tuples
            n = sum(q for _, q in named_items)
            if n == 0:
                continue
            per = order_total / n
            item_pairs = [(name, per) for name, qty in named_items for _ in range(qty)]
            if len({name for name, _ in named_items}) > 1:
                mixed += 1
        tok = parse_date(date_line)
        if tok and item_pairs:
            entries.append((tok, item_pairs))

    if not entries:
        return [], ["No orders found. Copy from your order history page (not item listings)."]
    resolved = resolve_dates([e[0] for e in entries], today)
    out = []
    for (tok, item_pairs), (dt, inferred) in zip(entries, resolved):
        for item_name, price in item_pairs:
            if is_cs(item_name):
                out.append(Tx(dt, clean(item_name), -price, "Purchase", source, year_inferred=inferred))
    notes = []
    if mixed:
        notes.append(
            f"{mixed} order(s) had mixed items with no individual prices — "
            f"order total was divided evenly. For exact prices, use the All Orders page."
        )
    return out, notes

def load_marketplace_order_file(text, source="Marketplace", today=None):
    """
    Parse order history in the structured export format:
        Order #12345678 (Mar 1, 2024)
        - Item Name: $1.00
        - Item Name: $2.00 (x5 individual items)
    """
    cur_date = None
    entries  = []
    for line in text.splitlines():
        line = line.strip()
        m = _ORDER_HEADER.search(line)
        if m:
            cur_date = parse_date(m.group(1))
            continue
        m = _ORDER_ITEM.match(line)
        if m and cur_date:
            item  = clean(m.group(1).strip())
            price = float(m.group(2).replace(",", ""))
            qty   = int(m.group(3)) if m.group(3) else 1
            if is_cs(item):
                entries.append((cur_date, item, price, qty))
    if not entries:
        return [], ["No structured orders found (expected 'Order #XXXXXXXX (Date)' format)."]
    resolved = resolve_dates([e[0] for e in entries], today)
    out = []
    for (tok, item, price, qty), (dt, inferred) in zip(entries, resolved):
        for _ in range(qty):
            out.append(Tx(dt, item, -price, "Purchase", source, year_inferred=inferred))
    return out, []

_CSV_DATE  = {"date","time","created","created at","order date","transaction date",
               "sold at","bought at","purchase date","sale date","timestamp"}
_CSV_ITEM  = {"item","item name","name","title","market name","market hash name","description"}
_CSV_PRICE = {"price","amount","total","value","sale price","purchase price",
               "unit price","item price","subtotal","fee-exclusive price"}
_CSV_TYPE  = {"type","action","kind","transaction type","order type","status"}
_CSV_QTY   = {"qty","quantity","count","units"}

def _csv_col(headers, synonyms):
    for i, h in enumerate(headers):
        if h.lower().strip() in synonyms:
            return i
    return None

def load_csv_transactions(text, source, today=None):
    """
    Parse a CSV transaction export from any marketplace.
    Handles any column order; recognises common header names for
    Date, Item, Price, Type (Buy/Sell) and Quantity.
    """
    import csv as _csv
    try:
        dialect = _csv.Sniffer().sniff(text[:2048], delimiters=",;\t")
    except Exception:
        dialect = _csv.excel
    reader  = _csv.reader(text.splitlines(), dialect)
    headers = None
    dc = ic = pc = tc = qc = None
    entries, bad = [], 0
    for row in reader:
        if not any(c.strip() for c in row):
            continue
        if headers is None:
            headers = row
            dc = _csv_col(headers, _CSV_DATE)
            ic = _csv_col(headers, _CSV_ITEM)
            pc = _csv_col(headers, _CSV_PRICE)
            tc = _csv_col(headers, _CSV_TYPE)
            qc = _csv_col(headers, _CSV_QTY)
            if ic is None or pc is None:
                return [], ["CSV has no recognisable Item or Price column. "
                            "Headers found: " + ", ".join(headers)]
            continue
        def get(idx):
            return row[idx].strip() if idx is not None and idx < len(row) else ""
        item  = clean(get(ic))
        price = parse_amount(get(pc))
        if not item or not price:
            bad += 1
            continue
        if not is_cs(item):
            continue
        # Type: treat anything with "sell"/"sale" as Sale, else Purchase
        raw_type = get(tc).lower()
        kind = "Sale" if any(w in raw_type for w in ("sell","sale","sold")) else "Purchase"
        # Quantity
        try:
            qty = max(1, int(float(get(qc)))) if qc else 1
        except ValueError:
            qty = 1
        val, sign = price
        if sign == "+":
            kind = "Sale"
        elif sign == "-":
            kind = "Purchase"
        tok = parse_date(get(dc)) if dc is not None else None
        if not tok:
            bad += 1
            continue
        entries.append((tok, item, qty, val, kind))
    if not entries:
        return [], ["No readable rows found in the CSV. "
                    "Make sure the file has Date, Item and Price columns."]
    resolved = resolve_dates([e[0] for e in entries], today)
    out = []
    for (tok, item, qty, val, kind), (dt, inferred) in zip(entries, resolved):
        for _ in range(qty):
            sign = 1 if kind == "Sale" else -1
            out.append(Tx(dt, item, sign * val, kind, source, year_inferred=inferred))
    notes = [f"Skipped {bad} unreadable row(s)."] if bad else []
    return out, notes


_TP_PRICE     = re.compile(r"\((\$[\d,.]+)\)")
_TP_FLOAT     = re.compile(r"^\d\.\d{6,}", re.MULTILINE)
_TP_RELDATE   = re.compile(
    r"^(?:about\s+)?(?:(\d+)|(?:a|an))\s+(day|week|month|year)s?\s+ago$", re.I
)
_TP_RARITY    = {
    "master agent","distinguished agent","superior agent","exceptional agent",
    "contraband","covert","classified","restricted","mil-spec",
}
_TP_NOISE_LOW = {
    "seller","buyer","seller accepts sale","seller sends trade",
    "buyer accepts trade","trade verified","search for trades",
    "completed, cancelled","completed, canceled",
    "you need to enable extension offer tracking",
    "you should enable offer tracking",
    "visit your steam trade offers page in order to enable it.",
    "affiliate","terms of service","privacy policy",
    "1password menu is available. press down arrow to select.",
}

def _tp_is_noise(line):
    low = line.lower().strip()
    if low in _TP_NOISE_LOW:                return True
    if re.match(r"^©", line):               return True
    if re.match(r"^\d$", line):             return True  # step numbers
    if _TP_FLOAT.match(line):               return True
    if re.match(r"^\d{1,4}$", line):        return True  # paint seed
    if re.match(r"#\d+", line):             return True
    return False

def _tp_rel_to_date(line, today):
    m = _TP_RELDATE.match(line.strip())
    if not m:
        return None
    n    = int(m.group(1)) if m.group(1) else 1
    unit = m.group(2).lower()
    if unit == "day":   return today - timedelta(days=n)
    if unit == "week":  return today - timedelta(weeks=n)
    if unit == "month": return today - timedelta(days=n * 30)
    if unit == "year":  return today - timedelta(days=n * 365)

def load_trade_pages(text, source="Trades", kind=None, today=None):
    """
    Parse a trade-history paste that has separate Sell and Buy tabs.
    kind: "Sale" or "Purchase". If None, auto-detects from context clues.
    Dates are approximate — these pages only show relative times ("9 months ago").
    Cancelled trades are skipped.
    """
    today   = today or date.today()
    lines   = [l.strip() for l in text.splitlines() if l.strip()]
    entries = []

    # Auto-detect kind if not provided
    if kind is None:
        joined_low = " ".join(lines[:10]).lower()
        kind = "Purchase" if "purchased" in joined_low or "buy" in joined_low else "Sale"

    for i, line in enumerate(lines):
        pm = _TP_PRICE.search(line)
        if not pm:
            continue
        price     = float(pm.group(1).replace("$", "").replace(",", ""))
        skin_part = line[:pm.start()].strip()

        # Weapon name = previous non-noise, non-price, non-date line
        weapon = ""
        for back in range(i - 1, max(i - 5, -1), -1):
            prev = lines[back].strip()
            if (not _tp_is_noise(prev)
                    and not _TP_PRICE.search(prev)
                    and not _TP_RELDATE.match(prev)
                    and prev.lower() not in ("successful", "cancelled", "canceled")):
                weapon = prev
                break

        # Build item name
        if weapon.lower() in _TP_RARITY:
            item = skin_part                           # agent: skin line IS the name
        elif weapon and skin_part and "|" not in weapon:
            item = f"{weapon} | {skin_part}"
        elif skin_part:
            item = skin_part
        else:
            item = weapon

        if not item or not is_cs(item):
            continue

        # Find status + relative date in the next few lines
        status = rel_date = None
        for j in range(i + 1, min(i + 9, len(lines))):
            low = lines[j].lower().strip()
            if low in ("successful", "cancelled", "canceled"):
                status = low
            if not rel_date:
                rel_date = _tp_rel_to_date(lines[j], today)
            if status and rel_date:
                break

        if status in ("cancelled", "canceled"):
            continue
        if not status or not rel_date:
            continue

        entries.append((rel_date, clean(item), price, kind))

    if not entries:
        return [], []

    sign = 1 if kind == "Sale" else -1
    out  = [Tx(dt, name, sign * price, kind, source, year_inferred=True)
            for dt, name, price, kind in entries]
    notes = [
        f"{len(out)} {kind.lower()}(s) loaded. Dates are approximate "
        f"(this page shows relative times only, e.g. '9 months ago')."
    ]
    return out, notes


def _is_trade_pages(text):
    """Return True if this text looks like a Sell/Buy trade-history paste."""
    low = text.lower()
    return (
        _TP_PRICE.search(text) is not None
        and _TP_FLOAT.search(text) is not None
        and ("seller accepts sale" in low or "trade verified" in low
             or "search for trades" in low)
    )


def trade_page_tab(text):
    """Which tab was pasted (Sell or Buy)? Asked up front, never during the progress bar. None if not a trade page."""
    if not _is_trade_pages(text):
        return None
    say("  Sell/Buy trade page detected. Which tab did you copy from?")
    return ("Sale", "Purchase")[menu(["Sell history (items you sold to others)", "Buy history (items you bought from others)"]) - 1]


def load_generic_order_history(path_or_text, source, today=None, page_kind=None):
    """
    Auto-detects format from file path or raw text string:
      1. CSV transaction export  (has header row with Date/Item/Price columns)
      2. Raw page paste          (contains 'Purchased' + date + price + status)
      3. Order export file       (Order #XXXXXXXX ...)
      4. Pipe format             (Date | Item | -$price)
    """
    text  = read_file(path_or_text) if isinstance(path_or_text, Path) else path_or_text
    today = today or date.today()

    # Sell/Buy trade pages: float values + "Seller Accepts Sale" / "Trade Verified" signatures
    if _is_trade_pages(text):
        rows, notes = load_trade_pages(text, source, page_kind or trade_page_tab(text), today)
        if rows:
            return rows, notes

    # CSV: first non-empty line has comma/semicolon/tab-separated values
    first = next((l for l in text.splitlines() if l.strip()), "")
    if re.search(r"[,;\t]", first) and not first.strip().startswith(("Purchased","Order")):
        rows, notes = load_csv_transactions(text, source, today)
        if rows:
            return rows, notes

    # "Order # XXXXXXXX" with space = All Orders page paste (has per-item prices)
    if _ORDER_BLOCK.search(text):
        rows, notes = load_marketplace_paste(text, source, today)
        if rows:
            return rows, notes

    # "Order #XXXXXXXX" no space = structured order export file
    if _ORDER_HEADER.search(text):
        rows, notes = load_marketplace_order_file(text, source, today)
        if rows:
            return rows, notes

    # "Purchased / Completed / Canceled" = older page layout
    if "Purchased" in text and _MP_DATE.search(text) and _MP_MONEY.search(text):
        rows, notes = load_marketplace_paste(text, source, today)
        if rows:
            return rows, notes

    return load_pipe_text(text, source, today)


def load_pipe_text(text, source, today=None):
    entries, bad = [], 0
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            bad += 1
            continue
        date_tok = parse_date(parts[0])
        amt      = parse_amount(parts[-1])
        if not date_tok or not amt:
            bad += 1
            continue
        item = clean(" | ".join(parts[1:-1]))
        if not is_cs(item):
            continue
        val, sign   = amt
        qty_match   = re.match(r"^(\d+)\s*[xX\u00d7]\s+(.+)$", item)
        qty, item   = (int(qty_match[1]), clean(qty_match[2])) if qty_match else (1, item)
        kind        = "Sale" if sign == "+" else "Purchase"
        entries.append((date_tok, item, qty, val, kind))
    notes = [f"Skipped {bad} unreadable line(s)."] if bad else []
    out   = []
    for (tok, item, qty, val, kind), (dt, inferred) in zip(entries, resolve_dates([e[0] for e in entries], today)):
        for _ in range(qty):
            sign = 1 if kind == "Sale" else -1
            out.append(Tx(dt, item, sign * val / qty, kind, source, year_inferred=inferred))
    return out, notes


class _MarketHTMLParser:
    FIELDS = {
        "market_listing_gainorloss": "sign",
        "market_listing_price":       "price",
        "market_listing_listed_date": "date",
        "market_listing_item_name":   "name",
        "market_listing_game_name":   "game",
    }
    def __init__(self):
        self.rows, self._row, self._stack = [], None, []

    def feed(self, html_text):
        pos      = 0
        tag_re   = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)([^>]*)>|&([a-zA-Z0-9#]+);")
        VOID     = {"br","img","input","meta","link","hr","wbr","source"}
        for m in tag_re.finditer(html_text):
            text_before = html_text[pos:m.start()]
            if text_before and self._row is not None:
                self._text(_html.unescape(text_before))
            pos = m.end()
            if m[4]:
                if self._row is not None:
                    self._text(_html.unescape(m[0]))
                continue
            closing, tag, attrs_raw = m[1] == "/", m[2].lower(), m[3]
            if closing:
                self._end(tag)
            else:
                classes = set((" ".join(re.findall(r'class="([^"]*)"', attrs_raw))).split())
                self._start(tag, classes)
                if tag in VOID:
                    self._end(tag)

    def _start(self, tag, classes):
        is_row = "market_listing_row" in classes
        fields = [self.FIELDS[c] for c in classes if c in self.FIELDS]
        if is_row:
            self._row = {"sign":"","price":"","date":[],"name":"","game":""}
            self.rows.append(self._row)
        if self._row is not None and "date" in fields:
            self._row["date"].append("")
        self._stack.append((tag, fields, is_row))

    def _end(self, tag):
        for i in range(len(self._stack)-1, -1, -1):
            t, _, is_row = self._stack[i]
            if t == tag:
                self._stack = self._stack[:i]
                if is_row:
                    self._row = None
                break

    def _text(self, data):
        if self._row is None:
            return
        for _, fields, _ in self._stack:
            for f in fields:
                if f == "date":
                    if self._row["date"]:
                        self._row["date"][-1] += data
                else:
                    self._row[f] += data


def _day_gap(a, month, day):
    return min(abs((safe_date(y, month, day) - a).days) for y in (a.year - 1, a.year, a.year + 1))


def _to_int(value, default=0):
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return default


def load_market(paths, today=None):
    """Steam Market history pages (JSON) and/or pipe-format text files. Returns (rows, notes, missing_urls)."""
    seen_starts, pages, text_rows, notes = set(), [], [], []
    total_count = page_size = 0
    for path in paths:
        text = read_file(path)
        if text.lstrip()[:1] != "{":
            rows, n = load_pipe_text(text, Path(path).stem, today)
            text_rows += rows
            notes += n
            continue
        try:
            data = json.loads(text)
        except (ValueError, RecursionError):
            notes.append(f"{path.name}: couldn't parse JSON.")
            continue
        html_text = data.get("results_html", "") if isinstance(data, dict) else ""
        if not html_text:
            notes.append(f"{path.name}: no market rows. Were you logged in when you saved this?")
            continue
        start = _to_int(data.get("start"), len(seen_starts) * 10000)
        if start in seen_starts:
            notes.append(f"{path.name}: duplicate page, skipped.")
            continue
        seen_starts.add(start)
        total_count = max(total_count, _to_int(data.get("total_count")))
        page_size   = _to_int(data.get("pagesize")) or page_size
        set_currency(html_text)
        parser = _MarketHTMLParser()
        parser.feed(html_text)
        pages.append((start, parser.rows))

    listed = [r for _, page in sorted(pages, key=lambda p: p[0]) for r in page]
    trades = [r for r in listed if r["sign"].strip()[:1] in ("+", "-", "\u2212")]
    skipped = len(listed) - len(trades)

    missing = []
    if page_size and total_count:
        missing = [(s // page_size + 1, MARKET_URL.format(start=s))                 # (page number, link), max 200
                   for s in range(0, min(total_count, page_size * 200), page_size) if s not in seen_starts]

    # Steam lists ACTED ON first, then LISTED ON. Years are not shown on this page.
    toks    = [next(iter([t for t in (parse_date(d) for d in r["date"]) if t]), (1, 1, None)) for r in trades]
    anchors = STEAM_MARKET_DATES
    close   = sum(1 for a, t in zip(anchors, toks) if _day_gap(a, t[0], t[1]) <= 1) if len(anchors) == len(trades) else 0
    aligned = bool(trades) and close >= 0.98 * len(trades)
    dated   = [(a, False) for a in anchors] if aligned else resolve_dates(toks, today)
    if trades and not missing:
        if aligned:
            notes.append(f"Dates verified against your Steam purchase history ({close} of {len(trades)} rows).")
        elif anchors:
            notes.append(f"Purchase history lists {len(anchors)} market transactions but these pages list "
                         f"{len(trades)}; years are estimated (marked *). Load the full purchase history for exact dates.")
        else:
            notes.append("No Steam purchase history loaded, so market years are estimated (marked *).")

    out = []
    for r, (dt, inferred) in zip(trades, dated):
        name = clean(r["name"])
        game = " ".join(r["game"].split())
        amt  = parse_amount(r["price"].strip())
        if not name or not amt or (game and not re.search(r"counter.?strike", game, re.I)) or not is_cs(name):
            skipped += 1
            continue
        kind = "Purchase" if r["sign"].strip()[:1] == "+" else "Sale"
        out.append(Tx(dt, name, -amt[0] if kind == "Purchase" else amt[0], kind, "Steam Market", year_inferred=inferred))
    out += text_rows
    if skipped:
        notes.append(f"Skipped {skipped} non-CS or listing-only rows.")
    return out, notes, missing


def estimate_keys(rows, price):
    cases = [r for r in rows if r.type == "Purchase" and is_case(r.item)]
    sold  = sum(1 for r in rows if r.type == "Sale" and is_case(r.item))
    keys  = sum(1 for r in rows if r.type == "Purchase" and is_key(r.item))
    missing = max(len(cases) - sold - keys, 0)
    dates = sorted(r.date for r in cases)
    return [Tx(dates[int(i * len(dates) / missing)], "Case Key (estimated)", -price, "Purchase", "Estimate", estimated=True)
            for i in range(missing)]


CATEGORIES = ["Container/Terminal", "Key", "Capsule", "Armory Pass", "Sticker", "Weapon", "Other"]
_WEAPON_RE = re.compile(
    r"(AK-47|AUG|AWP|CZ75-Auto|Desert Eagle|Dual Berettas|FAMAS|Five-SeveN|G3SG1|Galil AR|Glock-18|M249|M4A1-S|M4A4|"
    r"MAC-10|MAG-7|MP5-SD|MP7|MP9|Negev|Nova|P2000|P250|P90|PP-Bizon|R8 Revolver|SCAR-20|SG 553|SSG 08|Sawed-Off|"
    r"Tec-9|UMP-45|USP-S|XM1014|Zeus x27) \|")


def categorize(name):
    name = name.replace(" (estimated)", "")
    if re.search(r"\bkey$", name, re.I):
        return "Key"
    if re.search(r"\bPass$", name):
        return "Armory Pass"
    if re.search(r"Capsule|Patch Pack", name):
        return "Capsule"
    if re.search(r"\bCase(\s+\d+)?$|Terminal|Package", name):
        return "Container/Terminal"
    if name.startswith("Sticker"):
        return "Sticker"
    base = re.sub(r"^(\u2605 )?((StatTrak\u2122|Souvenir) )*(\u2605 )?", "", name)
    if name.startswith("\u2605") or _WEAPON_RE.match(base) or re.search(r"Knife|Bayonet|Karambit|Gloves|Wraps", base.split(" | ")[0]):
        return "Weapon"
    return "Other"


def _stem(name):
    name = re.sub(r"\s+Key$", "", name.replace(" (estimated)", ""))
    return name.replace("Weapon ", "").replace(" Case", "").strip().lower()


_FILTER_JS = r"""
function num(t) {
  var m = t.replace(/,/g, '').match(/\d+(\.\d+)?/);
  return m ? (t.indexOf('-') !== -1 ? -1 : 1) * parseFloat(m[0]) : 0;
}
function val(cell) {
  return cell.dataset.v !== undefined ? parseFloat(cell.dataset.v) : num(cell.textContent);
}
function fmt(v) {
  return (v < 0 ? '-' : '') + SYM + Math.abs(v).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}
function filterTable(inp) {
  var d = inp.dataset, q = inp.value.toLowerCase(), rows = document.getElementById(d.t).rows;
  var match = +d.m, amt = +d.a, qty = +d.q, n = 0, items = 0, sum = 0;
  var hasAmt = amt >= 0;
  for (var i = 1; i < rows.length; i++) {
    var c = rows[i].cells, text = '';
    if (hasAmt && c.length <= amt) continue;
    for (var j = 0; j < match && j < c.length; j++) text += c[j].textContent + ' ';
    var show = text.toLowerCase().indexOf(q) !== -1;
    rows[i].style.display = show ? '' : 'none';
    if (show) { n++; if (hasAmt) sum += val(c[amt]); if (qty >= 0) items += val(c[qty]); }
  }
  document.getElementById(d.t + '_out').textContent =
    q === '' ? '' : n + ' rows' + (qty >= 0 ? ', ' + items + ' items' : '') + (hasAmt ? ', total ' + fmt(sum) : '');
}
var _sortState = {};
function sortTable(th) {
  var tbl = th.closest('table');
  if (!tbl) return;
  var col = th.cellIndex;
  var key = tbl.id + ':' + col;
  var asc = _sortState[key] !== true;
  _sortState[key] = asc;
  var tbody = tbl.tBodies[0] || tbl;
  // rows[0] is always the header <tr> (no <thead> in generated tables); always skip it
  var rows = Array.from(tbody.rows).slice(1);
  // skip last row if it is a totals row (bold cell)
  var hasTotals = rows.length > 1 && rows[rows.length-1].querySelector('b');
  var dataRows = hasTotals ? rows.slice(0, rows.length - 1) : rows;
  var totalsRow = hasTotals ? rows[rows.length - 1] : null;
  dataRows.sort(function(a, b) {
    var ca = a.cells[col], cb = b.cells[col];
    if (!ca || !cb) return 0;
    // data-v attribute carries pre-computed floats (prices, totals); use those directly
    if (ca.dataset.v !== undefined && cb.dataset.v !== undefined) {
      var dva = parseFloat(ca.dataset.v), dvb = parseFloat(cb.dataset.v);
      if (!isNaN(dva) && !isNaN(dvb)) return asc ? dva - dvb : dvb - dva;
    }
    var sa = ca.textContent.trim(), sb = cb.textContent.trim();
    // ISO date: "2024-03-15" — compare lexicographically (already sortable)
    if (/^\d{4}-\d{2}-\d{2}$/.test(sa) && /^\d{4}-\d{2}-\d{2}$/.test(sb))
      return asc ? sa.localeCompare(sb) : sb.localeCompare(sa);
    // currency / numbers: strip symbols, commas, leading minus indicator "-$"
    var na = parseFloat(sa.replace(/[^0-9.\-]/g, '').replace(/(?<=\d),(?=\d)/g, ''));
    var nb = parseFloat(sb.replace(/[^0-9.\-]/g, '').replace(/(?<=\d),(?=\d)/g, ''));
    // re-apply sign from original text (e.g. "-$5.50")
    if (sa.indexOf('-') !== -1 && na > 0) na = -na;
    if (sb.indexOf('-') !== -1 && nb > 0) nb = -nb;
    if (!isNaN(na) && !isNaN(nb)) return asc ? na - nb : nb - na;
    return asc ? sa.localeCompare(sb) : sb.localeCompare(sa);
  });
  // update arrow indicators on all ths in this row
  Array.from(th.parentNode.cells).forEach(function(h) {
    h.dataset.sort = '';
    h.textContent = h.textContent.replace(/ [▲▼]$/, '');
  });
  th.dataset.sort = asc ? 'asc' : 'desc';
  th.textContent = th.textContent.replace(/ [▲▼]$/, '') + (asc ? ' ▲' : ' ▼');
  var parent = totalsRow ? totalsRow.parentNode : (dataRows[0] && dataRows[0].parentNode);
  dataRows.forEach(function(r) { if (parent) parent.insertBefore(r, totalsRow || null); });
  if (totalsRow && parent) parent.appendChild(totalsRow);
}
"""


def _normalize(name):
    """Lowercase + collapse whitespace for fuzzy duplicate matching."""
    return re.sub(r"\s+", " ", name.strip().lower())


def _build_reconciliation_panel(rows, table_fn, td_fn, tr_fn, empty_fn, e_fn, money_fn):
    """
    Build the Reconciliation tab:
    - Lifetime P&L breakdown by data source
    - Cross-source duplicate transaction detection
    """
    if not rows:
        return ""

    # ── 1. Lifetime P&L by source ──────────────────────────────────────────────
    by_src = defaultdict(lambda: {"spent": 0.0, "received": 0.0, "count": 0})
    for r in rows:
        if r.type == "Purchase":
            by_src[r.source]["spent"]    += r.amount   # negative
            by_src[r.source]["count"]    += 1
        elif r.type == "Sale":
            by_src[r.source]["received"] += r.amount   # positive
            by_src[r.source]["count"]    += 1

    total_spent    = sum(v["spent"]    for v in by_src.values())
    total_received = sum(v["received"] for v in by_src.values())
    total_net      = total_spent + total_received

    src_rows = []
    for src, v in sorted(by_src.items()):
        net = v["spent"] + v["received"]
        src_rows.append(tr_fn(
            td_fn(src), td_fn(v["count"], True),
            td_fn(money_fn(v["spent"])), td_fn(money_fn(v["received"])), td_fn(money_fn(net))
        ))
    src_rows.append(tr_fn(
        "<td><b>Total</b></td>", td_fn(sum(v["count"] for v in by_src.values()), True),
        td_fn(money_fn(total_spent)), td_fn(money_fn(total_received)),
        f'<td style="font-weight:bold">{e_fn(money_fn(total_net))}</td>'
    ))
    pnl_table = table_fn(
        ["Source", "Txns", "Spent (out)", "Received (in)", "Net P&L"],
        src_rows, "lcrrc"
    )

    # ── 2. Duplicate detection ─────────────────────────────────────────────────
    # Flag transactions sharing the same (date, item, amount, type) across different sources.
    seen_tx = defaultdict(list)
    for r in rows:
        key = (_normalize(r.item), r.date.isoformat(), f"{r.amount:.4f}", r.type)
        seen_tx[key].append(r.source)

    dupes = [(k, srcs) for k, srcs in seen_tx.items() if len(srcs) > 1 and len(set(srcs)) > 1]
    dupe_rows = []
    for (item, dt, amt, ttype), srcs in sorted(dupes, key=lambda x: x[0][1], reverse=True):
        dupe_rows.append(tr_fn(
            td_fn(dt), td_fn(item), td_fn(ttype, True),
            td_fn(money_fn(float(amt))), td_fn(", ".join(set(srcs)))
        ))
    if not dupe_rows:
        dupe_rows = ["<tr><td colspan=5 style='color:green'>&#10003; No duplicate transactions detected.</td></tr>"]
    dupe_table = table_fn(
        ["Date", "Item", "Type", "Amount", "Sources (potential duplicate)"],
        dupe_rows, "llcrr"
    )

    return f"""
<div id="reconcile" class="panel">
  <h2>Lifetime P&amp;L by Source</h2>
  {pnl_table}
  <h2>Duplicate Transaction Check</h2>
  <p class='note'>Flags any transaction with the same date, item, amount and type in two different sources.</p>
  {dupe_table}
</div>"""


def build_html(rows):
    sold   = [r for r in rows if r.type == "Sale"]
    bought = [r for r in rows if r.type == "Purchase"]
    cat    = {r.item: categorize(r.item) for r in rows}
    total_sold  = sum(r.amount for r in sold)
    total_spent = sum(r.amount for r in bought)          # negative number
    today = date.today()

    def e(v):
        return _html.escape(str(v))

    def mcell(v, extra=""):
        color = "green" if v >= 0 else "red"
        return f'<td data-v="{v:.6f}" style="text-align:right;color:{color}{extra}">{e(money(v))}</td>'

    def td(v, center=False):
        return f"<td{' class=c' if center else ''}>{e(v)}</td>"

    def tr(*cells):
        return "<tr>" + "".join(cells) + "</tr>"

    def table(headers, body, align="", table_id=""):
        marks = {"c": " class=c", "r": " class=r"}
        head  = "".join(f"<th{marks.get(a, '')} onclick=\"sortTable(this)\">{e(h)}</th>"
                        for h, a in zip(headers, align.ljust(len(headers))))
        ident = f" id={table_id}" if table_id else ""
        return f"<table{ident}><tr>{head}</tr>{''.join(body)}</table>"

    def finder(tid, hint, match_cols, amt_col, qty_col=-1):
        return (f'<p>Search: <input id="{tid}_q" size="38" placeholder="{e(hint)}" data-t="{tid}" '
                f'data-m="{match_cols}" data-a="{amt_col}" data-q="{qty_col}" oninput="filterTable(this)"> '
                f'<b id="{tid}_out"></b></p>')

    def empty(cols):
        return [f"<tr><td colspan={cols}>None recorded.</td></tr>"]

    def grouped(rs):
        g = defaultdict(list)
        for r in rs:
            g[r.item].append(r)
        return sorted(g.items(), key=lambda kv: (CATEGORIES.index(cat[kv[0]]), kv[0].lower()))

    def item_rows(rs):
        out = []
        for item, g in grouped(rs):
            dates = ", ".join(r.date.isoformat() for r in sorted(g, key=lambda x: x.date))
            flag  = " <span style='color:orange'>&#9888; est.</span>" if any(r.estimated for r in g) else ""
            out.append(tr(td(cat[item]), f"<td>{e(item)}{flag}</td>", td(len(g), True),
                          mcell(sum(r.amount for r in g)), f"<td class=d>{e(dates)}</td>"))
        return out or empty(5)

    # ----- helpers that answer common questions
    def best_category(rs):
        if not rs:
            return "None"
        money_by, count_by = defaultdict(float), Counter()
        for r in rs:
            money_by[cat[r.item]] += abs(r.amount)
            count_by[cat[r.item]] += 1
        c = max(money_by, key=money_by.get)
        return f"{c} \u2014 {money(money_by[c])} across {count_by[c]} items"

    def top_container(rs):
        counts = Counter(r.item for r in rs if cat[r.item] == "Container/Terminal")
        if not counts:
            return "None"
        name, n = counts.most_common(1)[0]
        return f"{name} \u2014 {n} bought"

    def top_item(rs, verb):
        if not rs:
            return "None"
        name, n = Counter(r.item for r in rs).most_common(1)[0]
        return f"{name} \u2014 {n} {verb}"

    def priciest(rs):
        if not rs:
            return "None"
        r = max(rs, key=lambda x: abs(x.amount))
        return f"{r.item} \u2014 {money(abs(r.amount))} on {r.date.isoformat()}"

    def per_period(rs, key):
        t = defaultdict(float)
        for r in rs:
            t[key(r)] += abs(r.amount)
        return t

    def peak(rs, key, label):
        t = per_period(rs, key)
        if not t:
            return "None"
        k = max(t, key=t.get)
        return f"{label(k)} \u2014 {money(t[k])}"

    def peak_year(rs):
        return peak(rs, lambda r: r.date.year, str)

    def peak_month(rs):
        return peak(rs, lambda r: (r.date.year, r.date.month), lambda k: date(k[0], k[1], 1).strftime("%B %Y"))

    def peak_day(rs):
        t = per_period(rs, lambda r: r.date)
        if not t:
            return "None"
        d = max(t, key=t.get)
        return f"{d.isoformat()} \u2014 {money(t[d])} across {sum(1 for r in rs if r.date == d)} items"

    def last_12_months(rs):
        cutoff = today - timedelta(days=365)
        return money(sum(abs(r.amount) for r in rs if cutoff < r.date <= today))

    def trend(rs):
        t = per_period(rs, lambda r: r.date.year)
        if len(t) < 2:
            return "Not enough years of data"
        latest, prev = max(t), max(t) - 1
        if latest == today.year:                       # this year is incomplete: compare the same stretch of last year
            cut = (today.month, today.day)
            a = sum(abs(r.amount) for r in rs if r.date.year == latest and (r.date.month, r.date.day) <= cut)
            b = sum(abs(r.amount) for r in rs if r.date.year == prev and (r.date.month, r.date.day) <= cut)
            text = f"{latest} so far: {money(a)} vs same period in {prev}: {money(b)}"
        else:
            a, b = t.get(latest, 0), t.get(prev, 0)
            text = f"{latest}: {money(a)} vs {prev}: {money(b)}"
        return text + (f" ({(a - b) / b * 100:+.0f}%)" if b else "")

    def qa(pairs):
        return table(["Question", "Answer"], [tr(td(q), td(a)) for q, a in pairs])

    years = list(range(min(r.date.year for r in rows), max(r.date.year for r in rows) + 1)) if rows else []

    def year_table(headers, cols, align):
        return table(headers, [tr(td(y, True), *cols(y)) for y in years], align)

    # ----- category numbers
    by_cat = {c: [0, 0.0, 0, 0.0] for c in CATEGORIES}
    for r in rows:
        v = by_cat[cat[r.item]]
        if r.type == "Purchase":
            v[0] += 1
            v[1] += r.amount
        else:
            v[2] += 1
            v[3] += r.amount
    net_by_cat = {c: v[1] + v[3] for c, v in by_cat.items() if v[0] or v[2]}
    cat_rows = [tr(td(c), td(v[0], True), mcell(v[1]), td(v[2], True), mcell(v[3]), mcell(v[1] + v[3]))
                for c, v in by_cat.items() if v[0] or v[2]]
    cat_rows.append(tr("<td><b>Total</b></td>", td(len(bought), True), mcell(total_spent), td(len(sold), True),
                       mcell(total_sold), mcell(total_sold + total_spent, ";font-weight:bold")))

    counts = defaultdict(lambda: [0, 0])
    for r in rows:
        counts[r.item][0 if r.type == "Purchase" else 1] += 1
    details = []
    for c in CATEGORIES:
        items = sorted((i for i in counts if cat[i] == c), key=str.lower)
        if items:
            body  = [tr(td(i), td(counts[i][0], True), td(counts[i][1], True)) for i in items]
            units = sum(sum(counts[i]) for i in items)
            details.append(f"<details><summary><b>{e(c)}</b> \u2014 {len(items)} different items, {units} bought or sold</summary>"
                           f"{table(['Item', 'Bought', 'Sold'], body, 'lcc')}</details>")

    by_source = defaultdict(lambda: [0.0, 0.0])
    for r in rows:
        by_source[r.source][0 if r.type == "Purchase" else 1] += r.amount
    source_rows = [tr(td(src), mcell(v[0]), mcell(v[1]), mcell(v[0] + v[1])) for src, v in sorted(by_source.items())]

    def money_year(y):
        spent = sum(r.amount for r in bought if r.date.year == y)
        got   = sum(r.amount for r in sold if r.date.year == y)
        return [mcell(spent), mcell(got), mcell(spent + got)]

    # ----- containers: money spent on each container and on its keys
    cont = defaultdict(lambda: {"name": "", "bought": 0, "spent": 0.0, "sold": 0, "keys": 0, "key_spent": 0.0})
    for r in rows:
        if r.estimated:
            continue
        if cat[r.item] == "Container/Terminal":
            d = cont[_stem(r.item)]
            d["name"] = r.item
            if r.type == "Purchase":
                d["bought"] += 1
                d["spent"]  += r.amount
            else:
                d["sold"] += 1
        elif cat[r.item] == "Key" and r.type == "Purchase":
            d = cont[_stem(r.item)]
            d["name"]       = d["name"] or re.sub(r"\s+Key$", "", r.item)
            d["keys"]      += 1
            d["key_spent"] += r.amount
    ordered   = sorted(cont.values(), key=lambda d: d["spent"] + d["key_spent"])
    cont_rows = [tr(td(d["name"]), td(d["bought"], True), mcell(d["spent"]), td(d["sold"], True),
                    td(d["keys"], True), mcell(d["key_spent"]), mcell(d["spent"] + d["key_spent"])) for d in ordered]
    cont_rows.append(tr("<td><b>Total</b></td>", td(sum(d["bought"] for d in ordered), True),
                        mcell(sum(d["spent"] for d in ordered)), td(sum(d["sold"] for d in ordered), True),
                        td(sum(d["keys"] for d in ordered), True), mcell(sum(d["key_spent"] for d in ordered)),
                        mcell(sum(d["spent"] + d["key_spent"] for d in ordered), ";font-weight:bold")))

    def costliest_container():
        d = ordered[0] if ordered else None
        if not d or d["spent"] + d["key_spent"] >= 0:
            return "None"
        return f"{d['name']} \u2014 {money(d['spent'] + d['key_spent'])} ({d['bought']} containers + {d['keys']} keys)"

    def most_keys():
        d = max(ordered, key=lambda x: x["keys"]) if ordered else None
        return f"{d['name']} \u2014 {d['keys']} keys" if d and d["keys"] else "None"

    cases_bought = sum(1 for r in bought if is_case(r.item) and not r.estimated)
    cases_sold   = sum(1 for r in sold if is_case(r.item))
    keys_bought  = sum(1 for r in bought if cat[r.item] == "Key" and not r.estimated)
    keys_vs_cases = f"{keys_bought} keys vs {cases_bought} cases bought ({cases_sold} cases sold)"
    keys_vs_containers = f"Keys {money(by_cat['Key'][1])} \u00b7 Containers {money(by_cat['Container/Terminal'][1])}"

    # ----- questions and answers
    net = total_sold + total_spent
    verdict = ("Yes \u2014 net gain" if net > 0 else "No \u2014 net loss" if net < 0 else "Break-even") + \
              f" of {money(abs(net))} ({money(total_sold)} received vs {money(-total_spent)} spent)"
    worst = min(net_by_cat, key=net_by_cat.get) if net_by_cat else None
    best  = max(net_by_cat, key=net_by_cat.get) if net_by_cat else None
    top_source = min(by_source, key=lambda k: by_source[k][0]) if by_source else None
    first = min(rows, key=lambda r: r.date) if rows else None
    last  = max(rows, key=lambda r: r.date) if rows else None

    summary_qa = qa([
        ("Did I come out ahead?", verdict),
        ("How much have I spent in total?", f"{money(total_spent)} on {len(bought)} items"),
        ("How much have I received from selling?", f"{money(total_sold)} from {len(sold)} items"),
        ("How much went to keys vs. containers?", keys_vs_containers),
        ("Which category costs me the most?", best_category(bought)),
        ("Which category lost me the most overall?", f"{worst} \u2014 {money(net_by_cat[worst])} net" if worst else "None"),
        ("Which category made me the most overall?",
         f"{best} \u2014 {money(net_by_cat[best])} net" if best and net_by_cat[best] > 0 else "None \u2014 every category is net negative"),
        ("Which container is my most expensive (containers + keys)?", costliest_container()),
        ("Which container have I bought the most?", top_container(bought)),
        ("How many keys vs. cases did I buy?", keys_vs_cases),
        ("What was my biggest purchase?", priciest(bought)),
        ("What was my biggest sale?", priciest(sold)),
        ("Which year did I spend the most?", peak_year(bought)),
        ("Which month did I spend the most?", peak_month(bought)),
        ("Which single day did I spend the most?", peak_day(bought)),
        ("Am I spending more or less lately?", trend(bought)),
        ("How much did I spend in the last 12 months?", last_12_months(bought)),
        ("Where do I spend the most?", f"{top_source} \u2014 {money(by_source[top_source][0])}" if top_source else "None"),
        ("When was my first and latest transaction?",
         f"First {first.date.isoformat()} ({first.source}); latest {last.date.isoformat()} ({last.source})" if rows else "None"),
    ])
    bought_qa = qa([
        ("How much have I spent?", f"{money(total_spent)} on {len(bought)} items"),
        ("How much went to keys vs. containers?", keys_vs_containers),
        ("Which category costs me the most?", best_category(bought)),
        ("Which item have I bought the most of?", top_item(bought, "bought")),
        ("Which container have I bought the most?", top_container(bought)),
        ("What was my biggest purchase?", priciest(bought)),
        ("Which year did I spend the most?", peak_year(bought)),
        ("Which month did I spend the most?", peak_month(bought)),
        ("Which single day did I spend the most?", peak_day(bought)),
        ("Am I spending more or less lately?", trend(bought)),
        ("How much did I spend in the last 12 months?", last_12_months(bought)),
    ])
    sold_qa = qa([
        ("How much have I received?", f"{money(total_sold)} from {len(sold)} items"),
        ("Which category earns me the most?", best_category(sold)),
        ("Which item have I sold the most of?", top_item(sold, "sold")),
        ("What was my biggest sale?", priciest(sold)),
        ("Which year did I sell the most?", peak_year(sold)),
        ("Which month did I sell the most?", peak_month(sold)),
        ("Which single day did I sell the most?", peak_day(sold)),
        ("Am I selling more or less lately?", trend(sold)),
        ("How much did I receive in the last 12 months?", last_12_months(sold)),
    ])
    container_qa = qa([
        ("Which container is my most expensive (containers + keys)?", costliest_container()),
        ("Which container did I buy the most keys for?", most_keys()),
        ("How many keys vs. cases did I buy?", keys_vs_cases),
    ])
    bought_years = year_table(["Year", "Items bought", "Spent"],
                              lambda y: [td(sum(1 for r in bought if r.date.year == y), True),
                                         mcell(sum(r.amount for r in bought if r.date.year == y))], "ccr")
    sold_years = year_table(["Year", "Items sold", "Received"],
                            lambda y: [td(sum(1 for r in sold if r.date.year == y), True),
                                       mcell(sum(r.amount for r in sold if r.date.year == y))], "ccr")

    tx_rows = [tr(td(r.date.isoformat()), td(cat[r.item]), td(r.item),
                  f"<td style='color:{'green' if r.type == 'Sale' else 'red'}'>{e(r.type)}</td>",
                  mcell(r.amount), td(r.source), td("\u26a0" if r.estimated else ("*" if r.year_inferred else "")))
               for r in sorted(rows, key=lambda x: x.date, reverse=True)] or empty(7)

    reconcile_panel = _build_reconciliation_panel(rows, table, td, tr, empty, e, money)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>CS2 Spending Summary</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; color: #222; }}
  h1   {{ color: #1a1a2e; }}
  h2   {{ color: #333f50; margin-top: 30px; border-bottom: 2px solid #333f50; padding-bottom: 4px; }}
  .tabs  {{ display: flex; gap: 6px; margin: 20px 0 0; flex-wrap: wrap; }}
  .tab   {{ padding: 10px 18px; background: #fff; border: 1px solid #ccc; cursor: pointer; font-size: 1em; }}
  .tab.active {{ background: #333f50; color: #fff; }}
  .panel {{ display: none; background: white; padding: 20px; border: 1px solid #ccc; max-width: 1400px; }}
  .panel.active {{ display: block; }}
  table  {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: .95em; }}
  th     {{ background: #333f50; color: white; padding: 8px 10px; text-align: left; cursor: pointer; user-select: none; white-space: nowrap; }}
  th:hover {{ background: #4a5a72; }}
  th[data-sort="asc"], th[data-sort="desc"] {{ background: #1a2b40; }}
  td     {{ padding: 7px 10px; border-bottom: 1px solid #eee; }}
  tr:hover {{ background: #f0f0f0; }}
  .c {{ text-align: center; }}
  .r {{ text-align: right; }}
  .d {{ font-size: .85em; color: #555; }}
  details {{ margin-top: 10px; }}
  summary {{ cursor: pointer; padding: 6px 0; }}
  input {{ padding: 6px 8px; font-size: 1em; }}
  .note  {{ background: #fffbe6; border: 1px solid #e6c700; padding: 14px; margin: 16px 0; border-radius: 4px; font-size: .9em; }}
  .legend {{ color: #888; font-size: .85em; margin-top: 10px; }}
  @media (max-width: 600px) {{ th, td {{ padding: 5px 6px; font-size: .85em; }} }}
</style>
</head>
<body>
<h1>CS2 Spending Summary</h1>
<p style="color:#666">Generated {today.isoformat()}</p>
<div class="note">
  <strong>About this file:</strong> Generated locally on your computer by CS2 Spending Tracker - Github.py.
  No data was sent anywhere. This file contains only your transaction data.
  To verify: open CS2 Spending Tracker - Github.py in any text editor and read it.
</div>
<div class="tabs">
  <button class="tab active" onclick="show('summary',this)">Summary</button>
  <button class="tab" onclick="show('sold',this)">Items Sold</button>
  <button class="tab" onclick="show('bought',this)">Items Purchased</button>
  <button class="tab" onclick="show('containers',this)">Containers</button>
  <button class="tab" onclick="show('txlog',this)">All Transactions</button>
  <button class="tab" onclick="show('reconcile',this)">Reconciliation</button>
</div>
<div id="summary" class="panel active">
  <h2>Quick Answers</h2>
  {summary_qa}
  <h2>By Category</h2>
  {table(["Category", "Bought", "Spent", "Sold", "Received", "Net"], cat_rows, "lcrcrr")}
  <h3>Items In Each Category (click a category to expand)</h3>
  {''.join(details)}
  <h2>By Source</h2>
  {table(["Source", "Spent", "Received", "Net"], source_rows, "lrrr")}
  <h2>By Year</h2>
  {year_table(["Year", "Spent", "Received", "Net"], money_year, "crrr")}
</div>
<div id="sold" class="panel">
  <h2>Items Sold</h2>
  {sold_qa}
  {sold_years}
  <h2>All Items Sold</h2>
  {finder("sold_t", "type an item or category, e.g. Weapon", 2, 3, 2)}
  {table(["Category", "Item", "Qty", "Total Received", "Dates"], item_rows(sold), "llcrl", "sold_t")}
</div>
<div id="bought" class="panel">
  <h2>Items Purchased</h2>
  {bought_qa}
  {bought_years}
  <h2>All Items Purchased</h2>
  {finder("bought_t", "type an item or category, e.g. Case", 2, 3, 2)}
  {table(["Category", "Item", "Qty", "Total Spent", "Dates"], item_rows(bought), "llcrl", "bought_t")}
</div>
<div id="containers" class="panel">
  <h2>Containers: Cases and Keys</h2>
  {container_qa}
  {table(["Container", "Bought", "Spent on containers", "Sold", "Keys bought", "Spent on keys", "Total spent"], cont_rows, "lcrccrr")}
</div>
<div id="txlog" class="panel">
  <h2>All Transactions</h2>
  {finder("tx", "type anything: an item, 2024-03, Sale, Key, Steam Market", 7, 4)}
  {table(["Date", "Category", "Item", "Type", "Amount", "Source", ""], tx_rows, "llllrll", "tx")}
  <p class="legend">* = year estimated from list order &nbsp; &#9888; = estimated key</p>
</div>
{reconcile_panel}
<footer style="margin:40px 0 0;padding:16px 0;border-top:1px solid #ccc;font-size:12px;color:#666;line-height:1.6">
  <p>Generated locally from pages you saved from your own Steam account. For personal use; provided "as is" with no guarantee of accuracy.
  Your use of Steam is governed by the <a href="https://store.steampowered.com/subscriber_agreement/" target="_blank" rel="noopener">Steam Subscriber Agreement</a>.</p>
  <p>Not affiliated with or endorsed by Valve Corporation. Steam&reg; and Counter-Strike are trademarks of Valve Corporation.</p>
</footer>
<script>
var SYM = {json.dumps(CUR[0])};
{_FILTER_JS}
function show(id, btn) {{
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  btn.classList.add('active');
}}
</script>
</body>
</html>"""


def parse_with_bar(label, fn, *args, fail=([], []), **kwargs):
    """
    Call fn(*args, **kwargs) in a background thread.
    While it runs: pause the always-on spinner and show a Win98 bouncing
    block bar instead. When done: fill the bar solid, then resume spinner.
    """
    result   = [None]
    error    = [None]
    finished = [False]

    def worker():
        try:
            result[0] = fn(*args, **kwargs)
        except Exception as e:
            error[0] = e
        finally:
            finished[0] = True

    _sp_clear_line()
    _sp_set(paused=True)          # hand the line to the block bar

    cols      = max(40, _shutil.get_terminal_size((72, 24)).columns - 4)
    bar_width = min(40, max(10, cols - len(label) - 16))
    FULL      = "\u2588"
    EMPTY     = "\u2591"
    BOUNCE    = 6

    t = _threading.Thread(target=worker, daemon=True)
    t.start()

    pos, going_right, tick = 0, True, 0
    while not finished[0]:
        bar = [EMPTY] * bar_width
        for k in range(BOUNCE):
            idx = pos + k
            if 0 <= idx < bar_width:
                bar[idx] = FULL
        print(f"\r  {label}  [{(''.join(bar))}]  working...", end="", flush=True)
        _time.sleep(0.05)
        tick += 1
        if tick % 2 == 0:
            if going_right:
                pos += 1
                if pos + BOUNCE >= bar_width:
                    going_right = False
            else:
                pos -= 1
                if pos <= 0:
                    going_right = True

    bar_str = FULL * bar_width
    print(f"\r  {label}  [{bar_str}]  done!   \n", flush=True)

    _sp_set(label="waiting...", paused=False)   # hand line back to spinner

    if error[0]:
        say(f"  Could not read that input ({type(error[0]).__name__}).")
        return fail
    return result[0]


def abort():
    """Ask for confirmation then hard-exit the script."""
    say("")
    say("  !! ABORT !!")
    say("  This will immediately terminate the program and all related processes.")
    say("  Nothing will be saved. Any data you have entered will be lost.")
    say("  There is no way to resume — you will need to start over.")
    if yes_no("  Are you sure you want to abort?", False):
        say("")
        say("  Program terminated. No files were written.")
        spinner_stop()
        sys.exit(0)


def show_preview(rows, label):
    buys  = [r for r in rows if r.type == "Purchase"]
    sells = [r for r in rows if r.type == "Sale"]
    say(f"\n  {label}: {len(rows)} transactions")
    say(f"    Purchases {len(buys):>4}  {money(sum(r.amount for r in buys))}")
    say(f"    Sales     {len(sells):>4}  {money(sum(r.amount for r in sells))}")
    sample = sorted(rows, key=lambda r: r.date, reverse=True)[:5]
    for r in sample:
        say(f"      {r.date}  {r.type:<8}  {money(r.amount):>10}  {r.item[:50]}")


SKIP, RESTART = "skip", "restart"
STEP_MENU = ["Load a saved file", "Paste the text directly", "Skip this step", "Start over from Step 1", "Abort"]
MAIN_MENU = ["Save the HTML report (finalize)", "Redo Step 1 (Steam purchase history)",
             "Redo Step 2 (Steam Market history)", "Add marketplace data (Step 3)", "Estimate missing keys", "Abort"]
MARKETPLACE_TEXT = ("Various marketplaces may have different pages for all transactions, all orders, etc. Try to find "
                    "the page that has an itemized breakdown of each purchase. You may need to paste two different data "
                    "sets, one for purchases, one for items sold. In some instances this may be captured. If you are not "
                    "sure, see the README.")
_MARKETPLACES = [0]


def menu(options, enter=None):
    """Numbered menu used everywhere. Returns 1..n, or `enter` when Enter is allowed."""
    for i, text in enumerate(options, 1):
        say(f"  {i}  {text}")
    while True:
        ch = ask("  Choose").strip().lower()
        if not ch and enter is not None:
            return enter
        if ch.isdigit() and 1 <= int(ch) <= len(options):
            return int(ch)
        say("  No input selected" if not ch else f"  Please choose a number from 1 to {len(options)}.")


def step_exit(choice, skip_question):
    """Choices 3-5 of every step menu. Returns SKIP or RESTART, or None to show the menu again."""
    if choice == 3 and yes_no(skip_question, False):
        return SKIP
    if choice == 4 and yes_no("  Start over from Step 1? Everything loaded so far will be cleared.", False):
        return RESTART
    if choice == 5:
        abort()
    return None


def accepted(rows, notes, label):
    for n in notes:
        say(f"  Note: {n}")
    if not rows:
        say("  Nothing readable was found. Check the steps above and try again.")
        return False
    show_preview(rows, label)
    say("")
    if yes_no("  Does that look right?", True):
        return True
    say("  Discarded. You can try again.")
    return False


def _paste_input(prompt):
    """Read a multi-line paste. The user types END on its own line to finish."""
    say(prompt)
    say("  (Paste your text below, then type END on a new line and press Enter)")
    _sp_set(paused=True)
    _sp_clear_line()
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip().upper() == "END":
            break
        lines.append(line)
    _sp_set(label="waiting...", paused=False)
    return "\n".join(lines)


def step_steam():
    banner("Step 1 of 3 — Steam purchase history")
    say(f"""
  1. Go to {STEAM_HISTORY_URL}
  2. Click "Load more transactions" until you see the full history.
  3. Press Ctrl+A, then Ctrl+C to copy the whole page.
  4. Paste it into Notepad and save it with any name, e.g. "Steam purchases 1.txt".
  5. Load that file with option 1 (or paste the page directly with option 2).
""")
    if ask_open("  Open that page in your browser now?"):
        webbrowser.open(STEAM_HISTORY_URL)
    while True:
        choice = menu(STEP_MENU)
        if choice == 1:
            f = pick_file("Select your Steam purchase history file", [("Text files", "*.txt *.csv")])
            if not f:
                continue
            rows, notes = parse_with_bar("Parsing Steam history", load_steam_history, f)
        elif choice == 2:
            text = _paste_input("\n  Paste your Steam purchase history page:")
            if not text.strip():
                say("  Nothing was pasted.")
                continue
            rows, notes = parse_with_bar("Parsing Steam history", load_steam_history_text, text)
        else:
            result = step_exit(choice, "  Skip Steam purchase history? Key purchases may be missing.")
            if result:
                return result
            continue
        if accepted(rows, notes, "Steam history"):
            return rows


MARKET_STEP_MENU = ["Load a saved file", "Skip this step", "Start over from Step 1", "Abort"]


def step_market():
    banner("Step 2 of 3 — Steam Market history")
    say(f"""
  1. Make sure you are logged in to Steam in your browser.
  2. Open this link (the page looks like a wall of text, that is correct):
     {MARKET_URL.format(start=0)}
  3. Press Ctrl+S and save it with any name, e.g. "Market 1.txt".
  4. Load it with option 1 below. If you have more than 500 market transactions,
     the tool will list the next pages to save: "Market 2.txt", "Market 3.txt", ...

  Note: pasting is not available for this step due to the size of Steam Market data.
        Save the page with Ctrl+S and load it as a file instead.
""")
    if ask_open("  Open that page in your browser now?"):
        webbrowser.open(MARKET_URL.format(start=0))
    files = []
    MARKET_FILES.clear()
    while True:
        choice = menu(MARKET_STEP_MENU)
        if choice == 1:
            f = pick_file("Select a saved market page", [("Text / JSON", "*.txt *.json")])
            if not f:
                continue
            files += [] if f in files else [f]
            rows, notes, missing = parse_with_bar("Parsing market pages", load_market, files, fail=([], [], []))
            if missing:
                for n in notes:
                    say(f"  Note: {n}")
                say(f"\n  {len(missing)} more page(s) to save. Open each link, press Ctrl+S, then load it with option 1:")
                for page, url in missing:
                    say(f"    Market {page}.txt  <-  {url}")
                if ask_open("  Open the next page in your browser now?"):
                    webbrowser.open(missing[0][1])
                continue
        else:
            # choices 2, 3, 4 map to skip/restart/abort (same as positions 3, 4, 5 in STEP_MENU)
            mapped = choice + 1   # shift so step_exit sees 3=skip, 4=restart, 5=abort
            result = step_exit(mapped, "  Skip Steam Market history? Your market buys and sales will be left out.")
            if result:
                return result
            continue
        if accepted(rows, notes, "Steam Market"):
            MARKET_FILES[:] = files
            return rows
        files = []


def step_other():
    banner("Step 3 of 3 — Marketplace history")
    say("\n  " + MARKETPLACE_TEXT)
    say("""
  Accepted: a copied orders/transactions page, a CSV export, or one line per transaction:
      Date | Item name | -$price    (minus = you spent)
      Date | Item name | +$price    (plus  = you received)
""")
    out = []
    while True:
        say("  Enter to finalize data or skip this step entirely.")
        choice = menu(STEP_MENU, enter=0)
        if choice == 0:
            if out:
                return out
            if yes_no("  No marketplace data loaded. Skip this step?", False):
                return SKIP
        elif choice in (1, 2):
            if choice == 1:
                f = pick_file("Select a marketplace file", [("Text / CSV", "*.txt *.csv")])
                text = read_file(f) if f else ""
            else:
                text = _paste_input("\n  Paste the marketplace page:")
            if not text.strip():
                say("  Nothing to read.")
                continue
            label = ask("  Name for this source", f"Marketplace {_MARKETPLACES[0] + 1}")
            rows, notes = parse_with_bar(f"Parsing {label}", load_generic_order_history, text, label, None, trade_page_tab(text))
            if accepted(rows, notes, label):
                out += rows
                _MARKETPLACES[0] += 1
        else:
            result = step_exit(choice, "  Skip this step?" + (" Data loaded in this step will be discarded." if out else ""))
            if result:
                return result


def _pick_save_path():
    """Ask where to save the HTML report. Uses a save dialog if tkinter is available."""
    downloads = Path.home() / "Downloads"
    default   = str(downloads / "CS2_Summary.html") if downloads.exists() else "CS2_Summary.html"
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.lift()
        root.attributes("-topmost", True)
        path = filedialog.asksaveasfilename(
            title        = "Save CS2 Summary report",
            initialdir   = str(downloads) if downloads.exists() else str(Path.home()),
            initialfile  = "CS2_Summary.html",
            defaultextension = ".html",
            filetypes    = [("HTML file", "*.html"), ("All files", "*.*")],
        )
        root.destroy()
        if not path:
            return None
        return Path(path)
    except Exception:
        raw = ask("  Save report as", default)
        if not raw:
            return None
        p = Path(raw).expanduser()
        if not p.suffix:
            p = p.with_suffix(".html")
        return p


def collect():
    """Run Steps 1-3 (from Step 1 again when asked). None means every step was skipped."""
    while True:
        results = []
        for step in (step_steam, step_market, step_other):
            result = step()
            if result == RESTART:
                break
            results.append(result)
        else:
            if all(r == SKIP for r in results):
                return None
            return [[] if r == SKIP else r for r in results]


def save_report(rows):
    out_path = _pick_save_path()
    if out_path is None:
        return False
    try:
        out_path.write_text(build_html(rows), encoding="utf-8")
    except PermissionError:
        out_path = Path.home() / "Downloads" / out_path.name
        say(f"  That folder is blocked. Saving to {out_path} instead.")
        try:
            out_path.write_text(build_html(rows), encoding="utf-8")
        except OSError as e:
            say(f"  Still failed: {e}")
            return False
    say(f"\n  Saved: {out_path.resolve()}")
    if ask_open("  Open the report in your browser now?"):
        webbrowser.open(out_path.resolve().as_uri())
    return True


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(DISCLAIMER)
    spinner_start("waiting for acknowledgement...")
    press_any_key("  Press any key to confirm you acknowledge the disclaimer above...")
    choose_key_price()
    data = collect()
    while True:
        if data is None:
            say("nothing has been selected.")
            spinner_stop()
            return
        steam, market, other = data
        rows = steam + market + other
        banner("Current totals")
        sold  = sum(r.amount for r in rows if r.type == "Sale")
        spent = -sum(r.amount for r in rows if r.type == "Purchase")
        est   = -sum(r.amount for r in rows if r.estimated)
        say(f"  Received from sales:  {money(sold)}")
        say(f"  Total spent:          {money(spent)}")
        if est:
            say(f"    of which estimated: {money(est)}")
        say(f"  Net:                  {money(sold - spent)}\n")
        choice = menu(MAIN_MENU)
        if choice == 1:
            if not rows:
                say("  Nothing to save yet.")
            elif save_report(rows):
                spinner_stop()
                return
        elif choice in (2, 3, 4):
            result = (step_steam, step_market, step_other)[choice - 2]()
            if result == RESTART:
                data = collect()
                continue
            result = [] if result == SKIP else result
            if choice == 2:
                steam = result
                if MARKET_FILES:
                    market = load_market(MARKET_FILES)[0]          # re-check market dates against the new history
            elif choice == 3:
                market = result
            else:
                other = other + result
            data = [steam, market, other]
        elif choice == 5:
            raw = ask("  Price per key (0 to skip)", f"{KEY_PRICE[0]:.2f}")
            price = parse_price(raw)
            if raw.strip() in ("0", "0.0", "0.00"):
                say("  Skipped.")
            elif price is None:
                say("  Couldn't read that as a price. Example: 2.49")
            else:
                KEY_PRICE[0] = price
                other = [r for r in other if not r.estimated]
                extra = estimate_keys(steam + market + other, price)
                data = [steam, market, other + extra]
                say(f"  Added {len(extra)} estimated key(s)." if extra
                    else "  No missing keys detected - every purchased case already has a matching key purchase.")
        else:
            abort()


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        spinner_stop()
        print("\nCancelled.")
    if os.name == "nt" and sys.stdin and sys.stdin.isatty():
        input("\nPress Enter to close...")
