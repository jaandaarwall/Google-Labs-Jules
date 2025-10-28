#!/usr/bin/env bash
set -e

# Optionally create & activate a virtualenv (if preferred)
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies from your requirements file
pip install -r requirements.txt
