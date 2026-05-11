"""
Build index.html from the hydrated HF pricing page DOM.

Pipeline:
  1. Read pricing-main.html (the hydrated <main> innerHTML pulled from
     Chrome via a Blob download — the SSR HTML alone is incomplete
     because the page is SvelteKit-hydrated).
  2. Make all relative asset URLs absolute (point back to dev.moon
     for now; CSS is mirrored locally).
  3. Strip SvelteKit's HTML comment markers (<!--[-->, <!--]-->,
     <!--d5o5ex-->, etc.) for cleanliness — they don't render but
     bloat the source.
  4. Replace Storage section (i=6) with a placeholder per user spec.
  5. Replace Inference Endpoints section (i=13) with the custom
     redesign from inference-endpoints.html (keeps the collapsible
     UX we built earlier).
  6. Write a self-contained index.html that loads ./style.css.
"""

import re
from pathlib import Path

LIVE_BASE = "https://new-pricing-page-92.us.dev.moon.huggingface.tech"
main_html = Path("pricing-main.html").read_text(encoding="utf-8")
print(f"main length: {len(main_html):,}")

# 1) Strip SvelteKit comment markers.
main_html = re.sub(r"<!--\[-->", "", main_html)
main_html = re.sub(r"<!--\]-->", "", main_html)
main_html = re.sub(r"<!--[a-z0-9]{4,12}-->", "", main_html)
main_html = re.sub(r"<!---->", "", main_html)
print(f"after stripping comments: {len(main_html):,}")

# 2) Make relative asset URLs absolute.
def absify(m):
    quote = m.group(1)
    attr_name = m.group(0).split("=")[0].rsplit(" ", 1)[-1]
    val = m.group(2)
    if val.startswith(("http://", "https://", "#", "data:", "mailto:", "//")):
        return m.group(0)
    if val.startswith("/"):
        return f'{attr_name}={quote}{LIVE_BASE}{val}{quote}'
    return m.group(0)

main_html = re.sub(
    r'(?:src|href)=(["\'])([^"\']+)\1',
    absify,
    main_html,
)

def absify_srcset(m):
    quote = m.group(1)
    parts = [p.strip() for p in m.group(2).split(",")]
    new_parts = []
    for p in parts:
        bits = p.split(" ", 1)
        url = bits[0]
        suffix = " " + bits[1] if len(bits) > 1 else ""
        if url.startswith(("http://", "https://", "data:", "//")):
            new_parts.append(p)
        elif url.startswith("/"):
            new_parts.append(f"{LIVE_BASE}{url}{suffix}")
        else:
            new_parts.append(p)
    return f'srcset={quote}{", ".join(new_parts)}{quote}'

main_html = re.sub(
    r'srcset=(["\'])([^"\']+)\1',
    absify_srcset,
    main_html,
)

# 3) Find each top-level <section> by walking the string and counting
#    depth. We want the OUTERMOST sections within <main>.
def find_top_sections(html):
    """Yield (start, end) tuples for each top-level <section> in html."""
    pos = 0
    while pos < len(html):
        # Find next <section open at any depth
        m = re.search(r"<section\b[^>]*>", html[pos:])
        if not m:
            return
        start_abs = pos + m.start()
        # If we're INSIDE another already-yielded section, skip past it.
        # For top-level scan, we always start from a position outside any
        # section, so depth begins at 0.
        depth = 1
        i = pos + m.end()
        while i < len(html) and depth > 0:
            mo = re.search(r"<(/?)section\b[^>]*>", html[i:])
            if not mo:
                return
            tag_start = i + mo.start()
            tag_end = i + mo.end()
            if mo.group(1) == "/":
                depth -= 1
            else:
                depth += 1
            i = tag_end
        if depth == 0:
            yield (start_abs, i)
            pos = i
        else:
            return

spans = list(find_top_sections(main_html))
print(f"found {len(spans)} top-level sections")
for i, (s, e) in enumerate(spans):
    snippet = main_html[s:s+120].replace("\n", " ")
    print(f"  [{i}] {s:>7} → {e:>7} ({e-s:>6}b): {snippet[:80]}")

if len(spans) < 13:
    raise SystemExit(f"expected ≥13 sections, got {len(spans)}")
# Section indices in the hydrated DOM:
#   [0] Hero  [1] Plan comparison  [2] Need support  [3] divider
#   [4] Storage  [5] divider  [6] Hub  [7] divider
#   [8] Spaces Hardware  [9] divider  [10] Inference Endpoints
#   [11] divider  [12] Join PRO
STORAGE_IDX = 4
IE_IDX = 10

# 4) Placeholders.
storage_replacement = '''<section class="w-full border-b border-gray-200/70 px-4">
  <div class="mx-auto max-w-7xl overflow-hidden border-l border-r border-gray-100 dark:border-gray-800">
    <div class="p-8 sm:p-10 lg:p-14">
      <span class="text-smd mb-4 inline-block rounded-full bg-blue-400/10 px-4 py-1 font-semibold text-blue-600 dark:bg-blue-600/10 dark:text-blue-500">Storage</span>
      <h2 class="mb-4 text-balance text-3xl font-bold text-gray-900 dark:text-white md:text-4xl">
        Transparent, volume-based pricing.
      </h2>
      <p class="mb-8 max-w-3xl text-lg text-gray-600 dark:text-gray-400">
        Store your AI models, datasets, Spaces, and Buckets with simple per-TB pricing.
      </p>
      <div class="rounded-2xl border border-dashed border-gray-200 dark:border-gray-800 px-8 py-14 text-center">
        <p class="text-sm uppercase tracking-widest text-gray-500">Section placeholder</p>
        <p class="mt-2 text-base text-gray-500 dark:text-gray-400">Storage pricing tiers coming soon.</p>
      </div>
    </div>
  </div>
</section>'''

