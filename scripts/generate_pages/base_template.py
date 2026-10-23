"""
Base template module for static page generation.
Provides HTML rendering functions and CSS for a premium dark theme.
"""

import json
import re
import urllib.parse
from typing import List, Tuple, Dict, Any


BASE_CSS = """
/* Design Tokens */
:root {
  --bg: #06060a;
  --card: #111118;
  --card-hover: #16161f;
  --border: #1a1a25;
  --text: #e4e4ed;
  --text-dim: #8888a0;
  --text-muted: #555568;
  --accent: #f97316;
  --cyan: #22d3ee;
  --red: #ef4444;
  --green: #22c55e;
  --yellow: #eab308;
  --font: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --mono: 'JetBrains Mono', monospace;
  --radius: 12px;
  --radius-large: 16px;
}

/* Reset & Base */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html {
  font-size: 16px;
  scroll-behavior: smooth;
}

body {
  font-family: var(--font);
  background-color: var(--bg);
  color: var(--text);
  line-height: 1.6;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* Typography */
h1, h2, h3, h4, h5, h6 {
  font-weight: 600;
  line-height: 1.3;
  margin-bottom: 0.75rem;
  color: var(--text);
}

h1 { font-size: 2.25rem; }
h2 { font-size: 1.875rem; }
h3 { font-size: 1.5rem; }
h4 { font-size: 1.25rem; }

p {
  margin-bottom: 1rem;
  color: var(--text-dim);
}

a {
  color: var(--accent);
  text-decoration: none;
  transition: color 0.2s ease;
}

a:hover {
  color: var(--cyan);
}

/* Header - Sticky Glassmorphism */
header {
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(6, 6, 10, 0.8);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
  padding: 1rem 1.5rem;
}

nav {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.logo {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text);
  text-decoration: none;
}

.logo:hover {
  color: var(--accent);
}

.nav-links {
  display: flex;
  gap: 2rem;
  list-style: none;
}

.nav-links a {
  color: var(--text-dim);
  font-size: 0.9375rem;
  font-weight: 500;
}

.nav-links a:hover {
  color: var(--accent);
}

/* Hamburger Menu (Mobile) */
.hamburger {
  display: none;
  flex-direction: column;
  gap: 4px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.5rem;
}

.hamburger span {
  width: 24px;
  height: 2px;
  background: var(--text);
  transition: transform 0.2s ease;
}

@media (max-width: 768px) {
  .hamburger {
    display: flex;
  }

  .nav-links {
    position: fixed;
    top: 60px;
    left: 0;
    right: 0;
    background: var(--bg);
    border-bottom: 1px solid var(--border);
    flex-direction: column;
    padding: 1rem;
    gap: 1rem;
    transform: translateY(-100%);
    opacity: 0;
    transition: transform 0.3s ease, opacity 0.3s ease;
    pointer-events: none;
  }

  .nav-links.active {
    transform: translateY(0);
    opacity: 1;
    pointer-events: auto;
  }
}

/* Main Content */
main {
  flex: 1;
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem 1.5rem;
  width: 100%;
}

/* Breadcrumb Nav */
.breadcrumb {
  margin-bottom: 1.5rem;
  font-size: 0.875rem;
  color: var(--text-muted);
}

.breadcrumb a {
  color: var(--text-dim);
}

.breadcrumb a:hover {
  color: var(--accent);
}

.breadcrumb-separator {
  margin: 0 0.75rem;
  color: var(--text-muted);
}

/* Cards */
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.5rem;
  margin-bottom: 1.5rem;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  position: relative;
  overflow: hidden;
}

.card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: var(--accent);
  opacity: 0;
  transition: opacity 0.2s ease;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
  background: var(--card-hover);
}

.card:hover::before {
  opacity: 1;
}

.card-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
  color: var(--text);
}

.card-content {
  color: var(--text-dim);
}

/* Heat Badges */
.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-right: 0.5rem;
  margin-bottom: 0.5rem;
}

.badge-hot {
  background: rgba(239, 68, 68, 0.2);
  color: var(--red);
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.badge-warm {
  background: rgba(234, 179, 8, 0.2);
  color: var(--yellow);
  border: 1px solid rgba(234, 179, 8, 0.3);
}

.badge-emerging {
  background: rgba(136, 136, 160, 0.2);
  color: var(--text-dim);
  border: 1px solid rgba(136, 136, 160, 0.3);
}

/* Pills (Source & Category) */
.pill {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
  background: rgba(249, 115, 22, 0.1);
  color: var(--accent);
  border: 1px solid rgba(249, 115, 22, 0.2);
  margin-right: 0.5rem;
  margin-bottom: 0.5rem;
  text-decoration: none;
}

.pill:hover {
  background: rgba(249, 115, 22, 0.2);
  color: var(--cyan);
}

/* Quote Cards */
.quote-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-left: 4px solid var(--accent);
  border-radius: var(--radius);
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

.quote-text {
  font-size: 1.125rem;
  font-style: italic;
  color: var(--text);
  margin-bottom: 1rem;
  line-height: 1.7;
}

.quote-source {
  font-size: 0.875rem;
  color: var(--text-muted);
  text-align: right;
}

/* FAQ Accordion (CSS Only) */
details {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 0.75rem;
  overflow: hidden;
}

summary {
  padding: 1rem 1.5rem;
  font-weight: 600;
  cursor: pointer;
  color: var(--text);
  list-style: none;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

summary::-webkit-details-marker {
  display: none;
}

summary::after {
  content: '+';
  font-size: 1.25rem;
  font-weight: 400;
  color: var(--text-muted);
  transition: transform 0.2s ease;
}

details[open] summary::after {
  content: '−';
  transform: rotate(180deg);
}

details[open] summary {
  border-bottom: 1px solid var(--border);
}

details .content {
  padding: 1rem 1.5rem;
  color: var(--text-dim);
}

/* Tag Chips */
.tag-chip {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.625rem;
  background: rgba(34, 211, 238, 0.1);
  color: var(--cyan);
  border: 1px solid rgba(34, 211, 238, 0.2);
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 500;
  margin-right: 0.5rem;
  margin-bottom: 0.5rem;
  text-decoration: none;
}

.tag-chip:hover {
  background: rgba(34, 211, 238, 0.2);
  color: var(--text);
}

/* Related Gaps Grid */
.grid {
  display: grid;
  gap: 1.5rem;
  margin-top: 2rem;
}

.grid-2 { grid-template-columns: repeat(2, 1fr); }
.grid-3 { grid-template-columns: repeat(3, 1fr); }
.grid-4 { grid-template-columns: repeat(4, 1fr); }

@media (max-width: 768px) {
  .grid-2, .grid-3, .grid-4 {
    grid-template-columns: 1fr;
  }
}

/* Utility Classes */
.mt-0 { margin-top: 0; }
.mb-0 { margin-bottom: 0; }
.mt-4 { margin-top: 1rem; }
.mb-4 { margin-bottom: 1rem; }
.mt-8 { margin-top: 2rem; }
.mb-8 { margin-bottom: 2rem; }
.text-center { text-align: center; }
.text-muted { color: var(--text-muted); }
.text-dim { color: var(--text-dim); }
.text-accent { color: var(--accent); }

/* Code & Mono */
code, pre {
  font-family: var(--mono);
  font-size: 0.875rem;
}

code {
  background: rgba(0, 0, 0, 0.3);
  padding: 0.125rem 0.375rem;
  border-radius: 4px;
  color: var(--cyan);
}

pre {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem;
  overflow-x: auto;
  margin-bottom: 1rem;
}

pre code {
  background: none;
  padding: 0;
  color: inherit;
}

/* Footer */
footer {
  background: var(--card);
  border-top: 1px solid var(--border);
  padding: 2rem 1.5rem;
  margin-top: auto;
}

.footer-content {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.footer-links {
  display: flex;
  gap: 1.5rem;
  list-style: none;
}

.footer-links a {
  color: var(--text-dim);
  font-size: 0.875rem;
}

.footer-links a:hover {
  color: var(--accent);
}

.copyright {
  color: var(--text-muted);
  font-size: 0.875rem;
}

@media (max-width: 768px) {
  .footer-content {
    flex-direction: column;
    text-align: center;
  }

  .footer-links {
    justify-content: center;
  }
}

/* Fluid Container */
.container {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 1.5rem;
}

/* Share Buttons */
.share-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 16px 0 24px;
  flex-wrap: wrap;
}
.share-label {
  font-size: 0.82rem;
  color: var(--text-muted);
  font-weight: 500;
}
.share-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 0.8rem;
  font-weight: 500;
  border: 1px solid var(--border);
  background: var(--card);
  color: var(--text);
  cursor: pointer;
  text-decoration: none;
  transition: background 0.15s, border-color 0.15s;
}
.share-btn:hover {
  background: var(--card-hover);
  border-color: var(--text-muted);
  color: var(--text);
}
.share-btn svg {
  width: 16px;
  height: 16px;
  fill: currentColor;
}
.share-btn.twitter { color: #1da1f2; border-color: #1da1f230; }
.share-btn.twitter:hover { background: #1da1f215; }
.share-btn.linkedin { color: #0a66c2; border-color: #0a66c230; }
.share-btn.linkedin:hover { background: #0a66c215; }
.share-btn.copy { color: var(--accent); border-color: var(--accent-border); }
.share-btn.copy:hover { background: var(--accent-dim); }
.share-toast {
  display: none;
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--green);
  color: #000;
  padding: 8px 20px;
  border-radius: 8px;
  font-size: 0.85rem;
  font-weight: 600;
  z-index: 999;
  animation: fadeInOut 2s ease;
}
@keyframes fadeInOut {
  0% { opacity: 0; transform: translateX(-50%) translateY(10px); }
  15% { opacity: 1; transform: translateX(-50%) translateY(0); }
  85% { opacity: 1; transform: translateX(-50%) translateY(0); }
  100% { opacity: 0; transform: translateX(-50%) translateY(-10px); }
}
"""


