package se.arsbmc.hlxmigrator.arapi;

public class LoginResult {
    public String sessionId;
    public String status;
    public String environment;
    public String user;
    public String serverVersion;

    public LoginResult(String sessionId, String status, String environment, String user, String serverVersion) {
        this.sessionId = sessionId;
        this.status = status;
        this.environment = environment;
        this.user = user;
        this.serverVersion = serverVersion;
    }
}
