# #!/usr/bin/env bash
# set -e

# # Optionally create & activate a virtualenv (if preferred)
# python3 -m venv .venv
# source .venv/bin/activate

# # Upgrade pip
# pip install --upgrade pip

# # Install dependencies from your requirements file
# pip install -r requirements.txt



#!/usr/bin/env bash
set -e

# Create venv outside the repo to avoid dirty working tree
python3 -m venv /tmp/venv
source /tmp/venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
fi

# Optionally install dev/test dependencies
if [ -f requirements-dev.txt ]; then
    pip install -r requirements-dev.txt
fi

# (Optional) Run migrations or tests
# flask db upgrade
# pytest
