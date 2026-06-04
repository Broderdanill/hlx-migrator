# HLX Migrator 0.7.3

## Visual diff details

This version improves the Details panel shown after a compare:

- Shows what object was compared.
- Shows source and target environments.
- Shows whether full ARAPI details were loaded.
- Shows the configured ignored keys used during comparison.
- Shows a readable differences table with:
  - change type
  - DeepDiff path
  - source value
  - target value
- Adds a side-by-side normalized JSON view.
- Keeps the raw DeepDiff output available for troubleshooting.

Only normalized definitions are displayed in the comparison view, so cache/runtime metadata such as `deepCachedAt` is not shown as a real metadata difference.
