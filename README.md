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


## 1.1.9 notes

- Customization Type detection now reads AR System object property `90015` when exposed by ARAPI. DEF exports show this as `object-prop`; sampled values map as `1 = Overlay` and `4 = Custom`.
- Numeric customization values are no longer treated generically as Base/Custom/Overlay unless they come from the known object property.
- Objects that still do not expose layer metadata remain `Unknown`.

## 1.1.8 notes

- Difference calculations now use the same normalization and ignored-key configuration as the Compare dialog.
- Missing customization layer metadata is shown as `Unknown` instead of being treated as `Base`.
- The Customization Type filter is a compact multi-select field for Base, Custom, Overlay and Unknown.
- The Java ARAPI service attempts to expose customization layer metadata from object details using ARAPI reflection and safe-object inspection.
