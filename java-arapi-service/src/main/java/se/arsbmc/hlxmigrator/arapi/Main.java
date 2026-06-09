package se.arsbmc.hlxmigrator.arapi;

import com.bmc.arsys.api.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import io.javalin.Javalin;
import io.javalin.http.Context;
import io.javalin.http.HttpStatus;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.file.*;
import java.util.*;
import java.lang.reflect.*;

public class Main {
    private static final ObjectMapper json = new ObjectMapper();
    private static final SessionManager sessions = new SessionManager();
    private static final Logger log = LoggerFactory.getLogger(Main.class);

    private static void configureLogging() {
        String level = System.getenv().getOrDefault("LOG_LEVEL", "INFO").toLowerCase(Locale.ROOT);
        System.setProperty("org.slf4j.simpleLogger.defaultLogLevel", level);
        System.setProperty("org.slf4j.simpleLogger.showDateTime", "true");
        System.setProperty("org.slf4j.simpleLogger.dateTimeFormat", "yyyy-MM-dd HH:mm:ss.SSS");
    }

    public static void main(String[] args) {
        configureLogging();
        int port = Integer.parseInt(System.getenv().getOrDefault("ARAPI_SERVICE_PORT", "8092"));

        log.info("Starting HLX Migrator ARAPI service with LOG_LEVEL={}", System.getenv().getOrDefault("LOG_LEVEL", "INFO"));

        Javalin app = Javalin.create(cfg -> cfg.http.defaultContentType = "application/json");

        app.exception(Exception.class, (e, ctx) -> {
            Throwable root = rootCause(e);
            log.error("ARAPI request failed: {} {} -> {}", ctx.method(), ctx.path(), root.toString(), root);
            ctx.status(HttpStatus.INTERNAL_SERVER_ERROR);
            ctx.json(ApiError.from(root instanceof Exception ? (Exception) root : e));
        });

        app.get("/health", ctx -> ctx.json(Map.of(
                "status", "ok",
                "service", "hlx-migrator-arapi",
                "port", port,
                "activeSessions", sessions.size(),
                "logLevel", System.getenv().getOrDefault("LOG_LEVEL", "INFO")
        )));

        app.post("/sessions/login", ctx -> {
            EnvConfig cfg = json.readValue(ctx.body(), EnvConfig.class);
            LoginResult result = sessions.login(cfg);
            ctx.json(result);
        });

        app.get("/sessions/me", ctx -> {
            String sessionId = sessionId(ctx);
            SessionManager.SessionEntry entry = sessions.info(sessionId);
            if (entry == null) {
                ctx.status(HttpStatus.UNAUTHORIZED);
                ctx.json(Map.of(
                        "valid", false,
                        "status", "expired",
                        "message", "Invalid or expired ARAPI session"
                ));
                return;
            }
            ctx.json(Map.of(
                    "valid", true,
                    "sessionId", entry.sessionId,
                    "environment", entry.environment,
                    "username", entry.username,
                    "createdAt", entry.createdAt.toString(),
                    "lastUsed", entry.lastUsed.toString()
            ));
        });

        app.post("/sessions/logout", ctx -> {
            String sessionId = sessionId(ctx);
            sessions.logout(sessionId);
            ctx.json(Map.of("status", "logged_out"));
        });

        app.get("/metadata/forms", ctx -> {
            ARServerUser user = user(ctx);
            List<String> names = user.getListForm();
            ctx.json(Map.of("forms", names));
        });

        app.get("/metadata/forms/{name}", ctx -> {
            ARServerUser user = user(ctx);
            String name = ctx.pathParam("name");
            Map<String,Object> out = new LinkedHashMap<>();
            Object formObj = user.getForm(name);
            out.put("type", "form");
            out.put("name", name);
            out.put("customizationType", detectCustomizationType(formObj));
            out.put("form", SafeObjectMapper.toSafe(formObj));
            out.put("fields", SafeObjectMapper.toSafe(user.getListFieldObjects(name)));
            out.put("views", SafeObjectMapper.toSafe(user.getListViewObjects(name, 0L, null)));
            ctx.json(out);
        });


        // Index endpoints: return names only. This is intentional.
        // Bulk object endpoints such as getListEscalationObjects() can produce very large
        // RPC replies and have caused ARError 91 / "can not receive ONC/RPC data" in large systems.
        app.get("/metadata/active-links", ctx -> {
            ARServerUser user = user(ctx);
            String form = ctx.queryParam("form");
            List<String> names = (form == null || form.isBlank())
                    ? user.getListActiveLink()
                    : user.getListActiveLink(form);
            ctx.json(Map.of("form", form == null ? "" : form, "activeLinks", names, "mode", "index_only"));
        });

        app.get("/metadata/filters", ctx -> {
            ARServerUser user = user(ctx);
            String form = ctx.queryParam("form");
            List<String> names = (form == null || form.isBlank())
                    ? user.getListFilter()
                    : user.getListFilter(form);
            ctx.json(Map.of("form", form == null ? "" : form, "filters", names, "mode", "index_only"));
        });

        app.get("/metadata/escalations", ctx -> {
            ARServerUser user = user(ctx);
            String form = ctx.queryParam("form");
            List<String> names = (form == null || form.isBlank())
                    ? user.getListEscalation()
                    : user.getListEscalation(form);
            ctx.json(Map.of("form", form == null ? "" : form, "escalations", names, "mode", "index_only"));
        });

        app.get("/metadata/workflow", ctx -> {
            ARServerUser user = user(ctx);
            String form = ctx.queryParam("form");
            Map<String,Object> out = new LinkedHashMap<>();
            out.put("form", form == null ? "" : form);
            out.put("mode", "index_only");
            if (form == null || form.isBlank()) {
                out.put("activeLinks", user.getListActiveLink());
                out.put("filters", user.getListFilter());
                out.put("escalations", user.getListEscalation());
            } else {
                out.put("activeLinks", user.getListActiveLink(form));
                out.put("filters", user.getListFilter(form));
                out.put("escalations", user.getListEscalation(form));
            }
            ctx.json(out);
        });

        app.get("/metadata/menus", ctx -> {
            ARServerUser user = user(ctx);
            ctx.json(Map.of("menus", user.getListMenu(0L, Collections.emptyList(), Collections.emptyList()), "mode", "index_only"));
        });

        app.get("/metadata/containers", ctx -> {
            ARServerUser user = user(ctx);
            ctx.json(Map.of("containers", user.getListContainer(0L, null, true, null, null), "mode", "index_only"));
        });

        app.get("/metadata/container-categories", ctx -> {
            ARServerUser user = user(ctx);
            ctx.json(categorizedContainers(user));
        });

        app.get("/metadata/images", ctx -> {
            ARServerUser user = user(ctx);
            ctx.json(Map.of("images", user.getListImage(), "mode", "index_only"));
        });

        // Detail endpoints: load one object on demand, not during startup indexing.
        app.get("/metadata/active-links/{name}", ctx -> {
            ARServerUser user = user(ctx);
            String name = ctx.pathParam("name");
            Object obj = user.getActiveLink(name);
            ctx.json(Map.of("type", "active_link", "name", name, "definitionLoaded", true,
                    "customizationType", detectCustomizationType(obj),
                    "object", SafeObjectMapper.toSafe(obj)));
        });

        app.get("/metadata/filters/{name}", ctx -> {
            ARServerUser user = user(ctx);
            String name = ctx.pathParam("name");
            Object obj = user.getFilter(name);
            ctx.json(Map.of("type", "filter", "name", name, "definitionLoaded", true,
                    "customizationType", detectCustomizationType(obj),
                    "object", SafeObjectMapper.toSafe(obj)));
        });

        app.get("/metadata/escalations/{name}", ctx -> {
            ARServerUser user = user(ctx);
            String name = ctx.pathParam("name");
            Object obj = user.getEscalation(name);
            ctx.json(Map.of("type", "escalation", "name", name, "definitionLoaded", true,
                    "customizationType", detectCustomizationType(obj),
                    "object", SafeObjectMapper.toSafe(obj)));
        });

        app.get("/metadata/menus/{name}", ctx -> {
            ARServerUser user = user(ctx);
            String name = ctx.pathParam("name");
            Object obj = user.getMenu(name, null);
            ctx.json(Map.of("type", "menu", "name", name, "definitionLoaded", true,
                    "customizationType", detectCustomizationType(obj),
                    "object", SafeObjectMapper.toSafe(obj)));
        });

        app.get("/metadata/containers/{name}", ctx -> {
            ARServerUser user = user(ctx);
            String name = ctx.pathParam("name");
            Object obj = user.getContainer(name);
            ctx.json(Map.of("type", "container", "name", name, "definitionLoaded", true,
                    "customizationType", detectCustomizationType(obj),
                    "object", SafeObjectMapper.toSafe(obj)));
        });

        app.get("/metadata/images/{name}", ctx -> {
            ARServerUser user = user(ctx);
            String name = ctx.pathParam("name");
            Object obj = user.getImage(name);
            ctx.json(Map.of("type", "image", "name", name, "definitionLoaded", true,
                    "customizationType", detectCustomizationType(obj),
                    "object", SafeObjectMapper.toSafe(obj)));
        });

        app.post("/export/def", ctx -> {
            ARServerUser user = user(ctx);
            ExportRequest req = json.readValue(ctx.body(), ExportRequest.class);
            List items = new ArrayList();
            for (ExportItem item : req.items) {
                Object structItem = createStructItemInfo(item);
                log.info("DEF export item: name='{}', objectType='{}', customizationType='{}', browserType='{}', mappedType='{}', struct={}",
                        item.name, item.objectType, item.customizationType, item.type, mapStructType(item), describeStructItemInfo(structItem));
                items.add(structItem);
            }
            Path dir = Paths.get(System.getenv().getOrDefault("EXPORT_DIR", "/data/exports"));
            Files.createDirectories(dir);
            String fileName = req.fileName == null || req.fileName.isBlank()
                    ? "export-" + System.currentTimeMillis() + ".def"
                    : req.fileName;
            Path target = dir.resolve(fileName).normalize();
            if (!target.startsWith(dir)) throw new IllegalArgumentException("Invalid export filename");
            // ARAPI signature: exportDefToFile(items, asXml, filePath, overwrite).
            // Use asXml=false to create classic AR System DEF, not ARXML.
            user.exportDefToFile(items, false, target.toString(), true);
            long fileSizeBytes = Files.exists(target) ? Files.size(target) : 0L;
            String exportedText = Files.exists(target) ? Files.readString(target) : "";
            String firstBytes = exportedText.stripLeading();
            ctx.json(Map.of(
                    "status", "exported",
                    "file", target.toString(),
                    "fileSizeBytes", fileSizeBytes,
                    "format", firstBytes.startsWith("<?xml") ? "ARXML" : "DEF",
                    "items", req.items.size()
            ));
        });


        app.post("/migrate/def", ctx -> {
            MigrateRequest req = json.readValue(ctx.body(), MigrateRequest.class);
            ARServerUser source = sessions.require(req.sourceSessionId);
            ARServerUser targetUser = sessions.require(req.targetSessionId);

            List items = new ArrayList();
            for (ExportItem item : req.items) {
                Object structItem = createStructItemInfo(item);
                log.info("DEF migration item: name='{}', objectType='{}', customizationType='{}', browserType='{}', mappedType='{}', struct={}",
                        item.name, item.objectType, item.customizationType, item.type, mapStructType(item), describeStructItemInfo(structItem));
                items.add(structItem);
            }

            Path dir = Paths.get(System.getenv().getOrDefault("EXPORT_DIR", "/data/exports"));
            Files.createDirectories(dir);
            String fileName = req.fileName == null || req.fileName.isBlank()
                    ? "migration-" + System.currentTimeMillis() + ".def"
                    : req.fileName;
            Path defFile = dir.resolve(fileName).normalize();
            if (!defFile.startsWith(dir)) throw new IllegalArgumentException("Invalid migration filename");

            // ARAPI signature: exportDefToFile(items, asXml, filePath, overwrite).
            // Use asXml=false to create classic AR System DEF, not ARXML.
            source.exportDefToFile(items, false, defFile.toString(), true);
            long fileSizeBytes = Files.exists(defFile) ? Files.size(defFile) : 0L;
            targetUser.importDefFromFile(defFile.toString());

            ctx.json(Map.of(
                    "status", "migrated",
                    "file", defFile.toString(),
                    "fileSizeBytes", fileSizeBytes,
                    "importCalled", true,
                    "items", req.items.size()
            ));
        });


        app.post("/data/export", ctx -> {
            ARServerUser user = user(ctx);
            DataExportRequest req = json.readValue(ctx.body(), DataExportRequest.class);
            if (req.form == null || req.form.isBlank()) throw new IllegalArgumentException("Missing form");
            Path dir = Paths.get(System.getenv().getOrDefault("EXPORT_DIR", "/data/exports"));
            Files.createDirectories(dir);
            String format = req.format == null || req.format.isBlank() ? "csv" : req.format.toLowerCase(Locale.ROOT);
            if (!format.equals("csv") && !format.equals("json")) throw new IllegalArgumentException("Unsupported export format: " + format);
            String ext = format.equals("json") ? ".json" : ".csv";
            String fileName = req.fileName == null || req.fileName.isBlank()
                    ? "data-" + safeFileName(req.form) + "-" + System.currentTimeMillis() + ext
                    : req.fileName;
            if (!fileName.endsWith(ext)) fileName += ext;
            Path target = dir.resolve(fileName).normalize();
            if (!target.startsWith(dir)) throw new IllegalArgumentException("Invalid export filename");
            List<FieldMeta> allFields = getFieldMeta(user, req.form);
            List<FieldMeta> exportFields = filterFields(allFields, req.fields);
            List<Object> entries = queryEntries(user, req.form, req.qualification, req.maxRows, fieldIds(exportFields));
            List<Map<String, Object>> normalizedRows = new ArrayList<>();
            for (Object e : entries) normalizedRows.add(normalizeEntryForExport(e, exportFields));

            if (format.equals("json")) {
                Files.writeString(target, json.writerWithDefaultPrettyPrinter().writeValueAsString(normalizedRows));
            } else {
                Files.writeString(target, buildCsv(normalizedRows, exportFields));
            }
            ctx.json(Map.of(
                    "status", "exported",
                    "form", req.form,
                    "matched", entries.size(),
                    "processed", entries.size(),
                    "fields", exportFields.size(),
                    "file", target.toString(),
                    "fileName", target.getFileName().toString(),
                    "fileSizeBytes", Files.size(target),
                    "format", format
            ));
        });

        app.post("/data/migrate", ctx -> {
            DataMigrateRequest req = json.readValue(ctx.body(), DataMigrateRequest.class);
            if (req.form == null || req.form.isBlank()) throw new IllegalArgumentException("Missing form");
            ARServerUser source = sessions.require(req.sourceSessionId);
            ARServerUser targetUser = sessions.require(req.targetSessionId);
            List<FieldMeta> migrationFields = getFieldMeta(source, req.form);
            List<Object> entries = queryEntries(source, req.form, req.qualification, req.maxRows, fieldIds(migrationFields));
            String mode = req.mode == null || req.mode.isBlank() ? "update" : req.mode.toLowerCase(Locale.ROOT);
            int created = 0, updated = 0, skipped = 0, errors = 0;
            List<Map<String,Object>> itemResults = new ArrayList<>();
            for (Object entry : entries) {
                String entryId = getEntryId(entry);
                boolean exists = entryId != null && !entryId.isBlank() && entryExists(targetUser, req.form, entryId);
                try {
                    if (mode.equals("skip") && exists) {
                        skipped++;
                        itemResults.add(Map.of("entryId", entryId == null ? "" : entryId, "action", "skipped"));
                    } else if (mode.equals("create_duplicate") || mode.equals("create")) {
                        Object newId = invokeCreateEntry(targetUser, req.form, entry);
                        created++;
                        itemResults.add(Map.of("entryId", entryId == null ? "" : entryId, "action", "created", "newEntryId", String.valueOf(newId)));
                    } else {
                        if (exists) {
                            invokeSetEntry(targetUser, req.form, entryId, entry);
                            updated++;
                            itemResults.add(Map.of("entryId", entryId == null ? "" : entryId, "action", "updated"));
                        } else {
                            Object newId = invokeCreateEntry(targetUser, req.form, entry);
                            created++;
                            itemResults.add(Map.of("entryId", entryId == null ? "" : entryId, "action", "created", "newEntryId", String.valueOf(newId)));
                        }
                    }
                } catch (Exception ex) {
                    errors++;
                    itemResults.add(Map.of("entryId", entryId == null ? "" : entryId, "action", "error", "error", ex.getMessage()));
                }
            }
            ctx.json(Map.of("status", errors == 0 ? "ok" : "completed_with_errors", "form", req.form, "matched", entries.size(), "processed", entries.size(), "created", created, "updated", updated, "skipped", skipped, "errors", errors, "mode", mode, "items", itemResults));
        });

        app.start(port);
    }



