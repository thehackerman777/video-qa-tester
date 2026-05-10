#!/usr/bin/env bash
# ============================================================
# Video QA Tester — Setup Script
# ============================================================
# Run this on a fresh Ubuntu 22.04+ VPS to set up everything.
# It installs Node.js, Docker, and builds the project.

set -euo pipefail

echo "🎬 Video QA Tester — Setup"
echo "=========================="
echo ""

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }

# --- Detect OS ---
if [ ! -f /etc/os-release ]; then
    error "Unsupported OS (only Ubuntu 20.04+ is supported)"
    exit 1
fi

. /etc/os-release
if [[ "$ID" != "ubuntu" ]]; then
    error "Unsupported OS: $ID (only Ubuntu is supported)"
    exit 1
fi

info "Detected: Ubuntu $VERSION_ID"

# --- Install Node.js 20 ---
if ! command -v node &> /dev/null; then
    info "Installing Node.js 20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
else
    info "Node.js $(node -v) already installed"
fi

# --- Install pnpm (for workspace management) ---
if ! command -v npm &> /dev/null; then
    info "npm found, good to go"
fi

# --- Install Docker ---
if ! command -v docker &> /dev/null; then
    info "Installing Docker..."
    curl -fsSL https://get.docker.com | sudo bash
    sudo usermod -aG docker "$USER"
    info "Docker installed (log out and back in for docker group to take effect)"
else
    info "Docker $(docker --version) already installed"
fi

# --- Install Docker Compose ---
if ! command -v docker-compose &> /dev/null; then
    info "Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
else
    info "Docker Compose $(docker-compose --version) already installed"
fi

# --- Install Playwright deps ---
info "Installing Playwright system dependencies..."
sudo apt-get install -y \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libdbus-1-3 libexpat1 libfontconfig1 libgbm1 libgcc1 \
    libglib2.0-0 libgtk-3-0 libnspr4 libpango-1.0-0 \
    libpangocairo-1.0-0 libstdc++6 libx11-6 libx11-xcb1 \
    libxcb1 libxcomposite1 libxcursor1 libxdamage1 libxext6 \
    libxfixes3 libxi6 libxrandr2 libxrender1 libxss1 \
    libxtst6 ca-certificates fonts-liberation wget curl \
    > /dev/null 2>&1

# --- Clone and install ---
if [ ! -d "video-qa-tester" ]; then
    info "You are inside the repo — skipping clone"
else
    info "Using existing directory"
    cd video-qa-tester
fi

info "Installing npm dependencies..."
npm install

info "Building packages..."
npm run build

# --- Create env file ---
if [ ! -f .env ]; then
    warn "Creating .env from .env.example — EDIT IT with your settings"
    cp .env.example .env
fi

# --- Summary ---
echo ""
echo "======================================"
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo "======================================"
echo ""
echo "Quick start:"
echo "  npm run cli test \"https://www.youtube.com/watch?v=dQw4w9WgXcQ\""
echo ""
echo "Channel scan (with API key):"
echo "  npm run cli scan \"@ChannelName\" --api-key YOUR_KEY"
echo ""
echo "Full stack (Docker):"
echo "  docker compose up -d"
echo "  Grafana: http://localhost:3001 (admin/admin)"
echo ""
echo "Edit .env with your settings:"
echo "  vi .env"
echo ""