# 5) Extract my custom IE section + script from inference-endpoints.html.
ie_src = Path("inference-endpoints.html").read_text(encoding="utf-8")
ie_section_match = re.search(r"<section\b.*?</section>", ie_src, flags=re.DOTALL)
ie_script_match = re.search(r"<script>\s*//\s*Source data.*?</script>", ie_src, flags=re.DOTALL)
if not ie_section_match:
    raise SystemExit("could not extract custom IE section")
custom_ie = ie_section_match.group(0)
custom_ie_script = ie_script_match.group(0) if ie_script_match else ""

# 6) Splice. Highest index first so earlier offsets remain valid.
storage_start, storage_end = spans[STORAGE_IDX]
ie_start, ie_end = spans[IE_IDX]

# Wrap each replacement in the same outer divider <div> that the original
# section's containing wrapper provided. The replacement strings above
# already include a <section> tag with the same outer classes.
main_html = main_html[:ie_start] + custom_ie + main_html[ie_end:]
main_html = main_html[:storage_start] + storage_replacement + main_html[storage_end:]

# 7) Write the final index.html.
final_html = f"""<!doctype html>
<html lang="en" class="dark">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Hugging Face Pricing — mock</title>
    <!-- Live HF compiled CSS, mirrored locally. Contains every Tailwind
         class used by the page plus the HF dark-mode overrides
         (e.g. `:where(.bg-white):is(.dark *) {{ ... #0B0F19 ... }}`).
         Do NOT add Tailwind CDN — it would inject conflicting rules. -->
    <link rel="stylesheet" href="./style.css" />
    <!-- Google Fonts: Source Sans Pro (200/300/400/600/700) and IBM
         Plex Mono. Critical — the compiled style.css only defines the
         italic 900 weight; everything else (regular, semibold, bold)
         lives in these Google-hosted @font-face declarations. Without
         them the browser font-synthesizes bold from the regular weight
         and the page looks visibly off. -->
    <link href="https://fonts.googleapis.com/css2?family=Source+Sans+Pro:ital,wght@0,200;0,300;0,400;0,600;0,700;1,200;1,300;1,400;1,600;1,700&display=swap" rel="stylesheet" />
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&display=swap" rel="stylesheet" />
    <style>
      /* --------------------------------------------------------------
         Custom utilities for the Inference Endpoints redesign.
         Tailwind CDN is intentionally NOT loaded (it would override the
         dark-mode bg-white rule baked into style.css), so we hand-roll
         these handful of utilities the IE section depends on.
         -------------------------------------------------------------- */
      :root {{
        --color-page: #0B0F19;
        --color-line: #2A3654;
      }}
      .bg-page {{ background-color: var(--color-page); }}
      .border-line {{ border-color: var(--color-line); }}
      .bg-line {{ background-color: var(--color-line); }}
      .bg-line\/50 {{ background-color: rgb(42 54 84 / 0.5); }}
      .bg-line\/40 {{ background-color: rgb(42 54 84 / 0.4); }}
      .border-line\/50 {{ border-color: rgb(42 54 84 / 0.5); }}
      .bg-page\/40 {{ background-color: rgb(11 15 25 / 0.4); }}
      .hover\:bg-line\/40:hover {{ background-color: rgb(42 54 84 / 0.4); }}
      .bg-\[\#0F121F\] {{ background-color: #0F121F; }}
      /* Per-section accent gradient on instance titles */
      .bg-\[radial-gradient\(ellipse_45\%_150\%_at_0\%_100\%\,rgb\(16_185_129\/0\.15\)\,rgb\(16_185_129\/0\.06\)_50\%\,rgb\(16_185_129\/0\)\)\] {{
        background-image: radial-gradient(ellipse 45% 150% at 0% 100%, rgb(16 185 129 / 0.15), rgb(16 185 129 / 0.06) 50%, rgb(16 185 129 / 0));
      }}
      .bg-\[radial-gradient\(ellipse_45\%_150\%_at_0\%_100\%\,rgb\(99_102_241\/0\.15\)\,rgb\(99_102_241\/0\.06\)_50\%\,rgb\(99_102_241\/0\)\)\] {{
        background-image: radial-gradient(ellipse 45% 150% at 0% 100%, rgb(99 102 241 / 0.15), rgb(99 102 241 / 0.06) 50%, rgb(99 102 241 / 0));
      }}
      .bg-\[radial-gradient\(ellipse_45\%_150\%_at_0\%_100\%\,rgb\(249_115_22\/0\.15\)\,rgb\(249_115_22\/0\.06\)_50\%\,rgb\(249_115_22\/0\)\)\] {{
        background-image: radial-gradient(ellipse 45% 150% at 0% 100%, rgb(249 115 22 / 0.15), rgb(249 115 22 / 0.06) 50%, rgb(249 115 22 / 0));
      }}
      /* Inference Endpoints expand/collapse */
      [data-expanded="true"] .chev {{ transform: rotate(90deg); }}
      tr.detail, tr.summary-first {{ display: none; }}
      tbody[data-expanded="true"] tr.detail,
      tbody[data-expanded="true"] tr.summary-first {{ display: table-row; }}
      tbody[data-expanded="true"] tr.summary-range {{ display: none; }}
    </style>
  </head>
  <body class="flex min-h-dvh flex-col bg-white text-black dark:bg-gray-950 PricingPage">
    <main class="flex flex-1 flex-col">
{main_html}
    </main>
    {custom_ie_script}
  </body>
</html>
"""

Path("index.html").write_text(final_html, encoding="utf-8")
print(f"wrote index.html: {len(final_html):,} bytes")
