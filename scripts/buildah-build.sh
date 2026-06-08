#!/usr/bin/env bash
set -euo pipefail

UI_IMAGE="${UI_IMAGE:-localhost/hlx-migrator-ui:latest}"
BACKEND_IMAGE="${BACKEND_IMAGE:-localhost/hlx-migrator-backend:latest}"

echo "Building backend image: ${BACKEND_IMAGE}"
buildah bud --no-cache --tag "${BACKEND_IMAGE}" --file java-arapi-service/Containerfile java-arapi-service

echo "Building UI image: ${UI_IMAGE}"
buildah bud --no-cache --tag "${UI_IMAGE}" --file python-ui/Containerfile python-ui

echo "Done."
buildah images | grep -E 'hlx-migrator-(ui|backend)' || true
