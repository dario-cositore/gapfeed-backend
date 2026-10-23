"""
Static HTML page generator for market gap pages.

This module generates individual SEO-optimized HTML pages for each market gap,
with structured data, related gaps, and full content rendering.
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Any

# Add shared module for RemoteDB
_shared_path = str(Path(__file__).resolve().parent.parent.parent / 'shared')
if _shared_path not in sys.path:
    sys.path.insert(0, _shared_path)

from .base_template import (
    render_html_page,
    render_breadcrumbs_html,
    render_heat_badge,
    render_quote_card,
    render_share_buttons,
    slugify,
    truncate,
    BASE_CSS
)


def parse_quote(quote_str: str) -> Dict[str, Any]:
    """
    Parse a quote string in the format: [source, urgency=X.XXX] title: content

    Args:
        quote_str: Raw quote string

    Returns:
        Dict with keys: source, urgency, title, text
    """
    # Extract source and urgency from brackets
    bracket_match = re.search(r'\[([^,]+),\s*urgency=([\d.]+)\]', quote_str)
    if not bracket_match:
        return {
            "source": "Unknown",
            "urgency": 0.0,
            "title": "",
            "text": quote_str
        }

    source = bracket_match.group(1).strip()
    urgency = float(bracket_match.group(2))

    # Remove the bracket portion
    remainder = quote_str[bracket_match.end():].strip()

    # Split on first colon to get title and text
    if ':' in remainder:
        title_part, text_part = remainder.split(':', 1)
        title = title_part.strip()
        text = text_part.strip()
    else:
        title = ""
        text = remainder

    return {
        "source": source,
        "urgency": urgency,
        "title": title,
        "text": text
    }


def derive_tags(gap: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Extract 2-5 meaningful tags from category and description.

    Args:
        gap: Gap dictionary with category and description

    Returns:
        List of (tag_name, tag_slug) tuples
    """
    # Start with category as a tag
    tags = []
    if gap.get('category'):
        cat_slug = slugify(gap['category'])
        tags.append((gap['category'], cat_slug))

    # Extract keywords from description
    description = gap.get('description', '').lower()

    # Common filler words to skip
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
        'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
        'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those',
        'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which', 'who',
        'when', 'where', 'why', 'how', 'all', 'each', 'every', 'both', 'few',
        'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only',
        'own', 'same', 'so', 'than', 'too', 'very', 'just', 'here', 'there',
        'now', 'then', 'well', 'how', 'again', 'further', 'however', 'thus',
        'therefore', 'hence', 'indeed', 'meanwhile', 'nevertheless', 'nonetheless'
    }

    # Extract words from description, filter stopwords, keep only meaningful ones
    words = re.findall(r'\b[a-z]{3,}\b', description)
    word_freq = {}
    for word in words:
        if word not in stop_words:
            word_freq[word] = word_freq.get(word, 0) + 1

    # Sort by frequency, take top candidates
    candidates = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

    # Add top keywords as tags (up to 3 more, total max 5)
    for word, freq in candidates:
        if len(tags) >= 5:
            break
        # Avoid duplicates with category
        if word not in [t[0].lower() for t in tags]:
            tags.append((word.title(), word))

    return tags


def find_related_gaps(
    gap: Dict[str, Any],
    all_gaps: List[Dict[str, Any]],
    max_count: int = 8
) -> List[Dict[str, Any]]:
    """
    Find related gaps based on category, source types, and keyword overlap.

    Args:
        gap: Current gap dictionary
        all_gaps: List of all gaps
        max_count: Maximum number of related gaps to return

    Returns:
        List of related gap dictionaries (excluding self)
    """
    related = []
    current_category = gap.get('category', '').lower()
    current_sources = set(gap.get('source_types', []))
    current_desc = gap.get('description', '').lower()
    current_title = gap.get('title', '').lower()

    for other_gap in all_gaps:
        # Skip self
        if other_gap.get('id') == gap.get('id'):
            continue

        score = 0
        reasons = []

        # 1. Same category (highest priority, up to 3)
        other_category = other_gap.get('category', '').lower()
        if current_category and other_category and current_category == other_category:
            score += 3
            reasons.append('category')

        # 2. Shared source types (medium priority, up to 2)
        other_sources = set(other_gap.get('source_types', []))
        shared_sources = current_sources.intersection(other_sources)
        if shared_sources:
            shared_count = len(shared_sources)
            score += min(shared_count, 2)
            reasons.append('sources')

        # 3. Keyword overlap in title/description (lower priority, up to 3)
        other_desc = other_gap.get('description', '').lower()
        other_title = other_gap.get('title', '').lower()

        # Extract significant words (4+ chars, not stop words)
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'
        }

        current_words = set(w for w in re.findall(r'\b[a-z]{4,}\b', current_desc + ' ' + current_title) if w not in stop_words)
        other_words = set(w for w in re.findall(r'\b[a-z]{4,}\b', other_desc + ' ' + other_title) if w not in stop_words)

        overlap = len(current_words.intersection(other_words))
        if overlap > 0:
            score += min(overlap, 3)
            reasons.append('keywords')

        if score > 0:
            related.append({
                'gap': other_gap,
                'score': score,
                'reasons': reasons
            })

    # Sort by score descending
    related.sort(key=lambda x: x['score'], reverse=True)

    # Return just the gap dicts (not the metadata)
    return [item['gap'] for item in related[:max_count]]


