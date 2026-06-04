# hlx-migrator ARAPI-service

Lägg dessa filer här innan du bygger containern:

- `lib/arapi261_build000.jar`
- `lib/arapiext261_build000.jar`

Bygg:

```bash
podman build -t hlx-migrator-backend:0.1.0 -f Containerfile .
```
