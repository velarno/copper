#!/bin/bash

# Setup script for pre-commit hooks

echo "Setting up pre-commit hooks..."

# Install pre-commit if not already installed
if ! command -v pre-commit &> /dev/null; then
    echo "Installing pre-commit..."
    uv add --group dev pre-commit
fi

# Install the pre-commit hooks
echo "Installing pre-commit hooks..."
pre-commit install

# Run pre-commit on all files to ensure everything is properly formatted
echo "Running pre-commit on all files..."
pre-commit run --all-files

echo "Pre-commit setup complete!"
echo ""
echo "Your pre-commit hooks are now configured to:"
echo "- Format code with black and isort"
echo "- Check code quality with flake8"
echo "- Run tests before each commit"
echo "- Ensure at least 50% test coverage"
echo ""
echo "To manually run pre-commit hooks:"
echo "  pre-commit run --all-files"
echo ""
echo "To run pre-commit on staged files only:"
echo "  pre-commit run"
