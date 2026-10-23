"""
Mention Resolver - Phase 1

Normalizes raw product/competitor mentions into canonical entities.
No external API calls, no DDG. Pure alias matching + string normalization.

Data sources:
1. product_category from Maya (e.g. "ecommerce_shopify" -> "Shopify")
2. competitor_mentions from Maya (e.g. '["PayPal"]' -> "PayPal")
3. Content scanning for known tool names (fallback)

Usage:
    from src.engines.mention_resolver import resolve_mentions_from_signals
    context = resolve_mentions_from_signals(signals)
"""
import re
import json
import logging
from collections import Counter, defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Canonical Entity Registry ────────────────────────────────────
# Maps lowercase aliases -> (canonical_name, entity_type)
# entity_type: "competitor" | "substitute" | "platform" | "tool"

ALIAS_MAP: dict[str, tuple[str, str]] = {}

def _add(canonical: str, entity_type: str, *aliases: str):
    ALIAS_MAP[canonical.lower()] = (canonical, entity_type)
    for alias in aliases:
        ALIAS_MAP[alias.lower()] = (canonical, entity_type)

# Ecommerce
_add("Shopify", "competitor", "shopify", "ecommerce_shopify")
_add("WooCommerce", "competitor", "woocommerce", "woo commerce", "woo_commerce")
_add("BigCommerce", "competitor", "bigcommerce", "big commerce")
_add("Magento", "competitor", "magento", "adobe commerce")
_add("Squarespace", "competitor", "squarespace")
_add("Wix", "competitor", "wix", "wix stores")
_add("Amazon", "platform", "amazon", "ecommerce_amazon", "amazon seller", "fba")
_add("Etsy", "platform", "etsy")
_add("eBay", "platform", "ebay", "e-bay")

# Payments
_add("Stripe", "competitor", "stripe", "payments_stripe")
_add("PayPal", "competitor", "paypal", "payments_paypal", "pay pal")
_add("Square", "competitor", "square", "payments_square", "square up")
_add("Wise", "platform", "wise", "transferwise", "platform_wise")
_add("Venmo", "platform", "venmo", "platform_venmo")
_add("Zelle", "platform", "zelle")
_add("Revolut", "platform", "revolut")
_add("Adyen", "competitor", "adyen")

# Project Management
_add("Jira", "competitor", "jira", "atlassian jira", "jira software")
_add("Asana", "competitor", "asana")
_add("Trello", "competitor", "trello")
_add("Monday.com", "competitor", "monday", "monday.com", "monday com")
_add("ClickUp", "competitor", "clickup", "click up")
_add("Notion", "competitor", "notion")
_add("Linear", "competitor", "linear", "linear app")
_add("Basecamp", "competitor", "basecamp")

# Communication
_add("Slack", "competitor", "slack", "communication_slack")
_add("Discord", "platform", "discord")
_add("Teams", "competitor", "microsoft teams", "ms teams", "teams")
_add("Zoom", "competitor", "zoom")
_add("WhatsApp", "substitute", "whatsapp", "whats app", "what's app")

# CRM / Sales
_add("Salesforce", "competitor", "salesforce", "sf", "sfdc")
_add("HubSpot", "competitor", "hubspot", "hub spot")
_add("Pipedrive", "competitor", "pipedrive")
_add("Zoho", "competitor", "zoho", "zoho crm")

# Dev Tools
_add("GitHub", "platform", "github", "development_github", "github.com")
_add("GitLab", "competitor", "gitlab")
_add("Bitbucket", "competitor", "bitbucket")
_add("Vercel", "competitor", "vercel")
_add("Netlify", "competitor", "netlify")
_add("AWS", "platform", "aws", "amazon web services", "cloud_aws")
_add("DigitalOcean", "platform", "digitalocean", "platform_digitalocean", "do")
_add("Heroku", "competitor", "heroku")
_add("Cloudflare", "competitor", "cloudflare")

# AI / LLM
_add("OpenAI", "competitor", "openai", "ai_openai", "chatgpt", "gpt-4", "gpt4")
_add("Anthropic", "competitor", "anthropic", "claude", "platform_anthropic")
_add("Google AI", "competitor", "gemini", "google ai", "bard")
_add("Midjourney", "competitor", "midjourney")
_add("Stable Diffusion", "competitor", "stable diffusion", "stability ai")

