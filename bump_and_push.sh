#!/bin/bash

# bump_and_push.sh - Automated version bump and push for s3dgraphy
# Usage: ./bump_and_push.sh [patch|minor|major]

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Help function
show_help() {
    echo "Usage: $0 [patch|minor|major]"
    echo ""
    echo "Automated version bump and push for s3dgraphy"
    echo ""
    echo "Commands:"
    echo "  patch    Increment patch version (1.0.0 → 1.0.1)"
    echo "  minor    Increment minor version (1.0.1 → 1.1.0)"
    echo "  major    Increment major version (1.1.0 → 2.0.0)"
    echo ""
    echo "Examples:"
    echo "  $0 patch"
    echo "  $0 minor"
    echo ""
}

# Check if argument provided
if [ $# -eq 0 ]; then
    echo -e "${RED}❌ Error: No bump type specified${NC}"
    show_help
    exit 1
fi

BUMP_TYPE=$1

# Validate bump type
if [[ ! "$BUMP_TYPE" =~ ^(patch|minor|major)$ ]]; then
    echo -e "${RED}❌ Error: Invalid bump type '$BUMP_TYPE'${NC}"
    show_help
    exit 1
fi

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}❌ Error: Not in a git repository${NC}"
    exit 1
fi

# Check if working directory is clean
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo -e "${YELLOW}⚠️  Warning: Working directory has uncommitted changes${NC}"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Check if bump2version is installed
if ! command -v bump2version &> /dev/null; then
    echo -e "${RED}❌ Error: bump2version not found${NC}"
    echo "Install with: pip install bump2version"
    exit 1
fi

# Get current version before bump
echo -e "${BLUE}📋 Getting current version...${NC}"
CURRENT_VERSION=$(grep 'current_version = ' .bumpversion.cfg | cut -d' ' -f3)
echo -e "Current version: ${GREEN}$CURRENT_VERSION${NC}"

# Perform version bump
echo -e "${BLUE}🔢 Bumping $BUMP_TYPE version...${NC}"
if bump2version "$BUMP_TYPE"; then
    echo -e "${GREEN}✅ Version bump successful${NC}"
else
    echo -e "${RED}❌ Version bump failed${NC}"
    exit 1
fi

# Get new version after bump
NEW_VERSION=$(grep 'current_version = ' .bumpversion.cfg | cut -d' ' -f3)
echo -e "New version: ${GREEN}$NEW_VERSION${NC}"

# Push commits and tags
echo -e "${BLUE}📤 Pushing to GitHub...${NC}"
if git push && git push --tags; then
    echo -e "${GREEN}✅ Push successful${NC}"
else
    echo -e "${RED}❌ Push failed${NC}"
    exit 1
fi

# Success message
echo ""
echo -e "${GREEN}🎉 SUCCESS!${NC}"
echo -e "Version bumped: ${YELLOW}$CURRENT_VERSION${NC} → ${GREEN}$NEW_VERSION${NC}"
echo -e "Tag created and pushed: ${GREEN}v$NEW_VERSION${NC}"
echo ""
echo -e "${BLUE}📝 Next steps:${NC}"
echo "1. Go to GitHub → Releases → Create new release"
echo "2. Tag: v$NEW_VERSION"
echo "3. Publish release → Auto-publish to PyPI!"