#!/usr/bin/env bash
set -e

# Optionally create & activate a virtualenv (if preferred)
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies from your requirements file
pip install -r requirements.txt


# Run any database migrations, build steps, etc.
# e.g. flask db upgrade  (if using Flask-Migrate)
# or pytest to run tests
