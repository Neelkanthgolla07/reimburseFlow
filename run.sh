#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python app.py