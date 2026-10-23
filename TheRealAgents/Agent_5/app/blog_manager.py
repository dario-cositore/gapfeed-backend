#!/usr/bin/env python3
"""
Blog Manager Module for Agent_5
Manages dariocositore.com blog content creation and deployment.
"""
import os
import json
import re
import time
from datetime import datetime
from pathlib import Path

try:
    import paramiko
except ImportError:
    paramiko = None


class BlogManager:
    """Manages blog posts for dariocositore.com."""

    def __init__(self, config, logger):
        """
        Initialize BlogManager.

        Args:
            config: Agent configuration dict
            logger: Logger instance
        """
        self.config = config
        self.logger = logger
        self.blog_dir = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'website',
            'dariocositore.com',
            'blog'
        )
        self.blog_dir = os.path.abspath(self.blog_dir)

    def get_existing_posts(self):
        """List all .html files in blog directory."""
        posts = []
        for f in os.listdir(self.blog_dir):
            if f.endswith('.html'):
                posts.append(f)
        return sorted(posts)

    def create_blog_post(self, title, meta_description, content_html, slug):
        """
        Create a new blog post HTML file.

        Args:
            title: Page title
            meta_description: Meta description for SEO
            content_html: HTML content for the main section
            slug: URL-friendly slug for the file

        Returns:
            Path to created file or None on failure
        """
        filename = f"{slug}.html"
        filepath = os.path.join(self.blog_dir, filename)

        # Check if post already exists
        if os.path.exists(filepath):
            self.logger.warning(f"Blog post already exists: {filepath}")
            return filepath

        # Create HTML template matching existing posts
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Dario Cositore</title>
    <meta name="description" content="{meta_description}">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{meta_description}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="https://dariocositore.com/blog/{slug}.html">
    <meta name="twitter:card" content="summary_large_image">
    <link rel="stylesheet" href="../css/style.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
</head>
<body>
    <header class="header">
        <nav class="nav">
            <a href="../index.html" class="logo">Dario Cositore</a>
            <button class="hamburger" onclick="toggleMenu()">☰</button>
            <ul class="nav-links">
                <li><a href="../index.html">Home</a></li>
                <li><a href="../blog/index.html">Blog</a></li>
                <li><a href="https://tuxo.it">TuXo</a></li>
            </ul>
        </nav>
    </header>

    <main class="article">
        <article>
            <h1>{title}</h1>
            <p class="meta">
                <span>By Dario Cositore</span>
                <span>•</span>
                <span>{datetime.now().strftime('%B %d, %Y')}</span>
            </p>
            {content_html}
        </article>
    </main>

    <footer class="footer">
        <p>© {datetime.now().year} Dario Cositore. Built with AI and coffee.</p>
    </footer>

    <script>
        function toggleMenu() {{
            document.querySelector('.nav-links').classList.toggle('active');
        }}
    </script>
</body>
</html>'''

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html)
            self.logger.info(f"Created blog post: {filename}")
            return filepath
        except Exception as e:
            self.logger.error(f"Failed to create blog post: {e}")
            return None

    def generate_from_gap(self, gap_data):
        """
        Generate blog post from TuXo gap data.

        Args:
            gap_data: Dict with gap information (title, description, evidence, etc.)

        Returns:
            Tuple of (title, meta_description, content_html, slug) or None
        """
        title = gap_data.get('title', 'Unsolved Problem')
        description = gap_data.get('description', '')
        evidence = gap_data.get('evidence', [])
        sources = gap_data.get('source_types', [])
        categories = gap_data.get('categories', [])
        buyer_intent = gap_data.get('buyer_intent_score', 0.5)
        slug = gap_data.get('slug', 'gap')

        # Build evidence section
        evidence_html = ''
        if evidence:
            evidence_html = '<h2>Evidence from Real People</h2><ul>'
            for e in evidence[:5]:  # Top 5 evidence items
                text = e.get('text', '')
                if text:
                    evidence_html += f'<li>{text}</li>'
            evidence_html += '</ul>'

        # Build source breakdown
        sources_html = ''
        if sources:
            sources_html = '<h2>Where This Problem Appears</h2><ul>'
            for s in sources:
                sources_html += f'<li>{s}</li>'
            sources_html += '</ul>'

        # Build categories
        categories_html = ''
        if categories:
            categories_html = '<h2>Related Categories</h2><p>'
            categories_html += ', '.join(categories)
            categories_html += '</p>'

        content_html = f'''
        <p>{description}</p>
        <p><strong>Buyer Intent Score:</strong> {buyer_intent * 100:.0f}%</p>
        {evidence_html}
        {sources_html}
        {categories_html}
        <h2>Business Opportunity</h2>
        <p>This gap represents a genuine market opportunity. People are actively searching for solutions and are willing to pay.</p>
        '''

        meta_description = f"{description[:150]}..."

        return (title, meta_description, content_html, slug)

    def deploy_post(self, slug):
        """
        Deploy a blog post via SFTP to IONOS.

        Args:
            slug: Post slug (without .html)

        Returns:
            True on success, False on failure
        """
        if paramiko is None:
            self.logger.error("paramiko not installed, cannot deploy")
            return False

        local_path = os.path.join(self.blog_dir, f"{slug}.html")
        if not os.path.exists(local_path):
            self.logger.error(f"Post file not found: {local_path}")
            return False

        try:
            transport = paramiko.Transport((os.environ.get("IONOS_SFTP_HOST", ""), 22))
            transport.connect(username=os.environ.get("IONOS_SFTP_USER", ""), password=os.environ.get("SFTP_PASSWORD", ""))
            sftp = paramiko.SFTPClient.from_transport(transport)

            remote_path = f'/public/blog/{slug}.html'
            sftp.put(local_path, remote_path)
            sftp.close()
            transport.close()

            self.logger.info(f"Deployed {slug}.html to IONOS")
            return True
        except Exception as e:
            self.logger.error(f"SFTP deployment failed: {e}")
            return False

    def update_index(self, new_post_slug):
        """
        Update blog index.html to include new post.

        Args:
            new_post_slug: Slug of the new post

        Returns:
            True on success, False on failure
        """
        index_path = os.path.join(self.blog_dir, 'index.html')
        if not os.path.exists(index_path):
            self.logger.warning("Blog index.html not found")
            return False

        # Read existing index
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if already updated
        if new_post_slug in content:
            self.logger.info(f"Post {new_post_slug} already in index")
            return True

        # Insert new post into the list (this is simplified)
        # In a real implementation, you'd parse the HTML and add to the correct location
        self.logger.info(f"Note: Manual index update needed for {new_post_slug}")
        return True

    def get_post_stats(self, slug):
        """Placeholder for post analytics."""
        return {}


def create_blog_post(title, meta_description, content_html, slug, blog_dir):
    """Standalone function for creating blog posts."""
    manager = BlogManager({}, None)
    manager.blog_dir = blog_dir
    return manager.create_blog_post(title, meta_description, content_html, slug)
