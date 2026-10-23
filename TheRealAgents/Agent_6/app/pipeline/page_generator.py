"""
Gap Page Generator — auto-generates static HTML for new gaps and redeploys.

Called by Agent_6 after gap detection. Fetches all gaps from DB,
generates static pages, regenerates sitemap, and deploys to IONOS.
"""

import json
import logging
import os
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

TUXO_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(TUXO_DIR))

logger = logging.getLogger(__name__)

# Lazy imports to avoid loading heavy modules when not needed
_remote_db = None
_gap_pages = None
_generate_sitemap = None


def _get_db():
    global _remote_db
    if _remote_db is None:
        from shared.remote_db import RemoteDB
        _remote_db = RemoteDB()
    return _remote_db


def _get_gap_page_generator():
    global _gap_pages
    if _gap_pages is None:
        from scripts.generate_pages.gap_pages import generate_gap_page
        _gap_pages = generate_gap_page
    return _gap_pages


def fetch_all_gaps():
    """Fetch all active gaps from MySQL."""
    db = _get_db()
    try:
        gaps = db.get_gaps(limit=1000)
        return gaps.get('gaps', []) if isinstance(gaps, dict) else gaps
    except Exception as e:
        logger.error(f"Failed to fetch gaps: {e}")
        return []


def generate_all_gap_pages(gaps, output_dir=None):
    """
    Generate static HTML pages for all gaps.

    Args:
        gaps: List of gap dicts from DB
        output_dir: Output directory (default: website/tuxo.it)

    Returns:
        dict: {pages_generated: int, pages_skipped: int, errors: int}
    """
    if output_dir is None:
        output_dir = str(TUXO_DIR / 'website' / 'gapfeed.com')

    generate_gap_page = _get_gap_page_generator()

    stats = {'pages_generated': 0, 'pages_skipped': 0, 'errors': 0}

    for gap in gaps:
        try:
            slug = gap.get('slug', '')
            if not slug:
                stats['pages_skipped'] += 1
                continue

            # Skip thin gaps (not enough evidence for a good page)
            evidence = gap.get('evidence_count', 0)
            if evidence < 20:
                stats['pages_skipped'] += 1
                continue

            output_path = generate_gap_page(gap, gaps, output_dir)
            stats['pages_generated'] += 1
            logger.info(f"  Generated: {output_path}")
        except Exception as e:
            stats['errors'] += 1
            logger.error(f"  Failed to generate page for gap #{gap.get('id')}: {e}")

    return stats


def regenerate_sitemap(output_dir=None):
    """
    Regenerate sitemap.xml with all gap pages, categories, sources.

    Args:
        output_dir: Output directory (default: website/tuxo.it)
    """
    if output_dir is None:
        output_dir = str(TUXO_DIR / 'website' / 'gapfeed.com')

    import re

    BASE_URL = "https://tuxo.it"
    WEBSITE_DIR = Path(output_dir)

    pages = []
    pages.append({"loc": BASE_URL + "/", "priority": "1.0", "changefreq": "daily"})

    # Gap pages
    gap_dir = WEBSITE_DIR / "gap"
    if gap_dir.exists():
        for f in sorted(gap_dir.glob("*.html")):
            pages.append({
                "loc": f"{BASE_URL}/gap/{f.stem}.html",
                "priority": "0.8",
                "changefreq": "weekly"
            })

    # Category pages
    cat_dir = WEBSITE_DIR / "categories"
    if cat_dir.exists():
        for f in sorted(cat_dir.glob("*.html")):
            slug = f.stem
            if slug == "index":
                pages.append({"loc": f"{BASE_URL}/categories/", "priority": "0.7", "changefreq": "daily"})
            else:
                pages.append({
                    "loc": f"{BASE_URL}/categories/{slug}.html",
                    "priority": "0.6",
                    "changefreq": "weekly"
                })

    # Source pages
    src_dir = WEBSITE_DIR / "sources"
    if src_dir.exists():
        for f in sorted(src_dir.glob("*.html")):
            slug = f.stem
            if slug == "index":
                pages.append({"loc": f"{BASE_URL}/sources/", "priority": "0.5", "changefreq": "daily"})
            else:
                pages.append({
                    "loc": f"{BASE_URL}/sources/{slug}.html",
                    "priority": "0.5",
                    "changefreq": "weekly"
                })

    # Static pages
    for page in ["privacy", "terms"]:
        pages.append({"loc": f"{BASE_URL}/{page}.html", "priority": "0.3", "changefreq": "monthly"})

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]
    for p in pages:
        lines.append("  <url>")
        lines.append(f"    <loc>{p['loc']}</loc>")
        lines.append(f"    <lastmod>{today}</lastmod>")
        lines.append(f"    <changefreq>{p['changefreq']}</changefreq>")
        lines.append(f"    <priority>{p['priority']}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")

    sitemap_path = Path(output_dir) / "sitemap.xml"
    with open(sitemap_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"  Sitemap: {len(pages)} URLs -> {sitemap_path}")
    return len(pages)


