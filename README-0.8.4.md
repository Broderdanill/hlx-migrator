# HLX Migrator 0.8.4

Changes:

- Added **Download DEF** next to **Migrate Selected**.
- Download exports selected source objects to a `.def` file using ARAPI `exportDefToFile`.
- Export uses a valid browser session when available and falls back to server-login session.
- The generated file is downloaded through `/api/download/{file}`.
- User activity log now records DEF export start/completion/failure.
