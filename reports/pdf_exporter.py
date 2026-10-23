"""
tuxo - Immigration Brief PDF Exporter (Simplified)

Generates professional PDF reports from immigration brief data.
"""

from datetime import datetime
from io import BytesIO
from fpdf import FPDF


class ImmigrationPDFExporter:
    """Export immigration brief to PDF."""

    def __init__(self):
        self.pdf = FPDF()
        self.pdf.set_auto_page_break(auto=True, margin=15)
        self.page_width = self.pdf.w - 20  # minus margins

    def _sanitize(self, text):
        """Encode to latin-1 with replacement for unsupported chars."""
        if not isinstance(text, str):
            return str(text)
        # Basic strip; replace common problematic Unicode with ASCII equivalents first
        replacements = {
            '\u2013': '-',  # en dash
            '\u2014': '-',  # em dash
            '\u2018': "'",  # left single quote
            '\u2019': "'",  # right single quote
            '\u201c': '"',  # left double quote
            '\u201d': '"',  # right double quote
            '\u2026': '...',  # ellipsis
        }
        for orig, repl in replacements.items():
            text = text.replace(orig, repl)
        # Encode to latin-1, replacing remaining unknown chars with ?
        return text.encode('latin-1', errors='replace').decode('latin-1')

    def _truncate(self, text, max_len=150):
        if not text:
            return ''
        return (text[:max_len] + '...') if len(text) > max_len else text

    def export(self, brief: dict, output_path: str = None) -> bytes:
        """Export a brief to PDF. Returns bytes if output_path is None."""
        pdf = self.pdf
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 16)

        # Title
        title = self._sanitize(brief.get('query', 'Immigration Brief').title())
        pdf.cell(0, 10, f'Immigration Intelligence Brief: {title}', ln=True, align='C')
        pdf.ln(5)

        # Metadata
        pdf.set_font('Helvetica', '', 10)
        gen_date = brief.get('generated_at', '')[:10] if brief.get('generated_at') else datetime.now().strftime('%Y-%m-%d')
        meta = f"Generated: {gen_date} | Signals: {brief.get('signal_count', 0)} (Gold: {brief.get('gold_count', 0)}) | Avg Urgency: {brief.get('avg_urgency', 0)}"
        pdf.cell(0, 6, self._sanitize(meta), ln=True, align='C')
        pdf.ln(10)

        # Executive Summary
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Executive Summary', ln=True)
        pdf.set_font('Helvetica', '', 10)

        summary = f"Analysis of {brief.get('signal_count', 0)} immigration signals from Reddit communities."
        if brief.get('prospect_signals', 0) > 0:
            summary += f" {brief.get('prospect_signals')} prospect signals detected (individuals actively seeking legal assistance)."
        pdf.multi_cell(0, 5, self._sanitize(summary))
        pdf.ln(5)

        # Top Pain Points
        if brief.get('top_pains'):
            pdf.ln(5)
            pdf.set_font('Helvetica', 'B', 12)
            pdf.cell(0, 8, 'Key Findings', ln=True)
            for i, pain in enumerate(brief['top_pains'][:5], 1):
                pdf.set_font('Helvetica', 'B', 10)
                line = f"{i}. {pain['name']} ({pain['count']} signals, urgency: {pain['avg_urgency']})"
                pdf.cell(0, 6, self._sanitize(line), ln=True)
                pdf.set_font('Helvetica', '', 9)
                if pain.get('insight'):
                    insight = self._truncate(f"Action: {pain['insight']}", 200)
                    pdf.multi_cell(0, 4, self._sanitize(insight))
                if pain.get('sample_title'):
                    sample = f"Sample: \"{self._truncate(pain['sample_title'], 100)}\""
                    pdf.cell(0, 4, self._sanitize(sample), ln=True)
                pdf.ln(2)

        # Visa Distribution
        if brief.get('visa_breakdown'):
            pdf.ln(5)
            pdf.set_font('Helvetica', 'B', 12)
            pdf.cell(0, 8, 'Visa Type Distribution', ln=True)
            pdf.set_font('Helvetica', '', 10)
            sorted_visas = sorted(brief['visa_breakdown'].items(), key=lambda x: x[1]['count'], reverse=True)
            for visa, info in sorted_visas[:8]:
                name = visa.title() if isinstance(visa, str) else str(visa)
                line = f"{name}: {info['count']} signals (urgency: {info.get('avg_urgency', 0)}, gold: {info.get('gold', 0)})"
                pdf.cell(0, 5, self._sanitize(line), ln=True)
            pdf.ln(5)

        # Prospect Signals
        if brief.get('prospect_examples'):
            pdf.ln(5)
            pdf.set_font('Helvetica', 'B', 12)
            pdf.cell(0, 8, 'Prospect Signals (Client Acquisition)', ln=True)
            pdf.set_font('Helvetica', '', 9)
            for i, p in enumerate(brief['prospect_examples'][:5], 1):
                pdf.set_font('Helvetica', 'B', 9)
                title = self._truncate(p.get('title', ''), 120)
                pdf.cell(0, 5, f"{i}. {self._sanitize(title)}", ln=True)
                pdf.set_font('Helvetica', 'I', 8)
                details = f"Source: r/{p.get('subreddit', 'unknown')} | Urgency: {p.get('urgency', 0)}"
                pdf.cell(0, 4, self._sanitize(details), ln=True)
                pdf.ln(1)

        # Footer
        pdf.set_y(-15)
        pdf.set_font('Helvetica', 'I', 8)
        footer = f'Generated by TUXO Immigration Intelligence | {datetime.now().strftime("%Y-%m-%d %H:%M")}'
        pdf.cell(0, 10, footer, align='C')  # footer is ASCII, safe

        if output_path:
            pdf.output(output_path)
            return None
        else:
            return bytes(pdf.output(dest='S'))  # bytes


if __name__ == '__main__':
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.engine.immigration_brief import generate_immigration_brief

    brief = generate_immigration_brief(min_urgency=0.0)
    exporter = ImmigrationPDFExporter()
    pdf_bytes = exporter.export(brief)
    Path('test_immigration_brief.pdf').write_bytes(pdf_bytes)
    print("Wrote test_immigration_brief.pdf, size:", len(pdf_bytes))