def deploy_to_ionos(output_dir=None):
    """
    Deploy gap pages, sitemap, categories, sources to IONOS via SFTP.

    Args:
        output_dir: Local directory to deploy from (default: website/tuxo.it)
    """
    import paramiko

    if output_dir is None:
        output_dir = str(TUXO_DIR / 'website' / 'gapfeed.com')

    HOST = os.environ.get("IONOS_SFTP_HOST", "")
    PORT = 22
    USERNAME = os.environ.get("IONOS_SFTP_USER", "")
    PASSWORD = os.environ.get("SFTP_PASSWORD", "")
    REMOTE_DIR = "/gapfeed.com"

    DEPLOY_ITEMS = {"gap", "categories", "sources", "sitemap.xml"}

    def upload_recursive(sftp, local_dir, remote_dir):
        for item in os.listdir(local_dir):
            lp = os.path.join(local_dir, item)
            rp = f"{remote_dir}/{item}"
            if os.path.isdir(lp):
                try:
                    sftp.mkdir(rp)
                except IOError:
                    pass
                upload_recursive(sftp, lp, rp)
            else:
                sftp.put(lp, rp)

    transport = paramiko.Transport((HOST, PORT))
    transport.connect(username=USERNAME, password=PASSWORD)
    sftp = paramiko.SFTPClient.from_transport(transport)

    try:
        uploaded = 0
        for item in DEPLOY_ITEMS:
            lp = os.path.join(output_dir, item)
            rp = f"{REMOTE_DIR}/{item}"
            if not os.path.exists(lp):
                logger.warning(f"  SKIP (not found): {item}")
                continue
            if os.path.isdir(lp):
                try:
                    sftp.mkdir(rp)
                except IOError:
                    pass
                upload_recursive(sftp, lp, rp)
            else:
                sftp.put(lp, rp)
            uploaded += 1
            logger.info(f"  Deployed: {item}")

        logger.info(f"  Deploy complete: {uploaded} items uploaded")
        return uploaded
    finally:
        sftp.close()
        transport.close()


def run_full_pipeline(gaps_created_count=0):
    """
    Full pipeline: generate pages -> regenerate sitemap -> deploy.

    Args:
        gaps_created_count: Number of new gaps (for logging)

    Returns:
        dict with pipeline stats
    """
    logger.info("=== GAP PAGE GENERATION PIPELINE ===")

    # 1. Fetch all gaps
    logger.info("[1/3] Fetching all gaps from DB...")
    gaps = fetch_all_gaps()
    if not gaps:
        logger.warning("  No gaps found, skipping page generation")
        return {'status': 'skipped', 'reason': 'no gaps'}

    logger.info(f"  Found {len(gaps)} gaps")

    # 2. Generate pages
    logger.info("[2/3] Generating static pages...")
    page_stats = generate_all_gap_pages(gaps)
    logger.info(f"  Generated: {page_stats['pages_generated']}, "
                f"Skipped: {page_stats['pages_skipped']}, "
                f"Errors: {page_stats['errors']}")

    # 3. Regenerate sitemap
    logger.info("[2.5/3] Regenerating sitemap...")
    sitemap_urls = regenerate_sitemap()

    # 4. Deploy
    logger.info("[3/3] Deploying to IONOS...")
    deployed = deploy_to_ionos()

    result = {
        'status': 'ok',
        'total_gaps': len(gaps),
        'pages_generated': page_stats['pages_generated'],
        'pages_errors': page_stats['errors'],
        'sitemap_urls': sitemap_urls,
        'deployed_items': deployed,
    }

    logger.info(f"=== PIPELINE COMPLETE: {json.dumps(result)} ===")
    return result


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(message)s')
    run_full_pipeline()
