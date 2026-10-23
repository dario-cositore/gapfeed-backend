"""
SEO infrastructure utilities: robots.txt, sitemap.xml, and sitemap page builder.
"""

import os

def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def _write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def generate_robots_txt(output_dir):
    """
    Generate robots.txt file.

    Args:
        output_dir: base output directory (e.g., "website/gapfeed.com")
    """
    content = """User-agent: *
Allow: /
Sitemap: https://gapfeed.com/sitemap.xml
"""
    robots_path = os.path.join(output_dir, "robots.txt")
    _write_file(robots_path, content)

def generate_sitemap(pages, output_dir):
    """
    Generate sitemap.xml from list of page dicts.

    Args:
        pages: list of dicts with keys: url (required), lastmod (YYYY-MM-DD), changefreq, priority
        output_dir: base output directory
    """
    sitemap_entries = []
    for p in pages:
        if not p.get("url"):
            continue
        entry_lines = [f'  <url>', f'    <loc>{p["url"]}</loc>']
        if p.get("lastmod"):
            entry_lines.append(f'    <lastmod>{p["lastmod"]}</lastmod>')
        if p.get("changefreq"):
            entry_lines.append(f'    <changefreq>{p["changefreq"]}</changefreq>')
        if p.get("priority") is not None:
            entry_lines.append(f'    <priority>{p["priority"]}</priority>')
        entry_lines.append('  </url>')
        sitemap_entries.append('\n'.join(entry_lines))

    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml_content += '\n'.join(sitemap_entries)
    xml_content += '\n</urlset>'

    sitemap_path = os.path.join(output_dir, "sitemap.xml")
    _write_file(sitemap_path, xml_content)

def build_sitemap_pages(gaps, categories, sources, tags):
    """
    Build list of sitemap page entries from all data.

    Args:
        gaps: list of gap dicts, each should have at least "slug" and ideally "lastmod" (YYYY-MM-DD)
        categories: dict of category_slug -> {...}
        sources: dict of source_slug -> {...}
        tags: dict of tag_slug -> {...}

    Returns:
        List of page dicts for sitemap generation.
    """
    pages = []

    # Landing page
    pages.append({
        "url": "https://gapfeed.com/",
        "lastmod": None,
        "changefreq": "daily",
        "priority": 1.0
    })

    # Gap pages
    for gap in gaps:
        slug = gap["slug"]
        # Try to get lastmod from various keys
        lastmod = gap.get("lastmod") or gap.get("updated_at") or gap.get("date")
        pages.append({
            "url": f"https://gapfeed.com/gap/{slug}.html",
            "lastmod": lastmod,
            "changefreq": "weekly",
            "priority": 0.8
        })

    # Category pages
    for slug in categories:
        pages.append({
            "url": f"https://gapfeed.com/categories/{slug}.html",
            "lastmod": None,
            "changefreq": "weekly",
            "priority": 0.7
        })

    # Source pages
    for slug in sources:
        pages.append({
            "url": f"https://gapfeed.com/sources/{slug}.html",
            "lastmod": None,
            "changefreq": "weekly",
            "priority": 0.6
        })

    # Tag pages
    for slug in tags:
        pages.append({
            "url": f"https://gapfeed.com/tags/{slug}.html",
            "lastmod": None,
            "changefreq": "weekly",
            "priority": 0.5
        })

    # Index pages
    pages.append({
        "url": "https://gapfeed.com/categories/",
        "lastmod": None,
        "changefreq": "weekly",
        "priority": 0.8
    })
    pages.append({
        "url": "https://gapfeed.com/sources/",
        "lastmod": None,
        "changefreq": "weekly",
        "priority": 0.7
    })
    pages.append({
        "url": "https://gapfeed.com/tags/",
        "lastmod": None,
        "changefreq": "weekly",
        "priority": 0.6
    })

    return pages
