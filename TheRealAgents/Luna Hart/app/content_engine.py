import sys
import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

# Import shared LLM client for auto-fallback
_tuxo_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_tuxo_root))
try:
    from shared.llm_client import llm_call as _shared_llm_call
except ImportError:
    _shared_llm_call = None

SYSTEM_PROMPT = """You are Luna Hart, the voice of TuXo - a gap discovery platform that scans the internet 24/7 for unsolved problems.

PERSONALITY:
- Blunt, slightly irreverent indie hacker who's tired of bullshit marketing.
- Talk like a real person at a coffee shop, not a LinkedIn robot.
- Use "you" and "we" naturally. Short sentences. Punchy.
- Excited about real data, bored by hype.
- Sarcastic when something is dumb, but never mean.
- Confident but not arrogant. Call out lazy thinking.

VOICE RULES - NEVER BREAK THESE:
- No corporate speak: leverage, synergize, paradigm, empower, ecosystem, etc.
- No generic inspiration or LinkedIn cringe.
- No filler: "in today's world", "it goes without saying", "thrilled to share".
- No em dashes ever. Use periods, commas or hyphens only.
- Use contractions (don't, can't, it's, you're).
- Short. Punchy. Get to the point.

TOPICS YOU CARE ABOUT:
- Founders who actually solve real pain instead of chasing hype.
- Real market data vs gut feelings.
- Automation that saves time, not complexity that creates jobs.
- The gap between what users complain about and what they actually want.

CONTENT RULES:
- Always base everything on real TuXo data (signal counts, gaps, heat scores, buyer intent, trends).
- Never fabricate numbers or stories.
- For X posts: under 280 characters, start with a strong take, end with a specific provocative question that makes people reply.
- Reference actual gaps or numbers when possible.
- Be opinionated. Have a clear point of view.

EXAMPLES OF YOUR VOICE:

Example 1 (Legal gap):
Input: "No accessible legal guidance for urgent crises (221 signals)"
Output: Legal help in a real crisis is still completely broken. 221 signals this month from people facing eviction, harassment, or custody issues with zero affordable options. We keep pretending the system works until it's your turn.
When are we finally going to build the on-demand legal triage tool that actually helps when it matters?

Example 2 (Finance gap):
Input: "Emergency financial assistance platform (120 signals)"
Output: Your rent just doubled, your card got declined, and there's still no single place to get emergency cash or payment relief. 120 people hit this exact pain in the last few weeks. Yet every fintech keeps pushing smart budgeting instead of real help when life goes sideways.
Who's actually going to build the emergency financial lifeline that works?

Example 3 (Data vs hype):
Input: "Why real gap data beats founder gut feelings"
Output: Founders are still building in 2026 based on talking to three friends while we have 6.9k real signals showing exactly where the pain is. 58% of the hottest gaps show clear buyer intent. The data is right there and it's loud.
Why are we still guessing?"""


