# HLX Migrator 0.5.3

Ändringar:

- Dark mode förbättrad.
- Syncstatus flyttad till expanderbar meny i topbar.
- Server-sync kan köras per miljö eller för alla miljöer.
- Objektlistan visar tydligare att kategorierna avser vald källa.
- Transportpanelen är borttagen.
- Valda objekt migreras via knappen **Migrera** med val av målmiljö och bekräftelse.
- Objektnamn klickas för markera/avmarkera.
- Diff-badges är klickbara filter.
- Statuspanelen är en användarlogg.
- Standard-YAML slår på fler objekt: Forms, Active Links, Filters, Menus, Escalations, Containers och Images.

Obs: faktisk migrering använder ARAPI exportDefToFile från källa följt av importDefFromFile i mål. Använd alltid testmiljö först.
