# Cleanup audit for 1.0.0

Removed from the source package:

- `.git/` repository metadata
- root-level `script.js`
- root-level `script_check.js`
- Python `__pycache__/`
- runtime `data/`
- bundled BMC ARAPI `.jar` files
- old `build_all.sh`
- duplicate `java-arapi-service/README.md`

Added:

- `scripts/buildah-build.sh`
- `java-arapi-service/lib/.gitkeep`

BMC ARAPI libraries must be copied manually into `java-arapi-service/lib/` before building.
