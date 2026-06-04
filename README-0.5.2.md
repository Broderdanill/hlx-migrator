# HLX Migrator 0.5.2

Changes:

- Dark mode UI.
- Removed per-row migration action button.
- Clicking an object name toggles selected/unselected.
- Startup server-cache can sync Forms, Active Links and Filters for forms matching scope.
- Scope still supports glob values such as `HLX*`.

Recommended sync section:

```yaml
sync:
  auto_start: true
  include_global: false
  continue_on_error: true
  object_types:
    forms: true
    form_details: false
    form_detail_limit: 0
    fields: true
    views: true
    active_links: true
    filters: true
    menus: false
    escalations: false
    containers: false
    images: false
```

Escalations remain disabled by default because this object type caused ARError 91 / RPC receive errors in the test environment.
