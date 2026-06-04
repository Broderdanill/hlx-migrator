# HLX Migrator 0.9.7

Changes:
- Incremental server sync support. Existing deep-cache is preserved when index metadata is unchanged.
- New/changed index entries are marked for deep refresh; unchanged objects are skipped in deep-cache.
- `sync.incremental` and `sync.purge_missing` config keys added.
- Sync Status button pulses while server sync is running.
- App icon size changed to 45x45.
- Example server-login password set to `P@ssw0rd`.