def render_html_page(
    title: str,
    meta_description: str,
    canonical_url: str,
    content_html: str,
    breadcrumbs: List[Tuple[str, str]],
    json_ld_blocks: List[Dict[str, Any]],
    page_type: str = 'other'
) -> str:
    """
    Render a complete HTML5 page with the base template.

    Args:
        title: Page title
        meta_description: Meta description (will be truncated if needed)
        canonical_url: Full canonical URL for the page
        content_html: Main content HTML string
        breadcrumbs: List of (label, url) tuples for breadcrumb nav
        json_ld_blocks: List of dicts to render as JSON-LD script blocks

    Returns:
        Complete HTML page as string
    """
    # Extract canonical path for tracking pixel
    canonical_path = canonical_url.replace("https://gapfeed.com", "")

    # Build breadcrumbs HTML
    breadcrumbs_html = render_breadcrumbs_html(breadcrumbs) if breadcrumbs else ""

    # Build JSON-LD scripts
    json_ld_html = ""
    for json_ld in json_ld_blocks:
        json_ld_html += f'    <script type="application/ld+json">\n      {json.dumps(json_ld, ensure_ascii=False)}\n    </script>\n'

    # For pages that display search results, also include a tracking pixel with search query
    # <img src="https://gapfeed.com/api/track.php?p={canonical_path}&t={page_type}&q={search_query}" width="1" height="1" alt="" style="position:absolute;width:1px;height:1px;opacity:0;pointer-events:none;">

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="description" content="{meta_description}">
  <link rel="canonical" href="{canonical_url}">

  <!-- Open Graph -->
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{meta_description}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{canonical_url}">
  <meta property="og:site_name" content="GapFeed">

  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{meta_description}">

  <!-- Self-hosted fonts -->
  <link href="/fonts/fonts.css" rel="stylesheet">

  <!-- Styles -->
  <style>
{BASE_CSS}
  </style>
