#!/bin/bash
# Kliqboost Automated Deployment Script
# Upgrades all services to Professional plan and redeploys

set -e

echo "🚀 Starting Kliqboost Professional Plan Deployment"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -d "web/kliqboost-api" ]; then
    print_error "Please run this script from the kliqboost project root directory"
    exit 1
fi

print_status "Checking git status..."
if [ -n "$(git status --porcelain)" ]; then
    print_warning "You have uncommitted changes. Committing them..."
    git add .
    git commit -m "Auto-commit before deployment"
fi

print_status "Pushing changes to trigger redeployment..."
git push origin main

print_success "Changes pushed! Render will now redeploy all services with Professional plan"

echo ""
echo "📋 Services being redeployed:"
echo "  • kliqboost-api (FastAPI backend)"
echo "  • kliqboost-admin (Admin panel)"
echo "  • kliqboost-portal (Client portal)"
echo "  • kliqboost-website (Marketing site)"
echo "  • kliqboost-vectordb (ChromaDB vector database)"
echo "  • kliqboost-autoresponder (AI userbot)"
echo "  • kliqboost-bot (Telegram bot)"
echo ""

print_status "Monitor deployment progress at: https://dashboard.render.com"

echo ""
print_warning "After all services show 'Live' status:"
echo "1. Create admin user: curl -X POST 'https://kliqboost-api.onrender.com/bot-stats/bootstrap-admin?email=admin@kliqboost.store&password=SecureAdmin2026!&name=Kliqboost%20Admin' -H 'X-Sync-Key: kliq-stats-2026-xK9m'"
echo "2. Test login at:"
echo "   - Admin: https://kliqboost-admin.onrender.com"
echo "   - Portal: https://kliqboost-portal.onrender.com"
echo "   - Credentials: admin@kliqboost.store / SecureAdmin2026!"

print_success "Deployment automation complete! 🎉"