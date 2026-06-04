# HLX Migrator 0.10.0

Changes from 0.9.9:

- Login now opens as a centered modal with backdrop instead of shifting the page layout.
- Download button now offers DEF export or Data export when exactly one Form is selected.
- Data export supports:
  - AR qualification
  - max rows, where 0 means unlimited
  - CSV or JSON
  - automatic file download through the shared export directory
- Data export is read-only and uses an available source session, falling back to server-login via the Python UI when available.

Build both UI and backend after upgrade.