def generate_summary_section(description: str) -> str:
    """
    Generate 2-3 keyword-rich summary paragraphs from description.

    Args:
        description: Raw gap description

    Returns:
        HTML string for summary section
    """
    # Use the description as base and expand slightly
    # Split into sentences
    sentences = re.split(r'[.!?]+', description)
    sentences = [s.strip() for s in sentences if s.strip()]

    # Take first 2-3 sentences and expand with keywords
    summary_sentences = sentences[:min(3, len(sentences))]

    # Keywords to sprinkle in
    keywords = ['market gap', 'unsolved problem', 'product opportunity', 'unmet need', 'product idea']

    # Build paragraphs
    p1 = f"<p>{summary_sentences[0] if summary_sentences else description[:150]}</p>"

    if len(summary_sentences) > 1:
        p2 = f"<p>{summary_sentences[1]}</p>"
    else:
        # Expand with keywords
        p2 = f"<p>This represents a significant {keywords[0]} that remains unaddressed by current solutions. Many users struggle with this {keywords[1]}, creating a clear {keywords[2]} for innovative companies.</p>"

    if len(summary_sentences) > 2:
        p3 = f"<p>{summary_sentences[2]}</p>"
    else:
        p3 = ""

    paragraphs = [p1, p2] + ([p3] if p3 else [])
    return f'<section class="card">\n  <h2>Summary</h2>\n{"".join(paragraphs)}\n</section>'


