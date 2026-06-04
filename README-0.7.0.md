# HLX Migrator 0.7.0

This version changes the cache/diff strategy:

- Startup still indexes metadata first so the UI becomes available quickly.
- After the index phase, the UI container starts a bounded deep-cache phase.
- Deep-cache loads full ARAPI definitions one object at a time and stores them in SQLite.
- Compare uses those full definitions and applies `diff.ignore_keys` from the ConfigMap.
- Switching object type or source/target environment clears the current selection to prevent accidental migration of objects selected in another list.

## Important sync settings

```yaml
sync:
  auto_start: true
  include_global: true
  continue_on_error: true
  details: true
  details_concurrency: 2
  details_max_per_type: 0
  details_refresh_existing: false
  detail_object_types:
    - form
    - active_link
    - filter
    - escalation
    - menu
    - active_link_guide
    - filter_guide
    - packing_list
    - application
    - image
```

`details_max_per_type: 0` means unlimited. In very large production environments you can set this to a number during testing, for example `100`.

`details_concurrency` should stay low for ARAPI/RPC stability. Start with `2`.

## Diff ignore defaults

Configure fields ignored in comparison:

```yaml
diff:
  ignore_order: true
  ignore_keys:
    - lastChanged
    - lastModified
    - lastModifiedBy
    - modifiedDate
    - timestamp
    - owner
    - changeDiary
    - lastUpdate
    - objectId
    - recordId
    - requestId
    - createDate
    - modifiedBy
    - lastModifiedDate
    - guid
    - internalId
```
