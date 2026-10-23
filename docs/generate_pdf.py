#!/usr/bin/env python3
"""Regenerate PDF from MASTER.md"""

import markdown
from pathlib import Path
from playwright.sync_api import sync_playwright

DOCS_DIR = Path(__file__).parent
MD_FILE = DOCS_DIR / 'MASTER.md'
HTML_FILE = DOCS_DIR / 'GapFeed-Master-Plan.html'
PDF_FILE = DOCS_DIR / 'GapFeed-Master-Plan.pdf'

md_text = MD_FILE.read_text(encoding='utf-8')
html_body = markdown.markdown(md_text, extensions=['tables', 'toc', 'fenced_code'])

html_full = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>GapFeed - Master Plan</title>
<style>
@page {{ size: A4; margin: 2cm 2.5cm; }}
body {{ font-family: Inter, Helvetica Neue, Segoe UI, Arial, sans-serif; font-size: 11px; line-height: 1.6; color: #1a1a1a; max-width: 800px; margin: 0 auto; padding: 40px 60px; }}
h1 {{ font-size: 28px; font-weight: 800; color: #4f9cf7; border-bottom: 3px solid #4f9cf7; padding-bottom: 10px; margin-top: 50px; }}
h1:first-of-type {{ font-size: 42px; text-align: center; border-bottom: none; margin-top: 100px; margin-bottom: 10px; }}
h2 {{ font-size: 20px; font-weight: 700; color: #1a1a1a; margin-top: 35px; border-bottom: 1px solid #e0e0e0; padding-bottom: 6px; }}
h3 {{ font-size: 15px; font-weight: 600; color: #333; margin-top: 24px; }}
h4 {{ font-size: 13px; font-weight: 600; color: #555; margin-top: 18px; }}
p {{ margin: 8px 0; }}
table {{ border-collapse: collapse; width: 100%; margin: 14px 0; font-size: 10px; }}
th {{ background-color: #4f9cf7; color: white; font-weight: 600; text-align: left; padding: 8px 10px; border: 1px solid #e0e0e0; }}
td {{ padding: 6px 10px; border: 1px solid #e0e0e0; vertical-align: top; }}
tr:nth-child(even) {{ background-color: #fafafa; }}
code {{ font-family: Consolas, Courier New, monospace; background-color: #f5f5f5; padding: 1px 4px; border-radius: 3px; font-size: 10px; color: #d63384; }}
pre {{ background-color: #f8f8f8; border: 1px solid #e0e0e0; border-radius: 6px; padding: 12px 16px; overflow-x: auto; font-size: 10px; line-height: 1.5; }}
pre code {{ background: none; padding: 0; color: #333; }}
blockquote {{ border-left: 4px solid #4f9cf7; margin: 16px 0; padding: 8px 16px; background-color: #f0f7ff; color: #555; }}
ul, ol {{ margin: 8px 0; padding-left: 24px; }}
li {{ margin: 4px 0; }}
hr {{ border: none; border-top: 2px solid #e0e0e0; margin: 30px 0; }}
a {{ color: #4f9cf7; text-decoration: none; }}
@media print {{ h1 {{ page-break-before: always; }} h1:first-of-type {{ page-break-before: avoid; }} table, pre {{ page-break-inside: avoid; }} }}
</style>
</head>
<body>
{html_body}
</body>
</html>"""

HTML_FILE.write_text(html_full, encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(f'file:///{HTML_FILE.resolve().as_posix()}')
    page.pdf(path=str(PDF_FILE), format='A4',
             margin={'top': '2cm', 'bottom': '2cm', 'left': '2.5cm', 'right': '2.5cm'},
             print_background=True)
    browser.close()

print(f'PDF: {PDF_FILE} ({PDF_FILE.stat().st_size / 1024:.1f} KB)')