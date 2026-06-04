# HLX Migrator 0.8.9

Changes:

- Adds `Timestamp` and `Last Changed By` columns to the object/workflow tables.
- Values are read from cached ARAPI metadata where available, with support for common fields such as `modifiedDate`, `lastModifiedDate`, `lastModifiedBy`, and `lastChangedBy`.
- Compare results keep source-side timestamp/changed-by metadata so the table does not lose these columns after compare.

Note: index-only rows may show blank metadata until deep-cache has loaded full object details.
