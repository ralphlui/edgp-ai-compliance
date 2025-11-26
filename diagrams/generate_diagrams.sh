#!/bin/bash

# EDGP AI Compliance Agent - Diagram Generation Script
# This script generates all PlantUML diagrams in multiple formats

set -e

echo "=================================="
echo "PlantUML Diagram Generator"
echo "EDGP AI Compliance Agent"
echo "=================================="
echo ""

# Check if PlantUML is installed
if ! command -v plantuml &> /dev/null
then
    echo "❌ PlantUML is not installed!"
    echo ""
    echo "Install instructions:"
    echo "  macOS:   brew install plantuml"
    echo "  Linux:   apt-get install plantuml"
    echo "  Windows: choco install plantuml"
    echo ""
    echo "Or download from: https://plantuml.com/download"
    exit 1
fi

echo "✅ PlantUML found: $(plantuml -version | head -n 1)"
echo ""

# Create output directories
mkdir -p ../images/png
mkdir -p ../images/svg
mkdir -p ../images/pdf

echo "📂 Creating output directories..."
echo "  - ../images/png/"
echo "  - ../images/svg/"
echo "  - ../images/pdf/"
echo ""

# Count .puml files
PUML_COUNT=$(ls -1 *.puml 2>/dev/null | wc -l)

if [ "$PUML_COUNT" -eq 0 ]; then
    echo "❌ No .puml files found in current directory"
    exit 1
fi

echo "📊 Found $PUML_COUNT diagram(s) to generate"
echo ""

# Generate PNG images
echo "🖼️  Generating PNG images..."
plantuml -o ../images/png *.puml
echo "   ✅ PNG generation complete"
echo ""

# Generate SVG images
echo "📐 Generating SVG images (vector graphics)..."
plantuml -tsvg -o ../images/svg *.puml
echo "   ✅ SVG generation complete"
echo ""

# Generate PDF files
echo "📄 Generating PDF files (for printing)..."
plantuml -tpdf -o ../images/pdf *.puml
echo "   ✅ PDF generation complete"
echo ""

# List generated files
echo "=================================="
echo "✅ All diagrams generated successfully!"
echo "=================================="
echo ""
echo "Output locations:"
echo "  PNG: images/png/"
ls -1 ../images/png/*.png 2>/dev/null | sed 's/^/    - /'
echo ""
echo "  SVG: images/svg/"
ls -1 ../images/svg/*.svg 2>/dev/null | sed 's/^/    - /'
echo ""
echo "  PDF: images/pdf/"
ls -1 ../images/pdf/*.pdf 2>/dev/null | sed 's/^/    - /'
echo ""

# Print file sizes
echo "File sizes:"
du -h ../images/png/*.png ../images/svg/*.svg ../images/pdf/*.pdf 2>/dev/null | awk '{print "    "$2": "$1}'
echo ""

echo "✅ Done! You can now use these images in your presentations and documentation."
echo ""
