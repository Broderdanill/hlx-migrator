# HLX Migrator 0.9.4

## Changes

- The UI now stays available while server startup sync/deep-cache is running.
- `/api/environments`, `/api/cache/summary`, and `/api/server-cache/status` now return a lightweight sync status instead of the full internal sync result payload.
- The full per-step cache payloads are still kept internally, but are not serialized to the browser on every refresh.
- Sync Status continues to show environment status, jobs, and progress while the cache is being built.

## Why

Large startup sync results could make the browser wait for huge JSON payloads and leave the page on a loading/hourglass state while deep-cache was still running. This version separates the UI status API from the internal cache job state.
