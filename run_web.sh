#!/usr/bin/env bash
# Start the web app. PORT (default 8000), HOST (default 127.0.0.1), SAATHI_REGISTRY = fixture (default; labelled DEMO data) | off (there is no live SEBI mode in this release)
cd "$(dirname "$0")" && exec python3 -B -m saathi_rc.web.app