</head>
<body>
  <!-- Header -->
  <header>
    <nav>
      <a href="/" class="logo">GapFeed</a>
      <button class="hamburger" aria-label="Toggle navigation">
        <span></span>
        <span></span>
        <span></span>
      </button>
      <ul class="nav-links">
        <li><a href="/">Home</a></li>
        <li><a href="/gaps/">Gaps</a></li>
        <li><a href="/categories/">Categories</a></li>
        <li><a href="/sources/">Sources</a></li>
      </ul>
    </nav>
  </header>

  <!-- Breadcrumbs -->
  {breadcrumbs_html}

  <!-- Main Content -->
  <main>
    {content_html}
  </main>

  <!-- Footer -->
  <footer>
    <div class="footer-content">
      <div class="copyright">
        &copy; {2026} GapFeed. All rights reserved.
      </div>
      <ul class="footer-links">
        <li><a href="/">Home</a></li>
        <li><a href="/gaps/">Gaps</a></li>
        <li><a href="/categories/">Categories</a></li>
        <li><a href="/sources/">Sources</a></li>
      </ul>
    </div>
  </footer>

  <!-- JSON-LD -->
{json_ld_html}

  <!-- Tracking Pixel -->
  <img src="https://gapfeed.com/api/track?page={canonical_path}&ref=" style="display:none" alt="">

  <!-- Mobile Menu Script (minimal, inline) -->
  <script>
    document.addEventListener('DOMContentLoaded', function() {{
      const hamburger = document.querySelector('.hamburger');
      const navLinks = document.querySelector('.nav-links');
      if (hamburger && navLinks) {{
        hamburger.addEventListener('click', function() {{
          navLinks.classList.toggle('active');
        }});
      }}
    }});
  </script>

  <!-- Visitor tracking - zero JS, works everywhere -->
  <img src="https://gapfeed.com/api/track.php?p={canonical_path}&t={page_type}" width="1" height="1" alt="" style="position:absolute;width:1px;height:1px;opacity:0;pointer-events:none;">
