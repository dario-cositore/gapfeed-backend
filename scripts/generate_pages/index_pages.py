"""
Index and detail page generators for categories, sources, and tags.
"""

import os
from .base_template import render_html_page, render_breadcrumbs_html, render_heat_badge

def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def _write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def generate_category_index(categories, output_dir):
    """
    Generate the category index page listing all categories.

    Args:
        categories: dict mapping category_slug to {"name": "...", "count": N, "gaps": [...]}
        output_dir: base output directory (e.g., "website/gapfeed.com")
    """
    index_path = os.path.join(output_dir, "categories", "index.html")
    _ensure_dir(os.path.dirname(index_path))

    cards_html = ""
    for slug, data in categories.items():
        name = data["name"]
        count = data["count"]
        cards_html += f'''<div class="card">
  <h3 class="card-title"><a href="/categories/{slug}.html">{name}</a></h3>
  <p class="card-content">{count} gaps</p>
</div>
'''

    content = f'''<h1>Browse Gaps by Category</h1>
<p>Explore market gaps organized by category. Each category represents a cluster of related unsolved problems discovered from real internet signals.</p>
<div class="grid grid-3">
{cards_html}
</div>'''

    breadcrumbs = [("Home", "/"), ("Categories", "/categories/")]

    json_ld_blocks = [
        {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": "Market Gap Categories",
            "description": "Explore market gaps organized by category.",
            "url": "https://gapfeed.com/categories/"
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://gapfeed.com/"},
                {"@type": "ListItem", "position": 2, "name": "Categories", "item": "https://gapfeed.com/categories/"}
            ]
        }
    ]

    html = render_html_page(
        title="Market Gap Categories | GapFeed",
        meta_description="Explore market gaps organized by category. Each category represents a cluster of related unsolved problems discovered from real internet signals.",
        canonical_url="https://gapfeed.com/categories/",
        content_html=content,
        breadcrumbs=breadcrumbs,
        json_ld_blocks=json_ld_blocks,
        page_type='category'
    )

    _write_file(index_path, html)

def generate_category_page(category_slug, category_data, output_dir):
    """
    Generate a category detail page showing gaps for this category.

    Args:
        category_slug: slug for the category
        category_data: dict with keys: "name", "count", "gaps" (list of gap dicts). May include "related_categories".
        output_dir: base output directory
    """
    name = category_data["name"]
    count = category_data["count"]
    gaps = category_data.get("gaps", [])

    # Build gap cards
    gap_cards = []
    for gap in gaps:
        title = gap["title"]
        slug = gap["slug"]
        description = gap.get("description", "")[:200] if len(gap.get("description", "")) > 200 else gap.get("description", "")
        description = description.rstrip() + ('...' if len(gap.get("description", "")) > 200 else '')
        heat_score = gap.get("heat_score", 0.5)
        evidence_count = gap.get("evidence_count", 0)
        gap_url = f"/gap/{slug}.html"
        heat_badge = render_heat_badge(heat_score)

        tags_html = ""
        # Category tags
        for cat_slug in gap.get("categories", []):
            cat_name = cat_slug.replace('-', ' ').title()
            tags_html += f'<a href="/categories/{cat_slug}.html" class="tag-chip">{cat_name}</a> '
        # Source type tags
        for src in gap.get("source_types", []):
            src_name = src.title()
            tags_html += f'<a href="/sources/{src}.html" class="tag-chip">{src_name}</a> '

        gap_card = f'''<div class="card">
  <h3 class="card-title"><a href="{gap_url}">{title}</a></h3>
  <p class="card-content">{description}</p>
  <div class="mt-4">
    {heat_badge}
    <span class="text-muted">Evidence: {evidence_count}</span>
  </div>
  <div class="mt-4">
    {tags_html}
  </div>
</div>
'''
        gap_cards.append(gap_card)

    gaps_grid = '<div class="grid grid-3">\n' + '\n'.join(gap_cards) + '\n</div>'

    intro = f'''<p>Discover valuable market gaps and unsolved problems in the {name} category. These opportunities represent real needs waiting for innovative solutions.</p>'''
    count_display = f'<p class="mt-4"><strong>{count} gaps</strong> found in {name}.</p>'

    content = f'''<h1>{name} Market Gaps</h1>
{intro}
{count_display}
{gaps_grid}'''

    # Related categories
    related = category_data.get("related_categories")
    if not related:
        # Compute from gap categories, exclude current
        cat_counter = {}
        for gap in gaps:
            for cat_slug in gap.get("categories", []):
                if cat_slug != category_slug:
                    cat_counter[cat_slug] = cat_counter.get(cat_slug, 0) + 1
        sorted_cats = sorted(cat_counter.items(), key=lambda x: x[1], reverse=True)[:4]
        related = [(slug, slug.replace('-', ' ').title()) for slug, _ in sorted_cats]

    if related:
        related_links = ""
        for slug, label in related:
            related_links += f'<a href="/categories/{slug}.html" class="pill">{label}</a> '
        content += f'''<div class="mt-8">
  <h3>Related Categories</h3>
  <div class="mt-4">{related_links}</div>
</div>'''

    breadcrumbs = [
        ("Home", "/"),
        ("Categories", "/categories/"),
        (name, f"/categories/{category_slug}.html")
    ]

    # ItemList for gaps
    item_list = []
    for i, gap in enumerate(gaps, start=1):
        item_list.append({
            "@type": "ListItem",
            "position": i,
            "name": gap["title"],
            "url": f"https://gapfeed.com/gap/{gap['slug']}.html"
        })

    json_ld_blocks = [
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://gapfeed.com/"},
                {"@type": "ListItem", "position": 2, "name": "Categories", "item": "https://gapfeed.com/categories/"},
                {"@type": "ListItem", "position": 3, "name": name, "item": f"https://gapfeed.com/categories/{category_slug}.html"}
            ]
        },
        {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": item_list
        }
    ]

    html = render_html_page(
        title=f"{name} Market Gaps | GapFeed",
        meta_description=f"Explore {count} market gaps in {name}. Discover unsolved problems and opportunities.",
        canonical_url=f"https://gapfeed.com/categories/{category_slug}.html",
        content_html=content,
        breadcrumbs=breadcrumbs,
        json_ld_blocks=json_ld_blocks,
        page_type='category'
    )

    page_path = os.path.join(output_dir, "categories", f"{category_slug}.html")
    _write_file(page_path, html)

