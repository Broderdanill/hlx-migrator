# HLX Migrator 0.5.0

Den här versionen gör gränssnittet mer Migrator-likt:

- vänster objektträd
- huvudtabell per objekttyp
- miljö-/cachekort med senaste sync, scope och antal objekt
- nedre job/status-panel
- transportlista längst ned

Server-cache kör vid pod-start med `serverlogin` från Secret. Default-sync är medvetet konservativ:

- Forms: på
- Active Links: på
- Filters/Menus/Escalations/Containers/Images: av tills man uttryckligen slår på dem i YAML

Scope respekteras:

```yaml
scope:
  include_form_prefixes: [HLX*]
  exclude_form_prefixes: []
```

Status:

```bash
curl http://localhost:8091/api/server-cache/status
curl http://localhost:8091/api/cache/summary
```
