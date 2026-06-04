#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

mkdir -p data/exports

if [[ ! -f python-ui/config/secrets.yaml ]]; then
  echo "Missing python-ui/config/secrets.yaml"
  echo "Create it with: cp python-ui/config/secrets.yaml.example python-ui/config/secrets.yaml"
  exit 1
fi

podman play kube kube/podman-play-kube.yaml
