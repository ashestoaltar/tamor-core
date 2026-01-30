"""
PDF Exporter

Phase 6.4: Plugin Framework Expansion

Converts markdown to styled PDF documents using WeasyPrint.
"""

import markdown
from weasyprint import HTML, CSS
from typing import Optional
from io import BytesIO


# Default PDF styles - Tamor branding
DEFAULT_CSS = """
@page {
    size: letter;
    margin: 1in;
}

body {
    font-family: 'Georgia', serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #333;
}

h1 {
    font-size: 24pt;
    color: #1a1a1a;
    border-bottom: 2px solid #d4a84b;
    padding-bottom: 8px;
    margin-bottom: 16px;
}

h2 {
    font-size: 18pt;
    color: #2a2a2a;
    margin-top: 24px;
}

h3 {
    font-size: 14pt;
    color: #3a3a3a;
}

strong {
    color: #1a1a1a;
}

hr {
    border: none;
    border-top: 1px solid #ddd;
    margin: 24px 0;
}

blockquote {
    border-left: 3px solid #d4a84b;
    padding-left: 16px;
    margin-left: 0;
    color: #555;
    font-style: italic;
}

code {
    background: #f5f5f5;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: monospace;
    font-size: 10pt;
}

pre {
    background: #f5f5f5;
    padding: 12px;
    border-radius: 4px;
    overflow-x: auto;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
}

th, td {
    border: 1px solid #ddd;
    padding: 8px 12px;
    text-align: left;
}

th {
    background: #f5f5f5;
}
"""


class PDFExporter:
    """Exports markdown content to styled PDF."""

    def __init__(self, custom_css: Optional[str] = None):
        self.css = custom_css or DEFAULT_CSS

    def markdown_to_html(self, md_content: str) -> str:
        """Convert markdown to HTML."""
        html_body = markdown.markdown(
            md_content,
            extensions=["tables", "fenced_code", "toc"]
        )

        html_doc = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
        </head>
        <body>
            {html_body}
        </body>
        </html>
        """
        return html_doc

    def export_to_pdf(self, md_content: str) -> bytes:
        """Convert markdown to PDF bytes."""
        html = self.markdown_to_html(md_content)

        # Generate PDF
        pdf_buffer = BytesIO()
        HTML(string=html).write_pdf(
            pdf_buffer,
            stylesheets=[CSS(string=self.css)]
        )

        return pdf_buffer.getvalue()