    private static String safeFileName(String value) {
        return String.valueOf(value).replaceAll("[^a-zA-Z0-9._-]+", "_");
    }

    private static String csv(String value) {
        if (value == null) value = "";
        return "\"" + value.replace("\"", "\"\"") + "\"";
    }

    private static Object parseQualificationBestEffort(ARServerUser user, String form, String qualification) {
        if (qualification == null || qualification.isBlank()) return null;
        for (Method m : user.getClass().getMethods()) {
            if (!m.getName().equals("parseQualification")) continue;
            Class<?>[] p = m.getParameterTypes();
            try {
                if (p.length == 2 && p[0] == String.class && p[1] == String.class) {
                    try { return m.invoke(user, form, qualification); } catch (Exception ignored) { }
                    try { return m.invoke(user, qualification, form); } catch (Exception ignored) { }
                }
            } catch (Exception ignored) { }
        }
        throw new IllegalArgumentException("Could not parse qualification with this ARAPI version: " + qualification);
    }

    private static List<Object> queryEntries(ARServerUser user, String form, String qualification, int maxRows, List<Integer> fieldIds) throws Exception {
        Object qual = parseQualificationBestEffort(user, form, qualification);
        List<String> methodNames = List.of("getListEntryObjects", "getListEntry");
        Exception last = null;
        for (String methodName : methodNames) {
            for (Method m : user.getClass().getMethods()) {
                if (!m.getName().equals(methodName)) continue;
                Object[] args = buildEntryQueryArgs(m.getParameterTypes(), form, qualification, qual, maxRows, fieldIds);
                if (args == null) continue;
                try {
                    Object result = m.invoke(user, args);
                    List<Object> listed = toObjectList(result);
                    if (listed == null) continue;

                    // Some ARAPI overloads ignore requested fields and return only a tiny default set.
                    // Re-read each returned entry by Request ID with the full field list to make CSV/JSON exports useful.
                    List<Object> full = new ArrayList<>();
                    for (Object entry : listed) {
                        String entryId = entry instanceof String ? (String) entry : getEntryId(entry);
                        if (entryId == null || entryId.isBlank()) {
                            full.add(entry);
                            continue;
                        }
                        try {
                            Object fullEntry = getEntryById(user, form, entryId, fieldIds);
                            full.add(fullEntry == null ? entry : fullEntry);
                        } catch (Exception ignored) {
                            full.add(entry);
                        }
                    }
                    return full;
                } catch (Exception e) { last = e; }
            }
        }
        throw new IllegalStateException("No compatible ARAPI entry list method found" + (last == null ? "" : ": " + last.getMessage()));
    }

