# HLX Migrator 0.8.8

Fixes:

- Download DEF now uses `ARServerUser.exportDefToFile(items, false, filePath, true)`.
  - The second parameter is `asXml`.
  - `false` produces classic AR System `.def` output.
  - Earlier versions accidentally passed the UI `related` flag as `asXml`, which produced ARXML content inside a `.def` file.
- Export response includes detected `format` (`DEF` or `ARXML`) and file size.
- Side-by-side diff remains the primary JSON view and uses a single synchronized scroll area with changed rows highlighted.
- Per-row Copy name action is retained.

Build both images because the DEF export fix is in the Java backend.
