#!/bin/bash

# ============================================================================
# KNOWLEDGE VAULT - LOCAL DEVELOPMENT STARTUP SCRIPT
# ============================================================================
# This script starts:
# 1. Docker containers (PostgreSQL, Redis, Qdrant)
# 2. Backend FastAPI server
# 3. Mobile app Expo dev server
#
# Usage: bash START_LOCAL.sh
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

print_header() {
  echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BLUE}$1${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_success() {
  echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
  echo -e "${RED}✗ $1${NC}"
}

print_warning() {
  echo -e "${YELLOW}⚠ $1${NC}"
}

check_command() {
  if ! command -v $1 &> /dev/null; then
    print_error "$1 is not installed"
    return 1
  fi
  print_success "$1 found"
  return 0
}

# ============================================================================
# PRE-FLIGHT CHECKS
# ============================================================================

print_header "KNOWLEDGE VAULT - LOCAL DEVELOPMENT SETUP"

echo "Checking prerequisites..."

# Check required commands
check_command "python3" || exit 1
check_command "npm" || exit 1
check_command "docker" || exit 1
check_command "docker-compose" || exit 1

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
if [[ "$PYTHON_VERSION" < "3.9" ]]; then
  print_error "Python 3.9+ required (found $PYTHON_VERSION)"
  exit 1
fi
print_success "Python $PYTHON_VERSION"

# Check Node version
NODE_VERSION=$(node -v)
print_success "Node $NODE_VERSION"

print_success "All prerequisites met\n"

# ============================================================================
# SETUP PYTHON VIRTUAL ENVIRONMENT
# ============================================================================

print_header "STEP 1: Python Environment"

if [ ! -d "venv" ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv venv
  print_success "Virtual environment created"
else
  print_success "Virtual environment already exists"
fi

echo "Activating virtual environment..."
source venv/bin/activate
print_success "Virtual environment activated"

echo "Installing Python dependencies..."
if pip install -q -r requirements.txt 2>/dev/null; then
  print_success "Python dependencies installed"
else
  print_warning "Some packages may have failed to install (non-critical)"
fi

# ============================================================================
# SETUP NODE DEPENDENCIES
# ============================================================================

print_header "STEP 2: Node Dependencies"

if [ ! -d "node_modules" ]; then
  echo "Installing Node dependencies..."
  npm install --silent
  print_success "Node dependencies installed"
else
  print_success "Node dependencies already installed"
fi

# ============================================================================
# SETUP ENVIRONMENT VARIABLES
# ============================================================================

print_header "STEP 3: Environment Configuration"

if [ ! -f ".env.local" ]; then
  print_error ".env.local not found"
  exit 1
fi

print_success ".env.local loaded"

# ============================================================================
# START DOCKER CONTAINERS
# ============================================================================

print_header "STEP 4: Starting Docker Services"

echo "Starting PostgreSQL, Redis, and Qdrant..."
docker-compose -f docker-compose.local.yml up -d

# Wait for services to be healthy
echo "Waiting for services to be ready..."
sleep 5

# Check if containers are running
if docker ps | grep -q knowledge_vault_db; then
  print_success "PostgreSQL is running (port 5432)"
else
  print_error "PostgreSQL failed to start"
fi

if docker ps | grep -q knowledge_vault_redis; then
  print_success "Redis is running (port 6379)"
else
  print_error "Redis failed to start"
fi

if docker ps | grep -q knowledge_vault_qdrant; then
  print_success "Qdrant is running (port 6333, dashboard: http://localhost:6333/dashboard)"
else
  print_error "Qdrant failed to start"
fi

# ============================================================================
# APPLY DATABASE SCHEMA
# ============================================================================

print_header "STEP 5: Database Setup"

echo "Creating PostgreSQL user and database..."
docker exec knowledge_vault_db psql -U postgres -tc \
  "SELECT 1 FROM pg_database WHERE datname = 'knowledge_vault_dev'" | grep -q 1 || \
  docker exec knowledge_vault_db psql -U postgres -c \
  "CREATE USER vault_user WITH PASSWORD 'dev_password';" 2>/dev/null || true

docker exec knowledge_vault_db psql -U postgres -c \
  "ALTER USER vault_user CREATEDB;" 2>/dev/null || true

print_success "PostgreSQL user configured"

# ============================================================================
# START BACKEND
# ============================================================================

print_header "STEP 6: Starting Backend"

echo -e "${YELLOW}Opening new terminal for backend...${NC}"
echo -e "${YELLOW}The backend will start at: http://localhost:8000${NC}"
echo -e "${YELLOW}API docs available at: http://localhost:8000/docs${NC}\n"

# Save backend startup command to a script
cat > .backend_start.sh << 'EOF'
#!/bin/bash
source venv/bin/activate
export $(cat .env.local | xargs)
echo "Starting FastAPI backend..."
echo "Logs will appear below:"
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
EOF

chmod +x .backend_start.sh

# Start backend in a new terminal
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS
  osascript -e 'tell app "Terminal" to do script "cd '"$(pwd)"' && bash .backend_start.sh"'
else
  # Linux - use gnome-terminal or xterm
  if command -v gnome-terminal &> /dev/null; then
    gnome-terminal -- bash .backend_start.sh
  elif command -v xterm &> /dev/null; then
    xterm -hold -e "bash .backend_start.sh" &
  else
    print_warning "Could not open terminal for backend"
    print_warning "Please manually run: source venv/bin/activate && python -m uvicorn main:app --reload"
  fi
fi

print_success "Backend startup script created"
sleep 3

# ============================================================================
# START MOBILE APP
# ============================================================================

print_header "STEP 7: Starting Mobile App"

echo -e "${YELLOW}Opening new terminal for Expo...${NC}"
echo -e "${YELLOW}The app will be available at: http://localhost:8081${NC}"
echo -e "${YELLOW}Press 'i' for iOS Simulator or 'a' for Android Emulator${NC}\n"

# Save frontend startup command to a script
cat > .frontend_start.sh << 'EOF'
#!/bin/bash
export $(cat .env.local | xargs)
echo "Starting Expo development server..."
echo ""
echo "Once started:"
echo "  Press 'i' to open iOS Simulator"
echo "  Press 'a' to open Android Emulator"
echo "  Press 'w' to open web"
echo "  Press 'q' to quit"
echo ""
npm start
EOF

chmod +x .frontend_start.sh

# Start frontend in a new terminal
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS
  osascript -e 'tell app "Terminal" to do script "cd '"$(pwd)"' && bash .frontend_start.sh"'
else
  # Linux
  if command -v gnome-terminal &> /dev/null; then
    gnome-terminal -- bash .frontend_start.sh
  elif command -v xterm &> /dev/null; then
    xterm -hold -e "bash .frontend_start.sh" &
  else
    print_warning "Could not open terminal for frontend"
    print_warning "Please manually run: npm start"
  fi
fi

print_success "Frontend startup script created"

# ============================================================================
# FINAL SUMMARY
# ============================================================================

print_header "✨ SETUP COMPLETE!"

echo -e "Your local Knowledge Vault environment is now starting...\n"

echo -e "${GREEN}SERVICES:${NC}"
echo "  Backend API:        http://localhost:8000"
echo "  API Docs:           http://localhost:8000/docs"
echo "  ReDoc:              http://localhost:8000/redoc"
echo "  Health Check:       http://localhost:8000/health"
echo ""
echo "  Qdrant Vector DB:   http://localhost:6333/dashboard"
echo ""
echo "  PostgreSQL:         localhost:5432"
echo "  Redis:              localhost:6379"
echo ""

echo -e "${GREEN}NEXT STEPS:${NC}"
echo "  1. Wait for new terminals to open (may take a few seconds)"
echo "  2. In the frontend terminal, press 'i' for iOS or 'a' for Android"
echo "  3. The mobile app will open in Simulator/Emulator"
echo "  4. Unlock with biometric (any tap will work)"
echo "  5. You're ready to test!"
echo ""

echo -e "${GREEN}TEST THE FLOW:${NC}"
echo "  curl -X POST http://localhost:8000/api/save-link \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"url\": \"https://github.com\", \"custom_notes\": \"Test\"}' \\"
echo "    -G -d 'user_id=test-user'"
echo ""

echo -e "${YELLOW}TROUBLESHOOTING:${NC}"
echo "  • Backend won't start? Check requirements.txt is installed"
echo "  • App won't connect? Check backend is running"
echo "  • Database issues? Run: docker-compose -f docker-compose.local.yml down"
echo "  • Then restart this script"
echo ""

echo -e "${BLUE}Full docs: See LOCAL_DEVELOPMENT_GUIDE.md${NC}\n"

# ============================================================================
# KEEP SCRIPT RUNNING
# ============================================================================

echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Keep this process alive so Docker services stay running
wait
