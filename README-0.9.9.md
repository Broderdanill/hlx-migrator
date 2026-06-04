# HLX Migrator 0.9.9

## Added

- Login panel now opens as a modal-style popup instead of pushing the layout down.
- Data migration proof-of-concept for selected Forms.
- When selected items are Forms, **Migrate Selected** asks whether to migrate Workflow/Definitions or Data/Entries.
- Data migration supports:
  - AR qualification
  - Max rows, where 0 means all matching entries
  - Request ID handling modes:
    - update existing and create missing
    - skip existing
    - create duplicates/new rows
- Data migration requires a valid user Login to the target environment.

## Notes

Data migration uses ARAPI entry APIs by reflection to support different ARAPI 26.1 method signatures. Test carefully in UTB before using in production.
