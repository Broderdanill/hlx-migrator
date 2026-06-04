#!/usr/bin/env bash
set -euo pipefail
podman pod logs -f hlx-migrator
