# HLX Migrator 0.6.3

Changes:

- Selection list is now compact text instead of large badges.
- Migrate Selected moved next to Compare Selected.
- UI text normalized to English.
- Added select-all checkbox in the table header.
- Clicking an object name still toggles selection.
- Migration now falls back to server-login sessions when browser sessions are not available.
- Migration success/error events are written to the user activity log.

Build:

```bash
podman build --no-cache -t localhost/hlx-migrator-backend:latest -f java-arapi-service/Containerfile java-arapi-service
podman build --no-cache -t localhost/hlx-migrator-ui:latest -f python-ui/Containerfile python-ui
podman kube down kube/podman-play-kube.yaml
podman play kube kube/podman-play-kube.yaml
```
