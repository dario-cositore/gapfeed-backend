"""
Analytics DB wrapper for direct MySQL queries (pymysql).
"""

import os
import pymysql
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta


class AnalyticsDB:
    """Direct MySQL connection for analytics queries."""

    def __init__(self):
        self.host = os.environ.get("DB_HOST", "")
        self.user = os.environ.get("DB_USER", "")
        self.password = os.environ.get("DB_PASS", "")
        self.database = os.environ.get("DB_NAME", "")

    def _connect(self):
        """Create a new connection."""
        return pymysql.connect(
            host=self.host,
            user=self.user,
            password=self.password,
            database=self.database,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=30
        )

    def _query(self, sql: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Execute a query and return results."""
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()
        finally:
            conn.close()

    def _execute(self, sql: str, params: tuple = None) -> int:
        """Execute a write query and return affected rows."""
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                affected = cursor.execute(sql, params)
                conn.commit()
                return affected
        finally:
            conn.close()

    def get_overview(self, days: int = 7) -> Dict[str, Any]:
        """Total page views, unique visitors, top 10 viewed gaps, device breakdown."""
        try:
            # Total page views in period
            total_views = self._query(
                "SELECT COUNT(*) as count FROM page_views "
                "WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)",
                (days,)
            )[0]['count']
        except Exception:
            total_views = 0

        try:
            # Unique visitors (by session_hash)
            unique_visitors = self._query(
                "SELECT COUNT(DISTINCT session_hash) as count FROM page_views "
                "WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)",
                (days,)
            )[0]['count']
        except Exception:
            unique_visitors = 0

        try:
            # Top 10 viewed gaps
            top_gaps = self._query(
                """
                SELECT g.id AS gap_id, pv.page_path, COUNT(*) AS views
                FROM page_views pv
                JOIN gaps g ON g.slug = SUBSTRING_INDEX(SUBSTRING_INDEX(pv.page_path, '/', -1), '.', 1)
                WHERE pv.page_type = 'gap'
                  AND pv.created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY g.id, pv.page_path
                ORDER BY views DESC
                LIMIT 10
                """,
                (days,)
            )
            top_gaps = [{'gap_id': row['gap_id'], 'page_path': row['page_path'], 'views': row['views']}
                        for row in top_gaps]
        except Exception:
            top_gaps = []

        try:
            # Device type breakdown
            device_breakdown = self._query(
                "SELECT device_type, COUNT(*) as count "
                "FROM page_views "
                "WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY) "
                "GROUP BY device_type",
                (days,)
            )
            device_breakdown = {row['device_type']: row['count'] for row in device_breakdown}
        except Exception:
            device_breakdown = {}

        return {
            'total_views': total_views,
            'unique_visitors': unique_visitors,
            'top_gaps': top_gaps,
            'device_breakdown': device_breakdown
        }

    def get_trending(self, days: int = 7, limit: int = 20) -> List[Dict[str, Any]]:
        """Gaps ranked by view velocity, comparing recent 50% vs older 50%."""
        half_days = max(1, days // 2)
        try:
            rows = self._query(
                """
                SELECT g.id AS gap_id, pv.page_path,
                       SUM(CASE WHEN pv.created_at >= DATE_SUB(NOW(), INTERVAL %s DAY) THEN 1 ELSE 0 END) as views_recent,
                       SUM(CASE WHEN pv.created_at < DATE_SUB(NOW(), INTERVAL %s DAY) AND pv.created_at >= DATE_SUB(NOW(), INTERVAL %s DAY) THEN 1 ELSE 0 END) as views_old
                FROM page_views pv
                JOIN gaps g ON g.slug = SUBSTRING_INDEX(SUBSTRING_INDEX(pv.page_path, '/', -1), '.', 1)
                WHERE pv.page_type = 'gap'
                  AND pv.created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY g.id, pv.page_path
                HAVING views_recent + views_old > 0
                ORDER BY (views_recent - views_old) DESC
                LIMIT %s
                """,
                (half_days, half_days, days, days, limit)
            )
            result = []
            for row in rows:
                views_recent = row['views_recent'] or 0
                views_old = row['views_old'] or 0
                growth_pct = 0
                if views_old > 0:
                    growth_pct = ((views_recent - views_old) / views_old) * 100
                else:
                    growth_pct = 100 if views_recent > 0 else 0
                result.append({
                    'gap_id': row['gap_id'],
                    'page_path': row['page_path'],
                    'views_recent': views_recent,
                    'views_old': views_old,
                    'growth_pct': round(growth_pct, 2)
                })
            return result
        except Exception:
            return []

    def get_top_searches(self, days: int = 7, limit: int = 20) -> List[Dict[str, Any]]:
        """Top queries by frequency with average results_count."""
        try:
            rows = self._query(
                """
                SELECT query_text, COUNT(*) as search_count, AVG(results_count) as avg_results
                FROM search_queries
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY query_text
                ORDER BY search_count DESC
                LIMIT %s
                """,
                (days, limit)
            )
            return [
                {
                    'query_text': row['query_text'],
                    'search_count': row['search_count'],
                    'avg_results': round(row['avg_results'], 2) if row['avg_results'] else 0
                }
                for row in rows
            ]
        except Exception:
            return []

    def get_zero_results(self, days: int = 7, limit: int = 20) -> List[Dict[str, Any]]:
        """Searches where results_count = 0."""
        try:
            rows = self._query(
                """
                SELECT query_text, COUNT(*) as search_count, MAX(created_at) as last_searched
                FROM search_queries
                WHERE results_count = 0
                  AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY query_text
                ORDER BY search_count DESC
                LIMIT %s
                """,
                (days, limit)
            )
            return [
                {
                    'query_text': row['query_text'],
                    'search_count': row['search_count'],
                    'last_searched': row['last_searched'].isoformat() if row['last_searched'] else None
                }
                for row in rows
            ]
        except Exception:
            return []

    def get_traffic_sources(self, days: int = 7, limit: int = 20) -> List[Dict[str, Any]]:
        """Top referrers from page_views."""
        try:
            rows = self._query(
                """
                SELECT referrer, COUNT(*) as views, COUNT(DISTINCT session_hash) as unique_visitors
                FROM page_views
                WHERE referrer IS NOT NULL
                  AND referrer != ''
                  AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY referrer
                ORDER BY views DESC
                LIMIT %s
                """,
                (days, limit)
            )
            return [
                {
                    'referrer': row['referrer'],
                    'views': row['views'],
                    'unique_visitors': row['unique_visitors']
                }
                for row in rows
            ]
        except Exception:
            return []

    def get_session_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Avg pages per session, bounce rate, avg duration, total sessions."""
        try:
            # Total sessions (distinct session_hash from page_views)
            total_sessions = self._query(
                "SELECT COUNT(DISTINCT session_hash) as count FROM page_views "
                "WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)",
                (days,)
            )[0]['count']
        except Exception:
            total_sessions = 0

        try:
            # Avg pages per session
            avg_pages = self._query(
                "SELECT AVG(page_count) as avg_pages FROM ("
                "SELECT session_hash, COUNT(*) as page_count "
                "FROM page_views "
                "WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY) "
                "GROUP BY session_hash) as session_pages",
                (days,)
            )[0]['avg_pages']
            avg_pages = round(avg_pages, 2) if avg_pages else 0
        except Exception:
            avg_pages = 0

        try:
            # Bounce rate: sessions with only one page view
            single_page_sessions = self._query(
                "SELECT COUNT(*) as count FROM ("
                "SELECT session_hash, COUNT(*) as page_count "
                "FROM page_views "
                "WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY) "
                "GROUP BY session_hash "
                "HAVING page_count = 1) as single_page",
                (days,)
            )[0]['count']
            bounce_rate_pct = round((single_page_sessions / total_sessions * 100), 2) if total_sessions > 0 else 0
        except Exception:
            bounce_rate_pct = 0

        try:
            # Avg session duration (seconds) from sessions table
            avg_duration = self._query(
                "SELECT AVG(TIMESTAMPDIFF(SECOND, first_seen, last_seen)) as avg_duration "
                "FROM sessions "
                "WHERE first_seen >= DATE_SUB(NOW(), INTERVAL %s DAY)",
                (days,)
            )[0]['avg_duration']
            avg_duration = round(avg_duration, 2) if avg_duration else 0
        except Exception:
            avg_duration = 0

        return {
            'avg_pages': avg_pages,
            'bounce_rate_pct': bounce_rate_pct,
            'avg_duration_seconds': avg_duration,
            'total_sessions': total_sessions
        }

    def get_gap_engagement(self, gap_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """Daily metrics for a specific gap from gap_engagement table."""
        try:
            rows = self._query(
                """
                SELECT date, views, unique_visitors, search_impressions, search_clicks
                FROM gap_engagement
                WHERE gap_id = %s
                  AND date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                ORDER BY date ASC
                """,
                (gap_id, days)
            )
            return [
                {
                    'date': row['date'].isoformat() if row['date'] else None,
                    'views': row['views'],
                    'unique_visitors': row['unique_visitors'],
                    'search_impressions': row['search_impressions'],
                    'search_clicks': row['search_clicks']
                }
                for row in rows
            ]
        except Exception:
            return []

# For testing
if __name__ == '__main__':
    db = AnalyticsDB()
    print(db.get_overview(days=7))
    print(db.get_trending(days=7, limit=5))
    print(db.get_top_searches(days=7, limit=5))
    print(db.get_zero_results(days=7, limit=5))
    print(db.get_traffic_sources(days=7, limit=5))
    print(db.get_session_metrics(days=7))
    # print(db.get_gap_engagement(gap_id=1, days=30))