    private static List<Object> toObjectList(Object result) {
        if (result instanceof List<?>) return new ArrayList<>((List<Object>) result);
        if (result != null && result.getClass().isArray()) {
            List<Object> out = new ArrayList<>();
            int n = Array.getLength(result);
            for (int i = 0; i < n; i++) out.add(Array.get(result, i));
            return out;
        }
        return null;
    }

    private static Object[] buildEntryQueryArgs(Class<?>[] p, String form, String qualification, Object qual, int maxRows, List<Integer> fieldIds) {
        Object[] args = new Object[p.length];
        int stringIndex = 0, intIndex = 0, listIndex = 0;
        for (int i = 0; i < p.length; i++) {
            Class<?> c = p[i];
            String cn = c.getName();
            if (c == String.class) {
                args[i] = stringIndex++ == 0 ? form : (qualification == null ? "" : qualification);
            } else if (cn.endsWith("QualifierInfo")) {
                args[i] = qual;
            } else if (c == int.class || c == Integer.class) {
                args[i] = intIndex++ == 0 ? 0 : Math.max(maxRows, 0);
            } else if (c == long.class || c == Long.class) {
                args[i] = 0L;
            } else if (c == boolean.class || c == Boolean.class) {
                args[i] = false;
            } else if (List.class.isAssignableFrom(c)) {
                // The first list is usually sort/order. Later lists are often field-id lists.
                args[i] = listIndex++ == 0 ? Collections.emptyList() : new ArrayList<>(fieldIds);
            } else if (c.isArray()) {
                if (c.getComponentType() == int.class) args[i] = toIntArray(fieldIds);
                else if (c.getComponentType() == Integer.class) args[i] = fieldIds.toArray(new Integer[0]);
                else args[i] = Array.newInstance(c.getComponentType(), 0);
            } else {
                args[i] = null;
            }
        }
        return args;
    }

