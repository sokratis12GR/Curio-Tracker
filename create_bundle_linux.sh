#!/usr/bin/env bash
set -euo pipefail
pyinstaller --clean --log-level=DEBUG curio_tracker_linux.spec