def expand_problem_description(description: str) -> str:
    """
    Expand and rewrite the full description to be more detailed and SEO-rich.

    Args:
        description: Original raw description

    Returns:
        Expanded HTML content with 2-3 paragraphs
    """
    # Split into sentences
    sentences = re.split(r'[.!?]+', description)
    sentences = [s.strip() for s in sentences if s.strip()]

    # Create 2-3 paragraphs
    if len(sentences) >= 4:
        p1 = ' '.join(sentences[:2])
        p2 = ' '.join(sentences[2:4])
        p3 = ' '.join(sentences[4:]) if len(sentences) > 4 else ''
    elif len(sentences) >= 2:
        p1 = ' '.join(sentences[:len(sentences)//2])
        p2 = ' '.join(sentences[len(sentences)//2:])
        p3 = ''
    else:
        p1 = description
        p2 = "This issue affects many users who often express frustration over the lack of adequate solutions. Existing options are either too complex, too expensive, or simply do not address the core needs effectively."
        p3 = ""

    # SEO enrich: add relevant phrases
    seo_phrases = [
        "market gap",
        "unmet need",
        "product opportunity",
        "unsolved problem",
        "user pain point"
    ]

    # Insert a phrase in paragraph 2 if it exists
    if p2:
        p2 = f"From a business perspective, this is a {seo_phrases[0]} that presents a {seo_phrases[2]} for those who can build the right solution. {p2}"

    paragraphs = [f"<p>{p}</p>" for p in [p1, p2] if p]
    if p3:
        paragraphs.append(f"<p>{p3}</p>")

    return f'<section class="card">\n  <h2>Problem Description</h2>\n{"".join(paragraphs)}\n</section>'


def generate_who_feels_section(gap: Dict[str, Any]) -> str:
    """
    Generate "Who Feels This" section based on gap data.

    Args:
        gap: Gap dictionary

    Returns:
        HTML string
    """
    description = gap.get('description', '')
    source_types = gap.get('source_types', [])

    # Try to infer audience from description keywords
    audience_indicators = {
        'developers': ['developer', 'programmer', 'engineer', 'coding', 'api', 'library', 'framework'],
        'designers': ['designer', 'ui', 'ux', 'graphic', 'creative', 'figma', 'sketch'],
        'small business': ['small business', 'startup', 'sme', 'entrepreneur', 'shop', 'store'],
        'enterprise': ['enterprise', 'corporation', 'company', 'large', 'scale', 'team'],
        'students': ['student', 'learning', 'education', 'university', 'college', 'course'],
        'marketers': ['marketing', 'seo', 'advertising', 'campaign', 'social media', 'content'],
        'freelancers': ['freelancer', 'contractor', 'consultant', 'independent', 'gig']
    }

    audience = "users and professionals"
    for audience_name, keywords in audience_indicators.items():
        if any(keyword in description.lower() for keyword in keywords):
            audience = audience_name
            break

    # Describe who complains based on source types
    source_desc = ""
    if source_types:
        source_names = [s.replace('-', ' ').title() for s in source_types]
        if len(source_names) == 1:
            source_desc = f"Discussions on {source_names[0]} reveal consistent frustration."
        elif len(source_names) == 2:
            source_desc = f"Discussions on {source_names[0]} and {source_names[1]} highlight this pain point."
        else:
            source_desc = f"Discussions across platforms like {', '.join(source_names[:2])} and others show widespread concern."
    else:
        source_desc = "User feedback consistently highlights this pain point."

    html = f'''<section class="card">
  <h2>Who Feels This</h2>
  <p>This problem affects <strong>{audience}</strong>. {source_desc} The issue comes up repeatedly in conversations about {_readable_category(gap.get('category', 'workflow tools'))}.</p>
</section>'''

    return html


def is_clean_quote(quote_text: str) -> bool:
    """
    Filter out messy/noisy quotes that shouldn't be displayed.

    Only keeps quotes that are real, complete, indexable thoughts.
    """
    if not quote_text:
        return False

    # Strip Maya's metadata prefix [source, urgency=X.XXX]
    text = re.sub(r'\[[^\]]+,\s*urgency=[\d.]+\]\s*', '', quote_text).strip()

    if len(text) < 80:  # Too short after stripping prefix
        return False

    # Must end with punctuation (complete thought, not truncated)
    # Exception: if >=195 chars, it's likely truncated by MySQL, allow it
    is_truncated = len(quote_text) >= 195  # MySQL truncation
    if not is_truncated and not text[-1] in '.!?)"\'':
        return False

    # Must have at least 12 words (complete thought)
    if len(text.split()) < 12:
        return False

    # Reject Reddit metadata patterns
    noise_patterns = [
        r'^(u/|r/|throwaway|deleted|removed)',
        r'^(Hi ev|Hello ev|Hey ev)',
        r'^(I am a bot|this action was performed)',
        r'>>',
        r'Thank you for your submission',
        r'Your post has been removed',
        r'Your comment has been removed',
        r'^(Edit:|UPDATE:|ETA:)',
        r'\[removed\]',
        r'\[deleted\]',
    ]
    for pattern in noise_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return False

    # Reject if it looks like a URL or code block
    if text.startswith('http') or text.startswith('```'):
        return False

    # Reject if mostly non-alphabetic (lots of symbols/numbers)
    alpha_ratio = sum(1 for c in text if c.isalpha()) / len(text)
    if alpha_ratio < 0.6:
        return False

    return True


def filter_quotes(quotes: list[str], min_count: int = 3, max_count: int = 8) -> list[str]:
    """
    Filter quotes down to the cleanest, most indexable ones.
    """
    import re
    clean = [q for q in quotes if is_clean_quote(q)]

    # Prefer longer quotes (more meaty)
    clean.sort(key=len, reverse=True)

    return clean[:max_count]


def generate_evidence_section(sample_quotes) -> str:
    """
    Generate "Evidence" section with parsed quote cards.

    Args:
        sample_quotes: List of quote strings OR list of {text, source, url} objects

    Returns:
        HTML string
    """
    if not sample_quotes:
        return ""

    # Normalize to object format
    normalized = []
    for q in sample_quotes:
        if isinstance(q, dict):
            # New format: {text, source, url} - already curated by Maya
            normalized.append(q)
        elif isinstance(q, str):
            # Old format: string with [source, urgency=X] prefix
            parsed = parse_quote(q)
            normalized.append({
                'text': parsed['text'],
                'source': parsed['source'],
                'url': '',
            })

    # Filter: object format (Maya-curated) needs only min 30 chars
    # String format needs full noise filter
    is_object_format = len(sample_quotes) > 0 and isinstance(sample_quotes[0], dict)
    if is_object_format:
        filtered = [q for q in normalized if len(q.get('text', '')) >= 30]
    else:
        filtered = [q for q in normalized if is_clean_quote(q.get('text', ''))]
    if not filtered:
        return ""

    # Prefer longer quotes
    filtered.sort(key=lambda q: len(q.get('text', '')), reverse=True)
    filtered = filtered[:8]

    cards_html = []
    for q in filtered:
        text = q.get('text', '')
        source = q.get('source', 'unknown')
        url = q.get('url', '')

        # Use title from parsed quote if available, else source
        parsed = parse_quote(text) if '[' in text else {'title': '', 'text': text}
        source_attr = parsed['title'] if parsed['title'] else source

        cards_html.append(render_quote_card(parsed['text'], source_attr, url if url else None))

    quotes_section = f'''<section class="card">
  <h2>Real Quotes From Real People</h2>
  {"".join(cards_html)}
</section>'''

    return quotes_section


def generate_why_matters_section(description: str, category: str) -> str:
    """
    Generate "Why This Matters" opportunity framing.

    Args:
        description: Gap description
        category: Gap category

    Returns:
        HTML string
    """
    keywords = ['market gap', 'product opportunity', 'unmet need', 'unsolved problem']

    content = f'''<section class="card">
  <h2>Why This Matters</h2>
  <p>This gap represents a potential {keywords[2]} because solving it would address a consistent pain point mentioned by many users. Current solutions either do not exist or fall short, creating a clear opening for a new {keywords[1]} in the {category} space.</p>
  <p>Businesses that can effectively solve this problem stand to gain early mover advantage, strong user loyalty, and significant market share in an underserved segment.</p>
</section>'''

    return content


def _readable_category(cat: str) -> str:
    """Convert raw category slug to human-readable name."""
    mapping = {
        'pricing_complaints': 'pricing transparency',
        'workflow_automation': 'workflow automation',
        'developer_tools': 'developer tooling',
        'saas': 'SaaS',
        'fintech': 'financial technology',
        'healthtech': 'health technology',
        'edtech': 'education technology',
        'ecommerce': 'e-commerce',
        'productivity': 'productivity',
        'ai_ml': 'AI/ML',
        'devtools': 'developer tooling',
        'bi_analytics': 'analytics',
        'security': 'security',
        'no_code': 'no-code',
        'api_tools': 'API tooling',
        'collaboration': 'team collaboration',
        'project_management': 'project management',
        'crm': 'CRM',
        'marketing': 'marketing',
        'social_media': 'social media',
        'communication': 'communication',
        'data_management': 'data management',
    }
    slug = cat.lower().replace(' ', '_').replace('-', '_')
    if slug in mapping:
        return mapping[slug]
    # Fallback: convert underscores to spaces and title case
    return slug.replace('_', ' ').title()


def generate_business_opportunity_section(gap: Dict[str, Any]) -> str:
    """
    Generate "Business Opportunity" section with auto-generated product ideas.

    Args:
        gap: Gap dictionary

    Returns:
        HTML string
    """
    raw_category = gap.get('category', 'tool')
    category = _readable_category(raw_category)
    description = gap.get('description', '')

    # Generate product ideas based on category and description clues
    ideas = [
        f"A {category} tool that automates the manual work and integrates seamlessly with existing workflows.",
        f"A platform for {category} that focuses on simplicity and accessibility, removing complexity barriers.",
        f"An API-first {category} service allowing developers to integrate this functionality directly into their applications."
    ]

    # Customize based on category keywords
    if 'mobile' in description.lower() or 'app' in description.lower():
        ideas[0] = f"A mobile-first {category} app that solves this problem on the go, with offline capabilities."
    if 'team' in description.lower() or 'collaboration' in description.lower():
        ideas[1] = f"A collaborative {category} platform with real-time features and team management capabilities."

    bullets = ''.join(f'  <li>{idea}</li>\n' for idea in ideas[:3])

    html = f'''<section class="card">
  <h2>Business Opportunity</h2>
  <p>Product ideas that could solve this:</p>
  <ul>
{bullets}  </ul>
</section>'''

    return html


def generate_source_breakdown(gap: Dict[str, Any]) -> str:
    """
    Generate "Source Breakdown" section showing signal distribution.

    Args:
        gap: Gap dictionary

    Returns:
        HTML string
    """
    source_types = gap.get('source_types', [])
    evidence_count = gap.get('evidence_count', 0)

    if not source_types or evidence_count == 0:
        return ""

    # Calculate per-source distribution (equal split if unknown counts)
    count_per_source = evidence_count // len(source_types)
    remainder = evidence_count % len(source_types)

    parts = [f'<p>This gap was identified from <strong>{evidence_count}</strong> signals across {len(source_types)} source types:</p>']
    parts.append('<ul>')

    for i, source in enumerate(source_types):
        count = count_per_source + (1 if i < remainder else 0)
        percentage = (count / evidence_count * 100) if evidence_count > 0 else 0
        source_name = source.replace('-', ' ').title()
        parts.append(f'  <li><strong>{source_name}</strong>: {count} signals ({percentage:.0f}%)</li>')

    parts.append('</ul>')

    html = f'''<section class="card">
  <h2>Source Analysis</h2>
{chr(10).join(parts)}
</section>'''

    return html


def _is_listicle(name: str, url: str, description: str) -> bool:
    """Filter out listicles, blogs, and 'top 10' type results."""
    noise_signals = [
        'top 10', 'top 5', 'best ', 'best of', 'review', 'comparison',
        'alternative', 'alternatives to', 'vs ', 'versus',
        'list of', 'guide to', 'how to choose',
        'forbes.com', 'nerdwallet.com', 'investopedia.com', 'bankrate.com',
        'techcrunch.com', 'thebalancemoney.com', 'wallethack', 'centsai',
        'blog.', '/blog/', 'medium.com', 'quora.com', 'reddit.com',
    ]
    combined = (name + ' ' + url + ' ' + description).lower()
    return any(s in combined for s in noise_signals)


def _is_real_product(name: str, url: str) -> bool:
    """Check if this looks like a real product (has a domain, not a blog post)."""
    if not url or url == '#':
        return False
    # Must have a real domain
    import re
    if not re.match(r'https?://', url):
        return False
    # Skip if name is too generic
    generic_names = {'app', 'platform', 'tool', 'software', 'service', 'solution'}
    if name.lower().strip() in generic_names:
        return False
    return True


def generate_competitive_landscape_section(gap: Dict[str, Any]) -> str:
    """
    Generate Competitive Landscape section - Phase 1.5 implementation.

    Filters out noise, shows verdict + up to 4 real competitors with
    "why it falls short" insight. Falls back to "No direct competitor found"
    with a meaningful insight sentence.

    Args:
        gap: Gap dictionary with competitors JSON, gap_validity, scoring

    Returns:
        HTML string
    """
    import json as json_mod

    # Parse competitors
    raw_competitors = gap.get('competitors', [])
    if raw_competitors is None:
        raw_competitors = []
    if isinstance(raw_competitors, str):
        try:
            raw_competitors = json_mod.loads(raw_competitors)
        except (json_mod.JSONDecodeError, TypeError):
            raw_competitors = []
    if not isinstance(raw_competitors, list):
        raw_competitors = []

    # Filter: remove listicles, keep real products
    valid_competitors = []
    for c in raw_competitors:
        name = c.get('name', '')
        url = c.get('url', '')
        desc = c.get('description', '')
        is_valid = c.get('is_valid', True)

        if not is_valid:
            continue
        if _is_listicle(name, url, desc):
            continue
        if not _is_real_product(name, url):
            continue

        valid_competitors.append(c)

    # Cap at 4
    valid_competitors = valid_competitors[:4]

    # Verdict
    gap_validity = gap.get('gap_validity', 'unvalidated')
    scoring = gap.get('scoring', {})
    if isinstance(scoring, str):
        try:
            scoring = json_mod.loads(scoring)
        except (json_mod.JSONDecodeError, TypeError):
            scoring = {}

    verdict = scoring.get('verdict', gap_validity)

    verdict_map = {
        'wide_open': ('No direct competitor found.', '#4ade80'),
        'high_opportunity': ('No direct competitor found.', '#4ade80'),
        'unvalidated': ('No direct competitor found.', '#94a3b8'),
        'moderate_opportunity': ('A few partial solutions exist.', '#fbbf24'),
        'competitive': ('Several competitors in this space.', '#fbbf24'),
        'saturated': ('Market is well-served by existing tools.', '#ef4444'),
    }

    # Also check gap_validity
    validity_map = {
        'high': ('No direct competitor found.', '#4ade80'),
        'medium': ('A few partial solutions exist.', '#fbbf24'),
        'low': ('Market is well-served by existing tools.', '#ef4444'),
        'unvalidated': ('No direct competitor found.', '#94a3b8'),
    }

    verdict_text, verdict_color = verdict_map.get(verdict, validity_map.get(gap_validity, ('No direct competitor found.', '#94a3b8')))

    # Insight sentence - derive from gap description
    description = gap.get('description', '')
    category = _readable_category(gap.get('category', 'tools'))

    if not valid_competitors:
        insight = (
            f"While there are many {category} tools on the market, "
            f"none currently address this specific problem comprehensively. "
            f"The gap remains wide open for a purpose-built solution."
        )
    else:
        insight = (
            f"Existing {category} tools partially touch this space, "
            f"but none offer a complete solution to the specific problem described above."
        )

    # Build HTML
    verdict_html = f'<div style="margin-bottom:12px;padding:12px;background:{verdict_color}10;border-left:3px solid {verdict_color};border-radius:0 6px 6px 0;font-size:14px;line-height:1.5"><strong style="color:{verdict_color}">{verdict_text}</strong></div>'

    insight_html = f'<p style="color:var(--text-dim);font-size:0.92rem;line-height:1.6;margin-bottom:16px">{insight}</p>'

    # Competitor table
    if valid_competitors:
        rows = []
        for c in valid_competitors:
            name = c.get('name', 'Unknown')
            url = c.get('url', '#')
            desc = c.get('description', '')
            source = c.get('source', 'Web')

            # Truncate description to 1-2 sentences
            if desc:
                sentences = desc.split('.')
                desc = '. '.join(sentences[:2]).strip()
                if not desc.endswith('.'):
                    desc += '.'

            name_link = f'<a href="{url}" target="_blank" rel="noopener" style="color:var(--accent)">{name}</a>' if url != '#' else name

            rows.append(f'''<tr>
  <td style="padding:10px 12px;border-bottom:1px solid var(--border);font-weight:500">{name_link}</td>
  <td style="padding:10px 12px;border-bottom:1px solid var(--border);color:var(--text-dim);font-size:0.88rem">{desc or 'Partial solution.'}</td>
  <td style="padding:10px 12px;border-bottom:1px solid var(--border);color:var(--text-muted);font-size:0.82rem">{source}</td>
</tr>''')

        table_html = f'''<div style="overflow-x:auto;margin-top:12px">
<table style="width:100%;border-collapse:collapse;font-size:0.9rem">
  <thead>
    <tr style="border-bottom:2px solid var(--border)">
      <th style="text-align:left;padding:8px 12px;color:var(--text-muted);font-size:0.78rem;font-weight:600;text-transform:uppercase;letter-spacing:0.05em">Product</th>
      <th style="text-align:left;padding:8px 12px;color:var(--text-muted);font-size:0.78rem;font-weight:600;text-transform:uppercase;letter-spacing:0.05em">What it does</th>
      <th style="text-align:left;padding:8px 12px;color:var(--text-muted);font-size:0.78rem;font-weight:600;text-transform:uppercase;letter-spacing:0.05em">Source</th>
    </tr>
  </thead>
  <tbody>
    {"".join(rows)}
  </tbody>
</table>
</div>'''
    else:
        table_html = ''

    html = f'''<section class="card">
  <h2>Competitive Landscape</h2>
  {verdict_html}
  {insight_html}
  {table_html}
</section>'''

    return html


def generate_tags_section(gap: Dict[str, Any]) -> str:
    """
    Generate "Tags" section with keyword tags.

    Args:
        gap: Gap dictionary

    Returns:
        HTML string
    """
    tags = derive_tags(gap)

    if not tags:
        return ""

    tag_links = []
    for tag_name, tag_slug in tags:
        tag_links.append(f'<a href="/tags/{tag_slug}.html" class="tag-chip">{tag_name}</a>')

    html = f'''<section class="card">
  <h2>Tags</h2>
  <p>{"".join(tag_links)}</p>
</section>'''

    return html


def generate_related_gaps_section(related_gaps: List[Dict[str, Any]]) -> str:
    """
    Generate "Related Gaps" section with cards.

    Args:
        related_gaps: List of related gap dictionaries

    Returns:
        HTML string
    """
    if not related_gaps:
        return ""

    cards = []
    for rgap in related_gaps:
        title = rgap.get('title', 'Untitled Gap')
        slug = rgap.get('slug', slugify(title))
        heat_score = rgap.get('heat_score', 0.0)
        badge_html = render_heat_badge(heat_score)

        card_html = f'''<div class="card">
  <h3 class="card-title">
    <a href="/gap/{slug}.html">{title}</a>
  </h3>
  <div class="card-content">
    {badge_html}
  </div>
</div>'''
        cards.append(card_html)

    grid_class = f"grid-{min(4, len(cards))}" if len(cards) > 1 else ""

    html = f'''<section class="card">
  <h2>Related Market Gaps</h2>
  <div class="grid {grid_class}">
{chr(10).join(cards)}
  </div>
</section>'''

    return html


def generate_faq_section(gap: Dict[str, Any]) -> str:
    """
    Generate FAQ section with auto-generated answers.

    Args:
        gap: Gap dictionary

    Returns:
        HTML string
    """
    title = gap.get('title', '')
    description = gap.get('description', '')
    evidence_count = gap.get('evidence_count', 0)
    source_types = gap.get('source_types', [])
    category = gap.get('category', '')

    # Q1: What is the problem?
    q1_answer = f"<p>{description[:200]}{'...' if len(description) > 200 else ''}</p>"

    # Q2: Who is affected?
    q2_answer = f"<p>This issue primarily affects professionals and teams working in the {_readable_category(category)} space. Based on the signals we analyzed, users frequently mention difficulties with existing tools, time wasted on manual tasks, and the need for better integration options.</p>"

    # Q3: How often does it come up?
    source_names = [s.replace('-', ' ').title() for s in source_types[:3]]
    q3_answer = f"<p>Based on {evidence_count} signals collected from sources like {', '.join(source_names)}, this problem comes up frequently in discussions. The volume of mentions indicates it's a persistent pain point, not an isolated complaint.</p>"

    # Q4: What kind of product could solve it?
    q4_answer = f"<p>A {category} tool that simplifies the process, provides better automation, or integrates more effectively with existing workflows. The ideal solution would be easy to adopt, address the root cause of frustration, and deliver clear ROI in time saved or errors avoided.</p>"

    faq_items = [
        (f"What is the {title} problem?", q1_answer),
        (f"Who is affected by {title}?", q2_answer),
        (f"How often does {title} come up?", q3_answer),
        (f"What kind of product could solve {title}?", q4_answer)
    ]

    details_html = []
    for question, answer in faq_items:
        details_html.append(f'''<details>
  <summary>{question}</summary>
  <div class="content">
{answer}  </div>
</details>''')

    html = f'''<section class="card">
  <h2>Frequently Asked Questions</h2>
{chr(10).join(details_html)}
</section>'''

    return html


def generate_gap_page(gap: Dict[str, Any], all_gaps: List[Dict[str, Any]], output_dir: str) -> str:
    """
    Generate a complete static HTML page for a market gap.

    Args:
        gap: Gap dictionary with required fields
        all_gaps: List of all gaps (for finding related ones)
        output_dir: Base output directory (e.g., 'website/gapfeed.com')

    Returns:
        Path to the generated HTML file
    """
    # Ensure output directory exists
    gap_dir = os.path.join(output_dir, 'gap')
    os.makedirs(gap_dir, exist_ok=True)

    # Parse dates
    created_at = gap.get('created_at', '')
    updated_at = gap.get('updated_at', '')

    try:
        # Try to parse ISO date
        if created_at:
            dt_created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            date_published = dt_created.strftime('%Y-%m-%d')
        else:
            date_published = '2025-01-01'
    except Exception:
        date_published = '2025-01-01'

    try:
        if updated_at:
            dt_updated = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            date_modified = dt_updated.strftime('%Y-%m-%d')
        else:
            date_modified = date_published
    except Exception:
        date_modified = date_published

    slug = gap.get('slug', slugify(gap.get('title', 'untitled')))
    canonical_url = f"https://gapfeed.com/gap/{slug}.html"
    title = f"{gap.get('title', 'Untitled Gap')} - Unmet Market Need | GapFeed"
    meta_description = truncate(gap.get('description', ''), 155)

    # Build breadcrumbs: Home > Category > Gap Title
    category = gap.get('category', 'General')
    breadcrumbs = [
        ('Home', '/'),
        (_readable_category(category), f'/category/{slugify(category)}.html'),
        (gap.get('title', 'Gap'), canonical_url)
    ]

    # Build JSON-LD blocks
    # 1. TechArticle
    json_ld_article = {
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": gap.get('title', ''),
        "datePublished": date_published,
        "dateModified": date_modified,
        "author": {
            "@type": "Organization",
            "name": "GapFeed Research"
        },
        "publisher": {
            "@type": "Organization",
            "name": "GapFeed",
            "url": "https://gapfeed.com"
        },
        "description": meta_description,
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": canonical_url
        }
    }

    # 2. BreadcrumbList
    json_ld_breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home",
                "item": "https://gapfeed.com"
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": category,
                "item": f"https://gapfeed.com/category/{slugify(category)}.html"
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": gap.get('title', ''),
                "item": canonical_url
            }
        ]
    }

    # 3. FAQPage
    faq_questions = [
        f"What is the {gap.get('title', '')} problem?",
        f"Who is affected by {gap.get('title', '')}?",
        f"How often does {gap.get('title', '')} come up?",
        f"What kind of product could solve {gap.get('title', '')}?"
    ]

    json_ld_faq = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Answer auto-generated from gap data."
                }
            }
            for q in faq_questions
        ]
    }

    json_ld_blocks = [json_ld_article, json_ld_breadcrumb, json_ld_faq]

    # Generate content sections
    content_parts = []

    # Metadata chips row
    category_pill = f'<a href="/category/{slugify(category)}.html" class="pill">{category}</a>'
    heat_badge = render_heat_badge(gap.get('heat_score', 0.0))
    evidence_chip = f'<span class="pill">{gap.get("evidence_count", 0)} signals</span>'

    # Format date
    try:
        date_str = dt_created.strftime('%b %d, %Y') if 'dt_created' in locals() else ''
    except:
        date_str = ''

    date_chip = f'<span class="pill">{date_str}</span>' if date_str else ''

    # Source pills
    source_pills = []
    for source in gap.get('source_types', [])[:5]:  # Limit to 5
        source_name = source.replace('-', ' ').title()
        source_pills.append(f'<span class="pill">{source_name}</span>')

    chips_html = f'''<div class="mb-8">
  {category_pill}
  {heat_badge}
  {evidence_chip}
  {date_chip}
  {" ".join(source_pills)}
</div>'''

    # H1
    content_parts.append(f'<h1>{gap.get("title", "Untitled Gap")}</h1>')
    content_parts.append(chips_html)

    # Share buttons
    content_parts.append(render_share_buttons(
        gap.get('title', ''),
        slug,
        gap.get('evidence_count', 0),
        gap.get('source_types', [])
    ))

    # Summary section
    content_parts.append(generate_summary_section(gap.get('description', '')))

    # Problem Description
    content_parts.append(expand_problem_description(gap.get('description', '')))

    # Who Feels This
    content_parts.append(generate_who_feels_section(gap))

    # Evidence (quotes) with platform links
    if gap.get('sample_quotes'):
        content_parts.append(generate_evidence_section(gap['sample_quotes']))

    # Why This Matters
    content_parts.append(generate_why_matters_section(gap.get('description', ''), category))

    # Competitive Landscape
    content_parts.append(generate_competitive_landscape_section(gap))

    # Business Opportunity
    content_parts.append(generate_business_opportunity_section(gap))

    # Source Breakdown
    content_parts.append(generate_source_breakdown(gap))

    # Tags
    content_parts.append(generate_tags_section(gap))

    # Related Gaps
    related = find_related_gaps(gap, all_gaps, max_count=8)
    if related:
        content_parts.append(generate_related_gaps_section(related))

    # FAQ
    content_parts.append(generate_faq_section(gap))

    # CTA
    content_parts.append('''<section class="card text-center">
  <h2>Explore More Opportunities</h2>
  <p class="mb-4">Found this gap interesting? Dive deeper into market needs and discover more potential product ideas.</p>
  <a href="/" class="pill" style="font-size: 1rem; padding: 0.5rem 1rem;">Back to Home</a>
</section>''')

    # Combine all content
    content_html = '\n\n'.join(content_parts)

    # Render full page
    full_html = render_html_page(
        title=title,
        meta_description=meta_description,
        canonical_url=canonical_url,
        content_html=content_html,
        breadcrumbs=breadcrumbs,
        json_ld_blocks=json_ld_blocks,
        page_type='gap'
    )

    # Write to file
    output_path = os.path.join(gap_dir, f"{slug}.html")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(full_html)

    return output_path
