# HLX Migrator

HLX Migrator är en första körbar grund för ett ARAPI-baserat verktyg som jämför metadata/workflow mellan BMC Helix / AR System-miljöer och exporterar valda objekt till `.def`.

Projektet är byggt som två containers:

| Container | Port | Ansvar |
|---|---:|---|
| `hlx-migrator-ui` | 8091 | Python/FastAPI, enkel GUI, cache, diff, transportlista |
| `hlx-migrator-backend` | 8092 | Java ARAPI-service, login, metadatahämtning, `.def` export |

Detta gör att GUI/backend-lagret kan bytas eller utvecklas utan att ARAPI-lagret behöver ändras.

## Varför två containers?

ARAPI-delen är Java/JVM-beroende och kräver BMC:s JAR-filer. GUI, cache och diffmotor är Python-baserade. Genom att separera dem kan du uppgradera BMC JAR-filer och JVM-flaggor utan att röra GUI-koden.

## ARAPI-stöd i denna version

Java-servicen använder `ARServerUser` och förväntar sig BMC Helix 26.1 JAR-filer:

- `arapi261_build000.jar`
- `arapiext261_build000.jar`

De ska ligga här:

```text
java-arapi-service/lib/arapi261_build000.jar
java-arapi-service/lib/arapiext261_build000.jar
```

## Funktioner i version 0.1

- Logga in mot flera miljöer.
- Lista formulär.
- Läsa formulär med fields och views.
- Cachea formulärmetadata i SQLite.
- Jämföra Forms mellan två miljöer.
- Visa skillnader i enkel GUI.
- Markera objekt för transportlista.
- Exportera valda objekt via ARAPI `exportDefToFile`.

## Begränsningar i version 0.1

- GUI är avsiktligt enkel HTML/JS för att ge en körbar start.
- Workflow, Menus, Containers och Images har endpoints i Java-servicen men är ännu inte fullt integrerade i cache/diff-GUI.
- Packing List-skapande och Deployment Management är nästa steg.
- `.def` export använder ARAPI StructItemInfo. Om din JAR har annan konstruktor för `StructItemInfo` kan `createStructItemInfo` behöva justeras efter `javap`.

## Konfiguration

Kopiera secrets-exemplet:

```bash
cp python-ui/config/secrets.yaml.example python-ui/config/secrets.yaml
```

Redigera:

```yaml
environments:
  um:
    name: um
    host: arserver-um.example.com
    port: 0
    rpc: 390620
  utb:
    name: utb
    host: arserver-utb.example.com
    port: 0
    rpc: 390620
```

Credentials ligger separat:

```yaml
credentials:
  um:
    username: Demo
    password: secret
  utb:
    username: Demo
    password: secret
```

## Bygg

Från projektroten:

```bash
./build.sh
```

Det bygger:

```bash
hlx-migrator-backend:0.1.0
hlx-migrator-ui:0.1.0
```

## Kör med podman play kube

```bash
./run.sh
```

Öppna:

```text
http://localhost:8091
```

## Stoppa

```bash
podman pod stop hlx-migrator
podman pod rm hlx-migrator
```

## Lokal utveckling utan container

Starta Java-servicen:

```bash
cd java-arapi-service
mvn package
ARAPI_SERVICE_PORT=8092 java -jar target/hlx-migrator-arapi-service-0.1.0.jar
```

Starta Python UI:

```bash
cd python-ui
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
APP_PORT=8091 ARAPI_BASE_URL=http://localhost:8092 uvicorn app.main:app --host 0.0.0.0 --port 8091
```

## Rekommenderade nästa steg

1. Lägg till workflow-cache för Active Links, Filters och Escalations.
2. Lägg till Menus, Containers, Images i diffmotorn.
3. Bygg riktig Packing List-funktion via `createContainer` / `setContainer`.
4. Lägg till mer avancerad GUI med Vue eller React.
5. Lägg till incremental sync med `getObjectChangeTimes`.
6. Lägg till Deployment Management-flöde med separata bekräftelsesteg.

## Säkerhet

- Ingen import/deploy görs i denna version.
- Export är icke-destruktivt.
- Credentials ska ligga i secret/config-volume, inte byggas in i image.
- Endast `hlx-migrator-backend` behöver nå AR Server.

## Podman play kube som primär driftmodell

Den rekommenderade körningen är en pod med två containers:

```text
hlx-migrator
├── hlx-migrator-ui       port 8091
└── hlx-migrator-backend  port 8092
```

Båda containers delar samma pod-nätverk. UI-containern når ARAPI-containern via:

```text
http://localhost:8092
```

Start:

```bash
./run-play-kube.sh
```

Loggar:

```bash
./logs.sh
```

Stoppa och ta bort podden:

```bash
./stop-play-kube.sh
```

Kontrollera podden:

```bash
podman pod ps
podman ps --pod
```

UI finns på:

```text
http://localhost:8091
```

ARAPI-servicens healthcheck finns på:

```text
http://localhost:8092/health
```

## 0.8.7 notes

- Side-by-side JSON diff is highlighted with one shared scrollbar.
- Source/Target JSON standalone tabs were removed.
- DEF download now exports classic AR System DEF using ARAPI non-XML format.
- Each row has a Copy Name action.
