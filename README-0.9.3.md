# HLX Migrator 0.9.3

## Changes

- Compare summary badges are now colored by status:
  - `equal` = green
  - `different` = orange/yellow
  - `missing_in_source` / `missing_in_target` = red
  - `not_compared` = muted
- Summary badges with count `0` are hidden.
- Browser-native `alert`, `confirm` and `prompt` dialogs are replaced with styled in-app modals.
- Migration target selection now uses an in-app modal.
- Migration confirmation and result dialogs now use the same dark HLX Migrator UI style.
- DEF download confirmation and error dialogs now use the same modal style.

## Build

Only the UI image needs rebuilding:

```bash
podman build --no-cache -t localhost/hlx-migrator-ui:latest -f python-ui/Containerfile python-ui
podman kube down kube/podman-play-kube.yaml
podman play kube kube/podman-play-kube.yaml
```
