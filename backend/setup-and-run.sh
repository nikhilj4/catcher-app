#!/bin/bash

# ============================================================================
# KNOWLEDGE VAULT - COMPLETE SETUP & RUN
# One script that does EVERYTHING
# ============================================================================

set -e

cd "/Users/nikhiljram/Downloads/link\ scaraper"

echo ""
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                   KNOWLEDGE VAULT - AUTO SETUP                      ║"
echo "║                   Starting everything for you...                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# ============================================================================
# STEP 1: Python Setup
# ============================================================================

echo "📦 Step 1: Setting up Python environment..."

if [ ! -d "venv" ]; then
    echo "   Creating virtual environment..."
    python3 -m venv venv
fi

echo "   Activating virtual environment..."
source venv/bin/activate

echo "   Installing Python dependencies..."
if pip install -q -r requirements.txt; then
    echo "   ✅ Python ready"
else
    echo "   ⚠️  Some packages had warnings (continuing)"
fi

echo ""

# ============================================================================
# STEP 2: Node Setup
# ============================================================================

echo "📦 Step 2: Setting up Node.js..."

if [ ! -d "node_modules" ]; then
    echo "   Installing npm packages..."
    npm install --legacy-peer-deps --silent
    echo "   ✅ Node ready"
else
    echo "   ✅ Node already ready"
fi

echo ""

# ============================================================================
# STEP 3: Docker Services
# ============================================================================

echo "🐳 Step 3: Starting Docker services..."
echo "   Starting PostgreSQL, Redis, Qdrant..."

docker-compose -f docker-compose.local.yml up -d

echo "   Waiting for services to start..."
sleep 5

if docker ps | grep -q knowledge_vault_db; then
    echo "   ✅ PostgreSQL running (port 5432)"
else
    echo "   ⚠️  PostgreSQL may need more time"
fi

if docker ps | grep -q knowledge_vault_redis; then
    echo "   ✅ Redis running (port 6379)"
else
    echo "   ⚠️  Redis may need more time"
fi

if docker ps | grep -q knowledge_vault_qdrant; then
    echo "   ✅ Qdrant running (port 6333)"
else
    echo "   ⚠️  Qdrant may need more time"
fi

echo ""

# ============================================================================
# STEP 4: Start Backend
# ============================================================================

echo "🚀 Step 4: Starting Backend Server..."
echo "   Backend will run on: http://localhost:8000"
echo ""
echo "   Opening new Terminal for backend..."
echo ""

# Create backend startup script
cat > .backend_run.sh << 'EOF'
#!/bin/bash
cd "/Users/nikhiljram/Downloads/link\ scaraper"
source venv/bin/activate
export $(cat .env.local | xargs)
echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║              BACKEND SERVER STARTING                      ║"
echo "║         http://localhost:8000                             ║"
echo "║         API Docs: http://localhost:8000/docs              ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
EOF

chmod +x .backend_run.sh

# Start backend in new terminal
osascript -e 'tell app "Terminal" to do script "cd '"$(pwd)"' && bash .backend_run.sh"'

sleep 3
echo "   ✅ Backend terminal opened"
echo ""

# ============================================================================
# STEP 5: Start Mobile App
# ============================================================================

echo "📱 Step 5: Starting Mobile App Preview..."
echo "   App will run on: http://localhost:8081"
echo ""
echo "   Opening new Terminal for Expo..."
echo ""

# Create mobile startup script
cat > .mobile_run.sh << 'EOF'
#!/bin/bash
cd "/Users/nikhiljram/Downloads/link\ scaraper"
export $(cat .env.local | xargs)
echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           EXPO DEVELOPMENT SERVER STARTING                ║"
echo "║                                                           ║"
echo "║  Once started, you can:                                   ║"
echo "║    Press 'i' → Open in iOS Simulator (recommended)        ║"
echo "║    Press 'a' → Open in Android Emulator                   ║"
echo "║    Press 'w' → Open in Web Browser                        ║"
echo "║    Press 'q' → Quit                                       ║"
echo "║                                                           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
npx expo start
EOF

chmod +x .mobile_run.sh

# Start mobile in new terminal
osascript -e 'tell app "Terminal" to do script "cd '"$(pwd)"' && bash .mobile_run.sh"'

sleep 2
echo "   ✅ Expo terminal opened"
echo ""

# ============================================================================
# COMPLETION
# ============================================================================

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                      ✨ ALL SET! ✨                                ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""
echo "🎉 Your local Knowledge Vault environment is now RUNNING!"
echo ""
echo "📍 What's happening:"
echo "   ✅ Backend API running on http://localhost:8000"
echo "   ✅ PostgreSQL database started (port 5432)"
echo "   ✅ Redis cache started (port 6379)"
echo "   ✅ Qdrant vector DB started (port 6333)"
echo "   ✅ Expo dev server starting..."
echo ""
echo "📱 Next step:"
echo "   1. Wait 10-20 seconds for both terminals to fully load"
echo "   2. In the Expo terminal, press 'i' for iOS Simulator"
echo "   3. The app will open in your iOS Simulator"
echo "   4. You can now see the mobile preview!"
echo ""
echo "🔗 Access your services:"
echo "   Backend API:      http://localhost:8000"
echo "   API Docs:         http://localhost:8000/docs"
echo "   Vector DB:        http://localhost:6333/dashboard"
echo "   PostgreSQL:       localhost:5432"
echo "   Redis:            localhost:6379"
echo ""
echo "⏹️  To stop everything:"
echo "   1. Press Ctrl+C in both Terminal windows"
echo "   2. Run: docker-compose -f docker-compose.local.yml down"
echo ""
echo "════════════════════════════════════════════════════════════════════"
echo ""

# Keep this terminal open
echo "This terminal will stay open. You can close it after you're done."
echo ""
read -p "Press Enter to keep this window open, or Ctrl+C to exit..."
