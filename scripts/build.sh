#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

podman build \
  -t hlx-migrator-backend:latest \
  -f "$SCRIPT_DIR/../java-arapi-service/Containerfile" \
  "$SCRIPT_DIR/../java-arapi-service"

podman build \
  -t hlx-migrator-ui:latest \
  -f "$SCRIPT_DIR/../python-ui/Containerfile" \
  "$SCRIPT_DIR/../python-ui"