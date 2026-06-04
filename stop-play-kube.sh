#!/usr/bin/env bash
set -euo pipefail
podman play kube --down kube/podman-play-kube.yaml || true
podman pod rm -f hlx-migrator || true