class ContentEngine:
    """
    Generates tailored marketing content (X posts, LinkedIn, Blog Outlines)
    using configured LLM based on provided topic and context data.
    """
    
    def __init__(self, config: dict, logger: logging.Logger):
        """
        Load LLM configuration.
        Expected config keys: llm.primary, llm.fallback, llm.max_tokens, llm.temperature.
        """
        self.logger = logger
        
        # Load specific configuration from nested 'llm' section
        llm_config = config.get("llm", {})
        self.primary_model = llm_config.get("primary", "mimo-v2.6-flash")
        self.fallback_model = llm_config.get("fallback", "mimo-v2.6-flash")
        self.max_tokens = llm_config.get("max_tokens", 2000)
        self.temperature = llm_config.get("temperature", 0.7)
        
        self.logger.info(f"ContentEngine initialized. Primary: {self.primary_model}, Fallback: {self.fallback_model}")

    def _llm_call(self, prompt: str) -> str:
        """
        Make LLM call using shared client with auto-fallback.
        Returns raw text response.
        """
        if _shared_llm_call is None:
            self.logger.error("Shared LLM client not available. Cannot make LLM calls.")
            return "ERROR: Shared LLM client not available."

        try:
            result = _shared_llm_call(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
                model=self.primary_model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                timeout=30
            )
            
            if result:
                return result
            
            # Primary failed, try fallback
            self.logger.warning("Primary model " + self.primary_model + " returned empty. Trying fallback.")
            result = _shared_llm_call(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
                model=self.fallback_model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                timeout=30
            )
            return result if result else "ERROR: Both models failed."
            
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            return f"LLM_API_ERROR: {e}"

    def _sanitize_output(self, text: str) -> str:
        """
        Remove em dashes, fix formatting, clean up list brackets and quotes.
        """
        # 1. Strip list brackets if LLM returned ["content"] or ['content']
        text = text.strip()
        if text.startswith("[") and text.endswith("]"):
            text = text[1:-1].strip()
        # Strip surrounding quotes
        if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
            text = text[1:-1].strip()
        
        # 2. Replace em/en dashes with periods
        text = re.sub(r'[\u2014\u2013]', '.', text)
        
        # 3. Remove bold markers
        text = text.replace('**', '')
        
        # 4. Clean up extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        if "LLM_API_ERROR" in text:
            return "Content generation failed due to API error."
            
        return text
    def _validate_post(self, text: str, platform: str) -> bool:
        """
        Validate post meets requirements (topic clarity, question ending, no em dashes, length).
        Returns True if valid, False otherwise with potential log message.
        """
        if "Content generation failed" in text:
            return False
            
        # Check for em dashes again (should be unnecessary if sanitize runs first, but good double-check)
        if re.search(r'[—–]', text):
            self.logger.warning(f"Validation failed: Post contains prohibited dashes for platform {platform}.")
            return False

        # Check if text ends with a question mark (?)
        # Allow for one trailing punctuation mark before the question mark for robustness
        if not re.search(r'[.?!\s]*\?$', text):
            self.logger.warning(f"Validation failed: Post for {platform} does not end with a question mark. Text: {text[:100]}...")
            # For critical platforms like X, we might force a fix or fail. Here we fail.
            return False
        
        # Check Length constraints
        platform_upper = platform.upper()
        if platform_upper == "X":
            if len(text) > 280:
                self.logger.warning(f"Validation failed: X post too long ({len(text)} chars).")
                return False
        elif platform_upper == "LINKEDIN":
            if len(text) > 3000:
                self.logger.warning(f"Validation failed: LinkedIn post too long ({len(text)} chars).")
                return False
        # Blog post outline is validated by structure, not character count.
        
        return True

    def generate_x_post(self, topic: str, data_context: Dict[str, Any], style: str = "insight") -> str:
        """
        Generate a single X post (under 280 chars). Must start with strong take and end with provocative question.
        Retries once on validation failure with stricter prompt.
        """
        signal_count = data_context.get("signal_count", data_context.get("tuxo_stats", {}).get("signal_count", 0))
        gap_count = data_context.get("gap_count", data_context.get("tuxo_stats", {}).get("gap_count", 0))
        
        prompt = f"""Current TuXo live stats:
- {signal_count} signals scanned
- {gap_count} active gaps

Topic to write about: {topic}
Style: {style}

Generate ONE X post in my exact voice.
- Max 280 characters.
- Start with a punchy, opinionated take.
- End with a specific provocative question that invites real replies (not "what do you think?").
- No em dashes. No corporate words. Talk like a real indie hacker.
- Use real numbers from the stats above if relevant.
- Make it feel like something I'd actually tweet while drinking coffee."""
        
        raw_output = self._llm_call(prompt)
        sanitized = self._sanitize_output(raw_output)
        
        if self._validate_post(sanitized, "X"):
            return sanitized
        
        # Retry once with stricter prompt
        self.logger.warning(f"X post validation failed for '{topic}'. Retrying with stricter prompt.")
        retry_prompt = f"""Rewrite this X post about: {topic}
Current TuXo stats: {signal_count} signals, {gap_count} gaps

STRICT REQUIREMENTS (must ALL pass):
- Exactly under 278 characters
- End with a question mark (?)
- Blunt indie hacker voice, no em dashes, no corporate words
- Start with a strong opinionated take
- Use contractions (don't, can't, it's)"""
        
        retry_output = self._llm_call(retry_prompt)
        retry_sanitized = self._sanitize_output(retry_output)
        
        if self._validate_post(retry_sanitized, "X"):
            self.logger.info(f"Retry succeeded for X post on '{topic}'.")
            return retry_sanitized
        
        self.logger.error(f"Failed to generate valid X post for topic: {topic} (after retry).")
        return f"Could not generate a valid X post for '{topic}' adhering to all constraints."

    def generate_x_thread(self, topic: str, data_context: Dict[str, Any], num_tweets: int = 3) -> List[str]:
        """
        Generate an X thread (list of strings, each under 280 chars).
        First tweet hooks, middle tweets expand, last tweet ends with question.
        """
        if num_tweets < 2:
            self.logger.warning("Thread requested with less than 2 tweets, defaulting to 3.")
            num_tweets = 3
            
        signal_count = data_context.get("signal_count", 0)
        prompt = f"""
        Generate an X thread of exactly {num_tweets} tweets about the topic: "{topic}".
        
        Structure requirements:
        - Tweet 1: Must be a strong hook related to the topic.
        - Tweets 2 to {num_tweets - 1}: Must expand on the topic, providing valuable insight.
        - Final Tweet ({num_tweets}): Must summarize the main point and end with an engagement question.
        
        Context Injection: Use the high volume of current signals ({signal_count}) to imply this is an urgent, relevant topic.
        
        Strict Constraints:
        1. Each tweet must be under 280 characters.
        2. ABSOLUTELY NO EM DASHES in any tweet.
        3. The content must flow logically from tweet to tweet.
        Output the tweets as a newline-separated list.
        """
        
        raw_output = self._llm_call(prompt)
        
        # Assuming the LLM outputs a list separated by newlines
        potential_tweets = [self._sanitize_output(t.strip()) for t in raw_output.splitlines() if t.strip()]
        
        valid_tweets = []
        for i, tweet in enumerate(potential_tweets):
            platform = "X"
            # Check structure and length for each individual tweet
            if self._validate_post(tweet, platform):
                valid_tweets.append(tweet)
            else:
                self.logger.warning(f"Tweet {i+1} validation failed. Discarding it. Content starts: {tweet[:50]}")

        # If the thread size is off, return what was successfully validated, perhaps padded if necessary
        if len(valid_tweets) != num_tweets:
            self.logger.warning(f"Thread generation mismatch. Requested {num_tweets}, validated {len(valid_tweets)} tweets.")
            # Truncate or pad to ensure list length matches expectation if possible, but prioritizing valid content.
            return valid_tweets[:num_tweets]
            
        return valid_tweets

    def generate_linkedin_post(self, topic: str, data_context: Dict[str, Any], style: str = "insight") -> str:
        """
        Generate a LinkedIn post (longer format, up to 3000 chars). Must end with engagement question.
        Retries once on validation failure with stricter prompt.
        """
        signal_count = data_context.get("signal_count", 50)
        gap_count = data_context.get("gap_count", 10)
        
        prompt = f"""
        Generate a professional and insightful LinkedIn post about the topic: "{topic}".
        The required style is: "{style}".
        
        Context for depth:
        - We are seeing {signal_count} external signals supporting this view.
        - This directly relates to {gap_count} identified gaps in current market solutions.
        - The tone should be reflective and authoritative, suitable for a B2B/technical audience.
        
        Constraints for LinkedIn Post:
        1. Total length must be less than 3000 characters.
        2. Must end with a strong, open-ended engagement question.
        3. ABSOLUTELY NO EM DASHES. Use standard formatting (line breaks for readability).
        """
        
        raw_output = self._llm_call(prompt)
        sanitized = self._sanitize_output(raw_output)
        
        if self._validate_post(sanitized, "LinkedIn"):
            return sanitized
        
        # Retry once with stricter prompt
        self.logger.warning(f"LinkedIn post validation failed for '{topic}'. Retrying with stricter prompt.")
        retry_prompt = f"""Rewrite this LinkedIn post about: {topic}
Context: {signal_count} signals, {gap_count} gaps

STRICT REQUIREMENTS (must ALL pass):
- Under 3000 characters
- Must end with a question mark
- Professional but not corporate, no em dashes
- Use line breaks for readability
- End with an open-ended engagement question"""
        
        retry_output = self._llm_call(retry_prompt)
        retry_sanitized = self._sanitize_output(retry_output)
        
        if self._validate_post(retry_sanitized, "LinkedIn"):
            self.logger.info(f"Retry succeeded for LinkedIn post on '{topic}'.")
            return retry_sanitized
        
        self.logger.error(f"Failed to generate valid LinkedIn post for topic: {topic} (after retry).")
        return f"Could not generate a valid LinkedIn post for '{topic}' adhering to all constraints."

    def generate_blog_post(self, topic: str, gap_data: Dict[str, Any], signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a blog post outline with title, meta description, and sections.
        Uses real gap structure data.
        """
        signal_summary = f"Based on {len(signals)} key signals collected across {gap_data.get('all_sources', 'multiple channels')}."
        gap_focus = gap_data.get("primary_gap", "market efficiency")
        
        prompt = f"""
        Create a detailed blog post outline for a long-form article (1500+ words) on the topic: "{topic}".
        The core focus for the content must be addressing the following market gap: "{gap_focus}".
        
        Context Injection:
        - {signal_summary}
        - Mention how this insight relates to Dario's resume expertise in orchestration layers and data reliability.
        
        Output Format: Return a single JSON object strictly following this structure:
        {{
          "title": "Compelling SEO-friendly H1 Title",
          "meta_description": "A concise, engaging meta description under 160 characters.",
          "sections": [
            {{"heading": "H2 Section 1 Title", "points": ["Key point 1", "Key point 2"]}},
            {{"heading": "H2 Section 2 Title (Deep Dive)", "points": ["Deep dive point A", "Deep dive point B"]}}
          ]
        }}
        
        Strict Constraints:
        1. Title must be compelling.
        2. Meta description must be informative.
        3. ABSOLUTELY NO EM DASHES anywhere in the output (especially in section headings or points).
        4. If you cannot output valid JSON, return the string "JSON_FORMAT_ERROR".
        """
        
        raw_output = self._llm_call(prompt)
        
        if raw_output.startswith("JSON_FORMAT_ERROR"):
            self.logger.error("Blog outline generation failed due to JSON formatting error.")
            return {"error": "JSON Parsing Failure", "raw_attempt": raw_output}
            
        try:
            outline = json.loads(raw_output)
            
            # Basic structure validation and sanitation of content elements
            if not isinstance(outline, dict) or "title" not in outline or "sections" not in outline:
                raise ValueError("Missing top-level keys in outline JSON.")
                
            # Sanitize headings/points one last time to catch any stray dashes
            for section in outline.get("sections", []):
                section["heading"] = self._sanitize_output(section["heading"])
                section["points"] = [self._sanitize_output(p) for p in section.get("points", [])]
                
            self.logger.info(f"Successfully generated blog outline for '{topic}'.")
            return outline
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON for blog outline: {e}. Output: {raw_output[:150]}...")
            return {"error": "JSON Decode Failed", "raw_attempt": raw_output}
        except Exception as e:
            self.logger.error(f"General error during blog outline processing: {e}")
            return {"error": str(e), "raw_attempt": raw_output}

    # Placeholder: In a real environment, trend_scout would likely call load_trends() or similar
    # to get context for filtering, but ContentEngine primarily focuses on generation based on input context.
    # We include placeholders for memory interaction as per spec, though they might be unused in this generation-only class.

    def save_trends(self, trends: List[Dict[str, Any]]):
        """Save to memory/trends.json (Deferring write logic to TrendScout as it handles state management)."""
        self.logger.warning("ContentEngine received request to save trends. State management write logic delegated to TrendScout.")
        # Action: In a real system, this would use a shared memory management utility.

    def load_trends(self) -> list:
        """Load from memory/trends.json (Deferring read logic to TrendScout)."""
        self.logger.warning("ContentEngine received request to load trends. State management read logic delegated to TrendScout.")
        return [] # Return empty list as it is not the primary responsibility of this class
        
    def get_trending_now(self) -> list:
        """Return currently tracked trends above threshold (Deferring to TrendScout or similar state manager)."""
        self.logger.warning("ContentEngine requested trending data. Assuming caller provides necessary context or this is a stub.")
        return []