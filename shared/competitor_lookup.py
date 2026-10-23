"""
Competitor Lookup Module (v2)

Searches for existing solutions/competitors for a given gap.
Uses DDG snippets + batch LLM relevance filtering + signal cross-referencing.

Architecture:
1. Search DDG for potential solutions (snippets only, no scraping)
2. Batch LLM call to filter irrelevant results and score relevance
3. Cross-reference competitor names against pain signals (string matching)
4. Calculate Opportunity Score: Demand × 1/(1 + Threat)
"""

import json
import logging
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ddgs import DDGS

logger = logging.getLogger(__name__)

class CompetitorLookup:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    def search_competitors(self, gap_title: str, category: str = None) -> list[dict]:
        """Search for existing solutions (raw DDG results)."""
        results = []
        queries = [
            f'"{gap_title}" tool software app',
            f'best {self._extract_keywords(gap_title)} solution',
            f'{self._extract_keywords(gap_title)} alternative product',
        ]
        if category:
            queries.append(f'{category} {self._extract_keywords(gap_title)} software')
        
        seen_urls = set()
        for query in queries:
            try:
                with DDGS() as ddgs:
                    for r in ddgs.text(query, max_results=5):
                        url = r.get('href', '')
                        if url not in seen_urls:
                            seen_urls.add(url)
                            results.append({
                                'title': r.get('title', ''),
                                'body': r.get('body', ''),
                                'url': url,
                            })
            except Exception as e:
                logger.warning(f"Search failed for query '{query}': {e}")
        
        return results[:12]  # Max 12 raw results for LLM filtering
    
    def filter_relevance_batch(self, gap_title: str, gap_description: str, 
                                raw_results: list[dict]) -> list[dict]:
        """
        Batch LLM filtering: send all snippets in one call,
        get back relevance scores and validity flags.
        """
        if not self.llm_client or not raw_results:
            # Fallback: return all as low-relevance
            return [{'name': r['title'][:50], 'url': r['url'], 
                    'relevance_score': 0.3, 'is_valid': False,
                    'reason': 'No LLM available', 'source': self._classify_source(r['url']),
                    'description': r['body'][:200]} for r in raw_results[:5]]
        
        # Format results for LLM
        snippets = ""
        for idx, r in enumerate(raw_results):
            snippets += f"[{idx}] Title: {r['title']}\n    Snippet: {r['body'][:150]}\n    URL: {r['url']}\n\n"
        
        prompt = f"""You are a market researcher analyzing competitors for this market gap:
"{gap_title}"
{gap_description[:200] if gap_description else ''}

Below are search results. For each, determine if it's an ACTUAL software/product solving this gap, or just a blog, article, agency, or irrelevant result.

{snippets}

Return ONLY a JSON array. Each object:
- "index": integer from the list
- "name": clean product name
- "relevance_score": 0.0-1.0 (1 = exact solution, 0 = irrelevant)
- "is_valid": true if relevance > 0.5 AND it's a product/tool
- "reason": short explanation

Be strict. SEO blog posts, forum discussions, and news articles are NOT competitors."""

        try:
            response = self.llm_client(prompt, max_tokens=1000, timeout=15)
            # Extract JSON from response
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                filtered = json.loads(json_match.group())
                # Merge with original data
                result = []
                for item in filtered:
                    idx = item.get('index', -1)
                    if 0 <= idx < len(raw_results):
                        result.append({
                            'name': item.get('name', raw_results[idx]['title'][:50]),
                            'url': raw_results[idx]['url'],
                            'relevance_score': item.get('relevance_score', 0),
                            'is_valid': item.get('is_valid', False),
                            'reason': item.get('reason', ''),
                            'source': self._classify_source(raw_results[idx]['url']),
                            'description': raw_results[idx]['body'][:200],
                        })
                return [r for r in result if r['is_valid']]
        except Exception as e:
            logger.warning(f"LLM batch filter failed: {e}")
        
        # Fallback
        return [{'name': r['title'][:50], 'url': r['url'], 
                'relevance_score': 0.3, 'is_valid': False,
                'reason': 'LLM failed', 'source': self._classify_source(r['url']),
                'description': r['body'][:200]} for r in raw_results[:5]]
    
    def cross_reference_complaints(self, competitors: list[dict], 
                                    pain_signals: list[dict]) -> list[dict]:
        """
        Match competitor names against pain signal text.
        Count negative mentions to determine if people are complaining about them.
        """
        for comp in competitors:
            comp['complaints_count'] = 0
            comp['complaint_mentions'] = []
            name_lower = comp['name'].lower()
            if len(name_lower) < 3:  # Skip very short names
                continue
            
            for signal in pain_signals:
                text = signal.get('text', '') or signal.get('content', '') or ''
                text_lower = text.lower()
                if name_lower in text_lower:
                    sentiment = signal.get('sentiment', 'neutral')
                    # Count negative mentions or any mention (presence = awareness)
                    if sentiment in ('negative', 'neutral'):
                        comp['complaints_count'] += 1
                        if len(comp['complaint_mentions']) < 3:
                            comp['complaint_mentions'].append(text[:100])
        
        return competitors
    
    def calculate_opportunity_score(self, demand_score: float, 
                                    competitors: list[dict],
                                    k_factor: float = 0.5) -> dict:
        """
        Calculate GapFeed Opportunity Score.
        
        Opportunity = Demand × (1 / (1 + Threat))
        
        Threat for each competitor decays exponentially with complaints:
        T_c = relevance × exp(-k × complaints)
        """
        threat_sum = 0.0
        for comp in competitors:
            r_c = comp.get('relevance_score', 0)
            m_c = comp.get('complaints_count', 0)
            effective_threat = r_c * math.exp(-k_factor * m_c)
            threat_sum += effective_threat
            comp['effective_threat'] = round(effective_threat, 3)
        
        opportunity_score = demand_score * (1 / (1 + threat_sum))
        
        # Verdict
        valid_comps = [c for c in competitors if c.get('is_valid')]
        complaint_total = sum(c.get('complaints_count', 0) for c in valid_comps)
        
        if len(valid_comps) == 0:
            verdict = 'wide_open'
            verdict_text = f"No relevant solutions found. Wide open."
        elif complaint_total > len(valid_comps) * 2:
            verdict = 'high_opportunity'
            verdict_text = f"{len(valid_comps)} solutions exist, but {complaint_total} complaints against them. Incumbents are failing."
        elif threat_sum < 0.5:
            verdict = 'moderate_opportunity'
            verdict_text = f"{len(valid_comps)} weak solutions found. Room for improvement."
        elif threat_sum > 1.5:
            verdict = 'saturated'
            verdict_text = f"{len(valid_comps)} strong solutions covering this space. Hard to compete."
        else:
            verdict = 'competitive'
            verdict_text = f"{len(valid_comps)} solutions exist. Differentiation needed."
        
        return {
            'opportunity_score': round(opportunity_score, 3),
            'demand_score': demand_score,
            'threat_sum': round(threat_sum, 3),
            'verdict': verdict,
            'verdict_text': verdict_text,
            'valid_competitor_count': len(valid_comps),
            'total_complaints': complaint_total,
        }
    
    def validate_gap(self, gap_title: str, category: str = None,
                     description: str = None, pain_signals: list[dict] = None,
                     demand_score: float = 0.5) -> dict:
        """
        Full validation pipeline.
        
        Returns competitors, opportunity score, and verdict.
        """
        # Step 1: Search
        raw_results = self.search_competitors(gap_title, category)
        
        # Step 2: Batch LLM filtering
        competitors = self.filter_relevance_batch(gap_title, description, raw_results)
        
        # Step 3: Cross-reference complaints
        if pain_signals:
            competitors = self.cross_reference_complaints(competitors, pain_signals)
        
        # Step 4: Calculate opportunity score
        scoring = self.calculate_opportunity_score(demand_score, competitors)
        
        return {
            'competitors': competitors,
            'competitor_count': len([c for c in competitors if c.get('is_valid')]),
            'scoring': scoring,
        }
    
    def _extract_keywords(self, title: str) -> str:
        """Extract core keywords from gap title."""
        title = re.sub(r'^(no |no reliable |no unified |no integrated |no clear |no affordable )', '', title.lower())
        title = re.sub(r'\b(tool|platform|system|way|for|to|and|the|a|an)\b', '', title)
        return re.sub(r'\s+', ' ', title).strip()[:100]
    
    def _classify_source(self, url: str) -> str:
        """Classify where we found this competitor."""
        url_lower = url.lower()
        for domain, name in [('producthunt.com', 'Product Hunt'), ('g2.com', 'G2'),
                             ('capterra.com', 'Capterra'), ('alternativeto.net', 'AlternativeTo'),
                             ('github.com', 'GitHub')]:
            if domain in url_lower:
                return name
        return 'Web'


def lookup_competitors(gap_title: str, category: str = None) -> dict:
    """Quick lookup without LLM."""
    lookup = CompetitorLookup()
    return lookup.validate_gap(gap_title, category)