def generate_source_index(sources, output_dir):
    """
    Generate the source index page listing all data sources.

    Args:
        sources: dict mapping source_slug to {"name": "...", "count": N, "gaps": [...], maybe "description": "..."}
        output_dir: base output directory
    """
    index_path = os.path.join(output_dir, "sources", "index.html")
    _ensure_dir(os.path.dirname(index_path))

    cards = []
    for slug, data in sources.items():
        name = data["name"]
        count = data["count"]
        desc = data.get("description", "")
        card = f'''<div class="card">
  <h3 class="card-title"><a href="/sources/{slug}.html">{name}</a></h3>
  <p class="card-content">{count} gaps</p>
  {f'<p class="text-dim">{desc[:100]}{"..." if len(desc) > 100 else ""}</p>' if desc else ''}
</div>
'''
        cards.append(card)

    grid = '<div class="grid grid-3">\n' + '\n'.join(cards) + '\n</div>'

    content = f'''<h1>Data Sources</h1>
<p>Discover where GapFeed finds market gaps. Each source provides unique signals that help identify unsolved problems and opportunities.</p>
{grid}'''

    breadcrumbs = [("Home", "/"), ("Sources", "/sources/")]

    json_ld_blocks = [
        {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": "Data Sources",
            "description": "List of data sources used by GapFeed to discover market gaps.",
            "url": "https://gapfeed.com/sources/"
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://gapfeed.com/"},
                {"@type": "ListItem", "position": 2, "name": "Sources", "item": "https://gapfeed.com/sources/"}
            ]
        }
    ]

    html = render_html_page(
        title="Data Sources | GapFeed",
        meta_description="Explore the data sources that power GapFeed's market gap discovery. Learn where we find unsolved problems and opportunities.",
        canonical_url="https://gapfeed.com/sources/",
        content_html=content,
        breadcrumbs=breadcrumbs,
        json_ld_blocks=json_ld_blocks,
        page_type='source'
    )

    _write_file(index_path, html)

