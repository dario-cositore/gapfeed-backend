#!/usr/bin/env python3
"""Generate a comprehensive sitemap.xml for gapfeed.com."""
import os
from datetime import datetime
from pathlib import Path

BASE_URL = "https://gapfeed.com"
WEBSITE_DIR = Path(__file__).resolve().parent.parent / "website" / "gapfeed.com"

# Collect all pages
pages = []

# Main pages
pages.append({"loc": BASE_URL + "/", "priority": "1.0", "changefreq": "daily"})

# Gap pages
gap_dir = WEBSITE_DIR / "gap"
if gap_dir.exists():
    for f in sorted(gap_dir.glob("*.html")):
        slug = f.stem
        pages.append({
            "loc": f"{BASE_URL}/gap/{slug}.html",
            "priority": "0.8",
            "changefreq": "weekly"
        })

# Category pages
cat_dir = WEBSITE_DIR / "categories"
if cat_dir.exists():
    for f in sorted(cat_dir.glob("*.html")):
        slug = f.stem
        if slug == "index":
            pages.append({"loc": f"{BASE_URL}/categories/", "priority": "0.7", "changefreq": "daily"})
        else:
            pages.append({
                "loc": f"{BASE_URL}/categories/{slug}.html",
                "priority": "0.6",
                "changefreq": "weekly"
            })

# Source pages
src_dir = WEBSITE_DIR / "sources"
if src_dir.exists():
    for f in sorted(src_dir.glob("*.html")):
        slug = f.stem
        if slug == "index":
            pages.append({"loc": f"{BASE_URL}/sources/", "priority": "0.5", "changefreq": "daily"})
        else:
            pages.append({
                "loc": f"{BASE_URL}/sources/{slug}.html",
                "priority": "0.5",
                "changefreq": "weekly"
            })

# Static pages
for page in ["privacy", "terms"]:
    pages.append({"loc": f"{BASE_URL}/{page}.html", "priority": "0.3", "changefreq": "monthly"})

# Generate XML
today = datetime.utcnow().strftime("%Y-%m-%d")
lines = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
]

for p in pages:
    lines.append("  <url>")
    lines.append(f"    <loc>{p['loc']}</loc>")
    lines.append(f"    <lastmod>{today}</lastmod>")
    lines.append(f"    <changefreq>{p['changefreq']}</changefreq>")
    lines.append(f"    <priority>{p['priority']}</priority>")
    lines.append("  </url>")

lines.append("</urlset>")

sitemap = "\n".join(lines)

# Write
output = WEBSITE_DIR / "sitemap.xml"
with open(output, "w", encoding="utf-8") as f:
    f.write(sitemap)

print(f"Generated sitemap with {len(pages)} URLs -> {output}")
print(f"  Gap pages: {sum(1 for p in pages if '/gap/' in p['loc'])}")
print(f"  Category pages: {sum(1 for p in pages if '/categories/' in p['loc'])}")
print(f"  Source pages: {sum(1 for p in pages if '/sources/' in p['loc'])}")
print(f"  Other: {sum(1 for p in pages if '/gap/' not in p['loc'] and '/categories/' not in p['loc'] and '/sources/' not in p['loc'])}")
