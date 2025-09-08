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
    echo "  setup                Setup virtual environment for publishing"
    echo "  help                 Show this help"
    echo
    echo "VERSION MANAGEMENT:"
    echo "  patch                Auto-increment patch version and publish"
    echo "  minor                Auto-increment minor version and publish"
    echo "  major                Auto-increment major version and publish"
    echo
    echo "SETUP OPTIONS:"
    echo "  setup                Create publishing virtual environment"
    echo "  setup --force        Recreate existing virtual environment"
    echo
    echo "EXAMPLES:"
    echo "  ./publish.sh setup               # Setup publishing environment"
    echo "  ./publish.sh publish             # Publish current version to PyPI"
    echo "  ./publish.sh test                # Test publish to TestPyPI"
    echo "  ./publish.sh patch               # Increment patch and publish"
    echo "  ./publish.sh dry-run             # Show what would happen"
    echo "  ./publish.sh check               # Check status"
    echo
    echo "ADVANCED:"
    echo "  ./publish.sh publish --force     # Skip safety checks"
    echo "  ./publish.sh test patch          # Test with patch increment"
    echo "  ./publish.sh setup --force       # Recreate virtual environment"
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
    
    # Check for virtual environment
    if [ -d "publish_env" ]; then
        echo -e "📦 Virtual environment: ${GREEN}Available${NC}"
        echo "   Location: ./publish_env"
        
        # Check if venv has required packages
        if [ -f "publish_env/bin/python" ]; then
            echo "   Status: Ready for publishing"
            
            # Check individual packages
            echo "   Dependencies:"
            for pkg in "twine" "requests" "build"; do
                if ./publish_env/bin/python -m pip show "$pkg" &> /dev/null; then
                    echo -e "     ✅ $pkg"
                else
                    echo -e "     ❌ $pkg"
                fi
            done
        else
            echo -e "   Status: ${YELLOW}Corrupted (run setup --force)${NC}"
        fi
    else
        echo -e "📦 Virtual environment: ${YELLOW}Not found${NC}"
        echo "   Run: ./publish.sh setup"
    fi
    
    # Get current version
    CURRENT_VERSION=$($PYTHON_CMD s3d_publish.py --dry-run 2>/dev/null | grep "Current version:" | cut -d' ' -f3 || echo "unknown")
    echo -e "📋 Current version: ${GREEN}$CURRENT_VERSION${NC}"
    
    # Check git status
    if git status --porcelain 2>/dev/null | grep -q .; then
        echo -e "⚠️  Git status: ${YELLOW}Uncommitted changes${NC}"
        git status --porcelain
    else
        echo -e "✅ Git status: ${GREEN}Clean${NC}"
    fi
    
    # Check for git tags
    if git tag --list | grep -q "v$CURRENT_VERSION"; then
        echo -e "🏷️  Git tag: ${GREEN}v$CURRENT_VERSION exists${NC}"
    else
        echo -e "🏷️  Git tag: ${YELLOW}v$CURRENT_VERSION not found${NC}"
    fi
    
    echo
    echo "🔧 System tools:"
    
    # Check Python
    if command -v $PYTHON_CMD &> /dev/null; then
        PYTHON_VERSION=$($PYTHON_CMD --version | cut -d' ' -f2)
        echo -e "   ✅ Python: ${GREEN}$PYTHON_VERSION${NC}"
    else
        echo -e "   ❌ Python: ${RED}Not found${NC}"
    fi
    
    # Check git
    if command -v git &> /dev/null; then
        GIT_VERSION=$(git --version | cut -d' ' -f3)
        echo -e "   ✅ Git: ${GREEN}$GIT_VERSION${NC}"
    else
        echo -e "   ❌ Git: ${RED}Not found${NC}"
    fi
    
    # Check system packages (if no venv)
    if [ ! -d "publish_env" ]; then
        echo
        echo "🌐 System packages:"
        for pkg in "build" "twine" "requests"; do
            if $PYTHON_CMD -m pip show "$pkg" &> /dev/null; then
                VERSION=$($PYTHON_CMD -m pip show "$pkg" | grep "Version:" | cut -d' ' -f2)
                echo -e "   ✅ $pkg: ${GREEN}$VERSION${NC}"
            else
                echo -e "   ❌ $pkg: ${RED}missing${NC} (install: pip install $pkg)"
            fi
        done
    fi
    
    # Check PyPI connectivity
    echo
    echo "🌍 PyPI connectivity:"
    if curl -s --connect-timeout 5 https://pypi.org &> /dev/null; then
        echo -e "   ✅ PyPI: ${GREEN}Reachable${NC}"
    else
        echo -e "   ⚠️  PyPI: ${YELLOW}Connection issue${NC}"
    fi
    
    if curl -s --connect-timeout 5 https://test.pypi.org &> /dev/null; then
        echo -e "   ✅ TestPyPI: ${GREEN}Reachable${NC}"
    else
        echo -e "   ⚠️  TestPyPI: ${YELLOW}Connection issue${NC}"
    fi
}

# Setup virtual environment
setup_environment() {
    echo -e "${BLUE}Setting up publishing environment...${NC}"
    
    FORCE_FLAG=""
    if [[ " $@ " =~ " --force " ]]; then
        FORCE_FLAG="--force"
        echo -e "${YELLOW}Force mode: Will recreate existing environment${NC}"
    fi
    
    $PYTHON_CMD s3d_publish.py --setup $FORCE_FLAG
    
    if [ $? -eq 0 ]; then
        echo
        echo -e "${GREEN}✅ Setup completed successfully!${NC}"
        echo -e "${BLUE}Next steps:${NC}"
        echo "  ./publish.sh check     # Verify setup"
        echo "  ./publish.sh test      # Test publication"
        echo "  ./publish.sh publish   # Publish to PyPI"
    else
        echo
        echo -e "${RED}❌ Setup failed!${NC}"
        echo "Check the error messages above for details."
        exit 1
    fi
}

