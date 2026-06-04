# HLX Migrator 0.9.0

Changes:

- Formats ARAPI Timestamp objects as readable UTC timestamps in object tables.
- Migration now verifies target objects after import:
  - target existed before
  - target exists after
  - target definition hash changed or not
  - target equals source after import
  - timestamp before/after
  - last changed by before/after
- Migration result dialog shows verification summary.
- Target cache is updated for verified migrated objects.

Note: if source and target definitions are already identical, AR System may import without updating Developer Studio timestamp. In that case verification should show `targetChanged: no` and `targetEqualsSource: yes`.
