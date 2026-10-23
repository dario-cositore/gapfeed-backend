"""
Deterministic extractors — no LLM, just regex, dictionaries, and pattern matching.

This is Stage A of enrichment: cheap extraction that runs on every signal
before any model call. Catches the obvious stuff so the LLM only handles
the hard cases.
"""

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Money extraction
# ---------------------------------------------------------------------------

_MONEY_PATTERNS = [
    # $12,000 / $12000 / $12k / $12K
    re.compile(r'\$\s?([\d,]+(?:\.\d{1,2})?)\s*(?:k|K)?', re.IGNORECASE),
    # 12,000 dollars / 12000 USD
    re.compile(r'([\d,]+(?:\.\d{1,2})?)\s*(?:dollars|USD|usd)', re.IGNORECASE),
    # EUR 12,000 / 12,000 EUR / €12,000
    re.compile(r'(?:EUR|€)\s?([\d,]+(?:\.\d{1,2})?)', re.IGNORECASE),
    re.compile(r'([\d,]+(?:\.\d{1,2})?)\s*(?:EUR|euros?)', re.IGNORECASE),
    # GBP / £
    re.compile(r'(?:GBP|£)\s?([\d,]+(?:\.\d{1,2})?)', re.IGNORECASE),
]


def extract_money(text: str) -> list[float]:
    """Extract dollar/amount mentions from text."""
    amounts = []
    for pattern in _MONEY_PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group(1).replace(",", "")
            try:
                val = float(raw)
                # Heuristic: if the match text contains 'k' or 'K', multiply
                if 'k' in match.group(0).lower() and val < 1000:
                    val *= 1000
                if val > 0:
                    amounts.append(val)
            except ValueError:
                continue
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for a in amounts:
        rounded = round(a, 2)
        if rounded not in seen:
            seen.add(rounded)
            unique.append(rounded)
    return unique


# ---------------------------------------------------------------------------
# Duration / tenure extraction
# ---------------------------------------------------------------------------

_DURATION_PATTERNS = [
    re.compile(r'(\d+)\s*(?:years?|yrs?)\s*(?:ago|old|using|on|with|in\s+business)?', re.IGNORECASE),
    re.compile(r'(\d+)\s*months?\s*(?:ago|old|using|on|with)?', re.IGNORECASE),
    re.compile(r'since\s+(\d{4})', re.IGNORECASE),
    re.compile(r'for\s+(?:the\s+)?(?:past\s+)?(\d+)\s*(?:years?|yrs?|months?)', re.IGNORECASE),
]


def extract_durations(text: str) -> list[str]:
    """Extract duration/tenure mentions (e.g., '3 years', 'since 2019')."""
    found = []
    for pattern in _DURATION_PATTERNS:
        for match in pattern.finditer(text):
            found.append(match.group(0).strip())
    return list(dict.fromkeys(found))  # dedupe preserving order


# ---------------------------------------------------------------------------
# Location extraction (rule-based, no NER)
# ---------------------------------------------------------------------------

# Common US city/state patterns
_US_STATE_ABBR = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
}

_US_STATE_FULL = {
    'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado',
    'connecticut', 'delaware', 'florida', 'georgia', 'hawaii', 'idaho',
    'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana',
    'maine', 'maryland', 'massachusetts', 'michigan', 'minnesota',
    'mississippi', 'missouri', 'montana', 'nebraska', 'nevada',
    'new hampshire', 'new jersey', 'new mexico', 'new york',
    'north carolina', 'north dakota', 'ohio', 'oklahoma', 'oregon',
    'pennsylvania', 'rhode island', 'south carolina', 'south dakota',
    'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington',
    'west virginia', 'wisconsin', 'wyoming'
}

_MAJOR_CITIES = {
    'new york', 'los angeles', 'chicago', 'houston', 'phoenix',
    'philadelphia', 'san antonio', 'san diego', 'dallas', 'san jose',
    'austin', 'jacksonville', 'fort worth', 'columbus', 'charlotte',
    'san francisco', 'indianapolis', 'seattle', 'denver', 'boston',
    'nashville', 'detroit', 'portland', 'las vegas', 'miami',
    'atlanta', 'toronto', 'vancouver', 'london', 'berlin', 'paris',
    'amsterdam', 'sydney', 'melbourne', 'mumbai', 'singapore',
    'dublin', 'tel aviv', 'bangalore', 'shenzhen', 'tokyo'
}

_COUNTRIES = {
    'usa', 'united states', 'us', 'u.s.', 'canada', 'uk', 'united kingdom',
    'australia', 'germany', 'france', 'india', 'brazil', 'mexico',
    'japan', 'china', 'singapore', 'ireland', 'netherlands', 'spain',
    'italy', 'sweden', 'norway', 'denmark', 'finland', 'switzerland',
    'uae', 'uae', 'israel', 'south korea', 'new zealand'
}

