from pathlib import Path
import os
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path(os.getenv("HLX_CONFIG_DIR", os.getenv("CONFIG_DIR", BASE_DIR / "config")))
ENV_FILE = Path(os.getenv("ENVIRONMENTS_FILE", CONFIG_DIR / "environments.yaml"))
SECRET_FILE = Path(os.getenv("SECRETS_FILE", CONFIG_DIR / "secrets.yaml"))
ARAPI_BASE_URL = os.getenv("HLX_ARAPI_BASE_URL", os.getenv("ARAPI_BASE_URL", "http://localhost:8092"))
DATA_DIR = Path(os.getenv("HLX_DATA_DIR", os.getenv("DATA_DIR", "/data")))
DB_URL = os.getenv("DB_URL", f"sqlite:///{DATA_DIR / 'cache.db'}")
EXPORT_DIR = Path(os.getenv("EXPORT_DIR", DATA_DIR / "exports"))
AUTO_SERVER_SYNC = os.getenv("HLX_AUTO_SERVER_SYNC", "true").lower() in {"1", "true", "yes", "on"}
AUTO_SERVER_SYNC_LIMIT = os.getenv("HLX_AUTO_SERVER_SYNC_LIMIT", "").strip()
AUTO_SERVER_SYNC_LIMIT = int(AUTO_SERVER_SYNC_LIMIT) if AUTO_SERVER_SYNC_LIMIT else None


def _read_yaml(path: Path, required: bool = True) -> dict:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Missing config file: {path}")
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


_DEFAULT_SYNC = {
    "auto_start": True,
    "forms": True,
    # When false, startup caches the scoped form index only.
    # Full form definitions can be synced manually or enabled explicitly.
    "form_details": False,
    "form_detail_limit": 0,
    "fields": True,
    "views": True,
    "active_links": True,
    "filters": True,
    # Escalations can be expensive and some AR Servers/RPC queues drop large responses.
    # Keep disabled by default and enable explicitly after baseline sync is stable.
    "escalations": True,
    "menus": True,
    "active_link_guides": True,
    "filter_guides": True,
    "packing_lists": True,
    "applications": True,
    "containers": False,
    "images": True,
    "include_global": True,
    "continue_on_error": True,
    # Deep metadata cache. Startup first builds a fast name index, then loads
    # full definitions in a bounded background queue. This makes compare
    # work like Migrator without blocking the UI from opening.
    "details": True,
    "details_concurrency": 2,
    "details_max_per_type": 0,
    "details_refresh_existing": False,
    "incremental": True,
    "purge_missing": False,
    "detail_object_types": [
        "form", "active_link", "filter", "escalation", "menu",
        "active_link_guide", "filter_guide", "packing_list", "application", "image"
    ],
}


