# HLX Migrator 0.4.0 - serverlogin och automatisk cache

Denna version har två inloggningsflöden:

1. **Serverlogin** från Kubernetes/Podman Secret. Används automatiskt vid pod-start för att läsa in cache/snapshot från alla miljöer i `environments.yaml`.
2. **Browser-login** per användare. Används för interaktiva åtgärder i GUI:t och hålls i browserns `sessionStorage`.

## Secret

I `kube/podman-play-kube.yaml` finns Secret `hlx-migrator-serverlogin`:

```yaml
credentials:
  um:
    username: Demo
    password: change-me
    authentication: ""
  utb:
    username: Demo
    password: change-me
    authentication: ""
```

Byt lösenord innan start.

## Automatisk sync

När `hlx-migrator-ui` startar kör den:

- login mot varje miljö med serverlogin
- full sync av Forms
- workflow sync av Active Links, Filters, Escalations, Menus, Containers och Images

Cachen skrivs i service-namespace per miljö, exempelvis `um` och `utb`, så diff kan köras utan att användaren först behöver synca manuellt.

## Status

```bash
curl http://localhost:8091/api/server-cache/status
```

Manuell refresh:

```bash
curl -X POST http://localhost:8091/api/server-cache/refresh
```

## Build/start

```bash
podman build --no-cache -t localhost/hlx-migrator-backend:latest -f java-arapi-service/Containerfile java-arapi-service
podman build --no-cache -t localhost/hlx-migrator-ui:latest -f python-ui/Containerfile python-ui
podman kube down kube/podman-play-kube.yaml
podman play kube kube/podman-play-kube.yaml
```
