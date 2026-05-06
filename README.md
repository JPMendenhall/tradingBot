# Trading Bot — Public Dashboard

This repo hosts the **public read-only dashboard** for an autonomous Solana copy-trading bot. The bot runs on a private machine; this repo only contains the static HTML viewer plus periodic JSON snapshots of the bot's state.

**Live dashboard:** https://JPMendenhall.github.io/tradingBot/ *(after first push + GitHub Pages enabled)*

## What's in this repo

```
docs/
  index.html              ← public dashboard (static SPA)
  data/
    snapshot.json         ← refreshed every minute by publish_dashboard.py
    bankroll_history.json
publish_dashboard.py      ← writes snapshot.json + git pushes
build_static_dashboard.py ← regenerates docs/index.html from local dashboard.py
.gitignore                ← deny-by-default (only the 6 files above are tracked)
```

## What's NOT in this repo

- The bot itself (`degen_bot.py`, ~9000 lines)
- The Flask dashboard backend (`dashboard.py`)
- All strategy logic, state files, prompts, scheduled-task config
- `.env`, service-account credentials, anything secret

## How it works

```
[ local machine ]                           [ GitHub Pages ]
     bot.py
     dashboard.py (Flask, port 5555)
            ↓ (calls get_state())
     publish_dashboard.py  ──── git push ───→  docs/data/snapshot.json
                                                      ↑
                                           docs/index.html
                                          fetches snapshot.json
                                          every 10 seconds
                                                      ↑
                                              public viewer (anyone)
```

The static page is read-only — there's no backend, no API, no way for a visitor to do anything except watch.

## First-time deploy

```bash
# 1. Build the static dashboard from your local dashboard.py
python build_static_dashboard.py

# 2. Initial commit + push
git add -A
git commit -m "initial public dashboard"
git push -u origin main

# 3. In GitHub repo settings → Pages:
#    - Source: Deploy from a branch
#    - Branch: main / docs
#    - Save
#
# After ~1 min, the dashboard will be live at:
#    https://JPMendenhall.github.io/tradingBot/
```

## Live updates (run on bot machine)

```bash
# One-shot push:
python publish_dashboard.py

# Continuous push every 60 seconds:
python publish_dashboard.py --loop 60

# Test without pushing:
python publish_dashboard.py --dry-run
```

## Rebuilding the dashboard HTML

If you change `dashboard.py`'s HTML/JS in the live Flask app, regenerate the static copy:

```bash
python build_static_dashboard.py
git add docs/index.html
git commit -m "dashboard: <what changed>"
git push
```

## Safety notes

- **`.gitignore` is deny-by-default.** Adding a new file to git requires explicitly whitelisting it. This is a hard guard against accidentally pushing `.env` or credentials.
- **The publisher only stages `docs/data/`.** Never anything else.
- **No write endpoints in the public dashboard.** All POST handlers are defanged client-side.
- **Snapshot age banner.** A small banner at the top shows how stale the data is so visitors aren't fooled by the dashboard auto-refresh ticking on cached data.