    private static String getEntryId(Object entry) {
        if (entry == null) return "";
        if (entry instanceof String s) return s;
        for (String method : List.of("getEntryId", "getEntryID", "getEntryIdValue", "getRequestId", "getRequestID")) {
            try {
                Object value = entry.getClass().getMethod(method).invoke(entry);
                if (value != null && !String.valueOf(value).isBlank()) return String.valueOf(value);
            } catch (Exception ignored) { }
        }
        Object safe = SafeObjectMapper.toSafe(entry);
        String found = findEntryIdInSafe(safe);
        return found == null ? "" : found;
    }

    private static String findEntryIdInSafe(Object value) {
        if (value instanceof Map<?,?> map) {
            for (Object key : map.keySet()) {
                String k = String.valueOf(key).toLowerCase(Locale.ROOT);
                if (k.equals("entryid") || k.equals("entry_id") || k.equals("requestid") || k.equals("request_id")) {
                    Object v = map.get(key);
                    if (v != null) return String.valueOf(v);
                }
            }
            for (Object v : map.values()) {
                String found = findEntryIdInSafe(v);
                if (found != null && !found.isBlank()) return found;
            }
        } else if (value instanceof List<?> list) {
            for (Object v : list) {
                String found = findEntryIdInSafe(v);
                if (found != null && !found.isBlank()) return found;
            }
        }
        return null;
    }

