import json
import os
from datetime import datetime, timezone

DATA_JSON_PATH = "/home/dario/.openclaw/workspace/3. gapfeed/website/gapfeed.com/gapfeed-astro/public/data/data.json"
SITEMAP_PATH = "/home/dario/.openclaw/workspace/3. gapfeed/website/gapfeed.com/gapfeed-astro/public/sitemap.xml"
RSS_PATH = "/home/dario/.openclaw/workspace/3. gapfeed/website/gapfeed.com/gapfeed-astro/public/rss.xml"

with open(DATA_JSON_PATH, 'r') as f:
    data = json.load(f)

gaps = data.get("gaps", [])

# Base URL
BASE_URL = "https://gapfeed.com"

# Generate Sitemap
sitemap_urls = [
    f"  <url>\n    <loc>{BASE_URL}/</loc>\n  </url>",
    f"  <url>\n    <loc>{BASE_URL}/about/</loc>\n  </url>",
    f"  <url>\n    <loc>{BASE_URL}/vision/</loc>\n  </url>",
    f"  <url>\n    <loc>{BASE_URL}/graphs/</loc>\n  </url>",
    f"  <url>\n    <loc>{BASE_URL}/sponsor/</loc>\n  </url>",
    f"  <url>\n    <loc>{BASE_URL}/transparency/</loc>\n  </url>",
    f"  <url>\n    <loc>{BASE_URL}/doc/</loc>\n  </url>",
    f"  <url>\n    <loc>{BASE_URL}/privacy/</loc>\n  </url>",
    f"  <url>\n    <loc>{BASE_URL}/terms/</loc>\n  </url>"
]

for gap in gaps:
    slug = gap.get("slug")
    if slug:
        sitemap_urls.append(f"  <url>\n    <loc>{BASE_URL}/gap/{slug}/</loc>\n  </url>")

sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(sitemap_urls)}
</urlset>"""

with open(SITEMAP_PATH, 'w') as f:
    f.write(sitemap_content)

# Generate RSS
current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
rss_items = []

for gap in gaps:
    slug = gap.get("slug")
    title = gap.get("title", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    desc = gap.get("description", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    category = gap.get("category", "")
    
    if slug:
        url = f"{BASE_URL}/gap/{slug}/"
        item = f"""    <item>
      <title>{title}</title>
      <link>{url}</link>
      <guid isPermaLink="true">{url}</guid>
      <description>{desc}</description>
      <category>{category}</category>
      <pubDate>{current_date}</pubDate>
    </item>"""
        rss_items.append(item)

rss_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>gapfeed</title>
    <link>https://gapfeed.com</link>
    <description>Real unsolved problems ranked by urgency, buyer intent, and momentum.</description>
    <lastBuildDate>{current_date}</lastBuildDate>
    <atom:link href="https://gapfeed.com/rss.xml" rel="self" type="application/rss+xml"/>
{chr(10).join(rss_items)}
  </channel>
</rss>"""

with open(RSS_PATH, 'w') as f:
    f.write(rss_content)

print("Generated sitemap.xml and rss.xml successfully!")