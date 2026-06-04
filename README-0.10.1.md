# HLX Migrator 0.10.1

## Fixes

- Data export CSV now exports one column per AR field instead of a single raw JSON column.
- CSV/JSON data export now reads form field metadata and requests full entry data for those fields.
- Data export and data migration options are collected in one dialog each, followed by a single confirmation step.
- Close buttons in modals now use a compact `×` button.

## Notes

- CSV headers use AR field names. Duplicate field names are disambiguated with `[fieldId]`.
- Request ID is always included as the first column.
- Data export still uses server credentials because it is read-only.
- Data migration still requires user Login for the target environment.
