#!/bin/bash
set -e

# Check if we have uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "Error: You have uncommitted changes. Please commit or stash them first."
    exit 1
fi

# Get current version
CURRENT_VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
echo "Current version: $CURRENT_VERSION"

# Increment patch version
IFS='.' read -ra VERSION_PARTS <<< "$CURRENT_VERSION"
MAJOR=${VERSION_PARTS[0]}
MINOR=${VERSION_PARTS[1]}
PATCH=${VERSION_PARTS[2]}
NEW_PATCH=$((PATCH + 1))
NEW_VERSION="$MAJOR.$MINOR.$NEW_PATCH"

echo "Bumping version to: $NEW_VERSION"

# Update version in pyproject.toml
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i "" "s/version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml
else
    # Linux
    sed -i "s/version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml
fi

# Commit version bump
git add pyproject.toml
git commit -m "bump version to $NEW_VERSION"

# Clean dist directory
rm -rf dist/*

# Build
echo "Building package..."
uv build

# Check if this is a PyPI release or just local/Docker
if [ "$1" = "--pypi" ]; then
    # Publish to PyPI
    echo "Publishing to PyPI..."
    if [ -z "$PYPI_API_TOKEN" ]; then
        echo "Error: PYPI_API_TOKEN environment variable not set"
        echo "For PyPI release, set PYPI_API_TOKEN and run with --pypi flag"
        exit 1
    fi
    uv publish --token "$PYPI_API_TOKEN"
else
    echo "Built package locally. To publish to PyPI, run with --pypi flag"
fi

# Build and push Docker image
echo "Building Docker image..."
docker build -t blitz-agent-mcp:$NEW_VERSION .
docker build -t blitz-agent-mcp:latest .

# Optional: push to registry (uncomment if you have a registry)
# echo "Pushing Docker image..."
# docker push your-registry/blitz-agent-mcp:$NEW_VERSION
# docker push your-registry/blitz-agent-mcp:latest

# Push commit
git push

# Create and push tag
git tag "v$NEW_VERSION"
git push origin "v$NEW_VERSION"

echo "Successfully released version $NEW_VERSION"
echo ""
echo "To install locally with uvx, run:"
echo "  uvx install ./dist/blitz_agent_mcp-$NEW_VERSION-py3-none-any.whl"
echo ""
echo "Or install from built package:"
echo "  pip install ./dist/blitz_agent_mcp-$NEW_VERSION-py3-none-any.whl" 