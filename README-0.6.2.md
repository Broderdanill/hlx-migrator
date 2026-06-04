# HLX Migrator 0.6.2

## Ändringar

- Standardvyn är nu ett snabbt source browser-läge.
- Ingen diff körs automatiskt när man byter kategori eller miljö.
- Välj källmiljö och destination med `UM → UTB`.
- Objektlistan visar bara objekt som finns i källmiljön.
- Markera objekt och tryck **Compare markerade** för att jämföra endast dessa objekt mot destinationen.
- Menus, Active Link Guides, Filter Guides, Packing Lists, Applications och Images scope-filtreras nu i indexläge via objektnamn, till exempel `HLX*`.
- Global/containertyper laddas fortfarande index-only för att undvika tunga ARAPI/RPC-anrop.

## Viktig scope-notering

För Forms, Active Links, Filters och Escalations används formulärscope när workflow hämtas per form.
För globala objekt som Menus och containerkategorier finns ännu inte full dependency-resolver. Där används samma glob-regler mot objektets namn, exempelvis `HLX*`.
