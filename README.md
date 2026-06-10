# HLX Migrator

HLX Migrator is a modern web-based migration and comparison tool for BMC Helix / Remedy AR System environments.

The goal of the project is to provide functionality similar to the classic Remedy Migrator while offering a modern user experience, automated environment synchronization, object comparison, workflow migration, and data migration.

The application is designed for developers, administrators, architects, and DevOps teams working with multiple AR System environments.

---

# Features

## Workflow Discovery

HLX Migrator automatically discovers and indexes workflow objects from configured AR System environments.

Supported object types:

* Forms
* Active Links
* Filters
* Escalations
* Menus
* Active Link Guides
* Filter Guides
* Packing Lists
* Applications
* Images

Object discovery respects configured scope rules.

Example:

```yaml
scope:
  include_form_prefixes:
    - "HLX*"

  exclude_form_prefixes: []

  customization_types:
    default:
      - Base
      - Custom
      - Overlay
      - Unknown
```

Only objects related to matching forms are indexed and displayed. The customization type defaults control which Remedy/Helix layers are preselected in Browse and Differences filters.

---

## Deep Metadata Cache

At startup HLX Migrator can automatically:

1. Connect to configured environments
2. Authenticate using server-side credentials
3. Read workflow metadata
4. Build a local cache
5. Load detailed object definitions

The cache provides:

* Faster browsing
* Faster comparisons
* Reduced AR API traffic
* Improved UI responsiveness

---

## Environment Comparison

Compare workflow between environments.

Examples:

```text
UM -> UTB
UTB -> PROD
DEV -> TEST
```

Comparison statuses:

| Status            | Meaning                   |
| ----------------- | ------------------------- |
| Equal             | Definitions are identical |
| Different         | Definitions differ        |
| Missing In Source | Exists only in target     |
| Missing In Target | Exists only in source     |

Comparisons are based on object definitions and metadata, not only object names.

---

## Workflow Migration

Workflow objects can be migrated directly between environments.

Supported operations:

* DEF Export
* DEF Import
* Environment-to-environment migration

Migration requires a user login against the target environment.

This ensures proper auditing inside AR System.

---

## DEF Export

Selected workflow objects can be exported as classic AR System DEF files.

Supported exports:

* Single object
* Multiple objects
* Related workflow objects

The generated files use the AR System DEF format rather than ARXML.

---

## Data Export

Form data can be exported directly from AR System.

Supported formats:

* CSV
* JSON

Export options:

* Qualification
* Maximum rows
* Selected fields

Example qualifications:

```text
'Status' = "Open"

'Assigned Group' = "Service Desk"

'Create Date' > $TIMESTAMP$
```

---

## Data Migration

Form data can be migrated between environments.

Supported options:

### Update Existing

Update entries where Request ID already exists.

### Skip Existing

Ignore entries already present.

### Create Duplicate

Create new entries regardless of existing Request IDs.

Migration options:

* Qualification
* Maximum rows
* Conflict handling
* Target environment

---

## User Login

HLX Migrator uses two different authentication models.

### Server Login

Used for:

* Startup synchronization
* Cache refresh
* Metadata indexing
* Comparisons

Credentials are stored in Kubernetes or Podman secrets.

### User Login

Used for:

* Workflow migration
* Data migration
* Future write operations

This provides proper audit tracking inside AR System.

---

## Synchronization

Synchronization can run:

* Automatically at startup
* Manually from the UI

Environment locks prevent concurrent operations against the same environment.

Examples:

```text
Sync UM
Migration UM
```

cannot run simultaneously.

---

## Activity Log

The Activity Log provides a user-friendly operational log.

Examples:

* Environment login
* Synchronization
* Workflow migration
* Data migration
* Exports
* Errors and warnings

The log is intended for users rather than low-level server diagnostics.

---

# Architecture

```text
┌─────────────────────────┐
│        Browser          │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│      FastAPI UI         │
│       Python API        │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   Java ARAPI Service    │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  BMC Helix AR System    │
└─────────────────────────┘
```

---

# Required BMC Libraries

The Java service depends on proprietary BMC Helix / AR System libraries.

These files are NOT included in the repository and must be supplied separately.

