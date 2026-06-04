# HLX Migrator 0.8.5

Fixes DEF download from the UI.

Changes:
- The backend ARAPI container now mounts the same `data` emptyDir volume at `/data`.
- Java exports DEF files to `/data/exports`.
- The Python UI exposes downloads from its `/app/data/exports` mount.
- Export responses now return only the safe file basename to the browser.
- This avoids broken URLs like `/api/download//data/exports/file.def`.

Rebuild both images and restart the pod because the kube YAML and UI code changed.
