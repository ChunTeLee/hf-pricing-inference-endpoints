"""
Rewrite relative url(...) refs inside style.css to absolute URLs.

The compiled CSS contains @font-face and background-image declarations
that reference assets via root-relative paths like
`url(/front/assets/fonts/...woff2)`. When we host this CSS at our
own origin, those paths resolve against US (404), not the source.

Result on the mock: the bold (700) and semibold (600) font weights
fail to load, so the browser SYNTHESIZES bold from the regular weight
— visibly different from the source. Same for background images.

Fix: rewrite all `url(/...)` inside style.css to absolute URLs
pointing back to the live origin.
"""

import re
from pathlib import Path

LIVE_BASE = "https://new-pricing-page-92.us.dev.moon.huggingface.tech"
css_path = Path("style.css")
css = css_path.read_text(encoding="utf-8")
print(f"before: {len(css):,} bytes")

# url() with single, double, or no quotes
def fix(m):
    quote = m.group(1) or ""
    val = m.group(2)
    if val.startswith(("http://", "https://", "data:", "//")):
        return m.group(0)
    if val.startswith("/"):
        return f"url({quote}{LIVE_BASE}{val}{quote})"
    return m.group(0)

css = re.sub(r'url\(([\'"]?)([^\'")]+)\1\)', fix, css)
css_path.write_text(css, encoding="utf-8")
print(f"after: {len(css):,} bytes")
print("absolutized relative url() refs")
