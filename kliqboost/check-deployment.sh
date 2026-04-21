#!/bin/bash
# Kliqboost Deployment Status Monitor
# Checks the status of all Render services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

echo "🔍 Checking Kliqboost deployment status..."
echo "=========================================="

# List of services to check
SERVICES=(
    "https://kliqboost-api.onrender.com"
    "https://kliqboost-admin.onrender.com"
    "https://kliqboost-portal.onrender.com"
    "https://kliqboost-website.onrender.com"
    "https://kliqboost-vectordb.onrender.com"
    "https://kliqboost-autoresponder.onrender.com"
    "https://kliqboost-bot.onrender.com"
)

SERVICE_NAMES=(
    "API Backend"
    "Admin Panel"
    "Client Portal"
    "Website"
    "Vector Database"
    "AI Autoresponder"
    "Telegram Bot"
)

ALL_LIVE=true

for i in "${!SERVICES[@]}"; do
    SERVICE="${SERVICES[$i]}"
    NAME="${SERVICE_NAMES[$i]}"

    echo -n "Checking $NAME... "

    # Try to connect with a short timeout
    if curl -s --max-time 10 --head "$SERVICE" > /dev/null 2>&1; then
        # Check if it's actually responding (not just Render's "service waking up" page)
        RESPONSE=$(curl -s --max-time 10 "$SERVICE" 2>/dev/null | head -1)

        if [[ "$RESPONSE" == *"SERVICE WAKING UP"* ]] || [[ "$RESPONSE" == *"INCOMING HTTP REQUEST DETECTED"* ]]; then
            print_warning "SLEEPING (Free tier)"
            ALL_LIVE=false
        elif [[ "$RESPONSE" == *"502"* ]] || [[ "$RESPONSE" == *"503"* ]] || [[ "$RESPONSE" == *"504"* ]]; then
            print_error "ERROR (Deploying/Crashed)"
            ALL_LIVE=false
        else
            print_success "LIVE ✓"
        fi
    else
        print_error "DOWN ✗"
        ALL_LIVE=false
    fi
done

echo ""
echo "=========================================="

if [ "$ALL_LIVE" = true ]; then
    print_success "All services are live and ready! 🎉"
    echo ""
    print_status "Next steps:"
    echo "1. Create admin user if not done:"
    echo '   curl -X POST "https://kliqboost-api.onrender.com/bot-stats/bootstrap-admin?email=admin@kliqboost.store&password=SecureAdmin2026!&name=Kliqboost%20Admin" -H "X-Sync-Key: kliq-stats-2026-xK9m"'
    echo ""
    echo "2. Test login:"
    echo "   Admin: https://kliqboost-admin.onrender.com"
    echo "   Portal: https://kliqboost-portal.onrender.com"
    echo "   Credentials: admin@kliqboost.store / SecureAdmin2026!"
else
    print_warning "Some services are still deploying or sleeping."
    echo ""
    print_status "Run this script again in a few minutes to check progress."
    print_status "Or check manually at: https://dashboard.render.com"
fi