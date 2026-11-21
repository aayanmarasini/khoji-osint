# KHOJI OSINT
![KHOJI OSINT](khoji-osint.png)

Developer: **@aayanmarasini**

## ✨ Features

- 🔍 **Username search** on 2400+ sites: social media, tech, education, gaming and more, from all countries
- ✅ **Verified results**: only confirmed profiles are shown as Found
- 📇 **Profile details**: name, location, bio, email and number when the profile page shows them
- 📧 **Email leak check**
- 🔑 **Password leak check**
- 🌐 **Proxy support** with fast auto check (HTTP and SOCKS5)
- ⚡ **Multi-worker scanning**
- 🗂️ **Filters** by category or country

## 📦 Installation

Requires Python 3.

```
git clone https://github.com/YOUR-USERNAME/khoji-osint.git
cd khoji-osint
```

## ▶️ Usage

**Windows:** double click `run.bat`

**Kali / Linux / Mac:**
```
python3 khoji.py
```

### Menu

```
[1] Username Search
[2] Email Leak Check
[3] Password Leak Check
[4] Proxy
[0] Exit
```

### Command line

```
python khoji.py -u username
python khoji.py -u username --only social,tech
python khoji.py -u username -f proxies.txt
python khoji.py -u username -w 150
python khoji.py -e email@example.com
```

| Option | Description |
|--------|-------------|
| `-u` | Username to search |
| `-e` | Email to check |
| `-f` | Proxy file |
| `-p` | Single proxy |
| `-w` | Number of workers (max 300) |
| `--only` | Filter: `social`, `tech`, `education` or a country code (`in`, `jp`, `ru`...) |
| `-q` | Hide "Not found" lines |

## 🌐 Proxies

Add proxies to `proxies.txt`, one per line:

```
1.2.3.4:8080
http://user:pass@1.2.3.4:8080
socks5://1.2.3.4:1080
```

Results are saved in the `results` folder.

## ⚠️ Disclaimer

For educational use and for checking your own accounts. Use it responsibly.