# Patterns like "I'm in Austin" or "based in NYC" or "located in Miami, FL"
_LOCATION_PATTERNS = [
    re.compile(r"(?:i'm|i am|based|located|live|living)\s+(?:in|near|around)\s+([A-Z][a-zA-Z\s,]+?)(?:\.|,|!|\?|$)", re.IGNORECASE),
    re.compile(r"from\s+([A-Z][a-zA-Z\s,]+?)(?:\.|,|!|\?|$)", re.IGNORECASE),
    re.compile(r"in\s+((?:new york|los angeles|san francisco|san diego|fort worth|north carolina|south carolina|new jersey|new mexico|hampshire)\b[a-zA-Z\s,]*?)(?:\.|,|!|\?|$)", re.IGNORECASE),
]


def extract_locations(text: str) -> list[str]:
    """Extract location mentions from text using pattern + dictionary matching."""
    locations = []

    # Pattern-based extraction
    for pattern in _LOCATION_PATTERNS:
        for match in pattern.finditer(text):
            candidate = match.group(1).strip().rstrip(".,!?").strip()
            if len(candidate) > 2 and len(candidate) < 60:
                locations.append(candidate)

    # Dictionary matching (cities)
    text_lower = text.lower()
    for city in _MAJOR_CITIES:
        if city in text_lower:
            locations.append(city.title())

    # State matching (full names)
    for state in _US_STATE_FULL:
        if state in text_lower:
            locations.append(state.title())

    # State abbreviation matching (word boundary)
    for abbr in _US_STATE_ABBR:
        if re.search(rf'\b{abbr}\b', text):
            locations.append(abbr)

    # Country matching
    for country in _COUNTRIES:
        if re.search(rf'\b{re.escape(country)}\b', text_lower):
            locations.append(country.title())

    # Dedupe preserving order
    seen = set()
    unique = []
    for loc in locations:
        key = loc.lower()
        if key not in seen:
            seen.add(key)
            unique.append(loc)
    return unique


# ---------------------------------------------------------------------------
# Product / platform extraction
# ---------------------------------------------------------------------------

_PRODUCT_DICT = {
    # Ecommerce
    'shopify': 'shopify', 'amazon': 'amazon', 'etsy': 'etsy', 'ebay': 'ebay',
    'woocommerce': 'woocommerce', 'bigcommerce': 'bigcommerce', 'magento': 'magento',
    'squarespace': 'squarespace', 'wix': 'wix',
    # Payments
    'stripe': 'stripe', 'paypal': 'paypal', 'square': 'square',
    'braintree': 'braintree', 'adyen': 'adyen', 'wise': 'wise',
    'transferwise': 'wise', 'venmo': 'venmo', 'zelle': 'zelle',
    # SaaS / Productivity
    'slack': 'slack', 'notion': 'notion', 'asana': 'asana', 'trello': 'trello',
    'jira': 'jira', 'monday.com': 'monday', 'clickup': 'clickup',
    'hubspot': 'hubspot', 'salesforce': 'salesforce', 'zoho': 'zoho',
    'mailchimp': 'mailchimp', 'sendgrid': 'sendgrid', 'intercom': 'intercom',
    'zendesk': 'zendesk', 'freshdesk': 'freshdesk',
    # Cloud / Infra
    'aws': 'aws', 'heroku': 'heroku', 'vercel': 'vercel', 'netlify': 'netlify',
    'cloudflare': 'cloudflare', 'digitalocean': 'digitalocean',
    # Social / Communication
    'twitter': 'twitter', 'x.com': 'twitter', 'facebook': 'facebook',
    'instagram': 'instagram', 'linkedin': 'linkedin', 'tiktok': 'tiktok',
    'youtube': 'youtube', 'reddit': 'reddit',
    # AI / Dev
    'openai': 'openai', 'chatgpt': 'openai', 'claude': 'anthropic',
    'anthropic': 'anthropic', 'github': 'github', 'gitlab': 'gitlab',
    # CRM / Marketing
    'activecampaign': 'activecampaign', 'convertkit': 'convertkit',
    'mailerlite': 'mailerlite', 'keap': 'keap', 'infusionsoft': 'keap',
    # Hosting
    'godaddy': 'godaddy', 'namecheap': 'namecheap', 'ionos': 'ionos',
    'bluehost': 'bluehost', 'hostgator': 'hostgator', 'siteground': 'siteground',
}

# Normalize aliases
_PRODUCT_ALIASES = {
    'gpt': 'openai', 'gpt-4': 'openai', 'gpt4': 'openai', 'chat gpt': 'openai',
    'g suite': 'google workspace', 'gsuite': 'google workspace',
    'transferwise': 'wise', 'fb': 'facebook', 'ig': 'instagram',
    'sf': 'salesforce', 'do': 'digitalocean',
}


