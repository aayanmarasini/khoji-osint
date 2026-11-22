#!/usr/bin/env python3
import argparse, base64, gzip, hashlib, http.client, json, os, queue, random, re, socket, ssl, string, sys, threading, time
from urllib.parse import urlparse, urljoin, quote, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
WORKERS = 0           # 0 = auto
TIMEOUT = 12
CHK_TIMEOUT = 5
PROXY_WORKERS = 300
MAXMS = 8000
HOST_GAP = 0.7        # seconds between hits on the same site, otherwise they ban me
TESTS = ("https://api.ipify.org", "https://icanhazip.com")
CTX = ssl.create_default_context()
IPRE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$|^[0-9a-fA-F:]{3,39}$")
DEV = "@aayanmarasini"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
os.system("")   # windows cmd needs this or colors look broken


def col(n):
    return "\033[38;5;%dm" % n


G, R, Y, D, X = col(84), col(203), col(221), col(244), "\033[0m"
C, W, B = col(51), col(255), "\033[1m"

ROWS = [" _  __ _   _   ___       _  ___ ",
        "| |/ /| | | | / _ \\     | ||_ _|",
        "| ' / | |_| || | | | _  | | | | ",
        "| . \\ |  _  || |_| || |_| | | | ",
        "|_|\\_\\|_| |_| \\___/  \\___/ |___|"]
SOFT404 = ["user not found", "does not exist", "page unavailable", "page not found",
           "profile not found", "no such user", "account not found", "user doesn't exist",
           "this account doesn't exist", "couldn't find this account", "nothing here",
           "isn't available", "is not available", "no longer available", "has been suspended"]
LANGS = ["en-US,en;q=0.9", "en-GB,en;q=0.9", "en-IN,en;q=0.9,hi;q=0.7", "es-ES,es;q=0.9,en;q=0.6",
         "fr-FR,fr;q=0.9,en;q=0.5", "de-DE,de;q=0.9,en;q=0.6", "pt-BR,pt;q=0.9,en;q=0.5", "en-CA,en;q=0.9,fr;q=0.5"]
REFS = ["", "", "", "https://www.google.com/", "https://www.bing.com/", "https://duckduckgo.com/", "https://t.co/"]
BAD = {"www", "home", "about", "user", "users", "profile", "login", "index", "share", "intent", "hashtag", "search"}



# threads: run fn on all items, results come out as they finish
# daemon threads so ctrl+c kills everything
def pmap(fn, items, workers):
    todo, out, stop = queue.Queue(), queue.Queue(), threading.Event()
    n = len(items)
    for it in items:
        todo.put(it)

    def work():
        while not stop.is_set():
            try:
                it = todo.get_nowait()
            except queue.Empty:
                return
            try:
                out.put(fn(it))
            except Exception:
                out.put(None)

    for _ in range(max(1, min(workers, n))):
        threading.Thread(target=work, daemon=True).start()
    try:
        for _ in range(n):
            while True:
                try:
                    r = out.get(timeout=0.2)
                    break
                except queue.Empty:
                    if stop.is_set():
                        return
            yield r
    finally:
        stop.set()


def worker_count():
    return WORKERS or (80 if POOL.used else 40)


def banner():
    print()
    for n, r in zip((46, 48, 49, 50, 51), ROWS):
        print("  " + col(n) + B + r + X)
    print(f"  {D}O S I N T   T O O L K I T{X}")
    print(f"  {D}developer: {X}{C}{DEV}{X}\n")


# ---------------- browser fingerprint, new one every request ----------------

