# HLX Migrator 0.9.8

## Changes

- Added environment locks in the Python UI/backend layer.
  - Server sync and migration cannot run concurrently against the same target environment.
  - Lock state is exposed in Sync Status.
- Migration now requires a valid user/browser session for the target environment.
  - Server-login is still used for read/cache operations.
  - Write/import operations use the logged-in user's ARAPI session for auditability.
- Renamed **Browser Login** to **Login** in the UI.
- Added `LOG_LEVEL` support for both containers.
  - Supported values: `TRACE`, `DEBUG`, `INFO`, `WARN`, `ERROR`.
  - Default: `INFO`.
- Added `/api/log-level` endpoint in the UI service.

## Build

```bash
podman build --no-cache -t localhost/hlx-migrator-backend:latest -f java-arapi-service/Containerfile java-arapi-service
podman build --no-cache -t localhost/hlx-migrator-ui:latest -f python-ui/Containerfile python-ui
podman kube down kube/podman-play-kube.yaml
podman play kube kube/podman-play-kube.yaml
```

