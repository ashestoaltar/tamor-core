#!/bin/bash
set -e

cd "$(dirname "$0")/../.."
source api/venv/bin/activate
python -m api.utils.run_migrations
