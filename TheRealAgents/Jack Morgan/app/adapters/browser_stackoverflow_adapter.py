"""
Browser Stack Overflow Adapter — fetches SO questions via real browser.
"""

import time
import logging
import json
import random
from pathlib import Path
from datetime import datetime, timezone

from app.adapters.browser_manager import get_browser_manager

logger = logging.getLogger(__name__)

TAG_ROTATION = [
    'javascript', 'python', 'java', 'c#', 'php', 'android', 'html',
    'css', 'reactjs', 'node.js', 'sql', 'typescript', 'docker',
    'git', 'amazon-web-services', 'linux', 'api', 'machine-learning',
    'flutter', 'go', 'rust', 'kubernetes', 'devops', 'firebase',
    'vue.js', 'angular', 'django', 'express', 'postgresql', 'mongodb',
]


class BrowserStackOverflowAdapter:
    """Stack Overflow adapter using Playwright browser."""

    def __init__(self, cursor_file: str = None):
        self.browser = get_browser_manager()
        self.cursor_file = cursor_file
        self.seen_ids = self._load_cursors()

    def _load_cursors(self) -> set:
        if not self.cursor_file:
            return set()
        try:
            p = Path(self.cursor_file)
            if p.exists():
                with open(p) as f:
                    data = json.load(f)
                    return set(data.get('seen_ids', []))
        except Exception:
            pass
        return set()

    def _save_cursors(self):
        if not self.cursor_file:
            return
        try:
            p = Path(self.cursor_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, 'w') as f:
                json.dump({'seen_ids': list(self.seen_ids)[-5000]}, f)
        except Exception as e:
            logger.warning(f"Failed to save cursors: {e}")

    def get_tag_rotation(self) -> list[str]:
        return TAG_ROTATION

    def fetch_recent_questions(self, tag: str = None, limit: int = 30) -> list[dict]:
        """Fetch recent SO questions, optionally filtered by tag."""
        page = self.browser.new_page()
        signals = []
        try:
            if tag:
                url = f'https://stackoverflow.com/questions/tagged/{tag}?tab=Newest'
            else:
                url = 'https://stackoverflow.com/questions?tab=Newest'

            self.browser.human_delay(1, 3)
            page.goto(url, wait_until='domcontentloaded', timeout=15000)
            self.browser.human_delay(1, 2)
            self.browser.human_scroll(page, 300, 600)

            questions = page.evaluate('''() => {
                const questions = [];
                const items = document.querySelectorAll('.s-post-summary, .question-summary');
                items.forEach(item => {
                    const titleEl = item.querySelector('.s-post-summary--title a, .question-hyperlink');
                    const excerptEl = item.querySelector('.s-post-summary--content-excerpt, .excerpt');
                    const tagEls = item.querySelectorAll('.s-post-summary--tag, .post-tag');
                    const voteEl = item.querySelector('.s-post-summary--stats-item-number');
                    const answerEl = item.querySelectorAll('.s-post-summary--stats-item-number')[1];
                    
                    if (titleEl) {
                        questions.push({
                            title: titleEl.textContent.trim(),
                            url: titleEl.href || '',
                            excerpt: excerptEl ? excerptEl.textContent.trim().substring(0, 500) : '',
                            tags: Array.from(tagEls).map(t => t.textContent.trim()),
                            votes: voteEl ? voteEl.textContent.trim() : '0',
                            answers: answerEl ? answerEl.textContent.trim() : '0',
                        });
                    }
                });
                return questions;
            }''')

            for q in questions[:limit]:
                q_url = q.get('url', '')
                q_id = q_url.split('/questions/')[1].split('/')[0] if '/questions/' in q_url else q_url
                if q_id in self.seen_ids:
                    continue
                self.seen_ids.add(q_id)

                signal = {
                    'title': q.get('title', ''),
                    'body': q.get('excerpt', '') or q.get('title', ''),
                    'url': q_url,
                    'source_url': q_url,
                    'source': 'stackoverflow',
                    'platform_metadata': {
                        'platform': 'stackoverflow',
                        'tag': tag or 'general',
                        'tags': q.get('tags', []),
                        'votes': q.get('votes', '0'),
                        'answers': q.get('answers', '0'),
                    },
                    'collected_at': datetime.now(timezone.utc).isoformat(),
                }
                signals.append(signal)

            self._save_cursors()
            logger.info(f"SO {tag or 'newest'}: {len(signals)} new questions via browser")
            return signals

        except Exception as e:
            logger.error(f"Browser SO fetch failed: {e}")
            return []
        finally:
            page.close()

    def fetch_unanswered(self, tag: str = None, limit: int = 30) -> list[dict]:
        """Fetch unanswered SO questions."""
        page = self.browser.new_page()
        signals = []
        try:
            if tag:
                url = f'https://stackoverflow.com/questions/tagged/{tag}?tab=Unanswered'
            else:
                url = 'https://stackoverflow.com/questions?tab=Unanswered'

            self.browser.human_delay(1, 3)
            page.goto(url, wait_until='domcontentloaded', timeout=15000)
            self.browser.human_delay(1, 2)
            self.browser.human_scroll(page, 300, 600)

            questions = page.evaluate('''() => {
                const questions = [];
                const items = document.querySelectorAll('.s-post-summary, .question-summary');
                items.forEach(item => {
                    const titleEl = item.querySelector('.s-post-summary--title a, .question-hyperlink');
                    const excerptEl = item.querySelector('.s-post-summary--content-excerpt, .excerpt');
                    const voteEl = item.querySelector('.s-post-summary--stats-item-number');
                    if (titleEl) {
                        questions.push({
                            title: titleEl.textContent.trim(),
                            url: titleEl.href || '',
                            excerpt: excerptEl ? excerptEl.textContent.trim().substring(0, 500) : '',
                            votes: voteEl ? voteEl.textContent.trim() : '0',
                        });
                    }
                });
                return questions;
            }''')

            for q in questions[:limit]:
                q_url = q.get('url', '')
                q_id = q_url.split('/questions/')[1].split('/')[0] if '/questions/' in q_url else q_url
                if q_id in self.seen_ids:
                    continue
                self.seen_ids.add(q_id)

                signal = {
                    'title': q.get('title', ''),
                    'body': q.get('excerpt', '') or q.get('title', ''),
                    'url': q_url,
                    'source_url': q_url,
                    'source': 'stackoverflow',
                    'platform_metadata': {
                        'platform': 'stackoverflow',
                        'tag': tag or 'unanswered',
                        'unanswered': True,
                        'votes': q.get('votes', '0'),
                    },
                    'collected_at': datetime.now(timezone.utc).isoformat(),
                }
                signals.append(signal)

            self._save_cursors()
            return signals

        except Exception as e:
            logger.error(f"Browser SO unanswered fetch failed: {e}")
            return []
        finally:
            page.close()