def generate_source_page(source_slug, source_data, output_dir):
    """
    Generate a source detail page showing gaps from this source.

    Args:
        source_slug: slug for the source
        source_data: dict with keys: "name", "count", "gaps" (list), maybe "description", "percentage"
        output_dir: base output directory
    """
    name = source_data["name"]
    count = source_data["count"]
    description = source_data.get("description", f"Market signals extracted from {name}.")
    percentage = source_data.get("percentage")
    gaps = source_data.get("gaps", [])

    gap_cards = []
    for gap in gaps:
        title = gap["title"]
        slug = gap["slug"]
        desc_snippet = gap.get("description", "")[:200] if len(gap.get("description", "")) > 200 else gap.get("description", "")
        desc_snippet = desc_snippet.rstrip() + ('...' if len(gap.get("description", "")) > 200 else '')
        heat_score = gap.get("heat_score", 0.5)
        evidence_count = gap.get("evidence_count", 0)
        gap_url = f"/gap/{slug}.html"
        heat_badge = render_heat_badge(heat_score)

        tags_html = ""
        for cat_slug in gap.get("categories", []):
            cat_name = cat_slug.replace('-', ' ').title()
            tags_html += f'<a href="/categories/{cat_slug}.html" class="tag-chip">{cat_name}</a> '
        for src in gap.get("source_types", []):
            src_name = src.title()
            tags_html += f'<a href="/sources/{src}.html" class="tag-chip">{src_name}</a> '

        gap_card = f'''<div class="card">
  <h3 class="card-title"><a href="{gap_url}">{title}</a></h3>
  <p class="card-content">{desc_snippet}</p>
  <div class="mt-4">
    {heat_badge}
    <span class="text-muted">Evidence: {evidence_count}</span>
  </div>
  <div class="mt-4">
    {tags_html}
  </div>
</div>
'''
        gap_cards.append(gap_card)

    gaps_grid = '<div class="grid grid-3">\n' + '\n'.join(gap_cards) + '\n</div>'

    count_text = f"{count} gaps"
    if percentage is not None:
        count_text += f" ({percentage:.1f}% of total)"
    count_display = f'<p class="mt-4"><strong>{count_text}</strong></p>'

    content = f'''<h1>{name} Market Signals</h1>
<p>{description}</p>
{count_display}
{gaps_grid}'''

    breadcrumbs = [
        ("Home", "/"),
        ("Sources", "/sources/"),
        (name, f"/sources/{source_slug}.html")
    ]

    json_ld_blocks = [
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://gapfeed.com/"},
                {"@type": "ListItem", "position": 2, "name": "Sources", "item": "https://gapfeed.com/sources/"},
                {"@type": "ListItem", "position": 3, "name": name, "item": f"https://gapfeed.com/sources/{source_slug}.html"}
            ]
        }
    ]

    html = render_html_page(
        title=f"{name} Market Signals | GapFeed",
        meta_description=f"{description[:155]}{'...' if len(description) > 155 else ''} Discover {count} market signals from {name} on GapFeed.",
        canonical_url=f"https://gapfeed.com/sources/{source_slug}.html",
        content_html=content,
        breadcrumbs=breadcrumbs,
        json_ld_blocks=json_ld_blocks,
        page_type='source'
    )

    page_path = os.path.join(output_dir, "sources", f"{source_slug}.html")
    _write_file(page_path, html)

def generate_tag_index(tags, output_dir):
    """
    Generate the tag index page.

    Args:
        tags: dict mapping tag_slug to {"name": "...", "count": N, "gaps": [...]}
        output_dir: base output directory
    """
    index_path = os.path.join(output_dir, "tags", "index.html")
    _ensure_dir(os.path.dirname(index_path))

    tag_cards = []
    for slug, data in tags.items():
        name = data["name"]
        count = data["count"]
        tag_cards.append(f'''<div class="card text-center">
  <h3 class="card-title"><a href="/tags/{slug}.html">{name}</a></h3>
  <p class="card-content">{count} gaps</p>
</div>
''')

    grid = '<div class="grid grid-4">\n' + '\n'.join(tag_cards) + '\n</div>'

    content = f'''<h1>Tags</h1>
<p>Browse market gaps by tag. Each tag represents a specific technology, industry, or theme.</p>
{grid}'''

    breadcrumbs = [("Home", "/"), ("Tags", "/tags/")]

    json_ld_blocks = [
        {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": "Tags",
            "description": "Browse market gaps by tag on GapFeed.",
            "url": "https://gapfeed.com/tags/"
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://gapfeed.com/"},
                {"@type": "ListItem", "position": 2, "name": "Tags", "item": "https://gapfeed.com/tags/"}
            ]
        }
    ]

    html = render_html_page(
        title="Tags | GapFeed",
        meta_description="Browse market gaps by tag on GapFeed. Explore opportunities by technology, industry, and theme.",
        canonical_url="https://gapfeed.com/tags/",
        content_html=content,
        breadcrumbs=breadcrumbs,
        json_ld_blocks=json_ld_blocks,
        page_type='tag'
    )

    _write_file(index_path, html)