# Social
_add("Reddit", "platform", "reddit", "platform_reddit", "r/")
_add("Twitter/X", "platform", "twitter", "x.com", "platform_twitter")
_add("Facebook", "platform", "facebook", "platform_facebook")
_add("LinkedIn", "platform", "linkedin")
_add("YouTube", "platform", "youtube", "platform_youtube")
_add("TikTok", "platform", "tiktok")
_add("Instagram", "platform", "instagram")

# Spreadsheets / Office (substitutes!)
_add("Excel", "substitute", "excel", "microsoft excel", "ms excel", "spreadsheets", "spreadsheet", "google sheets", "google sheet")
_add("Google Docs", "substitute", "google docs", "gdocs")
_add("Notion (workspace)", "substitute", "notion workspace", "notion as a tool")
_add("Airtable", "competitor", "airtable")

# Generic substitutes
_add("Manual work", "substitute", "manual", "manually", "manual work", "manual process", "doing it by hand", "by hand")
_add("Spreadsheets", "substitute", "spreadsheet", "spreadsheets", "excel", "google sheets", "csv")
_add("Email", "substitute", "email", "email chains", "email threads", "gmail", "outlook")
_add("Agency/VA", "substitute", "agency", "virtual assistant", "va", "freelancer", "outsourcing", "hiring someone")
_add("Custom code", "substitute", "custom code", "custom script", "in-house tool", "homemade solution", "built our own")
_add("Paper/forms", "substitute", "paper", "paper forms", "printed forms", "physical forms", "pen and paper")

# Domain-specific
_add("DigitalOcean", "platform", "digitalocean")
_add("Shopify Plus", "competitor", "shopify plus")
_add("QuickBooks", "competitor", "quickbooks", "quick books")
_add("Xero", "competitor", "xero")
_add("Freshbooks", "competitor", "freshbooks", "fresh books")
_add("Mailchimp", "competitor", "mailchimp", "mail chimp")
_add("SendGrid", "competitor", "sendgrid", "send grid")
_add("Twilio", "competitor", "twilio")
_add("Intercom", "competitor", "intercom")
_add("Zendesk", "competitor", "zendesk")
_add("Freshdesk", "competitor", "freshdesk")
_add("Figma", "competitor", "figma")
_add("Canva", "competitor", "canva")
_add("Webflow", "competitor", "webflow")
_add("WordPress", "competitor", "wordpress", "wp")
_add("Drupal", "competitor", "drupal")

# ─── Resolution Logic ─────────────────────────────────────────────

def resolve_mention(raw: str) -> Optional[tuple[str, str]]:
    """
    Resolve a raw mention string to (canonical_name, entity_type).
    Returns None if no match found.
    """
    if not raw or not isinstance(raw, str):
        return None

    cleaned = raw.strip().lower()
    # Remove common prefixes/suffixes
    cleaned = re.sub(r'^(the |a |an )', '', cleaned)
    cleaned = re.sub(r'\s*(app|software|tool|platform|system|service)$', '', cleaned)
    cleaned = cleaned.strip()

    # Direct alias match
    if cleaned in ALIAS_MAP:
        return ALIAS_MAP[cleaned]

    # Try without underscores (product_category format)
    no_underscore = cleaned.replace('_', ' ').split()[-1] if '_' in cleaned else None
    if no_underscore and no_underscore in ALIAS_MAP:
        return ALIAS_MAP[no_underscore]

    # Fuzzy: check if any alias is a substring
    for alias, (canonical, etype) in ALIAS_MAP.items():
        if len(alias) > 3 and alias in cleaned:
            return (canonical, etype)
        if len(cleaned) > 3 and cleaned in alias:
            return (canonical, etype)

    return None


def resolve_product_category(category: str) -> Optional[tuple[str, str]]:
    """
    Resolve a product_category like "ecommerce_shopify" to ("Shopify", "competitor").
    """
    if not category:
        return None

    # Direct match on full string
    result = resolve_mention(category)
    if result:
        return result

    # Extract the product part after the prefix
    if '_' in category:
        parts = category.split('_', 1)
        product_part = parts[1] if len(parts) > 1 else parts[0]
        return resolve_mention(product_part)

    return None


def extract_mention_context(text: str, mention: str, window: int = 100) -> str:
    """Extract the text around a mention for sentiment/context analysis."""
    if not text or not mention:
        return ""
    text_lower = text.lower()
    mention_lower = mention.lower()
    idx = text_lower.find(mention_lower)
    if idx == -1:
        return ""
    start = max(0, idx - window)
    end = min(len(text), idx + len(mention) + window)
    return text[start:end].strip()