class ConfigStore:
    def __init__(self):
        self.reload()

    def reload(self):
        self.env_data = _read_yaml(ENV_FILE)
        self.secret_data = _read_yaml(SECRET_FILE, required=False)

    def environments(self) -> list[str]:
        return sorted((self.env_data.get("environments") or {}).keys())

    def get_environment_base(self, name: str) -> dict:
        envs = self.env_data.get("environments") or {}
        if name not in envs:
            raise KeyError(f"Unknown environment: {name}")
        payload = dict(envs[name])
        payload["name"] = name
        return payload

    def get_login_payload(self, name: str, username: str, password: str, authentication: str = "") -> dict:
        payload = self.get_environment_base(name)
        payload["username"] = username
        payload["password"] = password
        payload["authentication"] = authentication or payload.get("authentication", "") or ""
        return payload

    def get_server_login_payload(self, name: str) -> dict:
        payload = self.get_environment_base(name)
        creds = (self.secret_data.get("credentials") or {}).get(name) or {}
        username = creds.get("username") or os.getenv(f"HLX_{name.upper()}_USERNAME")
        password = creds.get("password") or os.getenv(f"HLX_{name.upper()}_PASSWORD")
        auth = creds.get("authentication", creds.get("auth", "")) or payload.get("authentication", "") or ""
        if not username or password is None:
            raise KeyError(f"Serverlogin saknas för miljö {name}. Lägg credentials.{name}.username/password i secrets.yaml")
        payload["username"] = username
        payload["password"] = password
        payload["authentication"] = auth
        return payload

    def scope(self) -> dict:
        scope = self.env_data.get("scope") or {}
        def _as_list(value):
            if value is None:
                return []
            if isinstance(value, list):
                return [str(v).strip() for v in value if str(v).strip()]
            return [str(value).strip()] if str(value).strip() else []

        # Remedy/Helix Developer Studio has three customization layers. Keep all
        # enabled by default, but allow the ConfigMap to define which layers the
        # UI should preselect. Supported shapes:
        #   customization_types: [Base, Custom, Overlay]
        #   customization_types: {default: [Base, Custom], include: [...]}
        #   customization_type_default: [Base, Custom, Overlay]
        raw_ct = scope.get("customization_types", scope.get("customization_type_default"))
        if isinstance(raw_ct, dict):
            raw_ct = raw_ct.get("default", raw_ct.get("include"))
        ct = _as_list(raw_ct) or ["Base", "Custom", "Overlay"]
        canonical = {"base": "Base", "custom": "Custom", "overlay": "Overlay"}
        customization_types = []
        for value in ct:
            mapped = canonical.get(str(value).strip().lower())
            if mapped and mapped not in customization_types:
                customization_types.append(mapped)
        if not customization_types:
            customization_types = ["Base", "Custom", "Overlay"]

        return {
            "include_form_prefixes": _as_list(scope.get("include_form_prefixes")),
            "exclude_form_prefixes": _as_list(scope.get("exclude_form_prefixes")),
            "customization_types": customization_types,
        }

    def sync(self) -> dict:
        raw = self.env_data.get("sync") or {}
        merged = dict(_DEFAULT_SYNC)
        object_types = raw.get("object_types") or {}
        merged.update({k: v for k, v in raw.items() if k != "object_types"})
        merged.update(object_types)
        return merged


    def ui(self) -> dict:
        raw = self.env_data.get("ui") or {}
        def _int(name: str, default: int, low: int, high: int) -> int:
            try:
                value = int(raw.get(name, default))
            except Exception:
                value = default
            return max(low, min(value, high))
        page_size = _int("page_size", 100, 50, 2000)
        max_page_size = _int("max_page_size", 2000, page_size, 10000)
        return {
            "page_size": page_size,
            "max_page_size": max_page_size,
        }

    def diff(self) -> dict:
        raw = self.env_data.get("diff") or {}
        def _as_list(value):
            if value is None:
                return []
            if isinstance(value, list):
                return [str(v).strip() for v in value if str(v).strip()]
            return [str(value).strip()] if str(value).strip() else []
        default_ignore = [
            # AR/user metadata that normally differs between environments
            "lastChanged", "lastModified", "lastModifiedBy", "modifiedDate", "timestamp",
            "owner", "changeDiary", "lastUpdate", "objectId", "recordId", "requestId",
            "createDate", "modifiedBy", "lastModifiedDate",
            "lastUpdateTime", "lastUpdateBy", "modifiedTime", "lastChangedBy",
            "instanceId", "guid", "internalId", "changeFlag", "changeFlags",
            # HLX Migrator cache/runtime metadata; never compare these
            "deepCachedAt", "capturedAt", "cacheNamespace", "definitionLoaded", "indexOnly",
            "scopeMatched", "debug", "errors", "sync", "scope"
        ]
        return {
            "ignore_keys": _as_list(raw.get("ignore_keys")) or default_ignore,
            "ignore_order": bool(raw.get("ignore_order", True)),
        }


config_store = ConfigStore()
