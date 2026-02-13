#!/usr/bin/env bash
set -euo pipefail

# Parse flags
SKIP_BREW_CHECK=false
WITH_TRAINING=false
for arg in "$@"; do
    case "$arg" in
        --skip-brew-check) SKIP_BREW_CHECK=true ;;
        --with-training) WITH_TRAINING=true ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "  StockScout Development Setup"
echo "========================================"
echo ""

# ------------------------------------------------------------------
# 1. Detect OS and architecture
# ------------------------------------------------------------------
OS=$(uname -s)
ARCH=$(uname -m)
echo "OS: $OS"
echo "Architecture: $ARCH"
echo ""

if [ "$OS" != "Darwin" ] && [ "$OS" != "Linux" ]; then
    echo -e "${YELLOW}WARNING: This script is designed for macOS and Linux.${NC}"
    echo "You may need to adjust steps for your OS."
fi

# ------------------------------------------------------------------
# 2. Check Homebrew (macOS only)
# ------------------------------------------------------------------
if [ "$OS" = "Darwin" ]; then
    if command -v brew &> /dev/null; then
        BREW_PREFIX=$(brew --prefix)

        if [ "$ARCH" = "arm64" ]; then
            if [[ "$BREW_PREFIX" == "/usr/local" ]]; then
                echo -e "${RED}WARNING: You are running Intel Homebrew on Apple Silicon (M1/M2/M3).${NC}"
                echo "This can cause compatibility issues with native ARM packages."
                echo ""
                echo "To install native Apple Silicon Homebrew:"
                echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                echo ""
                echo "After installation, add to your shell profile (~/.zshrc):"
                echo "  eval \"\$(/opt/homebrew/bin/brew shellenv)\""
                echo ""
                if [ "$SKIP_BREW_CHECK" = false ]; then
                    read -p "Continue with Intel Homebrew anyway? (y/N) " -n 1 -r
                    echo
                    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                        exit 1
                    fi
                else
                    echo -e "${YELLOW}Skipping brew check (--skip-brew-check).${NC}"
                fi
            else
                echo -e "${GREEN}Homebrew is correctly installed for Apple Silicon ($BREW_PREFIX).${NC}"
            fi
        else
            echo -e "${GREEN}Homebrew detected at $BREW_PREFIX (Intel).${NC}"
        fi
    else
        echo -e "${YELLOW}Homebrew not found.${NC}"
        echo "Install it from: https://brew.sh"
        echo "Then re-run this script."
        exit 1
    fi
fi

echo ""

# ------------------------------------------------------------------
# 3. Find a suitable Python (3.9+)
# ------------------------------------------------------------------
PYTHON_CMD=""
# Search stable Python versions first, avoid bleeding-edge (3.13+)
for cmd in python3.12 python3.11 python3.10 python3.9 /usr/bin/python3 /usr/local/bin/python3.12 /usr/local/bin/python3.11 /usr/local/bin/python3.10 /usr/local/bin/python3.9 python3; do
    if command -v "$cmd" &> /dev/null; then
        VERSION=$("$cmd" --version 2>&1 | awk '{print $2}') || continue
        if [ -z "$VERSION" ]; then
            continue
        fi
        MAJOR=$(echo "$VERSION" | cut -d. -f1)
        MINOR=$(echo "$VERSION" | cut -d. -f2)
        if [ -n "$MAJOR" ] && [ -n "$MINOR" ] && [ "$MAJOR" -ge 3 ] 2>/dev/null && [ "$MINOR" -ge 9 ] 2>/dev/null; then
            PYTHON_CMD=$cmd
            echo -e "${GREEN}Found Python $VERSION ($cmd)${NC}"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}Python 3.9+ not found.${NC}"
    if [ "$OS" = "Darwin" ]; then
        echo "Install it with: brew install python@3.11"
    else
        echo "Install it with your package manager (e.g., apt install python3.11)"
    fi
    exit 1
fi

echo ""

# ------------------------------------------------------------------
# 4. Create virtual environment
# ------------------------------------------------------------------
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv .venv
    echo -e "${GREEN}Virtual environment created at .venv/${NC}"
else
    echo "Virtual environment already exists at .venv/"
fi

# Activate
# shellcheck disable=SC1091
source .venv/bin/activate
echo "Activated virtual environment (Python: $(python --version))"
echo ""

# ------------------------------------------------------------------
# 5. Install dependencies
# ------------------------------------------------------------------
echo "Upgrading pip..."
pip install --upgrade pip --quiet

echo "Installing project dependencies..."
pip install -r requirements.txt

if [ "$WITH_TRAINING" = true ]; then
    if [ -f "requirements-training.txt" ]; then
        echo "Installing ML training dependencies..."
        pip install -r requirements-training.txt
    else
        echo -e "${YELLOW}requirements-training.txt not found, skipping training deps.${NC}"
    fi
fi

echo ""

# ------------------------------------------------------------------
# 6. Set up environment file
# ------------------------------------------------------------------
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}Created .env from .env.example${NC}"
        echo "Edit .env to configure your settings."
    fi
else
    echo ".env file already exists."
fi

echo ""

# ------------------------------------------------------------------
# 7. Verify installation
# ------------------------------------------------------------------
echo "Verifying installation..."
VERIFY_OK=true

for pkg in fastapi uvicorn yfinance sklearn pandas numpy joblib; do
    if python -c "import $pkg" 2>/dev/null; then
        VERSION=$(python -c "import $pkg; print(getattr($pkg, '__version__', 'ok'))" 2>/dev/null || echo "ok")
        echo -e "  ${GREEN}$pkg${NC} ($VERSION)"
    else
        echo -e "  ${RED}$pkg - MISSING${NC}"
        VERIFY_OK=false
    fi
done

echo ""

if [ "$VERIFY_OK" = true ]; then
    echo -e "${GREEN}========================================"
    echo "  Setup complete!"
    echo "========================================${NC}"
else
    echo -e "${YELLOW}========================================"
    echo "  Setup completed with warnings"
    echo "========================================${NC}"
    echo "Some packages failed to import. Check the errors above."
fi

echo ""
echo "Next steps:"
echo "  source .venv/bin/activate"
echo "  uvicorn src.api.main:app --reload"
echo ""
echo "Run tests:"
echo "  pytest tests/ -v"
