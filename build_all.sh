#!/usr/bin/env bash
set -euo pipefail
podman build -t localhost/hlx-migrator-backend:latest -f java-arapi-service/Containerfile java-arapi-service
podman build -t localhost/hlx-migrator-ui:latest -f python-ui/Containerfile python-ui
