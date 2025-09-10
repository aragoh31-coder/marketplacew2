#!/bin/bash

# Script to update vulnerable dependencies
echo "Updating vulnerable dependencies..."

# Backup original requirements.txt
cp requirements.txt requirements.txt.bak
echo "Original requirements.txt backed up to requirements.txt.bak"

# Replace with updated requirements
cp requirements_updated.txt requirements.txt
echo "Updated requirements.txt with secure versions"

# Install updated dependencies
pip install -r requirements.txt --no-cache-dir
echo "Dependencies updated successfully"

# Note about ecdsa replacement
echo "NOTE: ecdsa package has been removed and replaced with cryptography for ECDSA functionality"
echo "Any code using ecdsa directly will need to be updated to use cryptography instead"