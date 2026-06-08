from pathlib import Path
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select, func

from .db import init_db, SessionLocal, CachedObject
from .settings import config_store, EXPORT_DIR, AUTO_SERVER_SYNC, AUTO_SERVER_SYNC_LIMIT
from .arapi_client import ArApiClient
from .cache import full_sync_forms, full_sync_workflow, deep_cache_object_details, cache_namespace, stable_hash, normalize, upsert_cached_object
from .diffing import compare_environments

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger("hlx-migrator-ui")

app = FastAPI(title="HLX Migrator", version="1.0.7")

SERVER_CACHE_STATUS = {
    "enabled": AUTO_SERVER_SYNC,
    "running": False,
    "startedAt": None,
    "finishedAt": None,
    "scope": {},
    "sync": {},
    "environments": {},
    "jobs": [],
}
SERVER_SESSIONS: dict[str, str] = {}
ENV_LOCKS: dict[str, dict] = {}
LOCK_GUARD = asyncio.Lock()


def _lock_public() -> dict:
    return {env: {k: v for k, v in info.items() if k != "token"} for env, info in ENV_LOCKS.items()}


async def acquire_env_lock(env: str, operation: str, owner: str) -> str:
    env = env.lower()
    async with LOCK_GUARD:
        existing = ENV_LOCKS.get(env)
        if existing:
            raise HTTPException(status_code=409, detail={
                "message": f"Environment {env.upper()} is busy with {existing.get('operation')}",
                "environment": env,
                "lock": {k: v for k, v in existing.items() if k != "token"},
            })
        token = str(uuid.uuid4())
        ENV_LOCKS[env] = {
            "environment": env,
            "operation": operation,
            "owner": owner or "unknown",
            "startedAt": now_iso(),
            "token": token,
        }
        return token


async def release_env_lock(env: str, token: str | None):
    if not token:
        return
    env = env.lower()
    async with LOCK_GUARD:
        existing = ENV_LOCKS.get(env)
        if existing and existing.get("token") == token:
            ENV_LOCKS.pop(env, None)
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class LoginReq(BaseModel):
    username: str
    password: str
    authentication: str = ""


class SyncReq(BaseModel):
    session_id: str | None = None
    limit: int | None = None
    include_global: bool = True


class ExportReq(BaseModel):
    environment: str
    session_id: str
    file_name: str = "transport.def"
    related: bool = True
    items: list[dict]


class ExportSelectedReq(BaseModel):
    source_environment: str
    source_session_id: str | None = None
    items: list[dict]
    related: bool = True
    file_name: str = "transport.def"


class MigrateReq(BaseModel):
    source_environment: str
    target_environment: str
    source_session_id: str | None = None
    target_session_id: str | None = None
    items: list[dict]
    related: bool = True
    file_name: str = "migration.def"


class CompareSelectedReq(BaseModel):
    source: str
    target: str
    object_type: str
    names: list[str]


class DataExportReq(BaseModel):
    source_environment: str
    source_session_id: str | None = None
    form: str
    qualification: str = ""
    max_rows: int = 0
    format: str = "csv"
    fields: list[str] = []
    file_name: str | None = None


class DataMigrateReq(BaseModel):
    source_environment: str
    target_environment: str
    source_session_id: str | None = None
    target_session_id: str | None = None
    form: str
    qualification: str = ""
    max_rows: int = 0
    mode: str = "update"



def _find_first_metadata_value(obj, keys: tuple[str, ...], max_depth: int = 6):
    """Find metadata values in cached ARAPI JSON without assuming one exact schema.

    ARAPI objects differ by type/version: some use modifiedDate, some lastModified,
    some wrap the real definition under definition/metadata. This helper walks the
    cached JSON shallowly and returns the first matching key.
    """
    keyset = {k.lower() for k in keys}

    def walk(value, depth: int):
        if depth > max_depth:
            return None
        if isinstance(value, dict):
            # Prefer direct keys before walking children so root metadata wins.
            for k, v in value.items():
                if str(k).lower() in keyset and v not in (None, ""):
                    return v
            for v in value.values():
                found = walk(v, depth + 1)
                if found not in (None, ""):
                    return found
        elif isinstance(value, list):
            for item in value[:50]:
                found = walk(item, depth + 1)
                if found not in (None, ""):
                    return found
        return None

    return walk(obj, 0)


