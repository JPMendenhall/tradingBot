"""
build_static_dashboard.py — Generate docs/index.html for GitHub Pages
======================================================================

The live dashboard (dashboard.py) is a Flask SPA that fetches /api/state.
The public static dashboard is the SAME HTML/JS, but with the fetch URL
rewritten to `data/snapshot.json` and POST endpoints (which won't work
on a static host) defanged so they no-op gracefully.

Run this whenever you change DASHBOARD_HTML in dashboard.py:

    python build_static_dashboard.py

It writes:
    docs/index.html   — the public-facing static page

Then run publish_dashboard.py to refresh docs/data/snapshot.json and push.
"""

import re
import os
from pathlib import Path

DASHBOARD_PY = Path(__file__).parent / "dashboard.py"
DOCS_DIR = Path(__file__).parent / "docs"
OUTPUT_HTML = DOCS_DIR / "index.html"


def extract_dashboard_html() -> str:
    """Read dashboard.py and pull out the DASHBOARD_HTML triple-quoted string.

    The string starts with the literal `DASHBOARD_HTML = r` followed by a
    triple-quote, then `<!DOCTYPE html>`, and runs through the closing
    `</body></html>` plus its own triple-quote terminator.
    """
    text = DASHBOARD_PY.read_text(encoding="utf-8")
    # Find the start
    m = re.search(r'DASHBOARD_HTML\s*=\s*r"""', text)
    if not m:
        raise RuntimeError("Could not find DASHBOARD_HTML in dashboard.py")
    start = m.end()
    # Find the closing """ on its own line OR at the very end of the HTML
    # (the actual close is `</body></html>"""`).
    end = text.find('</body></html>"""', start)
    if end < 0:
        raise RuntimeError("Could not find HTML close marker")
    html = text[start:end + len("</body></html>")]
    return html


def rewrite_for_static(html: str) -> str:
    """Surgically modify the HTML so it works on a static host:

    1. Replace fetch('/api/state') with fetch('data/snapshot.json')
    2. Replace fetch('/api/bankroll_history') with fetch('data/bankroll_history.json')
    3. Defang POST endpoints so the read-only public viewer doesn't accidentally
       try to POST (which would 404 silently and confuse users).
    4. Add a small banner explaining this is a read-only public mirror.
    """
    # 1. Main API endpoint — the SPA's heartbeat fetch
    html = html.replace("fetch('/api/state')", "fetch('data/snapshot.json?cb='+Date.now())")
    html = html.replace('fetch("/api/state")', 'fetch("data/snapshot.json?cb="+Date.now())')

    # 2. Bankroll history endpoint
    html = html.replace("fetch('/api/bankroll_history')", "fetch('data/bankroll_history.json?cb='+Date.now())")
    html = html.replace('fetch("/api/bankroll_history")', 'fetch("data/bankroll_history.json?cb="+Date.now())')

    # 3. Defang POST endpoints — the public site is read-only. Replace fetch
    #    calls with method:'POST' so they no-op instead of 404'ing.
    html = re.sub(
        r"fetch\(([^)]*?/api/todos/[^)]*?),\s*\{[^}]*?method:\s*['\"]POST['\"][^}]*?\}\)",
        r"Promise.resolve({ok:false,publicReadOnly:true}) /* defanged: \1 */",
        html,
    )

    # 4. Inject a small banner at the top of the body so visitors know this is
    #    a public read-only snapshot.
    banner = (
        '<div style="background:#0a1422;border-bottom:1px solid #1f2c44;'
        'padding:6px 10px;font-size:11px;color:#7cd3ff;text-align:center;'
        'font-family:\'Cascadia Code\',monospace">'
        'PUBLIC READ-ONLY SNAPSHOT &middot; pushed every ~5 min when bot is alive &middot; '
        '<span id="snapshot-age" style="color:#888">checking…</span>'
        '</div>'
    )
    html = html.replace("<body", "<!-- public mirror banner injected by build_static_dashboard.py -->\n<body", 1)
    # Insert banner right after the opening <body ...> tag
    html = re.sub(r"(<body[^>]*>)", r"\1\n" + banner, html, count=1)

    # 5. Add a snippet that updates the banner with snapshot age. We append
    #    it near the end of the existing setInterval refresh logic. Easiest:
    #    inject a small extra script just before </body>.
    extra_js = """
<script>
/* Public-mirror snapshot age tracker — independent of dashboard.js refresh */
(function(){
  function updateAge(){
    fetch('data/snapshot.json?cb='+Date.now(),{method:'HEAD'})
      .then(r=>{
        const lm=r.headers.get('last-modified');
        if(!lm){document.getElementById('snapshot-age').textContent='age unknown';return;}
        const ageMs=Date.now()-new Date(lm).getTime();
        const m=Math.floor(ageMs/60000);
        const s=Math.floor((ageMs%60000)/1000);
        const el=document.getElementById('snapshot-age');
        if(!el)return;
        el.textContent='snapshot '+(m>0?m+'m '+s+'s':s+'s')+' old';
        el.style.color=m>=5?'#ff6b35':m>=2?'#ffaa00':'#00ff88';
      }).catch(()=>{});
  }
  updateAge();
  setInterval(updateAge,15000);
})();
</script>
"""
    html = html.replace("</body>", extra_js + "\n</body>", 1)

    return html


def main():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "data").mkdir(parents=True, exist_ok=True)

    html = extract_dashboard_html()
    static_html = rewrite_for_static(html)

    OUTPUT_HTML.write_text(static_html, encoding="utf-8")
    print(f"[OK] wrote{OUTPUT_HTML} ({len(static_html):,} chars)")

    # Placeholder snapshot so GitHub Pages serves something on first deploy
    placeholder = DOCS_DIR / "data" / "snapshot.json"
    if not placeholder.exists():
        placeholder.write_text(
            '{"placeholder":true,"note":"Run publish_dashboard.py to populate."}',
            encoding="utf-8",
        )
        print(f"[OK] wroteplaceholder {placeholder}")


if __name__ == "__main__":
    main()
