# HLX Migrator 0.6.1

Changes:

- Generic `Containers` category removed from the main UI.
- Containers are now categorized into:
  - Active Link Guides
  - Filter Guides
  - Packing Lists
  - Applications
- Generic/unknown containers are kept as `other_container` only if explicitly enabled with `containers: true`; they are not shown in the normal object tree.
- Left side environment selector is simplified to `source → target`, for example `UM → UTB`.
- Startup sync remains index-only for heavy metadata objects.

Recommended sync config:

```yaml
sync:
  auto_start: true
  include_global: true
  continue_on_error: true
  object_types:
    forms: true
    form_details: false
    form_detail_limit: 0
    fields: true
    views: true
    active_links: true
    filters: true
    menus: true
    escalations: true
    active_link_guides: true
    filter_guides: true
    packing_lists: true
    applications: true
    containers: false
    images: true
```
