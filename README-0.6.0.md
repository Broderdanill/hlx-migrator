# HLX Migrator 0.6.0

Denna version ändrar ARAPI-syncen så att tunga workflow-objekt indexeras med namnlistor först.

## Varför

ARAPI-anropet `getListEscalationObjects()` kan generera mycket stora RPC-svar. I större miljöer kan AR Server/transporten stänga svaret och ge:

```text
ProcNumber 84
ARError 91
OncRpcException: can not receive ONC/RPC data
```

## Ändring

Startup/server-sync använder nu index-only för:

- Forms
- Active Links
- Filters
- Escalations
- Menus
- Containers
- Images

Java-servicen använder namnlistor, till exempel:

- `getListActiveLink()` / `getListActiveLink(form)`
- `getListFilter()` / `getListFilter(form)`
- `getListEscalation()` / `getListEscalation(form)`
- `getListMenu(...)`
- `getListContainer(...)`
- `getListImage()`

Detaljer ska hämtas senare vid klick/jämförelse/migrering.

## Rekommenderad sync-config

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
    menus: true
    escalations: true
    containers: true
    images: true
```

## Bygg

```bash
podman build --no-cache -t localhost/hlx-migrator-backend:latest -f java-arapi-service/Containerfile java-arapi-service
podman build --no-cache -t localhost/hlx-migrator-ui:latest -f python-ui/Containerfile python-ui
podman kube down kube/podman-play-kube.yaml
podman play kube kube/podman-play-kube.yaml
```
