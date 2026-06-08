package se.arsbmc.hlxmigrator.arapi;

import com.bmc.arsys.api.ARException;
import com.bmc.arsys.api.StatusInfo;
import java.util.*;

public class ApiError {
    public static Map<String, Object> from(Exception ex) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("error", ex.getClass().getName());
        out.put("message", ex.getMessage());
        if (ex.getCause() != null) out.put("cause", ex.getCause().getMessage());
        if (ex instanceof ARException ar) {
            List<Map<String, Object>> statuses = new ArrayList<>();
            try {
                for (StatusInfo s : ar.getLastStatus()) {
                    Map<String, Object> m = new LinkedHashMap<>();
                    m.put("number", s.getMessageNum());
                    m.put("type", String.valueOf(s.getMessageType()));
                    m.put("text", s.getMessageText());
                    m.put("appendedText", s.getAppendedText());
                    statuses.add(m);
                }
            } catch (Exception ignored) { }
            out.put("arStatus", statuses);
        }
        return out;
    }
}
