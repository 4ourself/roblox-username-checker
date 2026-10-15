import asyncio
import os
import random
import re
import sys
import time
from math import gcd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AVAILABLE = os.path.join(ROOT, "available.txt")

API = "https://auth.roblox.com/v2/usernames/validate"
BIRTHDAY = "2000-01-01T00:00:00.000Z"
CONCURRENCY = 20
LIMIT = 1.0
RETRIES = 2
RATELIMIT_INTERVAL = 2.0

LETTERS = "abcdefghijklmnopqrstuvwxyz"
ALNUM = LETTERS + "0123456789"

DEFAULT_LENGTHS = (4,)
DEFAULT_ALPHABET = LETTERS
EXAMPLES = "3L   4L   5L   3C   4C   5C   3-5C"
PROMPT = "(!) type of username (default 4L): "

LOGO = r"""   ___          _  __ 
  /   |        | |/ _|
 / /| |___  ___| | |_ 
/ /_| / __|/  *\ |*  |
\___  \__ \  __/ | |  
    |_/___/\___|_|_|  """

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json;charset=UTF-8",
    "origin": "https://www.roblox.com",
    "referer": "https://www.roblox.com/",
    "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"),
}

REQUIRED = ("aiohttp", "colorama")


def missing():
    import importlib.util
    return [name for name in REQUIRED if importlib.util.find_spec(name) is None]


def setup():
    packages = missing()
    if not packages:
        return

    if os.environ.get("_ROBLOX_CHECKER_SETUP") == "1":
        print("  libraries could not be installed: " + ", ".join(packages))
        print("  install them manually:  py -m pip install " + " ".join(packages))
        sys.exit(1)

    os.environ["_ROBLOX_CHECKER_SETUP"] = "1"
    import subprocess

    print("  installing libraries: " + ", ".join(packages) + " ...")
    for extra in ([], ["--user"]):
        try:
            subprocess.call([sys.executable, "-m", "pip", "install",
                             "--disable-pip-version-check", "-q", *extra, *packages])
        except Exception:
            pass
        if not missing():
            break

    if missing():
        print("  libraries could not be installed: " + ", ".join(missing()))
        print("  install them manually:  py -m pip install aiohttp colorama")
        sys.exit(1)

    os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)] + sys.argv[1:])


setup()

import aiohttp
from colorama import Fore, Style, init as colorama_init

try:
    from colorama import just_fix_windows_console as fix_windows
    fix_windows()
except Exception:
    colorama_init(autoreset=False)

BLUE = Fore.LIGHTBLUE_EX
GREEN = Fore.LIGHTGREEN_EX
RED = Fore.LIGHTRED_EX
YEL = Fore.LIGHTYELLOW_EX
DIM = Fore.LIGHTBLACK_EX
RST = Style.RESET_ALL


def clear():
    if os.name == "nt":
        os.system("cls")
    else:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def banner():
    clear()
    print(BLUE + LOGO + RST)
    print()


def note_ratelimit(state, attempt):
    state["ratelimit"] += 1
    now = time.time()
    if now - state["ratelimit_at"] < RATELIMIT_INTERVAL:
        return
    state["ratelimit_at"] = now
    print(f"{YEL}[ratelimit]{RST} {DIM}too many requests - waiting {int(1.0 + attempt)}s{RST}",
          flush=True)


def parse_type(text):
    text = text.strip().upper().replace(" ", "")
    lengths, alphabet = DEFAULT_LENGTHS, DEFAULT_ALPHABET

    if text:
        if text in ("L", "C"):
            text = "4" + text
        match = re.fullmatch(r"(\d+(?:[-,]\d+)*)([LC]?)", text)
        if not match:
            return None

        body, suffix = match.group(1), match.group(2)
        if "-" in body:
            if not re.fullmatch(r"\d+-\d+", body):
                return None
            start, end = (int(value) for value in body.split("-"))
            lengths = list(range(min(start, end), max(start, end) + 1))
        else:
            lengths = [int(value) for value in body.split(",")]

        lengths = sorted(set(lengths))
        if not lengths or lengths[0] < 3 or lengths[-1] > 20:
            return None
        alphabet = ALNUM if suffix == "C" else LETTERS

    kind = "characters (a-z 0-9)" if alphabet == ALNUM else "letters (a-z)"
    if len(lengths) > 1 and lengths == list(range(lengths[0], lengths[-1] + 1)):
        number = f"{lengths[0]}-{lengths[-1]}"
    else:
        number = ", ".join(str(length) for length in lengths)
    return lengths, alphabet, f"{number} {kind}"


def ask_type():
    banner()
    print(f"   {DIM}{EXAMPLES}{RST}")
    print()
    print(f"   {YEL}(!){RST} type of username {DIM}(default 4L){RST}: ", end="")

    while True:
        try:
            text = input()
        except (EOFError, KeyboardInterrupt):
            print()
            return None

        chosen = parse_type(text)
        if chosen:
            return chosen
        print(f"   {DIM}not a type i know - try 3L, 5C or 3-5C{RST}")
        print(f"   {YEL}(!){RST} type of username {DIM}(default 4L){RST}: ", end="")