</body>
</html>'''

    return html


def render_breadcrumbs_html(breadcrumbs: List[Tuple[str, str]]) -> str:
    """
    Render breadcrumb navigation HTML.

    Args:
        breadcrumbs: List of (label, url) tuples. Last item will not be linked.

    Returns:
        HTML string for breadcrumb nav.
    """
    if not breadcrumbs:
        return ""

    parts = ['<nav class="breadcrumb" aria-label="Breadcrumb">']

    for i, (label, url) in enumerate(breadcrumbs):
        is_last = (i == len(breadcrumbs) - 1)

        if is_last:
            parts.append(f'  <span>{label}</span>')
        else:
            parts.append(f'  <a href="{url}">{label}</a>')
            parts.append('  <span class="breadcrumb-separator" aria-hidden="true">&gt;</span>')

    parts.append('</nav>')
    return "\n".join(parts)


def render_heat_badge(score: float) -> str:
    """
    Render a heat badge based on score.

    Args:
        score: Numeric score between 0 and 1.

    Returns:
        HTML string for the badge.
    """
    if score >= 0.7:
        label = "HOT"
        class_name = "badge-hot"
    elif score >= 0.4:
        label = "WARM"
        class_name = "badge-warm"
    else:
        label = "EMERGING"
        class_name = "badge-emerging"

    return f'<span class="badge {class_name}">{label}</span>'


def render_quote_card(quote_text: str, source: str, source_url: str = None) -> str:
    """
    Render a styled quote card.

    Args:
        quote_text: The quote content
        source: Attribution/source for the quote
        source_url: Optional URL to the original post (links the source)

    Returns:
        HTML string for the quote card.
    """
    # Escape HTML entities in text to prevent injection
    quote_escaped = quote_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    source_escaped = source.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    if source_url:
        source_html = f'<a href="{source_url}" target="_blank" rel="noopener noreferrer">{source_escaped}</a>'
    else:
        # Link to platform based on source name
        platform_urls = {
            'reddit': 'https://www.reddit.com',
            'hacker news': 'https://news.ycombinator.com',
            'hn': 'https://news.ycombinator.com',
            'stackoverflow': 'https://stackoverflow.com',
            'stack overflow': 'https://stackoverflow.com',
            'dev.to': 'https://dev.to',
            'youtube': 'https://www.youtube.com',
            'producthunt': 'https://www.producthunt.com',
            'duckduckgo': 'https://duckduckgo.com',
            'web': 'https://duckduckgo.com',
            'github': 'https://github.com',
            'indiehackers': 'https://www.indiehackers.com',
        }
        source_lower = source_escaped.lower()
        platform_url = None
        for key, url in platform_urls.items():
            if key in source_lower:
                platform_url = url
                break
        if platform_url:
            source_html = f'<a href="{platform_url}" target="_blank" rel="noopener noreferrer">{source_escaped}</a>'
        else:
            source_html = source_escaped

    return f'''<div class="quote-card">
  <blockquote class="quote-text">{quote_escaped}</blockquote>
  <div class="quote-source">&mdash; {source_html}</div>