# Clean build artifacts
clean_build() {
    echo -e "${BLUE}Cleaning build artifacts...${NC}"
    
    # Remove build directories
    for dir in "build" "dist" "*.egg-info"; do
        if [ -d "$dir" ] || ls $dir 2>/dev/null; then
            rm -rf $dir
            echo -e "   ${GREEN}Removed $dir${NC}"
        fi
    done
    
    # Remove Python cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    
    echo -e "   ${GREEN}Build artifacts cleaned${NC}"
}

# Show version info
show_version_info() {
    echo -e "${BLUE}Version Information${NC}"
    echo "==================="
    
    # Current version from file
    CURRENT_VERSION=$($PYTHON_CMD s3d_publish.py --dry-run 2>/dev/null | grep "Current version:" | cut -d' ' -f3 || echo "unknown")
    echo -e "📋 Local version: ${GREEN}$CURRENT_VERSION${NC}"
    
    # Try to get PyPI version
    echo "🔍 Checking PyPI versions..."
    
    # Check main PyPI
    if command -v curl &> /dev/null; then
        PYPI_VERSION=$(curl -s https://pypi.org/pypi/s3dgraphy/json | grep -o '"version":"[^"]*"' | cut -d'"' -f4 2>/dev/null || echo "unknown")
        if [ "$PYPI_VERSION" != "unknown" ] && [ ! -z "$PYPI_VERSION" ]; then
            echo -e "📊 PyPI version: ${GREEN}$PYPI_VERSION${NC}"
        else
            echo -e "📊 PyPI version: ${YELLOW}Not found or not accessible${NC}"
        fi
    fi
    
    # Check git tags
    if command -v git &> /dev/null && git rev-parse --git-dir &> /dev/null; then
        LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "none")
        echo -e "🏷️  Latest git tag: ${GREEN}$LATEST_TAG${NC}"
    fi
}

# Interactive mode
interactive_mode() {
    echo -e "${BLUE}s3dgraphy Interactive Publication${NC}"
    echo "================================"
    echo
    
    show_version_info
    echo
    
    echo "What would you like to do?"
    echo "  1) Check status"
    echo "  2) Setup environment"
    echo "  3) Test publish (TestPyPI)"
    echo "  4) Publish to PyPI"
    echo "  5) Increment version and publish"
    echo "  6) Clean build artifacts"
    echo "  7) Exit"
    echo
    
    read -p "Enter your choice (1-7): " choice
    
    case $choice in
        1)
            check_status
            ;;
        2)
            setup_environment
            ;;
        3)
            echo "Starting test publication..."
            $PYTHON_CMD s3d_publish.py --test
            ;;
        4)
            echo "Starting production publication..."
            $PYTHON_CMD s3d_publish.py
            ;;
        5)
            echo "Choose version increment:"
            echo "  1) Patch (x.x.X)"
            echo "  2) Minor (x.X.x)" 
            echo "  3) Major (X.x.x)"
            read -p "Enter choice (1-3): " ver_choice
            
            case $ver_choice in
                1) $PYTHON_CMD s3d_publish.py --version patch ;;
                2) $PYTHON_CMD s3d_publish.py --version minor ;;
                3) $PYTHON_CMD s3d_publish.py --version major ;;
                *) echo "Invalid choice" ;;
            esac
            ;;
        6)
            clean_build
            ;;
        7)
            echo "Goodbye!"
            exit 0
            ;;
        *)
            echo "Invalid choice"
            exit 1
            ;;
    esac
}

# Check for script dependencies
check_script_deps() {
    local missing_deps=()
    
    # Check for required commands
    for cmd in "git" "curl"; do
        if ! command -v $cmd &> /dev/null; then
            missing_deps+=($cmd)
        fi
    done
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        echo -e "${YELLOW}⚠️  Missing optional dependencies: ${missing_deps[*]}${NC}"
        echo "   Some features may not work properly"
        echo
    fi
}

# Main logic
main() {
    # Check script dependencies
    check_script_deps
    
    # If no arguments, show interactive mode
    if [ $# -eq 0 ]; then
        interactive_mode
        exit 0
    fi
    
    # Handle commands
    case "$1" in
        "help"|"-h"|"--help")
            show_help
            ;;
        "check")
            check_status
            ;;
        "setup")
            shift
            setup_environment "$@"
            ;;
        "version"|"--version")
            show_version_info
            ;;
        "clean")
            clean_build
            ;;
        "interactive"|"-i")
            interactive_mode
            ;;
        "publish")
            shift
            echo -e "${BLUE}Publishing to PyPI...${NC}"
            $PYTHON_CMD s3d_publish.py "$@"
            ;;
        "test")
            shift
            echo -e "${BLUE}Publishing to TestPyPI...${NC}"
            $PYTHON_CMD s3d_publish.py --test "$@"
            ;;
        "dry-run")
            shift
            echo -e "${BLUE}Dry run mode...${NC}"
            $PYTHON_CMD s3d_publish.py --dry-run "$@"
            ;;
        "patch")
            shift
            echo -e "${BLUE}Incrementing patch version...${NC}"
            $PYTHON_CMD s3d_publish.py --version patch "$@"
            ;;
        "minor")
            shift
            echo -e "${BLUE}Incrementing minor version...${NC}"
            $PYTHON_CMD s3d_publish.py --version minor "$@"
            ;;
        "major")
            shift
            echo -e "${BLUE}Incrementing major version...${NC}"
            $PYTHON_CMD s3d_publish.py --version major "$@"
            ;;
        *)
            echo -e "${RED}❌ Unknown command: $1${NC}"
            echo
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"