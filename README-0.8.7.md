# HLX Migrator 0.8.7

Changes:
- Side-by-side JSON diff now uses one shared scrollbar and highlights changed lines.
- Removed separate Source JSON and Target JSON tabs from Full Diff; the side-by-side tab is now the primary JSON view.
- Added a per-row Copy Name button for workflow/object lists.
- DEF export now uses ARAPI `exportDefToFile(..., false)` so the generated file is classic AR System DEF format instead of XML export format.

Build both images after upgrading:

```bash
podman build --no-cache -t localhost/hlx-migrator-backend:latest -f java-arapi-service/Containerfile java-arapi-service
podman build --no-cache -t localhost/hlx-migrator-ui:latest -f python-ui/Containerfile python-ui
podman kube down kube/podman-play-kube.yaml
podman play kube kube/podman-play-kube.yaml
```