def extract_products(text: str) -> list[str]:
    """Extract product/platform mentions from text."""
    found = []
    text_lower = text.lower()

    for keyword, canonical in _PRODUCT_DICT.items():
        # Word boundary match for short terms, substring for longer ones
        if len(keyword) <= 3:
            if re.search(rf'\b{re.escape(keyword)}\b', text_lower):
                found.append(canonical)
        else:
            if keyword in text_lower:
                found.append(canonical)

    # Check aliases
    for alias, canonical in _PRODUCT_ALIASES.items():
        if re.search(rf'\b{re.escape(alias)}\b', text_lower):
            found.append(canonical)

    return list(dict.fromkeys(found))


# ---------------------------------------------------------------------------
# Pain verb / urgency extraction
# ---------------------------------------------------------------------------

_PAIN_VERBS = {
    'high': ['broke', 'broken', 'crashed', 'down', 'outage', 'froze', 'frozen',
             'lost', 'denied', 'rejected', 'banned', 'blocked', 'suspended',
             'deleted', 'removed', 'terminated', 'cancelled', 'stolen', 'hacked',
             'scammed', 'fraud', 'disaster', 'nightmare', 'urgent', 'emergency',
             'desperate', 'critical', 'immediately', 'stuck', 'trapped', 'screwed'],
    'medium': ['slow', 'frustrating', 'annoying', 'broken', 'bug', 'buggy',
               'failing', 'error', 'issue', 'problem', 'complaint', 'disappointed',
               'terrible', 'horrible', 'worst', 'hate', 'awful', 'useless',
               'overpriced', 'expensive', 'ripoff', 'scam', 'misleading'],
    'low': ['wish', 'would be nice', 'missing', 'lacking', 'needs', 'should',
            'could be better', 'not great', 'mediocre', 'underwhelming',
            'meh', 'disappointing']
}


def extract_pain_verbs(text: str) -> dict:
    """Extract pain-indicating words and return severity mapping."""
    text_lower = text.lower()
    result = {'high': [], 'medium': [], 'low': []}

    for severity, verbs in _PAIN_VERBS.items():
        for verb in verbs:
            if re.search(rf'\b{re.escape(verb)}\b', text_lower):
                result[severity].append(verb)

    return result


# ---------------------------------------------------------------------------
# Intent marker extraction
# ---------------------------------------------------------------------------

_INTENT_MARKERS = {
    'seeking_help': [
        r'(?:anyone|anybody)\s+(?:else|know|have|had)',
        r'what\s+(?:should|do|can)\s+(?:i|we)',
        r'how\s+(?:do|can|should)\s+(?:i|we)',
        r'need\s+(?:help|advice|recommendation)',
        r'looking\s+for',
        r'who\s+(?:do|should|can)\s+(?:i|we)',
        r'any\s+suggestions',
        r'does\s+anyone\s+know',
    ],
    'seeking_alternative': [
        r'(?:alternative|replacement|instead|switch(?:ing)?\s+to)',
        r'what\s+(?:do\s+you\s+use|are\s+you\s+using)',
        r'(?:better|best)\s+(?:alternative|option|tool)',
    ],
    'venting': [
        r'(?:just|had\s+to)\s+(?:rant|vent)',
        r'sick\s+of',
        r'fed\s+up',
        r'i\'?m\s+done',
        r'this\s+is\s+(?:ridiculous|unacceptable|insane)',
    ],
    'warning_others': [
        r'(?:heads\s+up|be\s+careful|watch\s+out|beware|psa|warning)',
        r'don\'?t\s+(?:use|buy|trust|go\s+with)',
    ],
}


def extract_intent_markers(text: str) -> list[str]:
    """Extract intent markers from text. Returns list of matched intents."""
    found = []
    for intent, patterns in _INTENT_MARKERS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                found.append(intent)
                break
    return found


# ---------------------------------------------------------------------------
# Domain extraction (from URLs)
# ---------------------------------------------------------------------------

def extract_source_domain(url: str) -> Optional[str]:
    """Extract the base domain from a URL for source identification."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Strip www.
        if domain.startswith("www."):
            domain = domain[4:]
        return domain if domain else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Master extraction function
# ---------------------------------------------------------------------------

def extract_all(text: str, source_url: str = "") -> dict:
    """
    Run all deterministic extractors on a text.

    Returns a dict with all extracted features. This is the input
    for Stage B (rules) and Stage C (LLM) of enrichment.
    """
    pain_verbs = extract_pain_verbs(text)
    # Determine overall pain severity from verb hits
    if pain_verbs['high']:
        pain_severity = 'high'
    elif pain_verbs['medium']:
        pain_severity = 'medium'
    elif pain_verbs['low']:
        pain_severity = 'low'
    else:
        pain_severity = 'none'

    return {
        'money_mentions': extract_money(text),
        'duration_mentions': extract_durations(text),
        'location_mentions': extract_locations(text),
        'product_mentions': extract_products(text),
        'pain_verbs': pain_verbs,
        'pain_severity': pain_severity,
        'intent_markers': extract_intent_markers(text),
        'source_domain': extract_source_domain(source_url) if source_url else None,
        'text_length': len(text),
        'has_question': '?' in text,
    }
