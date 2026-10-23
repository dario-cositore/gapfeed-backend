#!/usr/bin/env python3
"""
GapFeed Static Page Generator - Orchestrator

Reads gaps from MySQL, generates all static HTML pages for SEO farming.
Generates: gap pages, category pages, source pages, tag pages, robots.txt, sitemap.xml.
"""

import os
import sys
import json
import shutil
from datetime import datetime

# Add project root to path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from shared.remote_db import RemoteDB
from scripts.generate_pages.gap_pages import generate_gap_page, derive_tags
from scripts.generate_pages.index_pages import (
    generate_category_page,
    generate_source_page,
    generate_tag_page,
    generate_category_index,
    generate_source_index,
    generate_tag_index
)
from scripts.generate_pages.seo_infra import generate_robots_txt, generate_sitemap, build_sitemap_pages
from scripts.generate_pages.base_template import slugify

SITE_DIR = os.path.join(ROOT, "website", "gapfeed.com")


def get_all_gaps():
    """Fetch all gaps from MySQL."""
    db = RemoteDB()
    result = db.get_gaps(limit=500)
    gaps = result.get("gaps", [])
    print(f"Fetched {len(gaps)} gaps from MySQL")
    return gaps


def extract_categories(gaps):
    """Extract unique categories. Returns dict slug -> {name, count, gaps}."""
    cats = {}
    for g in gaps:
        cat = g.get("category", "uncategorized")
        cat_slug = slugify(cat)
        if cat_slug not in cats:
            cats[cat_slug] = {"name": _readable(cat), "count": 0, "gaps": []}
        cats[cat_slug]["gaps"].append(g)
        cats[cat_slug]["count"] += 1
    return cats


def _readable(slug):
    """Convert slug to readable name."""
    return slug.replace("_", " ").replace("-", " ").title()


def extract_sources(gaps):
    """Extract unique sources. Returns dict slug -> {name, count, gaps}."""
    srcs = {}
    for g in gaps:
        for s in g.get("source_types", []):
            clean = s.replace("www.", "").replace(".com", "").replace(".", "-")
            if clean not in srcs:
                srcs[clean] = {"name": s, "count": 0, "gaps": []}
            srcs[clean]["gaps"].append(g)
            srcs[clean]["count"] += 1
    return srcs


def extract_tags(gaps):
    """Extract all tags. derive_tags returns list of (display_name, slug) tuples.
    Returns dict slug -> {name, count, gaps}."""
    tags = {}
    for g in gaps:
        gap_tags = derive_tags(g)
        for t_name, t_slug in gap_tags:
            if t_slug not in tags:
                tags[t_slug] = {"name": t_name, "count": 0, "gaps": []}
            tags[t_slug]["gaps"].append(g)
            tags[t_slug]["count"] += 1
    return tags


def clean_generated_dirs(site_dir):
    """Remove old generated files but keep index.html and _staging."""
    keep = {"index.html", "_staging", "api", "immigration", "admin"}
    for item in os.listdir(site_dir):
        if item in keep:
            continue
        path = os.path.join(site_dir, item)
        if os.path.isdir(path):
            shutil.rmtree(path)
            print(f"  Cleaned: {item}/")
        else:
            os.remove(path)
            print(f"  Cleaned: {item}")


def ensure_dirs(site_dir):
    """Create output directories."""
    for d in ["gap", "categories", "sources", "tags"]:
        os.makedirs(os.path.join(site_dir, d), exist_ok=True)


def main():
    print("=" * 60)
    print("GapFeed Static Page Generator")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    # 1. Fetch data
    print("[1/6] Fetching gaps from MySQL...")
    gaps = get_all_gaps()
    if not gaps:
        print("ERROR: No gaps found. Aborting.")
        return

    categories = extract_categories(gaps)
    sources = extract_sources(gaps)
    tags = extract_tags(gaps)

    print(f"  {len(categories)} categories, {len(sources)} sources, {len(tags)} tags")
    print()

    # 2. Clean old files
    print("[2/6] Cleaning old generated files...")
    clean_generated_dirs(SITE_DIR)
    ensure_dirs(SITE_DIR)
    print()

    # 3. Generate gap pages
    print("[3/6] Generating gap pages...")
    gap_count = 0
    for g in gaps:
        try:
            out = generate_gap_page(g, gaps, SITE_DIR)
            gap_count += 1
        except Exception as e:
            print(f"  ERROR gap {g.get('id')}: {e}")
    print(f"  Generated {gap_count} gap pages")
    print()

    # 4. Generate category, source, tag pages
    print("[4/6] Generating index pages...")
    cat_count = 0
    for cat_slug, cat_data in categories.items():
        try:
            generate_category_page(cat_slug, cat_data, SITE_DIR)
            cat_count += 1
        except Exception as e:
            print(f"  ERROR category {cat_slug}: {e}")

    src_count = 0
    for src_slug, src_data in sources.items():
        try:
            generate_source_page(src_slug, src_data, SITE_DIR)
            src_count += 1
        except Exception as e:
            print(f"  ERROR source {src_slug}: {e}")

    tag_count = 0
    for tag_slug, tag_data in tags.items():
        try:
            generate_tag_page(tag_slug, tag_data, SITE_DIR)
            tag_count += 1
        except Exception as e:
            print(f"  ERROR tag {tag_slug}: {e}")

    # Generate index listing pages
    generate_category_index(categories, SITE_DIR)
    generate_source_index(sources, SITE_DIR)
    generate_tag_index(tags, SITE_DIR)

    print(f"  Generated {cat_count} category, {src_count} source, {tag_count} tag pages")
    print()

    # 5. Generate robots.txt and sitemap.xml
    print("[5/6] Generating robots.txt and sitemap.xml...")
    generate_robots_txt(SITE_DIR)
    sitemap_pages = build_sitemap_pages(gaps, categories, sources, tags)
    generate_sitemap(sitemap_pages, SITE_DIR)
    print(f"  Sitemap: {len(sitemap_pages)} pages")
    print()

    # 6. Summary
    print("[6/6] Summary")
    print("=" * 60)
    print(f"  Gap pages:       {gap_count}")
    print(f"  Category pages:  {cat_count}")
    print(f"  Source pages:    {src_count}")
    print(f"  Tag pages:       {tag_count}")
    print(f"  Total pages:     {gap_count + cat_count + src_count + tag_count + 3}")
    print(f"  Sitemap entries: {len(sitemap_pages)}")
    print("=" * 60)
    print("Done!")


if __name__ == "__main__":
    main()