def resolve_mentions_from_signals(signals: list[dict]) -> dict:
    """
    Main entry point: extract and resolve all mentions from a list of signals.

    Returns:
    {
        "competitors": [{"name": "Shopify", "mentions": 23, "authors": 18, ...}],
        "substitutes": [{"name": "spreadsheets", "mentions": 16, ...}],
        "platforms": [{"name": "Reddit", "mentions": 5, ...}],
        "tools": [{"name": "Figma", "mentions": 3, ...}],
        "unresolved": ["some_unknown_tool", ...],
        "coverage": 0.45  # fraction of signals with at least one resolved mention
    }
    """
    # Track mentions per entity
    entity_signals: dict[str, list[dict]] = defaultdict(list)
    entity_types: dict[str, str] = {}
    unresolved: list[str] = []
    signals_with_mentions = 0

    for signal in signals:
        signal_mentions = set()
        text = (signal.get('content') or '') + ' ' + (signal.get('title') or '')

        # Source 1: product_category
        pc = signal.get('product_category')
        if pc:
            resolved = resolve_product_category(pc)
            if resolved:
                canonical, etype = resolved
                entity_signals[canonical].append(signal)
                entity_types[canonical] = etype
                signal_mentions.add(canonical)

        # Source 2: competitor_mentions (JSON array string)
        cm = signal.get('competitor_mentions')
        if cm and cm.strip() not in ('[]', '', 'null'):
            try:
                mentions_list = json.loads(cm) if isinstance(cm, str) else cm
                if isinstance(mentions_list, list):
                    for m in mentions_list:
                        resolved = resolve_mention(str(m))
                        if resolved:
                            canonical, etype = resolved
                            entity_signals[canonical].append(signal)
                            entity_types[canonical] = etype
                        else:
                            raw = str(m).strip()
                            if raw and len(raw) > 2:
                                unresolved.append(raw)
            except (json.JSONDecodeError, TypeError):
                pass

        # Source 3: Scan content for known tool names (lightweight)
        text_lower = text.lower()
        for alias, (canonical, etype) in ALIAS_MAP.items():
            if len(alias) < 4:
                continue  # Skip very short aliases to avoid false positives
            if alias in text_lower and canonical not in signal_mentions:
                entity_signals[canonical].append(signal)
                entity_types[canonical] = etype
                signal_mentions.add(canonical)

        if signal_mentions:
            signals_with_mentions += 1

    # Build output buckets
    buckets = {"competitor": [], "substitute": [], "platform": [], "tool": []}

    for canonical, sigs in entity_signals.items():
        etype = entity_types.get(canonical, "tool")
        bucket = buckets.get(etype, buckets["tool"])

        # Unique authors
        authors = set()
        for s in sigs:
            a = s.get('author')
            if a:
                authors.add(a)

        # Negative context rate (simple heuristic)
        negative_count = 0
        for s in sigs:
            sentiment = (s.get('sentiment') or '').lower()
            if sentiment in ('negative', 'frustrated', 'angry'):
                negative_count += 1
            elif sentiment == 'neutral':
                # Check for pain keywords near the mention
                text = (s.get('content') or '').lower()
                pain_words = ['hate', 'terrible', 'awful', 'broken', 'frustrat', 'annoying',
                              'sucks', 'worst', 'garbage', 'unusable', 'nightmare', 'pain']
                if any(pw in text for pw in pain_words):
                    negative_count += 1

        negative_rate = negative_count / len(sigs) if sigs else 0

        # Extract common pain phrases near this entity
        pain_phrases = []
        for s in sigs[:10]:
            ctx = extract_mention_context(
                (s.get('content') or ''),
                canonical,
                window=80
            )
            if ctx and len(ctx) > 20:
                pain_phrases.append(ctx[:120])

        bucket.append({
            "name": canonical,
            "type": etype,
            "mention_count": len(sigs),
            "author_count": len(authors),
            "negative_rate": round(negative_rate, 2),
            "sample_pain_phrases": pain_phrases[:3],
            "signal_ids": [s['id'] for s in sigs[:20] if s.get('id')],
        })

    # Sort each bucket by mention count
    for bucket in buckets.values():
        bucket.sort(key=lambda x: x['mention_count'], reverse=True)

    # Dedupe unresolved
    unresolved_unique = list(set(unresolved))[:20]

    coverage = signals_with_mentions / len(signals) if signals else 0

    return {
        "competitors": buckets["competitor"],
        "substitutes": buckets["substitute"],
        "platforms": buckets["platform"],
        "tools": buckets["tool"],
        "unresolved": unresolved_unique,
        "coverage": round(coverage, 2),
    }
