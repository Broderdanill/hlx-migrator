# HLX Migrator 0.3.0

Denna version ändrar UI-flödet så att inloggning är första steget när sidan öppnas.

## Nytt i 0.3.0

- Första sidan är nu en inloggningsvy.
- Varje miljö kan loggas in separat med eget username/password/auth.
- Sessioner hålls i browserns `sessionStorage` som ARAPI-session-id, inte som lösenord.
- Efter inloggning mot vald källa och valt mål visas diff-/migratorvyn.
- Inloggningspanelen finns kvar som infälld panel och kan öppnas igen.
- Standardkonfigurationen är satt till:
  - `um` och `utb`
  - `ars-arserver:46262`
  - RPC `390620`
  - `sv_SE`
  - `Europe/Stockholm`
  - scope `HLX*`
- Nästa del i planen är påbörjad: workflow-cache och diff för Active Links, Filters, Escalations samt global metadata för Menus, Containers och Images.

## Viktiga JAR-filer

Lägg minst dessa i `java-arapi-service/lib/` innan backend-build:

```text
arapi261_build000.jar
arapiext261_build000.jar
arlogger-26.1.00-SNAPSHOT.jar
```

Lägg inte gamla 9.1/9.9-JAR:ar i samma classpath.

## Build

```bash
podman build --no-cache -t localhost/hlx-migrator-backend:latest -f java-arapi-service/Containerfile java-arapi-service
podman build --no-cache -t localhost/hlx-migrator-ui:latest -f python-ui/Containerfile python-ui
```

## Start med podman play kube

```bash
podman kube down kube/podman-play-kube.yaml || true
podman play kube kube/podman-play-kube.yaml
```

Öppna:

```text
http://localhost:8091
```

## Verifiera

```bash
curl http://localhost:8091/api/health
curl http://localhost:8092/health
```

## Workflow sync

I GUI:t finns nu knappar för:

- Sync Forms källa/mål
- Sync Workflow källa/mål
- Jämför Forms
- Jämför Active Links
- Jämför Filters
- Jämför Escalations
- Jämför Menus

Workflow sync använder formulär-scope och hämtar workflow per formulär, vilket gör att workflow kopplat till inkluderade formulär följer med.
