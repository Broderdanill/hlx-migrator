package se.arsbmc.hlxmigrator.arapi;

import com.bmc.arsys.api.ARServerUser;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

public class SessionManager {
    private final Map<String, SessionEntry> sessions = new ConcurrentHashMap<>();

    public LoginResult login(EnvConfig cfg) throws Exception {
        if (cfg.username == null || cfg.username.isBlank()) {
            throw new IllegalArgumentException("username saknas");
        }
        if (cfg.password == null) {
            throw new IllegalArgumentException("password saknas");
        }
        if (cfg.host == null || cfg.host.isBlank()) {
            throw new IllegalArgumentException("host saknas för miljö " + cfg.name);
        }

        ARServerUser user = new ARServerUser(
                cfg.username,
                cfg.password,
                cfg.authentication == null ? "" : cfg.authentication,
                cfg.host
        );

        user.setPort(cfg.port);
        if (cfg.locale != null && !cfg.locale.isBlank()) user.setLocale(cfg.locale);
        if (cfg.timezone != null && !cfg.timezone.isBlank()) user.setTimeZone(cfg.timezone);
        if (cfg.rpc > 0) user.usePrivateRpcQueue(cfg.rpc);

        user.login();

        String sessionId = UUID.randomUUID().toString();
        sessions.put(sessionId, new SessionEntry(sessionId, cfg.name, cfg.username, user));

        return new LoginResult(
                sessionId,
                "logged_in",
                cfg.name,
                user.getUser(),
                user.getServerVersion()
        );
    }

    public ARServerUser require(String sessionId) {
        if (sessionId == null || sessionId.isBlank()) {
            throw new IllegalStateException("X-HLX-Session saknas");
        }
        SessionEntry entry = sessions.get(sessionId);
        if (entry == null) {
            throw new IllegalStateException("Ogiltig eller utgången ARAPI-session");
        }
        entry.lastUsed = Instant.now();
        return entry.user;
    }

    public SessionEntry info(String sessionId) {
        if (sessionId == null || sessionId.isBlank()) return null;
        return sessions.get(sessionId);
    }

    public void logout(String sessionId) {
        SessionEntry entry = sessions.remove(sessionId);
        if (entry != null && entry.user != null) {
            entry.user.logout();
        }
    }

    public int size() {
        return sessions.size();
    }

    public static class SessionEntry {
        public final String sessionId;
        public final String environment;
        public final String username;
        public final ARServerUser user;
        public final Instant createdAt;
        public Instant lastUsed;

        public SessionEntry(String sessionId, String environment, String username, ARServerUser user) {
            this.sessionId = sessionId;
            this.environment = environment;
            this.username = username;
            this.user = user;
            this.createdAt = Instant.now();
            this.lastUsed = this.createdAt;
        }
    }
}
