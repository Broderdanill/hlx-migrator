package se.arsbmc.hlxmigrator.arapi;

import java.lang.reflect.*;
import java.util.*;

public class SafeObjectMapper {
    private static final Set<String> SKIP = Set.of("getClass", "getProxy", "getSession");

    public static Object toSafe(Object obj) {
        return toSafe(obj, 0, Collections.newSetFromMap(new IdentityHashMap<>()));
    }

    private static Object toSafe(Object obj, int depth, Set<Object> seen) {
        if (obj == null) return null;
        if (depth > 12) return String.valueOf(obj);
        if (obj instanceof String || obj instanceof Number || obj instanceof Boolean || obj instanceof Character) return obj;
        if (obj.getClass().isEnum()) return obj.toString();
        if (seen.contains(obj)) return "<cycle>";
        seen.add(obj);

        if (obj instanceof Map<?,?> map) {
            Map<String,Object> out = new TreeMap<>();
            for (Map.Entry<?,?> e : map.entrySet()) out.put(String.valueOf(e.getKey()), toSafe(e.getValue(), depth + 1, seen));
            return out;
        }
        if (obj instanceof Iterable<?> it) {
            List<Object> out = new ArrayList<>();
            for (Object x : it) out.add(toSafe(x, depth + 1, seen));
            return out;
        }
        if (obj.getClass().isArray()) {
            int len = Array.getLength(obj);
            List<Object> out = new ArrayList<>();
            for (int i = 0; i < len; i++) out.add(toSafe(Array.get(obj, i), depth + 1, seen));
            return out;
        }

        String pkg = obj.getClass().getPackageName();
        if (!pkg.startsWith("com.bmc.arsys")) return String.valueOf(obj);

        Map<String,Object> out = new TreeMap<>();
        out.put("_class", obj.getClass().getName());
        for (Method m : obj.getClass().getMethods()) {
            if (m.getParameterCount() != 0) continue;
            if (!Modifier.isPublic(m.getModifiers())) continue;
            String name = m.getName();
            if (SKIP.contains(name)) continue;
            if (!(name.startsWith("get") || name.startsWith("is"))) continue;
            try {
                Object value = m.invoke(obj);
                out.put(propName(name), toSafe(value, depth + 1, seen));
            } catch (Exception ignored) { }
        }
        return out;
    }

    private static String propName(String getter) {
        String raw = getter.startsWith("get") ? getter.substring(3) : getter.substring(2);
        if (raw.isEmpty()) return getter;
        return raw.substring(0,1).toLowerCase() + raw.substring(1);
    }
}
