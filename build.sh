#!/usr/bin/env bash
set -euo pipefail
podman build -t hlx-migrator-backend:0.1.0 -f java-arapi-service/Containerfile java-arapi-service
podman build -t hlx-migrator-ui:0.1.0 -f python-ui/Containerfile python-ui