def make_uas():
    o = []
    win, mac, lin = "Windows NT 10.0; Win64; x64", "Macintosh; Intel Mac OS X 10_15_7", "X11; Linux x86_64"
    for v in range(124, 146):
        for os_ in (win, mac, lin):
            o.append(("chrome", v, f"Mozilla/5.0 ({os_}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36"))
        o.append(("edge", v, f"Mozilla/5.0 ({win}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36 Edg/{v}.0.0.0"))
        o.append(("chrome", v, f"Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Mobile Safari/537.36"))
    for v in range(122, 146):
        o.append(("ff", v, f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{v}.0) Gecko/20100101 Firefox/{v}.0"))
        o.append(("ff", v, f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:{v}.0) Gecko/20100101 Firefox/{v}.0"))
        o.append(("ff", v, f"Mozilla/5.0 (X11; Linux x86_64; rv:{v}.0) Gecko/20100101 Firefox/{v}.0"))
    for v in ["16.6", "17.0", "17.2", "17.4", "17.6", "18.0", "18.2", "18.4"]:
        o.append(("safari", 0, f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/{v} Safari/605.1.15"))
        o.append(("safari", 0, f"Mozilla/5.0 (iPhone; CPU iPhone OS {v.replace('.', '_')} like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/{v} Mobile/15E148 Safari/604.1"))
    return o


UAS = make_uas()


def fp():
    kind, v, ua = random.choice(UAS)
    ref = random.choice(REFS)
    h = {"User-Agent": ua,
         "Accept": random.choice(["text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                                  "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"]),
         "Accept-Language": random.choice(LANGS),
         "Accept-Encoding": "gzip",
         "Upgrade-Insecure-Requests": "1",
         "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
         "Sec-Fetch-Site": "cross-site" if ref else "none", "Sec-Fetch-User": "?1"}
    if kind in ("chrome", "edge"):
        h["sec-ch-ua"] = f'"Chromium";v="{v}", "Not(A:Brand";v="24", "{"Microsoft Edge" if kind == "edge" else "Google Chrome"}";v="{v}"'
        h["sec-ch-ua-mobile"] = "?1" if "Mobile" in ua else "?0"
        h["sec-ch-ua-platform"] = '"Android"' if "Android" in ua else ('"Windows"' if "Windows" in ua else ('"macOS"' if "Mac" in ua else '"Linux"'))
    if kind == "ff" and random.random() < 0.5:
        h["DNT"] = "1"
    if ref:
        h["Referer"] = ref
    items = list(h.items())
    random.shuffle(items)                  # shuffle header order too
    ua_first = [i for i in items if i[0] == "User-Agent"]
    return dict(ua_first + [i for i in items if i[0] != "User-Agent"])


# small delay when hitting the same site again
_HL, _HN = threading.Lock(), {}


def host_wait(host):
    with _HL:
        now = time.time()
        t = max(now, _HN.get(host, 0))
        gap = 0.15 if POOL.used else HOST_GAP
        _HN[host] = t + gap + random.random() * 0.5
    if t > now:
        time.sleep(t - now)


# ---------------- network stuff (http proxy / socks5 / direct) ----------------

class ProxyError(Exception):
    pass


def recvn(s, n):
    b = b""
    while len(b) < n:
        c = s.recv(n - len(b))
        if not c:
            raise OSError("proxy closed connection")
        b += c
    return b


def socks5(px, host, port, timeout):
    s = socket.create_connection((px["host"], px["port"]), timeout)
    try:
        s.settimeout(timeout)
        user, pw = px.get("user", ""), px.get("pw", "")
        s.sendall(b"\x05\x02\x00\x02" if user else b"\x05\x01\x00")
        a = recvn(s, 2)
        if a[0] != 5:
            raise OSError("not a socks5 server")
        if a[1] == 2:
            ub, pb = user.encode(), pw.encode()
            s.sendall(b"\x01" + bytes([len(ub)]) + ub + bytes([len(pb)]) + pb)
            if recvn(s, 2)[1] != 0:
                raise OSError("socks auth failed")
        elif a[1] != 0:
            raise OSError("socks auth refused")
        hb = host.encode()
        s.sendall(b"\x05\x01\x00\x03" + bytes([len(hb)]) + hb + port.to_bytes(2, "big"))
        r = recvn(s, 4)
        if r[1] != 0:
            raise OSError("socks connect failed (%d)" % r[1])
        n = 16 if r[3] == 4 else 4
        if r[3] == 3:
            n = recvn(s, 1)[0]
        recvn(s, n + 2)
        return s
    except Exception:
        s.close()
        raise


def pauth(px):
    if px.get("user"):
        t = base64.b64encode(("%s:%s" % (px["user"], px.get("pw", ""))).encode()).decode()
        return {"Proxy-Authorization": "Basic " + t}
    return {}


class PConn(http.client.HTTPConnection):
    def __init__(self, u, px, timeout):
        self.px = px
        self.tls = u.scheme == "https"
        self.th = u.hostname
        self.tp = u.port or (443 if self.tls else 80)
        if px["type"] == "socks5":
            super().__init__(self.th, self.tp, timeout=timeout)
        else:
            super().__init__(px["host"], px["port"], timeout=timeout)
            if self.tls:
                self.set_tunnel(self.th, self.tp, pauth(px))

    def connect(self):
        try:
            if self.px["type"] == "socks5":
                self.sock = socks5(self.px, self.th, self.tp, self.timeout)
            else:
                super().connect()
        except Exception as e:
            raise ProxyError(str(e)[:80])
        if self.tls:
            self.sock = CTX.wrap_socket(self.sock, server_hostname=self.th)


def fetch(url, method="GET", headers=None, data=None, proxy=None, follow=True, timeout=TIMEOUT, cap=300000):
    hops = 0
    while True:
        u = urlparse(url)
        if u.scheme not in ("http", "https") or not u.hostname:
            raise ValueError("bad url")
        tls = u.scheme == "https"
        h = dict(headers or {})
        path = (u.path or "/") + ("?" + u.query if u.query else "")
        if proxy:
            conn = PConn(u, proxy, timeout)
            if proxy["type"] == "http" and not tls:
                path = url
                h.update(pauth(proxy))
        else:
            conn = (http.client.HTTPSConnection if tls else http.client.HTTPConnection)(u.hostname, u.port, timeout=timeout, **({"context": CTX} if tls else {}))
        try:
            conn.request(method, path, body=data, headers=h)
            r = conn.getresponse()
            code, body = r.status, r.read(cap)
            loc, enc = r.getheader("Location"), r.getheader("Content-Encoding", "")
        finally:
            conn.close()
        if follow and code in (301, 302, 303, 307, 308) and loc and hops < 6:
            url = urljoin(url, loc)
            hops += 1
            if code in (301, 302, 303):
                method, data = "GET", None
            continue
        if "gzip" in enc:
            try:
                body = gzip.decompress(body)
            except Exception:
                pass
        return code, body.decode("utf-8", "replace"), url


# ---------------- proxies ----------------

def parse_proxy(line):
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    if "://" not in s:
        p = s.split(":")
        if "@" not in s and len(p) == 4:        # ip:port:user:pass
            s = "%s:%s@%s:%s" % (p[2], p[3], p[0], p[1])
        s = "auto://" + s
    try:
        u = urlparse(s)
        if not u.hostname or not u.port:
            return None
        t = {"socks5h": "socks5", "socks": "socks5", "https": "http"}.get(u.scheme.lower(), u.scheme.lower())
    except ValueError:
        return None
    if t not in ("auto", "http", "socks5"):
        return None
    return {"type": t, "host": u.hostname, "port": u.port, "user": unquote(u.username or ""), "pw": unquote(u.password or ""), "id": "%s:%d" % (u.hostname, u.port)}


def real_ip():
    try:
        c, b, _ = fetch("https://api.ipify.org", headers=fp(), timeout=CHK_TIMEOUT)
        if c == 200 and IPRE.match(b.strip()):
            return b.strip()
    except Exception:
        pass
    return None


# quick hello to guess socks5 or http, dead ones get dropped here too
def sniff(px):
    try:
        s = socket.create_connection((px["host"], px["port"]), 3)
    except OSError:
        return None
    try:
        s.settimeout(2.5)
        s.sendall(b"\x05\x01\x00")
        a = s.recv(2)
        return "socks5" if a[:1] == b"\x05" else "http"
    except OSError:
        return "http"
    finally:
        s.close()


def check_one(px, me):
    t = sniff(px)
    if not t:
        return None
    if px["type"] != "auto":
        t = px["type"]
    p = dict(px, type=t)
    for test in TESTS:
        t0 = time.time()
        try:
            c, b, _ = fetch(test, headers=fp(), proxy=p, timeout=CHK_TIMEOUT)
            b = b.strip()
            if c == 200 and IPRE.match(b):
                p["ms"] = int((time.time() - t0) * 1000)
                p["ip"] = b
                p["transparent"] = bool(me and b == me)
                return p
        except Exception:
            continue
    return None


def check_all(pxs, maxms=MAXMS):
    me = real_ip()
    if not me:
        print(Y + "couldn't get your real ip, skipping the transparent-proxy check" + X)
    ok, done = [], 0
    try:
        for r in pmap(lambda p: check_one(p, me), pxs, PROXY_WORKERS):
            done += 1
            if r and not r["transparent"] and r["ms"] <= maxms:
                ok.append(r)
            if done % 5 == 0 or done == len(pxs):
                sys.stdout.write(f"\r{D}checking {done}/{len(pxs)}  alive {len(ok)}   (Ctrl+C = stop){X}  ")
                sys.stdout.flush()
    except KeyboardInterrupt:
        print("\n" + Y + "check stopped, using the ones that already passed" + X)
    print("\r" + " " * 70)
    ok.sort(key=lambda p: p["ms"])
    return ok


def load_file(path):
    out, seen = [], set()
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            p = parse_proxy(ln)
            if p and p["id"] not in seen:
                seen.add(p["id"])
                out.append(p)
    return out


def show(ok):
    for p in ok:
        print(f"{G}[+] {p['type']:<6} {p['host']}:{p['port']:<6} {p['ms']:>5}ms  exit {p['ip']}{X}")


class Pool:
    def __init__(self):
        self.l, self.fails, self.lock = [], {}, threading.Lock()
        self.used = False

    def on(self):
        return self.used

    def pick(self):
        if not self.used:
            return None
        with self.lock:
            if not self.l:
                raise ProxyError("no proxies left")
            return random.choice(self.l)

    def bad(self, p):
        with self.lock:
            n = self.fails.get(p["id"], 0) + 1
            self.fails[p["id"]] = n
            if n >= 3:
                self.l = [x for x in self.l if x["id"] != p["id"]]

    def good(self, p):
        self.fails[p["id"]] = 0

    def status(self):
        return f"PROXY ON ({len(self.l)} proxies)" if self.used else "PROXY OFF"


POOL = Pool()


def use_list(pxs, check=True, maxms=MAXMS):
    if not pxs:
        print(R + "no valid proxies in that list" + X)
        return
    print(f"{D}{len(pxs)} proxies loaded{X}")
    ok = check_all(pxs, maxms) if check else [dict(p, type="http" if p["type"] == "auto" else p["type"], ms=0, ip="?") for p in pxs]
    if check:
        show(ok)
    print(f"{G}{len(ok)} alive{X} / {len(pxs)}  (dead, slow and transparent ones dropped)")
    if ok:
        POOL.l = ok
        POOL.used = True
        POOL.fails = {}
        fn = os.path.join(HERE, "proxies_alive.txt")
        with open(fn, "w") as fh:
            for p in ok:
                au = f"{quote(p['user'])}:{quote(p['pw'])}@" if p.get("user") else ""
                fh.write(f"{p['type']}://{au}{p['host']}:{p['port']}\n")
        print(f"saved alive list: {fn}")


def proxy_menu(maxms):
    while True:
        print(f"\n{D}{POOL.status()}{X}")
        print(f"{G}[a]{X} load proxies from .txt (check + filter)\n{G}[b]{X} add one proxy\n{G}[c]{X} show current list\n{G}[d]{X} turn proxy off (clear all)\n{G}[0]{X} back")
        c = input(G + "proxy> " + X).strip().lower()
        if c == "a":
            f = input("file (Enter = proxies.txt): ").strip().strip('"') or os.path.join(HERE, "proxies.txt")
            try:
                use_list(load_file(f), True, maxms)
            except OSError as e:
                print(R + f"can't read file: {e}" + X)
        elif c == "b":
            p = parse_proxy(input("proxy (ip:port, http://.., socks5://user:pass@ip:port): "))
            if p:
                use_list([p], True, maxms)
            else:
                print(R + "bad proxy format" + X)
        elif c == "c":
            show([dict(p, ms=p.get("ms", 0), ip=p.get("ip", "?")) for p in POOL.l]) if POOL.l else print("empty")
        elif c == "d":
            POOL.l, POOL.used = [], False
        elif c == "0":
            return


# ---------------- sites ----------------

def load_sites(filt=""):
    s = json.load(open(os.path.join(HERE, "sites.json"), encoding="utf-8"))
    keys = {k.strip().lower() for k in filt.split(",") if k.strip()}
    keys = {"education" if k in ("edu", "study") else k for k in keys}
    if keys:
        s = [x for x in s if keys & {t.lower() for t in (x.get("tags") or [])} or x["name"].lower() in keys]
    random.shuffle(s)
    return s


# ---------------- checking one site ----------------

def arr(x):
    return [] if x is None else ([x] if isinstance(x, str) else list(x))


def strip(b):
    return re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", b, flags=re.S | re.I).lower()


WALLS = ["just a moment", "cf-browser-verification", "attention required! | cloudflare", "_pxcaptcha",
         "px-captcha", "access denied", "are you a robot", "verify you are human", "enable javascript and cookies",
         "request blocked", "unusual traffic", "datadome", "incapsula incident", "pardon our interruption",
         "checking your browser"]
LOGINWALL = ("login", "signin", "sign-in", "sign_in", "captcha", "challenge", "consent", "authwall", "checkpoint")


def walled(body):
    head = body[:6000].lower()
    return any(w in head for w in WALLS)


# if the string has {} the username goes in there, compared in lowercase
def has(strs, body, user):
    low = None
    for x in arr(strs):
        if "{}" in x:
            low = low or body.lower()
            if x.replace("{}", user).lower() in low:
                return True
        elif x in body:
            return True
    return False


def judge(s, status, body, user=""):
    t = s.get("type", "status_code")
    if status in (403, 429, 503) or status >= 520 or status == 0:
        return "error"
    if walled(body):
        return "error"
    f = s.get("found")
    if s.get("missCode") and status == s["missCode"]:
        ok = False
    elif t == "status_code":
        ok = status == s["code"] if s.get("code") else 200 <= status < 300
    elif t == "message":
        ok = not has(s.get("msg"), body, user) and status not in (404, 410)
    else:
        ok = 200 <= status < 300
    hit_ = False
    if ok and f:
        hit_ = has(f, body, user)
        ok = hit_
    if ok and not hit_ and any(x in strip(body)[:30000] for x in SOFT404):
        ok = False
    if ok:
        return "found"
    # strict sites: only say "not found" if the site really says it (404 or a miss text)
    # otherwise it's probably a block so leave it unverified
    if s.get("strict") and not (status in (404, 410) or (s.get("missCode") and status == s["missCode"]) or has(s.get("miss"), body, user)):
        return "unknown"
    return "notfound"


def meta(b, key):
    a = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]*content=["\']([^"\']*)' % key, b, re.I)
    if a:
        return a.group(1).strip()
    c = re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']%s["\']' % key, b, re.I)
    return c.group(1).strip() if c else ""


EMAIL = re.compile(r"[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9\-]{1,63}(?:\.[A-Za-z0-9\-]{1,63})*\.[A-Za-z]{2,10}")
EMAIL_JUNK = ("example.", "sentry", "wixpress", "w3.org", "schema.org", "yourdomain", "domain.com", "email.com",
              "noreply", "no-reply", "donotreply", "@2x", "godaddy", "your@", "name@", "user@", "test@")
PHONE_TAG = re.compile(r"""href=["']tel:([+\d][\d\s().\-%a-fA-F]{6,24})""", re.I)
PHONE_KEY = re.compile(r'"(?:telephone|phone|phoneNumber|phone_number|contact_phone)"\s*:\s*"(\+?[\d\s().\-]{7,22})"', re.I)
PHONE_TXT = re.compile(r"(?<![\w.+\-/])\+\d{1,3}[\s.\-]?\(?\d{1,4}\)?(?:[\s.\-]?\d{2,5}){2,4}(?![\w])")


def phones_in(b, text):
    out = []
    for rx, src in ((PHONE_TAG, b), (PHONE_KEY, b), (PHONE_TXT, text)):
        for m in rx.findall(src):
            m = unquote(m).strip()
            digits = re.sub(r"\D", "", m)
            if 8 <= len(digits) <= 15 and len(set(digits)) > 3 and m not in out:
                out.append(m)
    return out[:3]


def contacts(b, site_url):
    host = (urlparse(site_url).hostname or "").lower().replace("www.", "")
    root = ".".join(host.split(".")[-2:])
    raw = b[:250000]
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    mails = []
    for m in EMAIL.findall(raw):
        ml = m.lower()
        dom = ml.split("@")[1]
        if any(j in ml for j in EMAIL_JUNK) or ml.endswith((".png", ".jpg", ".gif", ".svg", ".webp", ".js", ".css")):
            continue
        if dom.endswith(root) and root:   # the site's own support mail, skip
            continue
        if ml not in mails:
            mails.append(ml)
    return mails[:3], phones_in(raw, text)


def grab(b, site_url):
    b = b[:250000]
    name = meta(b, "og:title")
    if not name:
        m = re.search(r"<title[^>]*>(.*?)</title>", b, re.S | re.I)
        name = m.group(1).strip() if m else ""
    bio = meta(b, "og:description") or meta(b, "description")
    m = re.search(r'"(?:addressLocality|location)"\s*:\s*"([^"]{2,60})"', b)
    mails, tels = contacts(b, site_url)
    return {"display_name": re.sub(r"\s+", " ", name)[:120], "bio": re.sub(r"\s+", " ", bio)[:300],
            "location": m.group(1) if m else "", "emails": mails, "phones": tels,
            "linked_urls": re.findall(r"https?://[^\s\"'<>)\]]+", bio)[:8]}


def hit_one(s, user, prof=False):
    r = {"name": s["name"], "url": s["url"].replace("{}", user), "state": "error"}
    try:
        if s.get("regex") and not re.match(s["regex"], user):
            r["state"] = "skipped"
            return r
        target = (s.get("probe") or s["url"]).replace("{}", user)
        data, method = None, s.get("method") or "GET"
        if method == "POST":
            pl = s.get("post") or ""
            data = (pl if isinstance(pl, str) else json.dumps(pl)).replace("{}", user).encode()
        host = urlparse(target).hostname or ""
        code, body, fin = 0, "", target
        for i in range(4):
            h = fp()   # new headers on every try
            if s.get("ua"):     # a few sites only show the profile to link preview bots
                h = {"User-Agent": s["ua"], "Accept": "text/html,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}
            h.update({k: v for k, v in (s.get("headers") or {}).items() if k.lower() != "user-agent"})
            px = POOL.pick()
            host_wait(host)
            try:
                code, body, fin = fetch(target, method, h, data, px, s.get("type") != "response_url")
                if px:
                    POOL.good(px)
            except ProxyError as e:
                POOL.bad(px)
                r["why"] = "proxy: " + str(e)
                continue
            except (OSError, http.client.HTTPException, ssl.SSLError) as e:
                r["why"] = str(e)[:60]       # timeout or reset, just try again
                code = 0
                time.sleep(0.5 + i)
                continue
            if code in (403, 429, 503) or code >= 520 or walled(body):   # got blocked, wait and retry
                time.sleep(1.5 * (i + 1) + random.random())
                continue
            break
        else:
            if not code:
                return r
        if fin != target:
            p0, p1 = urlparse(target).path.lower(), urlparse(fin).path.lower()
            if any(w in p1 for w in LOGINWALL) and not any(w in p0 for w in LOGINWALL):
                r["state"] = "unknown"
                r["why"] = "redirected to a login / captcha page"
                return r
        r["state"] = judge(s, code, body, user)
        r["http"] = code
        if r["state"] == "unknown":
            r["why"] = "blocked"
        if r["state"] == "found":
            # no proof string in the config so the name must show up on the page
            if s.get("type", "status_code") == "status_code" and not arr(s.get("found")):
                if user.lower() not in body.lower() and user.lower() not in strip(body):
                    r["state"] = "unknown"
                    r["why"] = "profile page does not show the name"
            if r["state"] == "found" and prof:
                r["profile"] = grab(body, r["url"])
    except ProxyError as e:
        r["why"] = str(e)
    except Exception as e:
        r["why"] = str(e)[:60]
    return r


# some sites have a few different ways to ask ("tries"), go through them one by one
# until we get a clear found / not found
def hit(s, user, prof=False):
    tries = s.get("tries")
    if not tries:
        return hit_one(s, user, prof)
    base = {k: v for k, v in s.items() if k != "tries"}
    last = None
    for t in tries:
        last = hit_one(dict(base, **t), user, prof)
        if last["state"] in ("found", "notfound", "skipped"):
            return last
    return last


def rand_name(shape):
    al = [string.ascii_lowercase, string.ascii_lowercase + string.digits, string.ascii_lowercase, string.ascii_lowercase + string.digits][shape % 4]
    n = [10, 11, 7, 14][shape % 4]
    return "".join(random.choice(al) for _ in range(n))


def ctrl_name(s):
    rx = s.get("regex")
    for k in range(12):
        u = rand_name(k)
        if not rx or re.match(rx, u):
            return u
    return None


# a "found" only counts if it comes back found a 2nd time
# and 2 random fake names on the same site both come back not found
def verified_hit(s, user, prof=True):
    r = hit(s, user, prof)
    if r["state"] != "found":
        return r
    again = hit(s, user)
    if again["state"] != "found":
        r["state"] = "unknown" if again["state"] == "error" else "notfound"
        r["why"] = "blocked" if again["state"] == "error" else "changed answer"
        r.pop("profile", None)
        return r
    for k in range(2):
        cu = ctrl_name(s)
        c = hit(s, cu) if cu else None
        if not c or c["state"] != "notfound":
            r["state"] = "unknown"
            r["why"] = "blocked" if (c and c["state"] == "error") else "says found for any name"
            r.pop("profile", None)
            break
    return r


# ---------------- scan + live output ----------------

def say(msg):
    sys.stdout.write("\r\033[2K" + msg + "\n")


def tag(state):
    return {"found": f"{G}{B}[Found]{X}", "notfound": f"{R}[Not found]{X}", "unknown": f"{Y}[Unverified]{X}"}.get(state, "")


def bar(st, done, n):
    return (f"  {G}Found ({st['found']}){X}  {R}Not found ({st['notfound']}){X}  {Y}Unverified ({st['unknown']}){X}"
            f"  {D}Errors ({st['error']})  {done}/{n}{X}")


def print_profile(r):
    p = r.get("profile") or {}
    bits = [b for b in (p.get("display_name"), p.get("location")) if b]
    if bits:
        say(f"{D}      name/loc : " + " | ".join(bits)[:140] + X)
    if p.get("bio"):
        say(f"{D}      bio      : {p['bio'][:140]}{X}")
    if p.get("emails"):
        say(f"{G}      email    : {', '.join(p['emails'])}{X}")
    if p.get("phones"):
        say(f"{G}      number   : {', '.join(p['phones'])}{X}")


def one_pass(user, sites, st, res, left, show_all, prof, workers, done0, total):
    done = done0
    try:
        for r in pmap(lambda x: verified_hit(x, user, prof), sites, workers):
            done += 1
            if r is None:
                st["error"] += 1
                continue
            st[r["state"]] += 1
            nm = r["name"]
            if r["state"] == "found":
                res.append(r)
                say(f"  {tag('found')} {W}{nm}{X}  {C}{r['url']}{X}")
                print_profile(r)
            elif r["state"] == "notfound":
                if show_all:
                    say(f"  {tag('notfound')} {W}{nm}{X}")
            elif r["state"] in ("unknown", "error"):
                left.append(r)
            sys.stdout.write("\r\033[2K" + bar(st, done, total))
            sys.stdout.flush()
    except KeyboardInterrupt:
        say(Y + "  stopped" + X)
        raise
    return done


def scan(user, sites, show_all=True, prof=True):
    n = len(sites)
    st = {"found": 0, "notfound": 0, "unknown": 0, "error": 0, "skipped": 0}
    res, left = [], []
    by = {s["name"]: s for s in sites}
    try:
        one_pass(user, sites, st, res, left, show_all, prof, worker_count(), 0, n)
        # 2nd try for the blocked / timed out ones, slower and with fewer workers
        retry = [by[r["name"]] for r in left if r.get("why") == "blocked" or r["state"] == "error"]
        if retry:
            keep = [r for r in left if by[r["name"]] not in retry]
            for r in left:
                if by[r["name"]] in retry:
                    st[r["state"]] -= 1
            left[:] = keep
            say(f"{D}  retrying {len(retry)} blocked / slow sites, slower this time...{X}")
            global HOST_GAP
            old, HOST_GAP = HOST_GAP, 2.5
            try:
                one_pass(user, retry, st, res, left, show_all, prof, max(10, worker_count() // 4), n - len(retry), n)
            finally:
                HOST_GAP = old
    except KeyboardInterrupt:
        pass
    sys.stdout.write("\r\033[2K")
    if POOL.on() and not POOL.l:
        say(R + "  all proxies died, nothing was sent from your own ip. reload them in [4]." + X)
    return res, st, left


def summary(st):
    print(f"\n  {D}{'-' * 56}{X}")
    print(f"  {G}{B}Found ({st['found']}){X}   {R}Not found ({st['notfound']}){X}   {Y}Unverified ({st['unknown']}){X}   {D}Errors ({st['error']}){X}")
    print(f"  {D}{'-' * 56}{X}")


def run_user(user, sites, show_all, recursive):
    if not re.match(r"^[\w.\-]{1,64}$", user):
        print(R + "  username can only have letters, numbers, _ . -" + X)
        return
    if POOL.used:
        print(f"  {D}{POOL.status()}{X}")
    else:
        print(f"  {D}no proxy on. for good results use a proxy (menu [4]), big sites block normal connections.{X}")
    allf, unv, seen, cur, extra = [], [], {user.lower()}, [user], 0
    ps = pats(sites) if recursive else []
    for level in range(3):
        nxt = []
        for u in cur:
            print(f"\n  {C}{B}> {u}{X}" + (f"  {D}(level {level}){X}" if level else "") + "\n")
            f, st, left = scan(u, sites, show_all, True)
            summary(st)
            allf += [(u, x) for x in f]
            unv += [(u, x) for x in left]
            if ps and level < 2:
                for x in f:
                    for l in (x.get("profile") or {}).get("linked_urls", []):
                        c = from_link(l, ps)
                        if c and c.lower() not in seen and extra < 3:
                            seen.add(c.lower())
                            nxt.append(c)
                            extra += 1
        cur = nxt
        if not cur:
            break
    if unv:
        print(f"\n  {Y}{B}Unverified sites ({len(unv)}){X}  {D}not counted as found, could not be confirmed{X}")
        for u, x in unv:
            why = (x.get("why") or "no answer / timeout") + (f"  (http {x['http']})" if x.get("http") else "")
            print(f"  {Y}?{X} {W}{x['name']:<24}{X} {D}{why}{X}")
        if not POOL.used:
            print(f"\n  {C}tip:{X} you are scanning without a proxy, so many sites block you. Turn on a proxy in menu [4] and scan again for better results.")
    if allf:
        print(f"\n  {G}{B}Profiles found{X}")
        for u, x in allf:
            print(f"  {G}+{X} {W}{x['name']:<24}{X} {C}{x['url']}{X}")
        mails = sorted({m for _, x in allf for m in (x.get("profile") or {}).get("emails", [])})
        tels = sorted({m for _, x in allf for m in (x.get("profile") or {}).get("phones", [])})
        if mails or tels:
            print(f"\n  {G}{B}Contact info seen on those profiles{X}")
            for m in mails:
                print(f"  {G}email :{X} {m}")
            for m in tels:
                print(f"  {G}number:{X} {m}")
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    fn = os.path.join(HERE, "results", f"{user}_{int(time.time())}.txt")
    with open(fn, "w", encoding="utf-8") as fh:
        for u, x in allf:
            fh.write(f"{x['name']}  {x['url']}\n")
            p = x.get("profile") or {}
            for k in ("display_name", "location", "bio"):
                if p.get(k):
                    fh.write(f"    {k}: {p[k]}\n")
            for m in p.get("emails", []):
                fh.write(f"    email: {m}\n")
            for m in p.get("phones", []):
                fh.write(f"    number: {m}\n")
        if unv:
            fh.write("\nunverified:\n")
            for u, x in unv:
                fh.write(f"  {x['name']}  {x['url']}  ({x.get('why') or 'no answer'})\n")
    print(f"\n  {D}saved: {fn}{X}")


def pats(sites):
    o = []
    for s in sites:
        p = s["url"].split("{}")
        if len(p) == 2:
            o.append(re.compile("^" + re.escape(p[0]) + r"([A-Za-z0-9_.\-]{2,40})" + re.escape(p[1]) + r"(?:[/?#].*)?$", re.I))
    return o


def from_link(l, ps):
    alt = l.replace("://www.", "://") if "://www." in l else l.replace("://", "://www.")
    for x in (l, alt):
        for r in ps:
            m = r.match(x)
            if m and m.group(1).lower() not in BAD:
                return m.group(1)
    return None


# ---------------- email leak / password leak ----------------

def lget(url, headers=None, tries=3):
    wait = 1
    for i in range(tries + 1):
        try:
            code, body, _ = fetch(url, headers=headers or fp(), proxy=POOL.pick(), timeout=25)
        except Exception as e:
            return 0, str(e)
        if code == 429 and i < tries:
            time.sleep(wait)
            wait *= 2
            continue
        return code, body


def leak_local(email, key):
    e = quote(email, safe="")
    if key:
        code, txt = lget(f"https://plus-api.xposedornot.com/v3/check-email/{e}?detailed=true", {"x-api-key": key, "User-Agent": "khoji-osint"})
    else:
        code, txt = lget(f"https://api.xposedornot.com/v1/check-email/{e}")
    mode = "plus" if key else "free"
    if code == 404:
        return {"breaches": [], "details": [], "risk": 0, "mode": mode}
    if code in (401, 403):
        return {"error": f"API key rejected ({code})"}
    if code != 200:
        return {"error": f"upstream returned {code}"}
    d = json.loads(txt)
    raw, names, det = d.get("breaches") or [], [], []
    if raw and isinstance(raw[0], list):
        names = [str(x) for x in raw[0]]
    else:
        for b in raw:
            if isinstance(b, dict):
                det.append(b)
                names.append(str(b.get("breach_id") or b.get("domain") or "?"))
            else:
                names.append(str(b))
    risk = min(100, 10 + len(names) * 6) if names else 0
    for b in det:
        if str(b.get("password_risk", "")).lower() in ("plaintext", "easytocrack", "unknown"):
            risk = min(100, risk + 10)
    return {"breaches": names, "details": det, "risk": risk, "mode": mode}


def leak(email):
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        print(R + "  that is not an email" + X)
        return
    key = os.environ.get("XON_API_KEY") or input("  XposedOrNot Plus API key (Enter = free mode): ").strip()
    if POOL.used:
        print(f"  {D}{POOL.status()}{X}")
    try:
        d = leak_local(email, key)
    except Exception as e:
        print(R + f"  failed: {e}" + X)
        return
    if d.get("error"):
        print(R + f"  {d['error']}" + X)
        return
    names = d["breaches"]
    if not names:
        print(f"\n  {G}{B}[Clean]{X} not found in any known breach")
        return
    rk = d["risk"]
    c = R if rk > 60 else Y if rk > 30 else G
    print(f"\n  {R}{B}[Breached]{X} found in {len(names)} breach(es)")
    if d.get("details"):
        for b in d["details"]:
            print(f"  {R}-{X} {b.get('breach_id')} ({b.get('domain')})  data: {b.get('exposed_data')}  pwd risk: {b.get('password_risk')}")
    else:
        print(f"  {W}" + ", ".join(names) + X)
        print(f"  {D}free mode = names only, a Plus API key gives details{X}")
    print(f"\n  risk {c}{rk}/100  [{'#' * (rk // 5)}{'.' * (20 - rk // 5)}]{X}")
    print(f"  {D}change those passwords, turn on 2FA, never reuse passwords{X}")


def pwd():
    print(f"  {D}type a password to check (it is shown on screen). Enter on empty line = back.{X}")
    print(f"  {D}only the first 5 chars of its SHA-1 hash are sent, the password itself never leaves your pc.{X}")
    while True:
        p = input("\n  password: ")
        if not p:
            return
        h = hashlib.sha1(p.encode()).hexdigest().upper()
        try:
            code, txt = lget("https://api.pwnedpasswords.com/range/" + h[:5], {"Add-Padding": "true", "User-Agent": "khoji-osint"})
        except Exception as e:
            print(R + f"  failed: {e}" + X)
            continue
        if code != 200:
            print(R + f"  error {code}: {str(txt)[:80]}" + X)
            continue
        n = 0
        for line in txt.splitlines():
            a, _, c = line.partition(":")
            if a.strip() == h[5:]:
                n = int(c)
        print(f"  {D}password : {X}{W}{B}{p}{X}")
        print(f"  {D}sha1     : {h}{X}")
        if n:
            print(f"  {R}{B}[Leaked]{X} seen {n:,} times in breach dumps, don't use it")
        else:
            print(f"  {G}{B}[Not leaked]{X} not in the known dumps")


def main():
    ap = argparse.ArgumentParser(description="KHOJI OSINT")
    ap.add_argument("-u", "--user")
    ap.add_argument("-e", "--email")
    ap.add_argument("-p", "--proxy", help="host:port, http://.., socks5://user:pass@host:port")
    ap.add_argument("-f", "--proxy-file", help="txt file, one proxy per line")
    ap.add_argument("--check-only", action="store_true", help="only test the proxies")
    ap.add_argument("--no-check", action="store_true")
    ap.add_argument("--ms", type=int, default=MAXMS)
    ap.add_argument("-r", "--recursive", action="store_true")
    ap.add_argument("-q", "--quiet", action="store_true", help="do not print every not found line")
    ap.add_argument("-w", "--workers", type=int, default=0, help="how many sites to check at the same time")
    ap.add_argument("--only", default="", help="category / country filter, e.g. social,tech,education,in,jp")
    a = ap.parse_args()
    global WORKERS
    WORKERS = max(0, min(a.workers, 300))
    banner()

    pxs = []
    if a.proxy:
        p = parse_proxy(a.proxy)
        if not p:
            print(R + "  bad proxy format" + X)
            return
        pxs.append(p)
    if a.proxy_file:
        try:
            pxs += load_file(a.proxy_file)
        except OSError as e:
            print(R + f"  can't read file: {e}" + X)
            return
    if pxs:
        use_list(pxs, not a.no_check, a.ms)
        if not POOL.used and (a.user or a.email or a.check_only):
            print(R + "  no working proxy, stopping (won't fall back to your real ip)" + X)
            return
    if a.check_only:
        return
    if a.user:
        return run_user(a.user.lstrip("@"), load_sites(a.only), not a.quiet, a.recursive)
    if a.email:
        return leak(a.email)
    while True:
        print(f"\n  {D}{POOL.status()}{X}")
        print(f"  {G}[1]{X} Username Search      {D}instagram, facebook, x, tiktok, snapchat + tech + education + all countries{X}")
        print(f"  {G}[2]{X} Email Leak Check")
        print(f"  {G}[3]{X} Password Leak Check")
        print(f"  {G}[4]{X} Proxy")
        print(f"  {G}[0]{X} Exit")
        c = input(f"\n  {G}khoji>{X} ").strip()
        if c == "1":
            u = input("  username: ").strip().lstrip("@")
            f = input(f"  {D}only some groups? social, tech, education or country code like in,jp,ru,kr,cn  (Enter = everything){X}\n  filter: ").strip()
            w = input(f"  {D}workers = how many sites at the same time (Enter = auto: {worker_count()}, max 300){X} ").strip()
            if w.isdigit():
                WORKERS = max(1, min(int(w), 300))
            rec = input(f"  {D}follow links found in bios? y/N{X} ").strip().lower() == "y"
            sites = load_sites(f)
            if not sites:
                print(R + "  no sites match that filter" + X)
                continue
            run_user(u, sites, not a.quiet, rec)
        elif c == "2":
            leak(input("  email: ").strip())
        elif c == "3":
            pwd()
        elif c == "4":
            proxy_menu(a.ms)
        elif c == "0":
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