    private static boolean entryExists(ARServerUser user, String form, String entryId) {
        if (entryId == null || entryId.isBlank()) return false;
        for (Method m : user.getClass().getMethods()) {
            if (!m.getName().equals("getEntry")) continue;
            try {
                Object[] args = buildEntryIdArgs(m.getParameterTypes(), form, entryId, null, Collections.emptyList());
                m.invoke(user, args);
                return true;
            } catch (Exception ignored) { }
        }
        return false;
    }

    private static Object invokeCreateEntry(ARServerUser user, String form, Object entry) throws Exception {
        return invokeEntryWrite(user, "createEntry", form, null, entry);
    }

    private static Object invokeSetEntry(ARServerUser user, String form, String entryId, Object entry) throws Exception {
        return invokeEntryWrite(user, "setEntry", form, entryId, entry);
    }

    private static Object invokeEntryWrite(ARServerUser user, String methodName, String form, String entryId, Object entry) throws Exception {
        Exception last = null;
        for (Method m : user.getClass().getMethods()) {
            if (!m.getName().equals(methodName)) continue;
            try {
                Object[] args = buildEntryIdArgs(m.getParameterTypes(), form, entryId, entry, Collections.emptyList());
                return m.invoke(user, args);
            } catch (Exception e) { last = e; }
        }
        throw new IllegalStateException("No compatible ARAPI " + methodName + " method found" + (last == null ? "" : ": " + last.getMessage()));
    }

    private static Object getEntryById(ARServerUser user, String form, String entryId, List<Integer> fieldIds) throws Exception {
        Exception last = null;
        for (Method m : user.getClass().getMethods()) {
            if (!m.getName().equals("getEntry")) continue;
            try {
                Object[] args = buildEntryIdArgs(m.getParameterTypes(), form, entryId, null, fieldIds);
                return m.invoke(user, args);
            } catch (Exception e) { last = e; }
        }
        throw new IllegalStateException("No compatible ARAPI getEntry method found" + (last == null ? "" : ": " + last.getMessage()));
    }

    private static Object[] buildEntryIdArgs(Class<?>[] p, String form, String entryId, Object entry, List<Integer> fieldIds) {
        Object[] args = new Object[p.length];
        int stringIndex = 0, listIndex = 0;
        for (int i = 0; i < p.length; i++) {
            Class<?> c = p[i];
            String cn = c.getName().toLowerCase(Locale.ROOT);
            if (c == String.class) {
                args[i] = stringIndex++ == 0 ? form : entryId;
            } else if (entry != null && c.isAssignableFrom(entry.getClass())) {
                args[i] = entry;
            } else if (cn.contains("entry") && entry != null) {
                args[i] = entry;
            } else if (c == int.class || c == Integer.class) {
                args[i] = 0;
            } else if (c == long.class || c == Long.class) {
                args[i] = 0L;
            } else if (c == boolean.class || c == Boolean.class) {
                args[i] = false;
            } else if (List.class.isAssignableFrom(c)) {
                args[i] = listIndex++ == 0 && entry != null ? Collections.emptyList() : new ArrayList<>(fieldIds);
            } else if (c.isArray()) {
                if (c.getComponentType() == int.class) args[i] = toIntArray(fieldIds);
                else if (c.getComponentType() == Integer.class) args[i] = fieldIds.toArray(new Integer[0]);
                else args[i] = Array.newInstance(c.getComponentType(), 0);
            } else {
                args[i] = null;
            }
        }
        return args;
    }

    private static int[] toIntArray(List<Integer> ids) {
        int[] arr = new int[ids.size()];
        for (int i = 0; i < ids.size(); i++) arr[i] = ids.get(i);
        return arr;
    }


    private static List<FieldMeta> getFieldMeta(ARServerUser user, String form) throws Exception {
        List<FieldMeta> fields = new ArrayList<>();
        for (Object field : user.getListFieldObjects(form)) {
            Integer id = reflectInt(field, List.of("getFieldID", "getFieldId", "getId"));
            if (id == null) continue;
            String name = reflectString(field, List.of("getName", "getFieldName", "getLabel"));
            if (name == null || name.isBlank()) name = String.valueOf(id);
            fields.add(new FieldMeta(id, name));
        }
        fields.sort(Comparator.comparingInt(f -> f.id));
        return fields;
    }

    private static List<Integer> fieldIds(List<FieldMeta> fields) {
        List<Integer> ids = new ArrayList<>();
        for (FieldMeta f : fields) ids.add(f.id);
        return ids;
    }

    private static List<FieldMeta> filterFields(List<FieldMeta> allFields, List<String> requested) {
        if (requested == null || requested.isEmpty()) return allFields;
        Set<String> wanted = new HashSet<>();
        for (String r : requested) {
            if (r != null && !r.isBlank()) wanted.add(r.trim().toLowerCase(Locale.ROOT));
        }
        if (wanted.isEmpty()) return allFields;
        List<FieldMeta> out = new ArrayList<>();
        for (FieldMeta f : allFields) {
            if (wanted.contains(String.valueOf(f.id).toLowerCase(Locale.ROOT)) || wanted.contains(f.name.toLowerCase(Locale.ROOT))) out.add(f);
        }
        return out.isEmpty() ? allFields : out;
    }


