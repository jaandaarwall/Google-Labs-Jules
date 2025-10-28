# #!/usr/bin/env bash
# set -e

# # Optionally create & activate a virtualenv (if preferred)
# python3 -m venv .venv
# source .venv/bin/activate

# # Upgrade pip
# pip install --upgrade pip

# # Install dependencies from your requirements file
# pip install -r requirements.txt

# # Run any database migrations, build steps, etc.
# # e.g. flask db upgrade  (if using Flask-Migrate)
# # or pytest to run tests


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

# run this after running this script
# git add setup.sh
# git commit -m "Fix setup.sh to use /tmp/venv and keep repo clean"
# git push origin flask-study-tracker


