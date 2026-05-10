#!/usr/bin/env bash
set -euo pipefail

echo "🎬 Video QA Tester — Python Setup"
echo "=================================="

# Install Python deps
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Copy env file if needed
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠ Edit .env with your YouTube test account credentials"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Quick start:"
echo "  1. First login:  python -m videoqa.cli.main login"
echo "  2. Test video:   python -m videoqa.cli.test <url>"
echo "  3. Scan channel: python -m videoqa.cli.scan @channel"
echo ""