    private static String detectCustomizationType(Object obj) {
        if (obj == null) return "Unknown";
        for (String method : List.of("getCustomizationType", "getCustomization", "getCustomType", "getOverlayType", "getObjPropCustomizationType")) {
            try {
                Object value = obj.getClass().getMethod(method).invoke(obj);
                String mapped = mapCustomizationValue(value);
                if (!"Unknown".equals(mapped)) return mapped;
            } catch (Exception ignored) { }
        }
        for (String method : List.of("isOverlay", "getOverlay", "isOverlaid")) {
            try {
                Object value = obj.getClass().getMethod(method).invoke(obj);
                if (value instanceof Boolean b && b) return "Overlay";
                if (value != null && "true".equalsIgnoreCase(String.valueOf(value))) return "Overlay";
            } catch (Exception ignored) { }
        }
        for (String method : List.of("isCustom", "getCustom", "isCustomized")) {
            try {
                Object value = obj.getClass().getMethod(method).invoke(obj);
                if (value instanceof Boolean b && b) return "Custom";
                if (value != null && "true".equalsIgnoreCase(String.valueOf(value))) return "Custom";
            } catch (Exception ignored) { }
        }
        try {
            Object safe = SafeObjectMapper.toSafe(obj);
            String fromSafe = findCustomizationInSafe(safe, 0);
            if (!"Unknown".equals(fromSafe)) return fromSafe;
        } catch (Exception ignored) { }
        return "Unknown";
    }

    private static String mapCustomizationValue(Object value) {
        if (value == null) return "Unknown";
        String text = String.valueOf(value).trim();
        if (text.isBlank()) return "Unknown";
        String low = text.toLowerCase(Locale.ROOT);
        if (low.contains("overlay") || "2".equals(low)) return "Overlay";
        if (low.contains("custom") || "1".equals(low)) return "Custom";
        if (low.contains("base") || "0".equals(low)) return "Base";
        return "Unknown";
    }

    private static String findCustomizationInSafe(Object safe, int depth) {
        if (safe == null || depth > 6) return "Unknown";
        if (safe instanceof Map<?,?> map) {
            for (Map.Entry<?,?> e : map.entrySet()) {
                String key = String.valueOf(e.getKey()).toLowerCase(Locale.ROOT);
                if (key.contains("customization") || key.contains("overlaytype") || key.equals("customtype") || key.equals("layer")) {
                    String mapped = mapCustomizationValue(e.getValue());
                    if (!"Unknown".equals(mapped)) return mapped;
                }
            }
            for (Object value : map.values()) {
                String mapped = findCustomizationInSafe(value, depth + 1);
                if (!"Unknown".equals(mapped)) return mapped;
            }
        } else if (safe instanceof Iterable<?> list) {
            for (Object value : list) {
                String mapped = findCustomizationInSafe(value, depth + 1);
                if (!"Unknown".equals(mapped)) return mapped;
            }
        }
        return "Unknown";
    }

    private static Integer reflectInt(Object obj, List<String> methods) {
        for (String method : methods) {
            try {
                Object value = obj.getClass().getMethod(method).invoke(obj);
                if (value instanceof Number n) return n.intValue();
                if (value != null) return Integer.parseInt(String.valueOf(value));
            } catch (Exception ignored) { }
        }
        return null;
    }

    private static String reflectString(Object obj, List<String> methods) {
        for (String method : methods) {
            try {
                Object value = obj.getClass().getMethod(method).invoke(obj);
                if (value != null && !String.valueOf(value).isBlank()) return String.valueOf(value);
            } catch (Exception ignored) { }
        }
        return null;
    }

    private static Map<String, Object> normalizeEntryForExport(Object entry, List<FieldMeta> fields) {
        Object safe = SafeObjectMapper.toSafe(entry);
        Map<String, Object> valuesById = extractEntryValuesByFieldId(safe);
        Map<String, Object> row = new LinkedHashMap<>();
        String entryId = getEntryId(entry);
        if (entryId == null || entryId.isBlank()) entryId = scalarToString(valuesById.get("1"));
        row.put("Request ID", entryId == null ? "" : entryId);
        Set<String> usedNames = new HashSet<>();
        usedNames.add("Request ID");
        for (FieldMeta f : fields) {
            String col = f.name;
            if (usedNames.contains(col)) col = f.name + " [" + f.id + "]";
            usedNames.add(col);
            row.put(col, valuesById.getOrDefault(String.valueOf(f.id), ""));
        }
        return row;
    }

    private static Map<String, Object> extractEntryValuesByFieldId(Object safe) {
        Map<String, Object> out = new LinkedHashMap<>();
        if (safe instanceof Map<?,?> map) {
            // Entry objects are often serialized either as {"1": Value, "8": Value}
            // or as {"contents": {"1": Value, ...}} depending on ARAPI version.
            for (Map.Entry<?,?> e : map.entrySet()) {
                String key = String.valueOf(e.getKey());
                if (key.matches("\\d+")) out.put(key, unwrapValue(e.getValue()));
            }
            for (String nestedKey : List.of("contents", "entryItems", "values", "fieldValues", "entry")) {
                Object nested = map.get(nestedKey);
                if (nested != null) out.putAll(extractEntryValuesByFieldId(nested));
            }
            Object key = map.get("key");
            Object value = map.get("value");
            if (key != null && value != null) {
                String k = extractFieldIdFromKey(key);
                if (k != null) out.put(k, unwrapValue(value));
            }
            for (Object v : map.values()) {
                if (v instanceof List<?> || v instanceof Map<?,?>) out.putAll(extractEntryValuesByFieldId(v));
            }
        } else if (safe instanceof List<?> list) {
            for (Object item : list) out.putAll(extractEntryValuesByFieldId(item));
        }
        return out;
    }

    private static String extractFieldIdFromKey(Object key) {
        if (key instanceof Map<?,?> map) {
            for (String k : List.of("fieldID", "fieldId", "id")) {
                Object v = map.get(k);
                if (v != null) return String.valueOf(v);
            }
        }
        String s = String.valueOf(key);
        return s.matches("\\d+") ? s : null;
    }

