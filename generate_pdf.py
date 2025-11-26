#!/usr/bin/env python3
"""
Generate PDF from Compliance Agent Report Markdown
"""

import markdown2
from weasyprint import HTML, CSS
from pathlib import Path

def generate_pdf():
    """Convert COMPLIANCE_AGENT_REPORT.md to PDF"""
    
    # Read markdown file
    md_file = Path("COMPLIANCE_AGENT_REPORT.md")
    if not md_file.exists():
        print(f"❌ Error: {md_file} not found")
        return
    
    print(f"📄 Reading {md_file}...")
    md_content = md_file.read_text(encoding='utf-8')
    
    # Convert markdown to HTML
    print("🔄 Converting Markdown to HTML...")
    html_content = markdown2.markdown(
        md_content,
        extras=[
            "fenced-code-blocks",
            "tables",
            "header-ids",
            "code-friendly",
            "cuddled-lists"
        ]
    )
    
    # Add CSS styling for better PDF output
    css_style = """
    <style>
        @page {
            size: A4;
            margin: 2cm;
            @bottom-right {
                content: "Page " counter(page) " of " counter(pages);
                font-size: 9pt;
                color: #666;
            }
        }
        body {
            font-family: 'Arial', 'Helvetica', sans-serif;
            line-height: 1.6;
            color: #333;
            font-size: 11pt;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-top: 30px;
            page-break-before: always;
            font-size: 24pt;
        }
        h1:first-of-type {
            page-break-before: avoid;
        }
        h2 {
            color: #34495e;
            border-bottom: 2px solid #95a5a6;
            padding-bottom: 8px;
            margin-top: 25px;
            font-size: 18pt;
        }
        h3 {
            color: #555;
            margin-top: 20px;
            font-size: 14pt;
        }
        h4 {
            color: #666;
            margin-top: 15px;
            font-size: 12pt;
        }
        code {
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 9pt;
            color: #c7254e;
        }
        pre {
            background-color: #f8f8f8;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 12px;
            overflow-x: auto;
            font-size: 9pt;
            line-height: 1.4;
        }
        pre code {
            background-color: transparent;
            padding: 0;
            color: #333;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
            font-size: 10pt;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #3498db;
            color: white;
            font-weight: bold;
        }
        tr:nth-child(even) {
            background-color: #f2f2f2;
        }
        blockquote {
            border-left: 4px solid #3498db;
            padding-left: 15px;
            margin-left: 0;
            color: #666;
            font-style: italic;
        }
        ul, ol {
            margin: 10px 0;
            padding-left: 30px;
        }
        li {
            margin: 5px 0;
        }
        .emoji {
            font-size: 14pt;
        }
        hr {
            border: none;
            border-top: 2px solid #ddd;
            margin: 30px 0;
        }
        strong {
            color: #2c3e50;
        }
        a {
            color: #3498db;
            text-decoration: none;
        }
        .page-break {
            page-break-before: always;
        }
    </style>
    """
    
    # Wrap in HTML structure
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Compliance Agent Technical Report</title>
        {css_style}
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    
    # Generate PDF
    print("📊 Generating PDF...")
    output_file = "COMPLIANCE_AGENT_REPORT.pdf"
    
    HTML(string=full_html).write_pdf(
        output_file,
        stylesheets=[CSS(string="""
            @page { size: A4; margin: 2cm; }
        """)]
    )
    
    print(f"✅ PDF generated successfully: {output_file}")
    print(f"📄 File size: {Path(output_file).stat().st_size / 1024:.1f} KB")

if __name__ == "__main__":
    generate_pdf()
