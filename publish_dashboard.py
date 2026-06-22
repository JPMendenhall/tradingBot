"""
publish_dashboard.py — Push a fresh dashboard snapshot to GitHub Pages
=====================================================================

This is a READ-ONLY snapshot publisher. It runs on the same machine as the
bot, calls the same `get_state()` function the live Flask dashboard uses,
serializes the result to docs/data/snapshot.json, and git-pushes the
update so GitHub Pages serves a fresh copy.

NO secrets ever cross this boundary:
  • .env, *-credentials.json, etc. are blocked by .gitignore
  • This script only writes docs/data/snapshot.json — never touches anything else
  • The git push only includes files .gitignore explicitly whitelists

Run modes:
    python publish_dashboard.py             # one-shot: write + commit + push
    python publish_dashboard.py --loop 60   # forever loop, push every 60 sec
    python publish_dashboard.py --no-push   # write the file but don't git push
    python publish_dashboard.py --dry-run   # write the file, show what would
                                            #   be pushed, but don't actually push

Wire it up:
    On first deploy:  python build_static_dashboard.py   (one-time build of HTML)
                      git init && git add -A && git commit -m init
                      git remote add origin https://github.com/USER/REPO.git
                      git push -u origin main
                      Enable GitHub Pages on main, /docs in repo settings

    Then for live updates:
                      python publish_dashboard.py --loop 60
"""

import json
import os
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
DOCS_DIR = ROOT / "docs"
DATA_DIR = DOCS_DIR / "data"
SNAPSHOT_FILE = DATA_DIR / "snapshot.json"
BANKROLL_FILE = DATA_DIR / "bankroll_history.json"


# ────────────────────────────────────────────────────────────────────────────
# Snapshot building — call dashboard.py's get_state() to ensure we never
# diverge from the live API. If we built our own JSON shape we'd inevitably
# drift; reusing get_state() means the static page renders identically.
# ────────────────────────────────────────────────────────────────────────────


def build_snapshot() -> dict:
    """Import dashboard.get_state() and return its dict.

    Side-effect: this triggers the same auto_resolve_todos() pass the live
    dashboard runs, but throttled internally to once per 60s.
    """
    sys.path.insert(0, str(ROOT))
    # Suppress the Flask app startup; we only need the data builder
    import dashboard  # noqa: E402
    return dashboard.get_state()


def build_bankroll_history() -> dict:
    sys.path.insert(0, str(ROOT))
    import dashboard  # noqa: E402
    return dashboard.get_bankroll_history()


def write_snapshot() -> tuple[Path, int]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    snap = build_snapshot()
    snap["__publish_meta"] = {
        "published_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S EDT"),
        "publisher": "publish_dashboard.py",
    }
    tmp = SNAPSHOT_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(snap, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, SNAPSHOT_FILE)

    # Bankroll history is pulled on a separate endpoint in the live dashboard
    try:
        bh = build_bankroll_history()
        BANKROLL_FILE.write_text(json.dumps(bh, default=str), encoding="utf-8")
    except Exception as e:
        print(f"  bankroll history failed (non-fatal): {e}")

    return SNAPSHOT_FILE, SNAPSHOT_FILE.stat().st_size


# ────────────────────────────────────────────────────────────────────────────
# Git push — minimal, only touches docs/data/. Never adds or commits anything
# the .gitignore doesn't already whitelist.
# ────────────────────────────────────────────────────────────────────────────


_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=ROOT, check=check,
        capture_output=True, text=True,
        creationflags=_CREATE_NO_WINDOW,
    )


def git_push_snapshot(dry_run: bool = False) -> bool:
    """Stage, commit, and push docs/data/. Returns True on success."""
    # Stage only the public dashboard data — never anything else
    _run(["git", "add", "docs/data/snapshot.json"], check=False)
    if BANKROLL_FILE.exists():
        _run(["git", "add", "docs/data/bankroll_history.json"], check=False)

    # If nothing changed, skip
    diff = _run(["git", "diff", "--cached", "--name-only"], check=False)
    if not diff.stdout.strip():
        print("  nothing to commit (snapshot identical to last push)")
        return True

    # Show what's staged so the operator sees what would go public
    print(f"  staged: {diff.stdout.strip()}")

    if dry_run:
        print("  dry-run: NOT committing or pushing")
        return True

    msg = f"snapshot {datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}"
    commit = _run(["git", "commit", "-m", msg], check=False)
    if commit.returncode != 0:
        print(f"  commit failed: {commit.stderr}")
        return False

    push = _run(["git", "push", "origin", "HEAD"], check=False)
    if push.returncode != 0:
        print(f"  push failed: {push.stderr}")
        return False

    print(f"  pushed: {msg}")
    return True


# ────────────────────────────────────────────────────────────────────────────


def one_shot(no_push: bool = False, dry_run: bool = False):
    path, size = write_snapshot()
    print(f"[OK] wrote {path} ({size:,} bytes)")
    if no_push and not dry_run:
        return
    git_push_snapshot(dry_run=dry_run)


def loop(interval_sec: int):
    print(f"→ publish loop every {interval_sec}s. Ctrl+C to stop.")
    while True:
        try:
            one_shot()
        except Exception as e:
            print(f"  cycle error (non-fatal): {e}")
        time.sleep(interval_sec)


def main():
    args = sys.argv[1:]
    if "--loop" in args:
        idx = args.index("--loop")
        interval = int(args[idx + 1]) if idx + 1 < len(args) else 60
        loop(interval)
    elif "--dry-run" in args:
        one_shot(dry_run=True)
    elif "--no-push" in args:
        one_shot(no_push=True)
    else:
        one_shot()


if __name__ == "__main__":
    main()