def _format_arapi_timestamp(value) -> str:
    """Format ARAPI timestamp-like values for table display.

    ARAPI often serializes timestamps as objects like
    {"_class":"com.bmc.arsys.api.Timestamp", "value": 1779440381}.
    The GUI should not show that raw object.
    """
    if value in (None, ""):
        return ""
    raw = value
    if isinstance(value, dict):
        raw = value.get("value") or value.get("time") or value.get("timestamp") or value.get("date")
    try:
        if isinstance(raw, str) and raw.strip().isdigit():
            raw = int(raw.strip())
        if isinstance(raw, (int, float)):
            # AR timestamps are seconds since epoch in practice. Guard against ms.
            if raw > 100000000000:
                raw = raw / 1000
            return datetime.fromtimestamp(raw, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        pass
    if isinstance(raw, str):
        text = raw.strip()
        # Keep readable ISO-like values, just normalize T/Z a little.
        if "T" in text:
            return text.replace("T", " ").replace("+00:00", " UTC").replace("Z", " UTC")
        return text
    return str(raw)



def _parse_display_timestamp(value: str | None):
    """Parse displayed timestamps such as '2026-06-04 11:30:39 UTC'."""
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith(" UTC"):
            text = text[:-4] + "+00:00"
        if "T" not in text and " " in text:
            text = text.replace(" ", "T", 1)
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

def _object_metadata_columns(data: dict) -> dict:
    timestamp = _find_first_metadata_value(data, (
        "modifiedDate", "lastModifiedDate", "lastUpdateTime", "lastUpdate",
        "lastChanged", "lastModified", "timestamp", "modifiedTime",
        "lastChangedDate", "changeDate",
    ))
    changed_by = _find_first_metadata_value(data, (
        "lastModifiedBy", "lastChangedBy", "lastUpdateBy", "modifiedBy",
        "changedBy", "lastModifiedUser",
    ))
    if changed_by in (None, ""):
        changed_by = _find_first_metadata_value(data, ("owner",), max_depth=2)
    return {
        "timestamp": _format_arapi_timestamp(timestamp),
        "lastChangedBy": str(changed_by) if changed_by not in (None, "") else "",
    }

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_job(env: str, object_type: str, status: str, message: str = "", counts: dict | None = None):
    job = {
        "time": now_iso(),
        "environment": env,
        "objectType": object_type,
        "status": status,
        "message": message,
        "counts": counts or {},
    }
    SERVER_CACHE_STATUS["jobs"].insert(0, job)
    SERVER_CACHE_STATUS["jobs"] = SERVER_CACHE_STATUS["jobs"][:300]
    return job


def public_server_cache_status() -> dict:
    """Return a lightweight server-cache status for the UI.

    The internal SERVER_CACHE_STATUS can contain very large per-step result
    payloads while startup deep-cache is running. Returning that full structure
    from /api/environments or /api/cache/summary can make the browser wait
    with a spinner until sync has progressed far enough. The UI only needs
    high-level environment status and the user-facing job log.
    """
    envs: dict = {}
    for env, status in (SERVER_CACHE_STATUS.get("environments") or {}).items():
        envs[env] = {
            "status": status.get("status"),
            "startedAt": status.get("startedAt"),
            "finishedAt": status.get("finishedAt"),
            "lastSyncMode": status.get("lastSyncMode"),
            "scope": status.get("scope"),
            "sync": status.get("sync"),
            "user": status.get("user"),
            "serverVersion": status.get("serverVersion"),
            "error": status.get("error"),
            # Small per-step summary only; omit full ARAPI result payloads.
            "steps": [
                {
                    "objectType": step.get("objectType"),
                    "status": step.get("status"),
                    "finishedAt": step.get("finishedAt"),
                }
                for step in (status.get("steps") or [])
            ],
        }
    return {
        "enabled": SERVER_CACHE_STATUS.get("enabled"),
        "running": SERVER_CACHE_STATUS.get("running"),
        "startedAt": SERVER_CACHE_STATUS.get("startedAt"),
        "finishedAt": SERVER_CACHE_STATUS.get("finishedAt"),
        "scope": SERVER_CACHE_STATUS.get("scope") or config_store.scope(),
        "sync": SERVER_CACHE_STATUS.get("sync") or config_store.sync(),
        "environments": envs,
        "jobs": list((SERVER_CACHE_STATUS.get("jobs") or [])[:200]),
        "locks": _lock_public(),
    }


@app.on_event("startup")
async def startup():
    init_db()
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    SERVER_CACHE_STATUS["scope"] = config_store.scope()
    SERVER_CACHE_STATUS["sync"] = config_store.sync()
    if AUTO_SERVER_SYNC and config_store.sync().get("auto_start", True):
        asyncio.create_task(server_cache_refresh_all())


async def server_cache_refresh_all():
    SERVER_CACHE_STATUS["running"] = True
    SERVER_CACHE_STATUS["scope"] = config_store.scope()
    SERVER_CACHE_STATUS["sync"] = config_store.sync()
    SERVER_CACHE_STATUS["startedAt"] = now_iso()
    SERVER_CACHE_STATUS["finishedAt"] = None
    add_job("all", "server-sync", "running", "Starting server sync for all environments")
    for env in config_store.environments():
        await server_cache_refresh_environment(env, set_global_running=False)
    SERVER_CACHE_STATUS["running"] = False
    SERVER_CACHE_STATUS["finishedAt"] = now_iso()
    add_job("all", "server-sync", "ok", "Server sync completed for all environments")


async def server_cache_refresh_environment(env: str, set_global_running: bool = True):
    lock_token = None
    try:
        lock_token = await acquire_env_lock(env, "server-sync", "serverlogin" if not set_global_running else "manual")
    except HTTPException as lock_error:
        add_job(env, "server-sync", "locked", f"Environment is busy: {lock_error.detail}")
        if set_global_running:
            SERVER_CACHE_STATUS["running"] = False
            SERVER_CACHE_STATUS["finishedAt"] = now_iso()
        return {"status": "locked", "environment": env, "detail": lock_error.detail}

    if set_global_running:
        SERVER_CACHE_STATUS["running"] = True
        SERVER_CACHE_STATUS["startedAt"] = now_iso()
        SERVER_CACHE_STATUS["finishedAt"] = None
        SERVER_CACHE_STATUS["scope"] = config_store.scope()
        SERVER_CACHE_STATUS["sync"] = config_store.sync()

    SERVER_CACHE_STATUS["environments"].setdefault(env, {})
    env_status = SERVER_CACHE_STATUS["environments"][env]
    env_status.clear()
    env_status.update({
        "status": "running",
        "startedAt": now_iso(),
        "finishedAt": None,
        "lastSyncMode": "serverlogin/manual" if set_global_running else "serverlogin/startup",
        "scope": config_store.scope(),
        "sync": config_store.sync(),
        "steps": [],
    })

    try:
        client = ArApiClient()
        add_job(env, "login", "running", "Serverlogin")
        login_result = await client.server_login(env)
        session_id = login_result["sessionId"]
        SERVER_SESSIONS[env] = session_id
        env_status.update({
            "sessionId": session_id[:12] + "...",
            "user": login_result.get("user"),
            "serverVersion": login_result.get("serverVersion"),
        })
        add_job(env, "login", "ok", f"Logged in as {login_result.get('user')}")

        sync_cfg = config_store.sync()
        if sync_cfg.get("forms", True):
            add_job(env, "forms", "running", "Indexing forms according to scope")
            forms = await full_sync_forms(env, session_id=session_id, limit=AUTO_SERVER_SYNC_LIMIT, service_cache=True)
            env_status["forms"] = forms
            env_status["steps"].append({"objectType": "forms", "status": "ok", "finishedAt": now_iso(), "result": forms})
            add_job(env, "forms", "ok", f"{forms.get('formsInScope', 0)} forms in scope", {"indexed": forms.get("indexed", 0), "synced": forms.get("synced", 0), "formsInScope": forms.get("formsInScope", 0), "mode": forms.get("mode")})

        workflow_enabled = any(sync_cfg.get(k, False) for k in (
            "active_links", "filters", "menus", "escalations", "images",
            "active_link_guides", "filter_guides", "packing_lists", "applications", "containers",
        ))
        if workflow_enabled:
            add_job(env, "workflow", "running", "Indexing workflow/metadata according to scope")
            workflow = await full_sync_workflow(env, session_id=session_id, include_global=sync_cfg.get("include_global", True), limit_forms=AUTO_SERVER_SYNC_LIMIT, service_cache=True)
            env_status["workflow"] = workflow
            env_status["steps"].append({"objectType": "workflow", "status": workflow.get("status", "ok"), "finishedAt": now_iso(), "result": workflow})
            add_job(env, "workflow", workflow.get("status", "ok"), "Workflow index completed", workflow.get("counts") or {})

        if sync_cfg.get("details", True):
            add_job(env, "details", "running", "Loading full ARAPI definitions for deep diff", {"concurrency": sync_cfg.get("details_concurrency", 2)})
            details = await deep_cache_object_details(env, session_id=session_id, service_cache=True)
            env_status["details"] = details
            env_status["steps"].append({"objectType": "details", "status": details.get("status", "ok"), "finishedAt": now_iso(), "result": details})
            detail_counts = {k: v.get("loaded", 0) for k, v in (details.get("counts") or {}).items()}
            add_job(env, "details", details.get("status", "ok"), "Deep metadata cache completed", detail_counts)

        env_status.update({"status": "ok", "finishedAt": now_iso()})
    except Exception as e:
        env_status.update({"status": "error", "error": str(e), "finishedAt": now_iso()})
        add_job(env, "environment", "error", str(e))
    finally:
        await release_env_lock(env, lock_token)
        if set_global_running:
            SERVER_CACHE_STATUS["running"] = False
            SERVER_CACHE_STATUS["finishedAt"] = now_iso()


@app.get("/", response_class=HTMLResponse)
def index():
    return (static_dir / "index.html").read_text(encoding="utf-8")


@app.get("/api/log-level")
def log_level():
    return {"logLevel": LOG_LEVEL}


@app.get("/api/health")
async def health():
    try:
        arapi = await ArApiClient().health()
    except Exception as e:
        arapi = {"status": "error", "message": str(e)}
    return {"status": "ok", "app": "hlx-migrator-ui", "version": "0.9.8", "logLevel": LOG_LEVEL, "arapi": arapi}


@app.get("/api/environments")
def environments():
    return {"environments": config_store.environments(), "scope": config_store.scope(), "sync": config_store.sync(), "serverCache": public_server_cache_status()}


@app.get("/api/server-cache/status")
def server_cache_status():
    return public_server_cache_status()


@app.get("/api/cache/summary")
def cache_summary():
    with SessionLocal() as db:
        rows = db.execute(
            select(
                CachedObject.environment,
                CachedObject.object_type,
                func.count(CachedObject.id),
                func.max(CachedObject.last_seen),
            ).group_by(CachedObject.environment, CachedObject.object_type)
        ).all()
    environments = {}
    for env, object_type, count, last_seen in rows:
        environments.setdefault(env, {})[object_type] = {"count": count, "lastSeen": last_seen.isoformat() if last_seen else None}
    return {"scope": config_store.scope(), "sync": config_store.sync(), "serverCache": public_server_cache_status(), "environments": environments}


@app.post("/api/server-cache/refresh")
async def server_cache_refresh():
    if SERVER_CACHE_STATUS.get("running"):
        return {"status": "already_running", "serverCache": public_server_cache_status()}
    asyncio.create_task(server_cache_refresh_all())
    return {"status": "started", "serverCache": public_server_cache_status()}


@app.post("/api/server-cache/refresh/{env}")
async def server_cache_refresh_env(env: str):
    if env not in config_store.environments():
        raise HTTPException(status_code=404, detail=f"Unknown environment: {env}")
    if SERVER_CACHE_STATUS.get("environments", {}).get(env, {}).get("status") == "running":
        return {"status": "already_running", "environment": env, "serverCache": public_server_cache_status()}
    asyncio.create_task(server_cache_refresh_environment(env, set_global_running=True))
    return {"status": "started", "environment": env, "serverCache": public_server_cache_status()}


@app.post("/api/environments/{env}/login")
async def login(env: str, req: LoginReq):
    try:
        return await ArApiClient().login(env, req.username, req.password, req.authentication)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/logout")
async def logout(req: SyncReq):
    if not req.session_id:
        return {"status": "no_session"}
    try:
        return await ArApiClient().logout(req.session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/session/validate")
async def validate_session(req: SyncReq):
    if not req.session_id:
        return {"valid": False, "status": "no_session"}
    try:
        info = await ArApiClient().me(req.session_id)
        return {"valid": True, "status": "ok", "session": info}
    except Exception as e:
        return {"valid": False, "status": "expired", "message": str(e)}


@app.post("/api/cache/{env}/sync/forms")
async def sync_forms(env: str, req: SyncReq):
    try:
        session_id = req.session_id or SERVER_SESSIONS.get(env)
        if not session_id:
            raise HTTPException(status_code=400, detail=f"No session for {env}")
        result = await full_sync_forms(env, session_id=session_id, limit=req.limit, service_cache=req.session_id is None)
        add_job(env, "forms", "ok", "Forms-sync", {"synced": result.get("synced", 0), "indexed": result.get("indexed", 0)})
        return result
    except Exception as e:
        add_job(env, "forms", "error", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cache/{env}/sync/workflow")
async def sync_workflow(env: str, req: SyncReq):
    try:
        session_id = req.session_id or SERVER_SESSIONS.get(env)
        if not session_id:
            raise HTTPException(status_code=400, detail=f"No session for {env}")
        result = await full_sync_workflow(env, session_id=session_id, include_global=req.include_global, limit_forms=req.limit, service_cache=req.session_id is None)
        add_job(env, "workflow", result.get("status", "ok"), "Workflow-sync", result.get("counts") or {})
        return result
    except Exception as e:
        add_job(env, "workflow", "error", str(e))
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/cache/{env}/sync/details")
async def sync_details(env: str, req: SyncReq):
    try:
        session_id = req.session_id or SERVER_SESSIONS.get(env)
        if not session_id:
            raise HTTPException(status_code=400, detail=f"No session for {env}")
        result = await deep_cache_object_details(env, session_id=session_id, service_cache=req.session_id is None)
        add_job(env, "details", result.get("status", "ok"), "Deep metadata cache", {k: v.get("loaded", 0) for k, v in (result.get("counts") or {}).items()})
        return result
    except Exception as e:
        add_job(env, "details", "error", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/objects/{object_type}")
def list_cached_objects_api(
    object_type: str,
    environment: str,
    q: str | None = None,
    name_q: str | None = None,
    timestamp_q: str | None = None,
    changed_from: str | None = None,
    changed_to: str | None = None,
    changed_by_q: str | None = None,
    limit: int = 500,
    offset: int = 0,
    sort: str = "name",
    direction: str = "asc",
):
    """Return a paged list of cached objects.

    The cache may contain tens of thousands of objects in production. The UI
    should never request/render all rows at once, so this endpoint supports
    limit/offset paging and returns total counts for navigation. Metadata
    columns are still computed from the rows in the requested page only.
    """
    allowed = {"form", "active_link", "filter", "escalation", "menu", "image", "active_link_guide", "filter_guide", "packing_list", "application", "other_container"}
    if object_type not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported object type: {object_type}")
    if environment not in config_store.environments():
        raise HTTPException(status_code=404, detail=f"Unknown environment: {environment}")

    q_norm = (q or "").strip()
    name_q_norm = (name_q or "").strip()
    timestamp_q_norm = (timestamp_q or "").strip()
    changed_from_norm = (changed_from or "").strip()
    changed_to_norm = (changed_to or "").strip()
    changed_from_dt = _parse_display_timestamp(changed_from_norm)
    changed_to_dt = _parse_display_timestamp(changed_to_norm)
    changed_by_q_norm = (changed_by_q or "").strip()
    safe_limit = max(1, min(int(limit or 500), int(config_store.ui().get("max_page_size", 2000))))
    safe_offset = max(0, int(offset or 0))
    sort_key = (sort or "name").lower()
    sort_dir = (direction or "asc").lower()

    def row_to_object(row: CachedObject) -> dict:
        try:
            data = json.loads(row.json_data or "{}")
        except Exception:
            data = {}
        meta = _object_metadata_columns(data)
        return {
            "name": row.object_name,
            "objectType": row.object_type,
            "hash": row.object_hash,
            "lastSeen": row.last_seen.isoformat() if row.last_seen else None,
            "timestamp": meta.get("timestamp") or "",
            "lastChangedBy": meta.get("lastChangedBy") or "",
            "definitionLoaded": bool(data.get("definitionLoaded")),
        }

    def object_matches_query(obj: dict, query: str) -> bool:
        if not query:
            return True
        needle = query.lower()
        return (
            needle in str(obj.get("name") or "").lower()
            or needle in str(obj.get("timestamp") or "").lower()
            or needle in str(obj.get("lastChangedBy") or "").lower()
        )

    def object_matches_field_filters(obj: dict) -> bool:
        if q_norm and not object_matches_query(obj, q_norm):
            return False
        if name_q_norm and name_q_norm.lower() not in str(obj.get("name") or "").lower():
            return False
        if timestamp_q_norm and timestamp_q_norm.lower() not in str(obj.get("timestamp") or "").lower():
            return False
        if changed_from_dt or changed_to_dt:
            obj_dt = _parse_display_timestamp(str(obj.get("timestamp") or ""))
            if obj_dt is None:
                return False
            if changed_from_dt and obj_dt < changed_from_dt:
                return False
            if changed_to_dt and obj_dt > changed_to_dt:
                return False
        if changed_by_q_norm and changed_by_q_norm.lower() not in str(obj.get("lastChangedBy") or "").lower():
            return False
        return True

    def object_sort_value(obj: dict, key: str):
        if key == "timestamp":
            text = str(obj.get("timestamp") or "")
            parsed = datetime.fromisoformat(text.replace(" UTC", "+00:00")) if text and ("-" in text) else None
            return parsed or datetime.min.replace(tzinfo=timezone.utc)
        if key == "lastchangedby":
            return str(obj.get("lastChangedBy") or "").lower()
        if key == "lastseen":
            return str(obj.get("lastSeen") or "")
        if key == "hash":
            return str(obj.get("hash") or "")
        return str(obj.get("name") or "").lower()

    with SessionLocal() as db:
        base_filters = [
            CachedObject.environment == environment,
            CachedObject.object_type == object_type,
        ]

        # Searching must include table columns that are derived from cached JSON
        # metadata, such as Timestamp and Last Changed By. For normal browsing we
        # keep paging in SQL. When q is present, we scan this object type once,
        # compute metadata columns, filter, sort and then page the matched result.
        if q_norm or name_q_norm or timestamp_q_norm or changed_from_dt or changed_to_dt or changed_by_q_norm:
            all_rows = list(
                db.execute(
                    select(CachedObject)
                    .where(*base_filters)
                    .order_by(CachedObject.object_name.asc(), CachedObject.id.asc())
                ).scalars().all()
            )
            all_objects = [row_to_object(row) for row in all_rows]
            matched = [obj for obj in all_objects if object_matches_field_filters(obj)]
            reverse = sort_dir == "desc"
            matched.sort(key=lambda obj: (object_sort_value(obj, sort_key), str(obj.get("name") or "").lower()), reverse=reverse)
            total = len(matched)
            objects = matched[safe_offset:safe_offset + safe_limit]
        else:
            total = db.execute(select(func.count()).select_from(CachedObject).where(*base_filters)).scalar_one()

            order_col = CachedObject.object_name
            if sort_key == "lastseen":
                order_col = CachedObject.last_seen
            elif sort_key == "hash":
                order_col = CachedObject.object_hash
            # Timestamp / Last Changed By are derived from JSON, so keep DB sort by
            # name for stable paging unless a query is active. The browser still
            # sorts the visible page for these columns.
            order_expr = order_col.desc() if sort_dir == "desc" else order_col.asc()

            stmt = (
                select(CachedObject)
                .where(*base_filters)
                .order_by(order_expr, CachedObject.id.asc())
                .offset(safe_offset)
                .limit(safe_limit)
            )
            rows = list(db.execute(stmt).scalars().all())
            objects = [row_to_object(row) for row in rows]
    return {
        "environment": environment,
        "object_type": object_type,
        "total": int(total),
        "count": len(objects),
        "limit": safe_limit,
        "offset": safe_offset,
        "hasNext": safe_offset + len(objects) < int(total),
        "hasPrev": safe_offset > 0,
        "objects": objects,
    }


async def _load_detail_for_compare(env: str, object_type: str, name: str) -> dict | None:
    from .cache import get_cached_object, upsert_cached_object

    cached = get_cached_object(env, object_type, name)
    if cached and cached.get("definitionLoaded") is True and cached.get("indexOnly") is not True:
        return cached

    session_id = SERVER_SESSIONS.get(env)
    if not session_id:
        return cached

    try:
        detail = await ArApiClient().get_object_detail(session_id, object_type, name)
        detail["definitionLoaded"] = True
        detail["indexOnly"] = False
        upsert_cached_object(env, object_type, name, detail)
        add_job(env, object_type, "ok", f"Loaded detail for {name}")
        return detail
    except Exception as e:
        add_job(env, object_type, "error", f"Failed to load detail for {name}: {e}")
        return cached


def _diff_rows(diff_obj: dict) -> list[dict]:
    """Flatten DeepDiff output into rows that are easier to read in the UI.

    DeepDiff keeps rich data in different buckets. This converts the most common
    buckets into a stable visual table: kind, path, source value and target value.
    The original DeepDiff JSON is still returned for troubleshooting.
    """
    rows: list[dict] = []

    def add(kind: str, path: str, source=None, target=None):
        rows.append({"kind": kind, "path": path, "source": source, "target": target})

    for path, change in (diff_obj.get("values_changed") or {}).items():
        add("value changed", path, change.get("old_value"), change.get("new_value"))

    for path, change in (diff_obj.get("type_changes") or {}).items():
        add(
            "type changed",
            path,
            {"type": change.get("old_type"), "value": change.get("old_value")},
            {"type": change.get("new_type"), "value": change.get("new_value")},
        )

    for key in ("dictionary_item_removed", "set_item_removed"):
        for path in diff_obj.get(key) or []:
            add("removed", path, "present", None)

    for key in ("dictionary_item_added", "set_item_added"):
        for path in diff_obj.get(key) or []:
            add("added", path, None, "present")

    for path, value in (diff_obj.get("iterable_item_removed") or {}).items():
        add("removed", path, value, None)

    for path, value in (diff_obj.get("iterable_item_added") or {}).items():
        add("added", path, None, value)

    for bucket, payload in sorted(diff_obj.items()):
        if bucket in {
            "values_changed", "type_changes", "dictionary_item_removed", "set_item_removed",
            "dictionary_item_added", "set_item_added", "iterable_item_removed", "iterable_item_added",
        }:
            continue
        if isinstance(payload, dict):
            for path, value in payload.items():
                add(bucket, path, value, None)
        elif isinstance(payload, list):
            for path in payload:
                add(bucket, str(path), None, None)
        else:
            add(bucket, "root", payload, None)

    return rows


@app.post("/api/compare/selected")
async def compare_selected(req: CompareSelectedReq):
    from .cache import normalize
    from deepdiff import DeepDiff
    import json

    if req.source not in config_store.environments() or req.target not in config_store.environments():
        raise HTTPException(status_code=404, detail="Unknown source or target environment")

    diff_cfg = config_store.diff()
    ignore_keys = set(diff_cfg.get("ignore_keys") or [])
    ignore_order = bool(diff_cfg.get("ignore_order", True))

    summary = {"equal": 0, "different": 0, "missing_in_source": 0, "missing_in_target": 0, "detail_load_failed": 0}
    objects = []
    add_job(req.source, "compare", "running", f"Comparing {len(req.names)} {req.object_type} object(s) with {req.target}", {"items": len(req.names)})

    for name in req.names:
        src = await _load_detail_for_compare(req.source, req.object_type, name)
        tgt = await _load_detail_for_compare(req.target, req.object_type, name)
        if src is None:
            summary["missing_in_source"] += 1
            tgt_meta = _object_metadata_columns(tgt or {})
            objects.append({"name": name, "status": "missing_in_source", "timestamp": tgt_meta.get("timestamp", ""), "lastChangedBy": tgt_meta.get("lastChangedBy", ""), "compared": {"source": None, "target": tgt}})
            continue
        if tgt is None:
            summary["missing_in_target"] += 1
            src_meta = _object_metadata_columns(src or {})
            objects.append({"name": name, "status": "missing_in_target", "timestamp": src_meta.get("timestamp", ""), "lastChangedBy": src_meta.get("lastChangedBy", ""), "compared": {"source": src, "target": None}})
            continue

        src_detail = src.get("definitionLoaded") is True and src.get("indexOnly") is not True
        tgt_detail = tgt.get("definitionLoaded") is True and tgt.get("indexOnly") is not True
        if not src_detail or not tgt_detail:
            summary["detail_load_failed"] += 1

        src_norm = normalize(src, ignore_keys)
        tgt_norm = normalize(tgt, ignore_keys)
        diff_obj = json.loads(DeepDiff(src_norm, tgt_norm, ignore_order=ignore_order).to_json())
        compared = {
            "sourceEnvironment": req.source,
            "targetEnvironment": req.target,
            "objectType": req.object_type,
            "name": name,
            "detailLoaded": src_detail and tgt_detail,
            "ignoreKeys": sorted(ignore_keys),
            "ignoreOrder": ignore_order,
            "source": src_norm,
            "target": tgt_norm,
            "diffRows": _diff_rows(diff_obj),
        }
        src_meta = _object_metadata_columns(src or {})
        if diff_obj:
            summary["different"] += 1
            objects.append({"name": name, "status": "different", "timestamp": src_meta.get("timestamp", ""), "lastChangedBy": src_meta.get("lastChangedBy", ""), "detailLoaded": src_detail and tgt_detail, "diff": diff_obj, "compared": compared})
        else:
            summary["equal"] += 1
            objects.append({"name": name, "status": "equal", "timestamp": src_meta.get("timestamp", ""), "lastChangedBy": src_meta.get("lastChangedBy", ""), "detailLoaded": src_detail and tgt_detail, "diff": {}, "compared": compared})

    add_job(req.source, "compare", "ok", "Compare completed", summary)
    return {"source": req.source, "target": req.target, "object_type": req.object_type, "diffConfig": diff_cfg, "summary": summary, "objects": objects}


@app.get("/api/diff/forms")
def diff_forms(source: str, target: str, source_session_id: str | None = None, target_session_id: str | None = None, service_cache: bool = False):
    src_ns = source if service_cache else cache_namespace(source, source_session_id)
    tgt_ns = target if service_cache else cache_namespace(target, target_session_id)
    return compare_environments(src_ns, tgt_ns, "form")


@app.get("/api/diff/{object_type}")
def diff_object_type(object_type: str, source: str, target: str, source_session_id: str | None = None, target_session_id: str | None = None, service_cache: bool = False):
    allowed = {"form", "active_link", "filter", "escalation", "menu", "image", "active_link_guide", "filter_guide", "packing_list", "application", "other_container"}
    if object_type not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported object type: {object_type}")
    src_ns = source if service_cache else cache_namespace(source, source_session_id)
    tgt_ns = target if service_cache else cache_namespace(target, target_session_id)
    return compare_environments(src_ns, tgt_ns, object_type)


@app.post("/api/export/def")
async def export_def(req: ExportReq):
    try:
        return await ArApiClient().export_def(req.session_id, req.items, req.file_name, req.related)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/export/selected")
async def export_selected_def(req: ExportSelectedReq):
    try:
        source_session_id, source_mode = await _validated_or_server_session(req.source_environment, req.source_session_id)
        if not source_session_id:
            raise HTTPException(status_code=400, detail=f"No valid source session is available for {req.source_environment}. Run Server Sync or log in again.")
        file_name = req.file_name or f"transport-{now_iso().replace(':', '').replace('+', 'Z')}.def"
        add_job(req.source_environment, "download", "running", f"Creating DEF export for {len(req.items)} selected object(s) ({source_mode})", {"items": len(req.items)})
        result = await ArApiClient().export_def(source_session_id, req.items, file_name, req.related)
        result["sourceSessionMode"] = source_mode

        # The Java ARAPI service writes the DEF file inside the shared pod volume and
        # returns an absolute path such as /data/exports/file.def. The browser must
        # never receive that absolute container path as part of the route, because
        # /api/download//data/exports/file.def will not match our safe download endpoint.
        returned_file = result.get("fileName") or result.get("file") or file_name
        safe_file_name = Path(str(returned_file)).name
        result["fileName"] = safe_file_name
        result["downloadUrl"] = f"/api/download/{safe_file_name}"

        add_job(req.source_environment, "download", "ok", f"DEF export ready: {safe_file_name}", {"items": len(req.items), "fileSizeBytes": result.get("fileSizeBytes")})
        return result
    except HTTPException:
        raise
    except Exception as e:
        add_job(req.source_environment, "download", "error", str(e), {"items": len(req.items)})
        raise HTTPException(status_code=500, detail=str(e))


async def _validated_or_server_session(env: str, browser_session_id: str | None) -> tuple[str | None, str]:
    """Prefer a valid browser session, but automatically fall back to server-login.

    Browser sessionStorage can survive a pod restart, while the Java ARAPI service
    keeps sessions only in memory. This helper prevents stale browser sessions from
    breaking migration even though the UI still says "logged in".
    """
    client = ArApiClient()
    if browser_session_id:
        try:
            await client.me(browser_session_id)
            return browser_session_id, "browser"
        except Exception:
            pass
    server_session = SERVER_SESSIONS.get(env)
    if server_session:
        try:
            await client.me(server_session)
            return server_session, "serverlogin"
        except Exception:
            SERVER_SESSIONS.pop(env, None)
    return None, "missing"


async def _validated_browser_session(env: str, browser_session_id: str | None) -> tuple[str | None, str]:
    """Validate a browser/user ARAPI session. Write operations must use this.

    Server-login is intentionally not accepted here so target AR System audit fields
    reflect the actual user performing the migration.
    """
    if not browser_session_id:
        return None, "missing"
    try:
        info = await ArApiClient().me(browser_session_id)
        return browser_session_id, str(info.get("username") or "browser")
    except Exception:
        return None, "expired"


async def _fetch_detail_hash(session_id: str, environment: str, object_type: str, name: str) -> dict:
    """Fetch one target/source object detail and return normalized hash + metadata.

    This is used to verify migration. It intentionally ignores volatile metadata
    using the same normalizer as compare, so identical definitions still compare
    equal even if timestamps/users differ.
    """
    try:
        detail = await ArApiClient().get_object_detail(session_id, object_type, name)
        detail["definitionLoaded"] = True
        detail["indexOnly"] = False
        meta = _object_metadata_columns(detail)
        return {
            "exists": True,
            "hash": stable_hash(detail),
            "timestamp": meta.get("timestamp", ""),
            "lastChangedBy": meta.get("lastChangedBy", ""),
            "detail": detail,
        }
    except Exception as e:
        return {"exists": False, "hash": None, "error": str(e), "timestamp": "", "lastChangedBy": ""}



@app.post("/api/export/data")
async def export_data(req: DataExportReq):
    try:
        source_session_id, source_mode = await _validated_or_server_session(req.source_environment, req.source_session_id)
        if not source_session_id:
            raise HTTPException(status_code=400, detail=f"No valid source session is available for {req.source_environment}. Run Server Sync or log in again.")
        fmt = (req.format or "csv").lower()
        file_name = req.file_name or f"data-{req.source_environment}-{req.form.replace(':','_')}-{int(datetime.now(timezone.utc).timestamp())}.{fmt}"
        add_job(req.source_environment, "data-export", "running", f"Exporting data from {req.form} ({source_mode})", {"maxRows": req.max_rows, "format": fmt})
        result = await ArApiClient().export_data(source_session_id, req.form, req.qualification, req.max_rows, fmt, req.fields, file_name)
        safe_file_name = Path(str(result.get("fileName") or result.get("file") or file_name)).name
        result["fileName"] = safe_file_name
        result["downloadUrl"] = f"/api/download/{safe_file_name}"
        result["sourceSessionMode"] = source_mode
        add_job(req.source_environment, "data-export", "ok", f"Data export ready: {safe_file_name}", {"rows": result.get("processed"), "fileSizeBytes": result.get("fileSizeBytes")})
        return result
    except HTTPException:
        raise
    except Exception as e:
        add_job(req.source_environment, "data-export", "error", str(e), {"form": req.form})
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/migrate/data")
async def migrate_data(req: DataMigrateReq):
    lock_token = None
    try:
        source_session_id, source_mode = await _validated_or_server_session(req.source_environment, req.source_session_id)
        target_session_id, target_user = await _validated_browser_session(req.target_environment, req.target_session_id)
        if not source_session_id:
            raise HTTPException(status_code=400, detail=f"No valid source session is available for {req.source_environment}. Run Server Sync or log in again.")
        if not target_session_id:
            raise HTTPException(status_code=401, detail={
                "message": f"Login required for target environment {req.target_environment.upper()} before data migration.",
                "loginRequired": True,
                "environment": req.target_environment,
                "reason": target_user,
            })
        lock_token = await acquire_env_lock(req.target_environment, f"data-migration:{req.form}", target_user)
        add_job(req.target_environment, "data-migrate", "running", f"Migrating data for {req.form} as {target_user}", {"mode": req.mode, "maxRows": req.max_rows})
        result = await ArApiClient().migrate_data(source_session_id, target_session_id, req.form, req.qualification, req.max_rows, req.mode)
        result["sourceSessionMode"] = source_mode
        result["targetUser"] = target_user
        add_job(req.target_environment, "data-migrate", "ok" if result.get("errors", 0) == 0 else "warn", f"Data migration completed for {req.form}", {"created": result.get("created"), "updated": result.get("updated"), "skipped": result.get("skipped"), "errors": result.get("errors")})
        return result
    except HTTPException:
        raise
    except Exception as e:
        add_job(req.target_environment, "data-migrate", "error", str(e), {"form": req.form})
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await release_env_lock(req.target_environment, lock_token)


@app.post("/api/migrate/def")
async def migrate_def(req: MigrateReq):
    lock_token = None
    try:
        source_session_id, source_mode = await _validated_or_server_session(req.source_environment, req.source_session_id)
        target_session_id, target_user = await _validated_browser_session(req.target_environment, req.target_session_id)
        target_mode = "browser" if target_session_id else "missing"
        if not source_session_id:
            raise HTTPException(status_code=400, detail=f"No valid source session is available for {req.source_environment}. Run Server Sync or log in again.")
        if not target_session_id:
            raise HTTPException(status_code=401, detail={
                "message": f"Login required for target environment {req.target_environment.upper()} before migration.",
                "loginRequired": True,
                "environment": req.target_environment,
                "reason": target_user,
            })

        lock_token = await acquire_env_lock(req.target_environment, "migration", target_user)
        add_job(req.target_environment, "migrate", "running", f"Pre-checking {len(req.items)} target object(s) before migration as {target_user}", {"items": len(req.items), "user": target_user})
        before_by_key = {}
        source_by_key = {}
        for item in req.items:
            object_type = item.get("objectType") or item.get("object_type") or "form"
            name = item.get("name") or item.get("objectName")
            if not name:
                continue
            key = f"{object_type}::{name}"
            before_by_key[key] = await _fetch_detail_hash(target_session_id, req.target_environment, object_type, name)
            source_by_key[key] = await _fetch_detail_hash(source_session_id, req.source_environment, object_type, name)

        add_job(req.target_environment, "migrate", "running", f"Importing {len(req.items)} selected object(s) from {req.source_environment} to {req.target_environment} ({source_mode} → {target_mode})", {"items": len(req.items)})
        result = await ArApiClient().migrate_def(source_session_id, target_session_id, req.items, req.file_name, req.related)
        result["sourceSessionMode"] = source_mode
        result["targetSessionMode"] = target_mode

        verification = []
        changed_count = 0
        equal_to_source_count = 0
        unchanged_count = 0
        for item in req.items:
            object_type = item.get("objectType") or item.get("object_type") or "form"
            name = item.get("name") or item.get("objectName")
            if not name:
                continue
            key = f"{object_type}::{name}"
            before = before_by_key.get(key, {"exists": False, "hash": None})
            source = source_by_key.get(key, {"exists": False, "hash": None})
            after = await _fetch_detail_hash(target_session_id, req.target_environment, object_type, name)
            if after.get("exists") and after.get("detail"):
                upsert_cached_object(req.target_environment, object_type, name, after["detail"])
            changed = before.get("hash") != after.get("hash")
            equal_to_source = bool(source.get("hash") and after.get("hash") == source.get("hash"))
            if changed:
                changed_count += 1
            else:
                unchanged_count += 1
            if equal_to_source:
                equal_to_source_count += 1
            verification.append({
                "objectType": object_type,
                "name": name,
                "targetExistedBefore": before.get("exists", False),
                "targetExistsAfter": after.get("exists", False),
                "targetChanged": changed,
                "targetEqualsSource": equal_to_source,
                "targetTimestampBefore": before.get("timestamp", ""),
                "targetTimestampAfter": after.get("timestamp", ""),
                "targetLastChangedByBefore": before.get("lastChangedBy", ""),
                "targetLastChangedByAfter": after.get("lastChangedBy", ""),
                "beforeHash": before.get("hash"),
                "afterHash": after.get("hash"),
                "sourceHash": source.get("hash"),
                "error": after.get("error") if not after.get("exists") else None,
            })

        result["verification"] = {
            "checked": len(verification),
            "changed": changed_count,
            "unchanged": unchanged_count,
            "equalToSource": equal_to_source_count,
            "items": verification,
        }
        add_job(req.target_environment, "migrate", "ok", f"Migration completed and verified: {equal_to_source_count}/{len(verification)} target object(s) equal source", {"items": len(req.items), "changed": changed_count, "unchanged": unchanged_count, "equalToSource": equal_to_source_count, "file": result.get("file"), "sourceSessionMode": source_mode, "targetSessionMode": target_mode})
        return result
    except HTTPException:
        raise
    except Exception as e:
        add_job(req.target_environment, "migrate", "error", str(e), {"items": len(req.items)})
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await release_env_lock(req.target_environment, lock_token)


@app.get("/api/download/{file_name}")
def download(file_name: str):
    path = (EXPORT_DIR / file_name).resolve()
    if not str(path).startswith(str(EXPORT_DIR.resolve())) or not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=file_name)