def stream(lengths, alphabet):
    base = len(alphabet)
    blocks = [(length, base ** length) for length in sorted(lengths)]
    total = sum(size for _length, size in blocks)

    def name_of(index):
        for length, size in blocks:
            if index < size:
                chars = []
                for _ in range(length):
                    index, rest = divmod(index, base)
                    chars.append(alphabet[rest])
                return "".join(reversed(chars))
            index -= size
        return None

    step = total
    while gcd(step, total) != 1:
        step = random.randrange(1, total)

    index = random.randrange(total)
    for _ in range(total):
        name = name_of(index)
        if name is not None:
            yield name
        index = (index + step) % total


async def token(session):
    payload = {"username": "username", "birthday": BIRTHDAY, "context": "Signup"}
    try:
        async with session.post(API, json=payload,
                                timeout=aiohttp.ClientTimeout(total=10)) as response:
            value = response.headers.get("x-csrf-token")
            if value:
                session.headers["x-csrf-token"] = value
                return True
    except Exception:
        pass
    return False


async def check(session, username, state):
    payload = {"username": username, "birthday": BIRTHDAY, "context": "Signup"}

    for attempt in range(RETRIES + 1):
        try:
            async with session.post(API, json=payload,
                                    timeout=aiohttp.ClientTimeout(total=LIMIT)) as response:
                if response.status == 403:
                    value = response.headers.get("x-csrf-token")
                    if value:
                        session.headers["x-csrf-token"] = value
                    continue
                if response.status == 429:
                    note_ratelimit(state, attempt)
                    await asyncio.sleep(1.0 + attempt)
                    continue
                if response.status != 200:
                    await asyncio.sleep(0.2)
                    continue

                code = (await response.json(content_type=None)).get("code")
                if code == 0:
                    return "available"
                if code == 1:
                    return "taken"
                if code in (2, 3, 4, 5):
                    return "invalid"
                return "error"
        except (asyncio.TimeoutError, aiohttp.ClientError, ValueError):
            await asyncio.sleep(0.2)

    return "error"


async def worker(session, queue, state, out_file):
    while True:
        username = await queue.get()
        try:
            if username is None:
                return
            status = await check(session, username, state)
        finally:
            queue.task_done()

        state["checked"] += 1
        if status == "taken":
            state["taken"] += 1
            print(f"{RED}[taken]{RST} {username}", flush=True)
        elif status == "available":
            state["available"] += 1
            print(f"{GREEN}[available]{RST} {username}", flush=True)
            out_file.write(username + "\n")
            out_file.flush()
        elif status == "invalid":
            state["invalid"] += 1
        else:
            state["error"] += 1
            print(f"{DIM}[error] {username}{RST}", flush=True)


async def feeder(queue, names):
    for username in names:
        await queue.put(username)
    for _ in range(CONCURRENCY):
        await queue.put(None)


async def run(chosen, state):
    lengths, alphabet, label = chosen
    queue = asyncio.Queue(maxsize=CONCURRENCY * 4)
    connector = aiohttp.TCPConnector(limit=CONCURRENCY, ttl_dns_cache=300)
    out_file = open(AVAILABLE, "a", encoding="utf-8")

    try:
        async with aiohttp.ClientSession(headers=HEADERS, connector=connector) as session:
            print(f"   {DIM}connecting to roblox ...{RST}", flush=True)
            if not await token(session):
                state["failed"] = True
                return

            banner()
            print(f"   {DIM}{label}  |  threads {CONCURRENCY}  |  limit {int(LIMIT)}s{RST}")
            print()

            workers = [asyncio.create_task(worker(session, queue, state, out_file))
                       for _ in range(CONCURRENCY)]
            feed = asyncio.create_task(feeder(queue, stream(lengths, alphabet)))
            await asyncio.gather(feed, *workers)
    finally:
        out_file.close()


def summary(state, started):
    elapsed = max(time.time() - started, 0.001)
    print()
    print(f"   {BLUE}done{RST}  -  checked {state['checked']}  |  "
          f"{RED}taken {state['taken']}{RST}  |  {GREEN}available {state['available']}{RST}")
    if state["invalid"] or state["error"]:
        print(f"   {DIM}skipped {state['invalid'] + state['error']} "
              f"(filtered or unreachable){RST}")
    if state["ratelimit"]:
        print(f"   {YEL}rate limited {state['ratelimit']} times{RST}")
    print(f"   {DIM}{round(elapsed, 1)}s  |  {round(state['checked'] / elapsed, 1)}/s  "
          f"|  saved to available.txt{RST}")


def main():
    chosen = ask_type()
    if chosen is None:
        banner()
        return 0

    state = {"checked": 0, "taken": 0, "available": 0, "invalid": 0,
             "error": 0, "failed": False, "ratelimit": 0, "ratelimit_at": 0.0}
    started = time.time()

    try:
        asyncio.run(run(chosen, state))
    except KeyboardInterrupt:
        pass

    if state["failed"]:
        banner()
        print(f"   {RED}roblox is not reachable - check your internet connection{RST}\n")
        return 1

    summary(state, started)
    return 0


if __name__ == "__main__":
    sys.exit(main())