    private static Object unwrapValue(Object value) {
        if (value instanceof Map<?,?> map) {
            if (map.containsKey("value")) return unwrapValue(map.get("value"));
            for (String k : List.of("characterValue", "integerValue", "realValue", "enumValue", "dateValue", "timeValue", "decimalValue", "currencyValue", "diaryValue")) {
                if (map.containsKey(k)) return unwrapValue(map.get(k));
            }
        }
        if (value instanceof List<?> || value instanceof Map<?,?>) return value;
        return value == null ? "" : value;
    }

    private static String scalarToString(Object value) {
        if (value == null) return "";
        if (value instanceof String s) return s;
        if (value instanceof Number || value instanceof Boolean) return String.valueOf(value);
        try { return json.writeValueAsString(value); } catch (Exception ignored) { return String.valueOf(value); }
    }

    private static String buildCsv(List<Map<String, Object>> rows, List<FieldMeta> fields) {
        List<String> headers = new ArrayList<>();
        if (rows.isEmpty()) {
            headers.add("Request ID");
            Set<String> used = new HashSet<>(headers);
            for (FieldMeta f : fields) {
                String col = used.contains(f.name) ? f.name + " [" + f.id + "]" : f.name;
                used.add(col);
                headers.add(col);
            }
        } else {
            headers.addAll(rows.get(0).keySet());
        }
        StringBuilder csv = new StringBuilder();
        for (int i = 0; i < headers.size(); i++) {
            if (i > 0) csv.append(',');
            csv.append(csv(headers.get(i)));
        }
        csv.append('\n');
        for (Map<String, Object> row : rows) {
            for (int i = 0; i < headers.size(); i++) {
                if (i > 0) csv.append(',');
                csv.append(csv(scalarToString(row.get(headers.get(i)))));
            }
            csv.append('\n');
        }
        return csv.toString();
    }

    private record FieldMeta(int id, String name) { }

    private static Map<String, Object> categorizedContainers(ARServerUser user) throws Exception {
        Map<String, List<String>> categories = new LinkedHashMap<>();
        categories.put("activeLinkGuides", new ArrayList<>());
        categories.put("filterGuides", new ArrayList<>());
        categories.put("packingLists", new ArrayList<>());
        categories.put("applications", new ArrayList<>());
        categories.put("otherContainers", new ArrayList<>());

        List<String> names = user.getListContainer(0L, null, true, null, null);
        try {
            List<Container> objects = user.getListContainerObjects(names);
            for (Container c : objects) {
                String name = objectName(c);
                String cls = c.getClass().getSimpleName().toLowerCase(Locale.ROOT);
                if (cls.contains("activelinkguide")) {
                    categories.get("activeLinkGuides").add(name);
                } else if (cls.contains("filterguide")) {
                    categories.get("filterGuides").add(name);
                } else if (cls.contains("packinglist")) {
                    categories.get("packingLists").add(name);
                } else if (cls.contains("application")) {
                    categories.get("applications").add(name);
                } else {
                    categories.get("otherContainers").add(name);
                }
            }
        } catch (Exception e) {
            // Fallback: keep service stable even if full container classification fails.
            // Names are still useful, but the UI will not show the generic bucket by default.
            categories.get("otherContainers").addAll(names);
        }

        Map<String, Integer> counts = new LinkedHashMap<>();
        for (Map.Entry<String, List<String>> e : categories.entrySet()) counts.put(e.getKey(), e.getValue().size());

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("mode", "categorized_index");
        out.put("counts", counts);
        out.putAll(categories);
        return out;
    }

    private static String objectName(Object obj) {
        for (String method : List.of("getName", "getKey", "getLabel")) {
            try {
                Object value = obj.getClass().getMethod(method).invoke(obj);
                if (value != null && !String.valueOf(value).isBlank()) return String.valueOf(value);
            } catch (Exception ignored) { }
        }
        return String.valueOf(obj);
    }

    private static String sessionId(Context ctx) {
        String h = ctx.header("X-HLX-Session");
        if (h != null && !h.isBlank()) return h;
        String q = ctx.queryParam("sessionId");
        if (q != null && !q.isBlank()) return q;
        return null;
    }

    private static ARServerUser user(Context ctx) {
        return sessions.require(sessionId(ctx));
    }

    private static Object createStructItemInfo(ExportItem item) throws Exception {
        int type = mapStructType(item);
        String name = item.name;
        if (name == null || name.isBlank()) {
            throw new IllegalArgumentException("Missing object name in migration/export item: " + describeExportItem(item));
        }

        try {
            Class<?> cls = Class.forName("com.bmc.arsys.api.StructItemInfo");

            // Prefer the no-arg constructor plus explicit setters when available.
            // This avoids ambiguity between ARAPI versions that expose different
            // constructor argument orders for StructItemInfo.
            try {
                Object obj = cls.getDeclaredConstructor().newInstance();
                boolean typeSet = trySetInt(obj, type,
                        "setType", "setObjectType", "setItemType", "setStructItemType", "setTypeId");
                boolean nameSet = trySetString(obj, name,
                        "setName", "setObjectName", "setItemName", "setStructItemName");
                if (typeSet && nameSet) {
                    log.debug("Created StructItemInfo via setters: {}", describeStructItemInfo(obj));
                    return obj;
                }
            } catch (NoSuchMethodException ignored) {
                // No default constructor. Fall through to constructor based creation.
            }

            // Prefer (String, int). In some ARAPI versions this is the canonical order.
            for (var c : cls.getConstructors()) {
                Class<?>[] p = c.getParameterTypes();
                if (p.length == 2 && p[0] == String.class && p[1] == int.class) {
                    Object obj = c.newInstance(name, type);
                    log.debug("Created StructItemInfo via (String,int): {}", describeStructItemInfo(obj));
                    return obj;
                }
            }

            // Fallback to (int, String) for ARAPI versions exposing that order.
            for (var c : cls.getConstructors()) {
                Class<?>[] p = c.getParameterTypes();
                if (p.length == 2 && p[0] == int.class && p[1] == String.class) {
                    Object obj = c.newInstance(type, name);
                    log.debug("Created StructItemInfo via (int,String): {}", describeStructItemInfo(obj));
                    return obj;
                }
            }

            throw new IllegalArgumentException("No compatible StructItemInfo constructor or setters found");
        } catch (Exception e) {
            throw new IllegalArgumentException("Could not create ARAPI StructItemInfo for " + describeExportItem(item)
                    + " mappedType=" + type + ": " + rootCause(e).getMessage(), e);
        }
    }

