#!/bin/bash

# bump_and_push.sh - Automated version bump and push for s3dgraphy
# Usage:
#   ./bump_and_push.sh [patch|minor|major]
#   ./bump_and_push.sh --tag-only      (or -t)
#
# In --tag-only mode bump2version is NOT invoked: the script reads the
# current version from pyproject.toml, creates the matching `vX.Y.Z` tag
# if it doesn't already exist, and pushes commits and tags. This is the
# preferred path for releases whose version was bumped manually (e.g.
# PEP 440 pre-releases like 1.6.0.dev0 / 1.6.0a1 / 1.6.0rc1 that the
# default SemVer regex in .bumpversion.cfg cannot parse).

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
    echo "       $0 --tag-only           (alias: -t)"
    echo ""
    echo "Automated version bump and push for s3dgraphy"
    echo ""
    echo "Commands:"
    echo "  patch        Increment patch version (1.0.0 → 1.0.1)"
    echo "  minor        Increment minor version (1.0.1 → 1.1.0)"
    echo "  major        Increment major version (1.1.0 → 2.0.0)"
    echo "  --tag-only   Skip bump2version: read version from pyproject.toml,"
    echo "               create tag vX.Y.Z if missing, push commits + tags."
    echo "               Use this after a manual version edit (e.g. dev/rc)."
    echo ""
    echo "Examples:"
    echo "  $0 patch"
    echo "  $0 minor"
    echo "  $0 --tag-only"
    echo ""
    echo "PEP 440 pre-releases (1.6.0.dev0, 1.6.0a1, 1.6.0rc1):"
    echo "  Edit pyproject.toml, src/s3dgraphy/__init__.py and the"
    echo "  current_version line in .bumpversion.cfg by hand, commit,"
    echo "  then run: $0 --tag-only"
    echo ""
}

# Check if argument provided
if [ $# -eq 0 ]; then
    echo -e "${RED}❌ Error: No bump type specified${NC}"
    show_help
    exit 1
fi

BUMP_TYPE=$1

# Validate bump type / mode
TAG_ONLY=0
case "$BUMP_TYPE" in
    --tag-only|-t)
        TAG_ONLY=1
        ;;
    patch|minor|major)
        :
        ;;
    -h|--help)
        show_help
        exit 0
        ;;
    *)
        echo -e "${RED}❌ Error: Invalid bump type '$BUMP_TYPE'${NC}"
        show_help
        exit 1
        ;;
esac

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}❌ Error: Not in a git repository${NC}"
    exit 1
fi

# Helper: read version string from pyproject.toml (line: version = "x.y.z")
read_pyproject_version() {
    grep -E '^version[[:space:]]*=' pyproject.toml \
        | head -n1 \
        | sed -E 's/^version[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/'
}

# ---------------------------------------------------------------------------
# --tag-only mode: no bump2version, just tag the current version and push.
# ---------------------------------------------------------------------------
if [ "$TAG_ONLY" -eq 1 ]; then
    if [ ! -f pyproject.toml ]; then
        echo -e "${RED}❌ Error: pyproject.toml not found in $(pwd)${NC}"
        exit 1
    fi

    CURRENT_VERSION=$(read_pyproject_version)
    if [ -z "$CURRENT_VERSION" ]; then
        echo -e "${RED}❌ Error: could not read version from pyproject.toml${NC}"
        exit 1
    fi

    TAG="v$CURRENT_VERSION"
    echo -e "${BLUE}🏷  Tag-only mode${NC}"
    echo -e "Current version: ${GREEN}$CURRENT_VERSION${NC}"
    echo -e "Target tag:      ${GREEN}$TAG${NC}"

    # Warn on dirty tree but don't refuse — user may have just committed.
    if ! git diff --quiet || ! git diff --cached --quiet; then
        echo -e "${YELLOW}⚠️  Working directory has uncommitted changes${NC}"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Aborted."
            exit 1
        fi
    fi

    # Create tag if missing
    if git rev-parse -q --verify "refs/tags/$TAG" > /dev/null; then
        echo -e "${YELLOW}ℹ️  Tag $TAG already exists locally — skipping tag creation${NC}"
    else
        echo -e "${BLUE}🏷  Creating tag $TAG at HEAD...${NC}"
        git tag -a "$TAG" -m "Release $TAG"
        echo -e "${GREEN}✅ Tag $TAG created${NC}"
    fi

    # Push
    echo -e "${BLUE}📤 Pushing commits and tags to origin...${NC}"
    if git push && git push --tags; then
        echo -e "${GREEN}✅ Push successful${NC}"
    else
        echo -e "${RED}❌ Push failed${NC}"
        exit 1
    fi

    echo ""
    echo -e "${GREEN}🎉 SUCCESS!${NC}"
    echo -e "Tagged and pushed: ${GREEN}$TAG${NC}"
    echo ""
    echo -e "${BLUE}📝 Next steps:${NC}"
    echo "1. Go to GitHub → Releases → Create new release"
    echo "2. Tag: $TAG"
    echo "3. Publish release → Auto-publish to PyPI!"
    exit 0
fi

# ---------------------------------------------------------------------------
# Standard bump2version flow (patch/minor/major) — unchanged behavior.
# ---------------------------------------------------------------------------

# Check if working directory is clean
ALLOW_DIRTY=0
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo -e "${YELLOW}⚠️  Warning: Working directory has uncommitted changes${NC}"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
    ALLOW_DIRTY=1
fi

# Ensure virtual environment with bump2version
VENV_DIR=".venv"

# Find python interpreter
PYTHON_BIN=$(command -v python3 || command -v python)
if [ -z "$PYTHON_BIN" ]; then
    echo -e "${RED}❌ Error: python3 not found on PATH${NC}"
    exit 1
fi

# Create venv if missing
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${BLUE}📦 Creating virtual environment in ${VENV_DIR}${NC}"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VENV_BIN="$VENV_DIR/bin"
VENV_PYTHON="$VENV_BIN/python"
BUMP_CMD="$VENV_BIN/bump2version"
BUMP_ARGS=()

if [ "$ALLOW_DIRTY" -eq 1 ]; then
    BUMP_ARGS+=("--allow-dirty")
fi

# Install bump2version if missing in venv
if ! "$VENV_PYTHON" -m pip show bump2version > /dev/null 2>&1; then
    echo -e "${BLUE}📥 Installing bump2version inside ${VENV_DIR}${NC}"
    "$VENV_PYTHON" -m pip install --upgrade pip bump2version
fi

# Get current version before bump
echo -e "${BLUE}📋 Getting current version...${NC}"
CURRENT_VERSION=$(grep 'current_version = ' .bumpversion.cfg | cut -d' ' -f3)
echo -e "Current version: ${GREEN}$CURRENT_VERSION${NC}"

# Perform version bump
echo -e "${BLUE}🔢 Bumping $BUMP_TYPE version...${NC}"
if "$BUMP_CMD" "${BUMP_ARGS[@]}" "$BUMP_TYPE"; then
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
