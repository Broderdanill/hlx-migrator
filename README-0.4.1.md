# HLX Migrator 0.4.1 - scoped robust server-cache

Den här versionen ändrar server-cache så att den respekterar `scope` och inte kör tung workflow-läsning som en enda stor ARAPI-operation.

## Viktiga ändringar

- `scope.include_form_prefixes` och `scope.exclude_form_prefixes` används innan forms och formulärkopplat workflow cacheas.
- `HLX*` fungerar som glob-mönster.
- Auto-sync kör stegvis och sparar status per steg.
- Fel i en kategori stoppar inte hela syncen om `continue_on_error: true`.
- Escalations är avstängda som default eftersom ARAPI/RPC tappade svaret i din miljö vid `getListEscalationObjects`.
- Nya Java-endpoints finns för separata objektfamiljer:
  - `/metadata/active-links?form=...`
  - `/metadata/filters?form=...`
  - `/metadata/escalations?form=...`

## Rekommenderad config

```yaml
scope:
  include_form_prefixes: [HLX*]
  exclude_form_prefixes: []
sync:
  auto_start: true
  include_global: true
  continue_on_error: true
  object_types:
    forms: true
    fields: true
    views: true
    active_links: true
    filters: true
    menus: true
    escalations: false
    containers: false
    images: false
```

## Verifiering

```bash
curl http://localhost:8091/api/environments
curl http://localhost:8091/api/server-cache/status
```

Manuell refresh:

```bash
curl -X POST http://localhost:8091/api/server-cache/refresh
```

## Escalations

När forms/active links/filters/menus fungerar stabilt kan du slå på:

```yaml
sync:
  object_types:
    escalations: true
```

Om du fortfarande får ARError 91 bör vi nästa steg batcha escalation-hämtning ytterligare eller endast hämta namngivna escalations i mindre grupper.