Required files:

```text
arapi261_build000.jar
arapiext261_build000.jar
arlogger-26.1.00-SNAPSHOT.jar
```

Place them in:

```text
java-arapi-service/lib/
```

before building the backend container.

Example:

```text
java-arapi-service/
└── lib/
    ├── arapi261_build000.jar
    ├── arapiext261_build000.jar
    └── arlogger-26.1.00-SNAPSHOT.jar
```

The exact filenames may vary depending on the Helix version being used.

---

# Build

## Using Buildah

```bash
./scripts/buildah-build.sh
```

Example:

```bash
buildah bud \
  -t localhost/hlx-migrator-backend:latest \
  -f java-arapi-service/Containerfile \
  java-arapi-service

buildah bud \
  -t localhost/hlx-migrator-ui:latest \
  -f python-ui/Containerfile \
  python-ui
```

---

# Deployment

## Start

```bash
podman play kube kube/podman-play-kube.yaml
```

## Stop

```bash
podman kube down kube/podman-play-kube.yaml
```

---

# Configuration

## environments.yaml

Example:

```yaml
environments:
  um:
    host: ars-arserver
    port: 46262
    rpc: 390620

  utb:
    host: ars-arserver
    port: 46262
    rpc: 390620

scope:
  include_form_prefixes:
    - "HLX*"

  exclude_form_prefixes: []

  customization_types:
    default:
      - Base
      - Custom
      - Overlay
      - Unknown

sync:
  auto_start: true

  include_global: false

  object_types:
    forms: true
    form_details: true
    fields: true
    views: true

    active_links: true
    filters: true
    escalations: true

    menus: true
    web_services: true
    associations: true

    containers: true
    images: true
```

---

## secrets.yaml

Example:

```yaml
credentials:
  um:
    username: Demo
    password: P@ssw0rd

  utb:
    username: Demo
    password: P@ssw0rd
```

Never commit secrets.yaml to source control.

---

# Environment Variables

## Backend

```text
HLX_CONFIG_DIR
HLX_ARAPI_LIB_DIR
ARAPI_SERVICE_PORT
EXPORT_DIR
LOG_LEVEL
```

## UI

```text
HLX_ARAPI_BASE_URL
HLX_CONFIG_DIR
HLX_DATA_DIR
HLX_AUTO_SERVER_SYNC
LOG_LEVEL
```

Supported log levels:

```text
TRACE
DEBUG
INFO
WARN
ERROR
```

---

# Security Recommendations

* Use browser login for all write operations.
* Store credentials in Kubernetes secrets.
* Limit access to production environments.
* Audit all workflow and data migrations.
* Never commit AR System credentials to source control.

---

# Contributing

This project is intended for internal use.

Contributions should follow:

* Consistent coding style
* English UI text
* Proper logging
* Backwards-compatible configuration changes

---

# License

Internal project.

Copyright © HLX.

## Version 1.0.6 notes

- Name search remains always visible.
- Changed By and Changed From/To filters are now inside an expandable Filters panel.
- Compare, Migrate, and Download buttons are disabled until at least one object is selected.



## 1.1.11 notes

- Replaced the Customization Type multi-select with a compact dropdown chip to reduce filter-bar clutter.
- Optimized result table rendering for large datasets by using fixed table layout, containment hints, and lighter Details button handling.
- Result rows now avoid embedding full row JSON in inline click handlers, which improves perceived responsiveness when paging through large Differences lists.

## 1.1.10 notes

- Customization Type detection now has a DEF fallback. If ARAPI object reflection does not expose layer metadata, the backend exports the single object to a temporary DEF file and parses the top-level `object-prop` property `90015`.
- Successfully inspected objects with no `90015` marker are treated as `Base` instead of `Unknown`. `Unknown` is reserved for objects where the layer could not be inspected.
- Object property `90015` values `1` and `2` are treated as `Overlay`; value `4` is treated as `Custom`.

## 1.1.9 notes

- Customization Type detection now reads AR System object property `90015` when exposed by ARAPI. DEF exports show this as `object-prop`; sampled values map as `1 = Overlay` and `4 = Custom`.
- Numeric customization values are no longer treated generically as Base/Custom/Overlay unless they come from the known object property.
- Objects that still do not expose layer metadata remain `Unknown`.