</div>'''


def render_share_buttons(gap_title: str, slug: str, evidence_count: int, source_types: list) -> str:
    """
    Render social share buttons for a gap page.

    Args:
        gap_title: The gap title
        slug: URL slug
        evidence_count: Number of signals
        source_types: List of source platform names

    Returns:
        HTML string for share buttons row.
    """
    url = f"https://gapfeed.com/gap/{slug}.html"
    sources_str = ", ".join(s.replace("-", " ").title() for s in source_types[:3])
    sources_text = f" across {sources_str}" if sources_str else ""

    # Twitter text (max 280 chars)
    tweet = f'"{gap_title}" - unmet market gap{sources_text}. {evidence_count} signals detected by @DarioCositore'
    if len(tweet) > 250:
        tweet = tweet[:247] + "..."
    tweet_url = f"https://twitter.com/intent/tweet?text={urllib.parse.quote(tweet)}&url={urllib.parse.quote(url)}"

    # LinkedIn share
    li_url = f"https://www.linkedin.com/sharing/share-offsite/?url={urllib.parse.quote(url)}"

    escaped_title = gap_title.replace('"', '&quot;').replace("'", "\\'")

    return f'''<div class="share-row">
  <span class="share-label">Share:</span>
  <a href="{tweet_url}" target="_blank" rel="noopener" class="share-btn twitter">
    <svg viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
    X
  </a>
  <a href="{li_url}" target="_blank" rel="noopener" class="share-btn linkedin">
    <svg viewBox="0 0 24 24"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
    LinkedIn
  </a>
  <button class="share-btn copy" onclick="navigator.clipboard.writeText('{url}').then(()=>{{var t=document.getElementById('share-toast');t.style.display='block';setTimeout(()=>t.style.display='none',2000);}})">
    <svg viewBox="0 0 24 24"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>
    Copy link
  </button>
  <div id="share-toast" class="share-toast">Link copied!</div>
</div>'''


def slugify(text: str) -> str:
    """
    Convert text to a URL-safe slug.

    Args:
        text: Input string to slugify

    Returns:
        URL-safe slug (lowercase, hyphens, no special chars)
    """
    # Lowercase
    slug = text.lower()
    # Replace non-alphanumeric with hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    # Collapse multiple hyphens
    slug = re.sub(r'-+', '-', slug)
    # Strip leading/trailing hyphens
    slug = slug.strip('-')
    return slug


def truncate(text: str, max_len: int = 155) -> str:
    """
    Truncate text to maximum length, avoiding cutting mid-word.

    Args:
        text: Input text
        max_len: Maximum length (default 155)

    Returns:
        Truncated text with ellipsis if needed.
    """
    if len(text) <= max_len:
        return text

    # Truncate at max_len and find last space
    truncated = text[:max_len]
    last_space = truncated.rfind(' ')

    if last_space > 0:
        truncated = truncated[:last_space]

    return truncated.rstrip() + '...'
