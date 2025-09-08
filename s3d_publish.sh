#!/bin/bash

# s3dgraphy Publication Script (Unix wrapper)
# ===========================================

set -e  # Exit on any error

# Detect script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Detect Python command
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Help function
show_help() {
    echo -e "${BLUE}s3dgraphy Publication Tool${NC}"
    echo "=========================="
    echo
    echo "Usage: ./publish.sh [command] [options]"
    echo
    echo "COMMANDS:"
    echo "  publish              Publish to PyPI (production)"
    echo "  test                 Publish to TestPyPI"
    echo "  dry-run              Show what would be done"
    echo "  check                Check current status"
    echo "  help                 Show this help"
    echo
    echo "VERSION MANAGEMENT:"
    echo "  patch                Auto-increment patch version and publish"
    echo "  minor                Auto-increment minor version and publish"
    echo "  major                Auto-increment major version and publish"
    echo
    echo "EXAMPLES:"
    echo "  ./publish.sh publish         # Publish current version to PyPI"
    echo "  ./publish.sh test            # Test publish to TestPyPI"
    echo "  ./publish.sh patch           # Increment patch and publish"
    echo "  ./publish.sh dry-run         # Show what would happen"
    echo "  ./publish.sh check           # Check status"
    echo
    echo "ADVANCED:"
    echo "  ./publish.sh publish --force # Skip safety checks"
    echo "  ./publish.sh test patch      # Test with patch increment"
    echo
}

# Check status function
check_status() {
    echo -e "${BLUE}s3dgraphy Publication Status${NC}"
    echo "============================"
    echo
    
    # Check if we're in the right directory
    if [ ! -f "pyproject.toml" ] && [ ! -f "setup.py" ]; then
        echo -e "${RED}❌ Not in s3dgraphy root directory${NC}"
        echo "   Missing pyproject.toml or setup.py"
        exit 1
    fi
    
    # Get current version
    CURRENT_VERSION=$($PYTHON_CMD publish.py --dry-run 2>/dev/null | grep "Current version:" | cut -d' ' -f3 || echo "unknown")
    echo -e "📋 Current version: ${GREEN}$CURRENT_VERSION${NC}"
    
    # Check git status
    if git status --porcelain | grep -q .; then
        echo -e "⚠️  ${YELLOW}Uncommitted changes present${NC}"
        git status --porcelain
    else
        echo -e "✅ ${GREEN}Git working directory clean${NC}"
    fi
    
    # Check required tools
    echo
    echo "🔧 Tool availability:"
    
    if command -v $PYTHON_CMD &> /dev/null; then
        PYTHON_VERSION=$($PYTHON_CMD --version 2>&1)
        echo -e "   ✅ Python: ${GREEN}$PYTHON_VERSION${NC}"
    else
        echo -e "   ❌ ${RED}Python not found${NC}"
    fi
    
    if $PYTHON_CMD -m pip show build &> /dev/null; then
        echo -e "   ✅ ${GREEN}build module available${NC}"
    else
        echo -e "   ⚠️  ${YELLOW}build module missing${NC} (install: pip install build)"
    fi
    
    if $PYTHON_CMD -m pip show twine &> /dev/null; then
        echo -e "   ✅ ${GREEN}twine available${NC}"
    else
        echo -e "   ⚠️  ${YELLOW}twine missing${NC} (install: pip install twine)"
    fi
    
    if command -v git &> /dev/null; then
        echo -e "   ✅ ${GREEN}git available${NC}"
    else
        echo -e "   ❌ ${RED}git not found${NC}"
    fi
    
    echo
}

# Main command processing
case "${1:-help}" in
    help|-h|--help)
        show_help
        ;;
    
    check|status)
        check_status
        ;;
    
    publish)
        shift  # Remove 'publish' from arguments
        echo -e "${GREEN}🚀 Publishing to PyPI...${NC}"
        $PYTHON_CMD publish.py "$@"
        ;;
    
    test)
        shift  # Remove 'test' from arguments
        echo -e "${YELLOW}🧪 Publishing to TestPyPI...${NC}"
        $PYTHON_CMD publish.py --test "$@"
        ;;
    
    dry-run|dry)
        shift  # Remove 'dry-run' from arguments
        echo -e "${BLUE}🧪 Dry run mode...${NC}"
        $PYTHON_CMD publish.py --dry-run "$@"
        ;;
    
    patch)
        shift  # Remove 'patch' from arguments
        echo -e "${GREEN}📈 Incrementing patch version and publishing...${NC}"
        $PYTHON_CMD publish.py --version patch "$@"
        ;;
    
    minor)
        shift  # Remove 'minor' from arguments
        echo -e "${GREEN}📈 Incrementing minor version and publishing...${NC}"
        $PYTHON_CMD publish.py --version minor "$@"
        ;;
    
    major)
        shift  # Remove 'major' from arguments  
        echo -e "${GREEN}📈 Incrementing major version and publishing...${NC}"
        $PYTHON_CMD publish.py --version major "$@"
        ;;
    
    *)
        echo -e "${RED}❌ Unknown command: $1${NC}"
        echo
        show_help
        exit 1
        ;;
esac
