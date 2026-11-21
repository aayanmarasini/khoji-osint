# KHOJI OSINT
made by @aayanmarasini

Put a username, see where it exists. Also checks emails and passwords against known leaks.

## How to run
You only need Python 3. Nothing else to install.

Windows: double click `run.bat` (or `python khoji.py`).

Kali / Linux / Mac:
```
git clone https://github.com/YOUR-USERNAME/khoji-osint.git
cd khoji-osint
python3 khoji.py
```
or `./run.sh` (if it says permission denied: `chmod +x run.sh`). To update later, run `git pull` inside the folder.

## Menu
1. Username Search
2. Email Leak Check
3. Password Leak Check (you type the password and it shows on screen, then tells you if it leaked and how many times)
4. Proxy (load proxies.txt, add one by hand, or turn it off)
0. Exit

## Username search
It checks about 2400 sites: Instagram, Facebook, X, TikTok, Snapchat, YouTube, Telegram, Reddit, LinkedIn and so on, plus the big sites of a lot of countries, gaming, music, video, coding and education sites.

You can filter by group or country when it asks: `social`, `tech`, `education`, or a country code like `in`, `jp`, `ru`, `kr`, `cn`. Leave it empty to scan everything.

While it runs you see this:
```
[Found] GitHub  https://github.com/name
    name/loc : Some Name | City
    email    : name@mail.com
    number   : +977 98xxxxxxxx
[Not found] Facebook
```

### What counts as Found
A site is only shown as Found when all of this is true:
- the site says the profile exists
- it says the same thing again on a second request
- two random made up names on that same site both come back Not found
- if the site has no special "profile" marker, the username must also appear on the page
- the page is not a captcha, "checking your browser" or login wall (those are treated as blocked, never as found or not found)

If any of those fail it is NOT shown as Found. Email and number are only printed when they are written on the profile page itself. Nothing is guessed.

### Unverified (shown first, Found comes last)
Some sites block bots (Instagram, Facebook, X and TikTok do it a lot) or say "found" for every name. Those can't be confirmed, so they never go in Found. Blocked ones get a second try, slower, with a new fingerprint. Whatever is still left is printed at the end as a list with the reason, and saved in the results file, so you can open those few by hand.

### Workers
It checks many sites at the same time. Default is 40 workers (80 when a proxy is on). When you start a username search it asks how many you want, or use `-w 120`. Max 300. More workers = faster, but also more chance to get blocked without proxies.

### Instagram, Facebook, X, TikTok, Threads, Reddit, Snapchat, YouTube, Telegram, Pinterest, Twitch, VK, Tumblr, Medium, Spotify, GitHub, Steam
These need more than a plain page request, so each one has its own list of ways to ask (the official profile api, the link preview page, oembed). The tool tries them one after another until one gives a clear answer. For these sites "Not found" is only printed when the site really says the profile does not exist (a 404 or a "page not found" text). If the site just blocks you, it goes to Unverified instead, so you never get a wrong Not found.

### Not getting blocked
- every request has a new fingerprint (browser, language, headers, referer)
- only about one request per second to the same site
- on 403 / 429 it waits and tries again
- with proxies on, each request can use a different proxy

## Proxies
Add them to `proxies.txt`, one per line:
```
1.2.3.4:8080
http://user:pass@1.2.3.4:8080
socks5://1.2.3.4:1080
1.2.3.4:1080:user:pass
```
Loading is fast: dead ones are dropped in a second or two, up to 300 are tested at once. Press Ctrl+C while it checks and it stops right away and keeps the ones that already passed. Dead, slow and transparent proxies get dropped. If every proxy dies, the tool stops. It will not switch to your own IP by itself.

## Command line
```
python khoji.py -u name
python khoji.py -u name --only social,tech
python khoji.py -u name -f proxies.txt
python khoji.py -u name -f proxies.txt -w 150
python khoji.py -u name -q        (hide the Not found lines)
python khoji.py -e you@mail.com
```

Results are saved in the `results` folder. Use it on yourself, or when you have a real reason.
