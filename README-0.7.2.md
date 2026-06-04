# HLX Migrator 0.7.2

Fixes diff normalization so built-in cache/runtime metadata is always ignored, even when ConfigMap defines custom `diff.ignore_keys`.

Important: `deepCachedAt`, `capturedAt`, `definitionLoaded`, `indexOnly`, `cacheNamespace`, `debug`, `errors`, `sync`, and `scope` are never compared.

Build UI image after upgrading:

```bash
podman build --no-cache -t localhost/hlx-migrator-ui:latest -f python-ui/Containerfile python-ui
podman kube down kube/podman-play-kube.yaml
podman play kube kube/podman-play-kube.yaml
```

Backend rebuild is not required for this fix.