## 1.1.8 notes

- Difference calculations now use the same normalization and ignored-key configuration as the Compare dialog.
- Missing customization layer metadata is shown as `Unknown` instead of being treated as `Base`.
- The Customization Type filter is a compact multi-select field for Base, Custom, Overlay and Unknown.
- The Java ARAPI service attempts to expose customization layer metadata from object details using ARAPI reflection and safe-object inspection.


## 1.1.12 notes

- Result table columns can now be resized by dragging the divider on the right side of each resizable column header.
- Column widths are saved in the browser, so users can keep a wider Name column without changing server configuration.
- The default Name column is wider, and a Reset columns button restores the default layout.

### 1.1.14

- Aligned Advanced Filter fields so Customization follows the same label/input layout as Changed By and timestamp filters.
- Updated the dark theme to use the requested HLX color palette: dark blue, middle blue, cyan accent, yellow warning/accent, red error and dark green success.
- Difference view continues to compare only the currently selected source and destination environment pair.

### 1.1.13

- Fixed row **Details** action after the resizable-column optimization.
- Details now opens from the current rendered row index without embedding large JSON payloads in the table HTML.


## 1.1.15

- Updated button styling to a flatter, more modern single-colour appearance.
- Removed gradient/radial colour shifts from buttons and busy/sync button states.



### 1.1.16

- Refreshed the visual design for a more modern dark UI.
- Standardized panels, tables, buttons, filters, modal windows, and activity log styling.
- Improved filter alignment and spacing, including the customization filter.
- Kept the existing dark BMC-inspired palette while reducing heavy shadows and visual noise.


### 1.1.17

- Tightened the visual layout for better overview when working with many objects.
- Reduced table row height and made table controls more compact.
- Kept the modern dark theme while improving density in the object lists, sidebar, filters, and activity log.

### 1.1.18

UI layout polish:

- Moved paging/page-size controls and Reset columns into the table section where they logically belong.
- Changed Status / Activity Log from a fixed overlay to a normal panel below the result table, avoiding overlap with long result lists.
- Kept compact table row styling from 1.1.17.



## 1.1.19

- Table columns now default to fit the available viewport better, with horizontal scrolling only when resized/narrower than minimum widths.
- Result rows are more compact for high-volume object lists.
- Scrollbars are styled to match the dark UI.
- Object type navigation now uses compact monochrome icons inspired by Developer Studio categories.


## 1.1.21

- Clear View in Status / Activity Log now hides already-cleared server events persistently, so opening Sync Status does not re-populate old log rows.
- Browser polling is less aggressive when sync is idle and avoids unnecessary re-rendering of navigation, counters and job lists.
- The UI now shows a clearer current sync step while background sync is running, so long startup syncs feel active instead of frozen.
- Result tables show a lightweight loading state during object/difference fetches.


### 1.1.21

- Added Web Services as a first-class object type. They are detected from AR System containers where the container type is 5, matching DEF exports that use `begin container` with `type : 5`.
- Added Associations as a first-class object type. The Java ARAPI service uses reflection for association list/detail calls so it can work across ARAPI versions where the exact method signature differs.
- Browse, Differences, Sync Status, counts, Details, DEF export/migration payloads and the left object tree now include Web Services and Associations.


## Recent changes
- **1.1.24**: Kept the 12px table font while reducing table padding/controls for compact rows, and clarified the shared-cache/multi-user diff model.
- **1.1.23**: Moved source/destination into the header and tightened navigation/table spacing.


## 1.1.23

- Moved source/destination selection into the top header for a clearer flow.
- Made result rows significantly more compact for large object lists.
- Added Enter-to-login support in password/auth fields.
- Tightened navigation and table spacing.


## 1.1.24

- Restored/kept the normal table font size and made rows compact by reducing padding, button height and cell spacing instead of shrinking text.
- Documented the intended multi-user model: metadata and difference indexes are shared by environment pair, while browser selection/filter/login state remains user-local.
- Read-only Browse/Differences/Compare operations are designed to run in parallel across users; write operations still lock the affected target environment.