    private static boolean trySetInt(Object obj, int value, String... methods) {
        for (String method : methods) {
            try {
                obj.getClass().getMethod(method, int.class).invoke(obj, value);
                return true;
            } catch (Exception ignored) { }
            try {
                obj.getClass().getMethod(method, Integer.class).invoke(obj, value);
                return true;
            } catch (Exception ignored) { }
        }
        return false;
    }

    private static boolean trySetString(Object obj, String value, String... methods) {
        for (String method : methods) {
            try {
                obj.getClass().getMethod(method, String.class).invoke(obj, value);
                return true;
            } catch (Exception ignored) { }
        }
        return false;
    }

    private static String describeStructItemInfo(Object obj) {
        if (obj == null) return "<null>";
        Map<String, Object> values = new LinkedHashMap<>();
        values.put("class", obj.getClass().getName());
        for (String method : List.of(
                "getType", "getObjectType", "getItemType", "getStructItemType", "getTypeId",
                "getName", "getObjectName", "getItemName", "getStructItemName")) {
            try {
                Method m = obj.getClass().getMethod(method);
                values.put(method, m.invoke(obj));
            } catch (Exception ignored) { }
        }
        values.put("toString", String.valueOf(obj));
        return values.toString();
    }

    private static String describeExportItem(ExportItem item) {
        if (item == null) return "<null>";
        return "{name='" + item.name + "', objectType='" + item.objectType + "', type=" + item.type + "}";
    }

    private static int mapStructType(ExportItem item) {
        String ot = item.objectType == null ? "" : item.objectType.toLowerCase(Locale.ROOT).trim();

        return switch (ot) {
            case "form", "schema", "forms" -> arConst(
                    List.of("AR_STRUCT_ITEM_SCHEMA", "AR_STRUCT_ITEM_FORM"), 1);
            case "filter", "filters" -> arConst(
                    List.of("AR_STRUCT_ITEM_FILTER"), 2);
            case "active_link", "active-link", "activelink", "active_links", "active link" -> arConst(
                    List.of("AR_STRUCT_ITEM_ACTIVE_LINK", "AR_STRUCT_ITEM_ACTLINK", "AR_STRUCT_ITEM_ACTL"), 3);
            case "escalation", "escalations" -> arConst(
                    List.of("AR_STRUCT_ITEM_ESCALATION"), 4);
            case "menu", "menus", "character_menu", "file_menu", "search_menu", "sql_menu", "data_dictionary_menu" -> arConst(
                    List.of("AR_STRUCT_ITEM_CHAR_MENU", "AR_STRUCT_ITEM_MENU"), 5);
            case "active_link_guide", "active-link-guide", "filter_guide", "filter-guide",
                    "packing_list", "packing-list", "application", "applications",
                    "other_container", "container", "containers" -> arConst(
                    List.of("AR_STRUCT_ITEM_CONTAINER"), 6);
            case "image", "images" -> arConst(
                    List.of("AR_STRUCT_ITEM_IMAGE"), 7);
            default -> {
                if (item.type > 0) {
                    log.warn("Unknown objectType='{}' for '{}'; falling back to browser supplied type={}",
                            item.objectType, item.name, item.type);
                    yield item.type;
                }
                throw new IllegalArgumentException("Unsupported object type for DEF export/migration: " + describeExportItem(item));
            }
        };
    }

    private static int arConst(List<String> names, int fallback) {
        for (String name : names) {
            try {
                java.lang.reflect.Field field = Constants.class.getField(name);
                Object value = field.get(null);
                if (value instanceof Number n) return n.intValue();
            } catch (Exception ignored) { }
        }
        log.debug("No ARAPI Constants value found for {}; using fallback {}", names, fallback);
        return fallback;
    }

    private static Throwable rootCause(Throwable t) {
        Throwable current = t;
        while (current instanceof InvocationTargetException && ((InvocationTargetException) current).getTargetException() != null) {
            current = ((InvocationTargetException) current).getTargetException();
        }
        while (current.getCause() != null && current.getCause() != current) {
            if (current instanceof InvocationTargetException && ((InvocationTargetException) current).getTargetException() != null) {
                current = ((InvocationTargetException) current).getTargetException();
                continue;
            }
            current = current.getCause();
        }
        return current;
    }


    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class DataExportRequest {
        public String form;
        public String qualification = "";
        public int maxRows = 0;
        public String format = "csv";
        public List<String> fields = new ArrayList<>();
        public String fileName;
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class DataMigrateRequest {
        public String sourceSessionId;
        public String targetSessionId;
        public String form;
        public String qualification = "";
        public int maxRows = 0;
        public String mode = "update";
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class ExportRequest {
        public List<ExportItem> items = new ArrayList<>();
        public boolean related = true;
        public String fileName;
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class MigrateRequest {
        public String sourceSessionId;
        public String targetSessionId;
        public List<ExportItem> items = new ArrayList<>();
        public boolean related = true;
        public String fileName;
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class ExportItem {
        public int type;
        public String objectType;
        public String name;
        public String customizationType;
    }
}
