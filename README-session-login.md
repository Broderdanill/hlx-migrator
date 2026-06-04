# HLX Migrator - sessionbaserad login

Denna version använder browser-sessioner i stället för credentials i Kubernetes Secret.

## Princip

- Användaren väljer miljö i webben.
- Användaren skriver username/password per miljö.
- Python UI skickar credentials till Java ARAPI-service för login.
- Java ARAPI-service skapar en `ARServerUser` per login och returnerar `sessionId`.
- Browsern sparar endast `sessionId` i `sessionStorage`, inte lösenordet.
- Metadata/export-anrop använder `X-HLX-Session` mot Java-service.

## Viktiga filer

- `java-arapi-service/src/main/java/se/arsbmc/hlxmigrator/arapi/SessionManager.java`
- `java-arapi-service/src/main/java/se/arsbmc/hlxmigrator/arapi/Main.java`
- `python-ui/app/arapi_client.py`
- `python-ui/app/main.py`
- `python-ui/app/static/index.html`
- `kube/podman-play-kube.yaml`

## ARAPI-JAR

Lägg BMC 26.1-relaterade JAR-filer i:

```text
java-arapi-service/lib/
```

Minst:

```text
arapi261_build000.jar
arapiext261_build000.jar
arlogger-26.1.00-SNAPSHOT.jar
```

Undvik att blanda in 9.1/9.9-JAR:ar i samma classpath.

## Bygg

```bash
podman build --no-cache \
  -t localhost/hlx-migrator-backend:latest \
  -f java-arapi-service/Containerfile \
  java-arapi-service

podman build --no-cache \
  -t localhost/hlx-migrator-ui:latest \
  -f python-ui/Containerfile \
  python-ui
```

## Kör

```bash
podman play kube kube/podman-play-kube.yaml
```

Öppna:

```text
http://localhost:8091
```

## Stoppa

```bash
podman kube down kube/podman-play-kube.yaml
```