def generate_tag_page(tag_slug, tag_data, output_dir):
    """
    Generate a tag detail page showing gaps with this tag.

    Args:
        tag_slug: slug for the tag
        tag_data: dict with keys: "name", "count", "gaps" (list)
        output_dir: base output directory
    """
    name = tag_data["name"]
    count = tag_data["count"]
    gaps = tag_data.get("gaps", [])

    gap_cards = []
    for gap in gaps:
        title = gap["title"]
        slug = gap["slug"]
        desc = gap.get("description", "")[:200] if len(gap.get("description", "")) > 200 else gap.get("description", "")
        desc = desc.rstrip() + ('...' if len(gap.get("description", "")) > 200 else '')
        heat_score = gap.get("heat_score", 0.5)
        evidence_count = gap.get("evidence_count", 0)
        gap_url = f"/gap/{slug}.html"
        heat_badge = render_heat_badge(heat_score)

        tags_html = ""
        for cat_slug in gap.get("categories", []):
            cat_name = cat_slug.replace('-', ' ').title()
            tags_html += f'<a href="/categories/{cat_slug}.html" class="tag-chip">{cat_name}</a> '
        for src in gap.get("source_types", []):
            src_name = src.title()
            tags_html += f'<a href="/sources/{src}.html" class="tag-chip">{src_name}</a> '

        gap_card = f'''<div class="card">
  <h3 class="card-title"><a href="{gap_url}">{title}</a></h3>
  <p class="card-content">{desc}</p>
  <div class="mt-4">
    {heat_badge}
    <span class="text-muted">Evidence: {evidence_count}</span>
  </div>
  <div class="mt-4">
    {tags_html}
  </div>
</div>
'''
        gap_cards.append(gap_card)

    gaps_grid = '<div class="grid grid-3">\n' + '\n'.join(gap_cards) + '\n</div>'

    content = f'''<h1>{name} Market Gaps</h1>
<p>Explore market gaps tagged with {name}. Find unsolved problems and opportunities related to this tag.</p>
<div class="mt-4"><strong>{count} gaps</strong></div>
{gaps_grid}'''

    # Related categories
    cat_counter = {}
    for gap in gaps:
        for cat_slug in gap.get("categories", []):
            cat_counter[cat_slug] = cat_counter.get(cat_slug, 0) + 1
    top_cats = sorted(cat_counter.items(), key=lambda x: x[1], reverse=True)[:4]
    if top_cats:
        related_links = ""
        for slug, _ in top_cats:
            label = slug.replace('-', ' ').title()
            related_links += f'<a href="/categories/{slug}.html" class="pill">{label}</a> '
        content += f'''<div class="mt-8">
  <h3>Related Categories</h3>
  <div class="mt-4">{related_links}</div>
</div>'''

    breadcrumbs = [
        ("Home", "/"),
        ("Tags", "/tags/"),
        (name, f"/tags/{tag_slug}.html")
    ]

    item_list = []
    for i, gap in enumerate(gaps, start=1):
        item_list.append({
            "@type": "ListItem",
            "position": i,
            "name": gap["title"],
            "url": f"https://gapfeed.com/gap/{gap['slug']}.html"
        })

    json_ld_blocks = [
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://gapfeed.com/"},
                {"@type": "ListItem", "position": 2, "name": "Tags", "item": "https://gapfeed.com/tags/"},
                {"@type": "ListItem", "position": 3, "name": name, "item": f"https://gapfeed.com/tags/{tag_slug}.html"}
            ]
        },
        {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": item_list
        }
    ]

    html = render_html_page(
        title=f"{name} Market Gaps | GapFeed",
        meta_description=f"Explore {count} market gaps tagged with {name}. Discover unsolved problems and opportunities.",
        canonical_url=f"https://gapfeed.com/tags/{tag_slug}.html",
        content_html=content,
        breadcrumbs=breadcrumbs,
        json_ld_blocks=json_ld_blocks,
        page_type='tag'
    )

    page_path = os.path.join(output_dir, "tags", f"{tag_slug}.html")
    _write_file(page_path, html)
