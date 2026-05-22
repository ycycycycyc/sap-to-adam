#!/usr/bin/env bash
set -euo pipefail

python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

mkdir -p outputs

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Add your ANTHROPIC_API_KEY before running live extraction."
else
  echo ".env already exists; leaving it unchanged."
fi

echo "Setup complete. Run: source venv/bin/activate && python src/extract.py"
