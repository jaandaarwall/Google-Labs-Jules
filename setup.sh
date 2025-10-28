#!/usr/bin/env bash
set -e

pip install uv

# Optionally create & activate a virtualenv (if preferred)
uv venv .venv
source .venv/bin/activate

# Upgrade pip
uv pip install --upgrade pip

# Install dependencies from your requirements file
uv pip install -r requirements.txt

# If you have dev/test dependencies:

# Run any database migrations, build steps, etc.
# e.g. flask db upgrade  (if using Flask-Migrate)
# or pytest to run tests
