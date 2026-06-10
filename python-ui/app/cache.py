import json
import hashlib
import fnmatch
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from .db import SessionLocal, CachedObject
from .arapi_client import ArApiClient
from .settings import config_store

VOLATILE_KEYS = {
    "lastChanged", "lastModified", "lastModifiedBy", "modifiedDate", "timestamp",
    "owner", "changeDiary", "lastUpdate", "objectId", "recordId", "requestId",
    "createDate", "modifiedBy", "lastModifiedDate", "lastUpdateTime", "lastUpdateBy",
    "modifiedTime", "lastChangedBy", "instanceId", "guid", "internalId",
    "changeFlag", "changeFlags",
    # HLX Migrator cache/runtime metadata
    "deepCachedAt", "capturedAt", "cacheNamespace", "definitionLoaded", "indexOnly",
    "scopeMatched", "debug", "errors", "sync", "scope"
}


def normalize(obj, ignore_keys: set[str] | None = None):
    """Return a deterministic object representation for diff/hash.

    User-configured ignore_keys are *added* to the built-in volatile/cache
    keys. Built-in cache/runtime keys such as deepCachedAt must never be
    compared even when ConfigMap provides its own diff.ignore_keys list.
    """
    effective_ignore = set(VOLATILE_KEYS)
    if ignore_keys:
        effective_ignore.update(str(k) for k in ignore_keys)

    if isinstance(obj, dict):
        return {
            k: normalize(v, effective_ignore)
            for k, v in sorted(obj.items())
            if k not in effective_ignore
        }
    if isinstance(obj, list):
        return [normalize(v, effective_ignore) for v in obj]
    return obj


def stable_hash(obj) -> str:
    payload = json.dumps(normalize(obj), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cache_namespace(environment: str, session_id: str | None = None) -> str:
    if session_id:
        return f"{environment}::{session_id[:12]}"
    return environment


def upsert_cached_object(environment: str, object_type: str, object_name: str, data: dict) -> None:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
    h = stable_hash(data)
    with SessionLocal() as db:
        existing = db.execute(select(CachedObject).where(
            CachedObject.environment == environment,
            CachedObject.object_type == object_type,
            CachedObject.object_name == object_name,
        )).scalar_one_or_none()
        if existing:
            existing.json_data = payload
            existing.object_hash = h
            existing.last_seen = datetime.now(timezone.utc)
        else:
            db.add(CachedObject(environment=environment, object_type=object_type, object_name=object_name, object_hash=h, json_data=payload))
        db.commit()




def upsert_cached_index_object(environment: str, object_type: str, object_name: str, data: dict, *, incremental: bool = True) -> dict:
    """Upsert a lightweight index row without destroying an existing deep definition.

    If an existing object already has full metadata and incremental sync is enabled,
    we keep the full payload when the lightweight index has not changed. If the index
    payload changes, the object is marked for deep refresh by setting indexOnly=True
    while preserving the latest index metadata.
    """
    now = datetime.now(timezone.utc)
    index_payload = {**data, "indexOnly": True, "definitionLoaded": False}
    index_hash = stable_hash(index_payload)
    with SessionLocal() as db:
        existing = db.execute(select(CachedObject).where(
            CachedObject.environment == environment,
            CachedObject.object_type == object_type,
            CachedObject.object_name == object_name,
        )).scalar_one_or_none()
        if not existing:
            db.add(CachedObject(environment=environment, object_type=object_type, object_name=object_name, object_hash=index_hash, json_data=json.dumps(index_payload, ensure_ascii=False, sort_keys=True)))
            db.commit()
            return {"action": "new", "changed": True}
        try:
            old = json.loads(existing.json_data or "{}")
        except Exception:
            old = {}
        old_index_hash = old.get("indexHash") or stable_hash({k: v for k, v in old.items() if k not in {"definitionLoaded", "indexOnly", "deepCachedAt", "capturedAt"}})
        unchanged = old_index_hash == index_hash
        if incremental and unchanged and old.get("definitionLoaded") is True and old.get("indexOnly") is not True:
            # Preserve deep details, just record that the object still exists.
            old["lastIndexedAt"] = now.isoformat()
            old["indexHash"] = index_hash
            existing.json_data = json.dumps(old, ensure_ascii=False, sort_keys=True)
            existing.last_seen = now
            db.commit()
            return {"action": "unchanged", "changed": False}
        merged = {**old, **index_payload, "indexHash": index_hash, "lastIndexedAt": now.isoformat()}
        # If the lightweight index changed, force detail refresh on the next deep-cache phase.
        if incremental and not unchanged:
            merged["definitionLoaded"] = False
            merged["indexOnly"] = True
        existing.json_data = json.dumps(merged, ensure_ascii=False, sort_keys=True)
        existing.object_hash = stable_hash(merged)
        existing.last_seen = now
        db.commit()
        return {"action": "changed" if not unchanged else "indexed", "changed": not unchanged}

def get_cached_objects(environment: str, object_type: str | None = None) -> list[CachedObject]:
    with SessionLocal() as db:
        stmt = select(CachedObject).where(CachedObject.environment == environment)
        if object_type:
            stmt = stmt.where(CachedObject.object_type == object_type)
        return list(db.execute(stmt).scalars().all())


def get_cached_object(environment: str, object_type: str, object_name: str) -> dict | None:
    with SessionLocal() as db:
        obj = db.execute(select(CachedObject).where(
            CachedObject.environment == environment,
            CachedObject.object_type == object_type,
            CachedObject.object_name == object_name,
        )).scalar_one_or_none()
        return json.loads(obj.json_data) if obj else None


def _match_pattern(value: str, pattern: str) -> bool:
    """Case-insensitive glob/prefix match.

    Patterns with *, ?, or [] are treated as glob patterns.
    Plain values are treated as prefixes for backwards compatibility.
    Example: HLX* matches HLX:Foo and hlx:foo.
    """
    value_norm = (value or "").upper()
    pattern_norm = (pattern or "").upper()
    if not pattern_norm:
        return False
    if any(ch in pattern_norm for ch in "*?[]"):
        return fnmatch.fnmatchcase(value_norm, pattern_norm)
    return value_norm.startswith(pattern_norm)


def in_scope(form_name: str) -> bool:
    scope = config_store.scope()
    includes = scope.get("include_form_prefixes") or []
    excludes = scope.get("exclude_form_prefixes") or []

    if excludes and any(_match_pattern(form_name, p) for p in excludes):
        return False

    if includes:
        return any(_match_pattern(form_name, p) for p in includes)

    return True


def object_in_scope(object_name: str) -> bool:
    """Scope check for global/index-only objects such as menus and containers.

    For now we cannot reliably know every dependency without loading full
    definitions. To keep startup fast and avoid RPC-heavy calls, global object
    categories are filtered by object name using the same include/exclude glob
    rules as forms. This prevents menus/guides/applications outside e.g. HLX*
    from flooding the UI. Later we can add a true dependency resolver.
    """
    return in_scope(object_name)


def filter_index_values(values: list) -> list:
    result = []
    for obj in values or []:
        if isinstance(obj, dict):
            name = _object_name(obj, "object", 0)
            if object_in_scope(name):
                result.append(obj)
        else:
            name = str(obj)
            if object_in_scope(name):
                result.append(obj)
    return result


def scope_debug(all_forms: list[str], scoped_forms: list[str]) -> dict:
    return {
        "scope": config_store.scope(),
        "formsTotal": len(all_forms),
        "formsInScope": len(scoped_forms),
        "examplesInScope": scoped_forms[:20],
        "examplesOutOfScope": [f for f in all_forms if f not in set(scoped_forms)][:20],
    }


def _object_name(obj: dict, fallback_prefix: str, index: int) -> str:
    for key in ("name", "key", "label", "description", "value"):
        value = obj.get(key) if isinstance(obj, dict) else None
        if value:
            return str(value)
    return f"{fallback_prefix}-{index}"


def _upsert_many(ns: str, object_type: str, values: list, extra: dict | None = None, seen: set | None = None) -> int:
    count = 0
    for idx, obj in enumerate(values or []):
        if not isinstance(obj, dict):
            obj = {"value": str(obj), "name": str(obj), "definitionLoaded": False, "indexOnly": True}
        else:
            obj = {**obj, "definitionLoaded": obj.get("definitionLoaded", False), "indexOnly": obj.get("indexOnly", True)}
        if extra:
            obj = {**obj, **extra}
        name = _object_name(obj, object_type, idx)
        if seen is not None:
            if name in seen:
                continue
            seen.add(name)
        upsert_cached_index_object(ns, object_type, name, obj, incremental=bool(config_store.sync().get("incremental", True)))
        count += 1
    return count


async def full_sync_forms(environment: str, session_id: str, limit: int | None = None, service_cache: bool = False) -> dict:
    """Sync forms respecting scope.

    Startup is intentionally conservative: by default it stores a scoped form index
    only. Fetching every full form definition (fields/views/display properties) can
    be very heavy when the scope contains thousands of forms. Enable
    sync.form_details=true to fetch full definitions automatically.
    """
    client = ArApiClient()
    sync_cfg = config_store.sync()
    all_forms = await client.list_forms(session_id)
    scoped_forms = [f for f in all_forms if in_scope(f)]

    # Store the scoped index as its own object so the GUI can show what scope did.
    ns = environment if service_cache else cache_namespace(environment, session_id)
    upsert_cached_object(ns, "form_index", "__scoped_forms__", {
        "environment": environment,
        "scope": config_store.scope(),
        "formsTotal": len(all_forms),
        "formsInScope": len(scoped_forms),
        "forms": scoped_forms,
        "capturedAt": datetime.now(timezone.utc).isoformat(),
    })

    # Also store one light-weight row per form name so lists/diffs can render immediately.
    indexed = 0
    new_count = 0
    changed_count = 0
    unchanged_count = 0
    incremental = bool(sync_cfg.get("incremental", True))
    for form in scoped_forms:
        res = upsert_cached_index_object(ns, "form", form, {
            "type": "form",
            "name": form,
            "scopeMatched": True,
        }, incremental=incremental)
        indexed += 1
        if res.get("action") == "new":
            new_count += 1
        elif res.get("changed"):
            changed_count += 1
        else:
            unchanged_count += 1

    detail_enabled = bool(sync_cfg.get("form_details", False))
    detail_limit = sync_cfg.get("form_detail_limit", 0) or 0
    detail_forms = list(scoped_forms)
    if limit:
        detail_forms = detail_forms[:limit]
    elif detail_limit > 0:
        detail_forms = detail_forms[:detail_limit]
    elif not detail_enabled:
        detail_forms = []

    synced = 0
    errors = []
    for form in detail_forms:
        try:
            data = await client.get_form(session_id, form)
            data["definitionLoaded"] = True
            upsert_cached_object(ns, "form", form, data)
            synced += 1
        except Exception as e:
            errors.append({"form": form, "error": str(e)})

    debug = scope_debug(all_forms, scoped_forms)
    return {
        "environment": environment,
        "cacheNamespace": ns,
        "type": "forms",
        "mode": "index_only" if not detail_forms else "index_plus_details",
        "formsTotal": len(all_forms),
        "formsInScope": len(scoped_forms),
        "indexed": indexed,
        "new": new_count,
        "changed": changed_count,
        "unchanged": unchanged_count,
        "incremental": bool(sync_cfg.get("incremental", True)),
        "purgeMissing": bool(sync_cfg.get("purge_missing", False)),
        "detailsRequested": len(detail_forms),
        "synced": synced,
        "scope": config_store.scope(),
        "debug": debug,
        "errors": errors,
    }


async def sync_workflow_robust(
    environment: str,
    session_id: str,
    include_global: bool = True,
    limit_forms: int | None = None,
    service_cache: bool = False,
) -> dict:
    """Robust workflow sync that respects scope and fetches each object family separately.

    It never calls full bulk object endpoints during auto-sync. The Java service returns
    name lists only for workflow/global metadata, so even Escalations can be indexed
    without ARGetMultipleEscalations / ProcNumber 84 RPC failures. Details are loaded
    later on demand.
    """
    client = ArApiClient()
    sync_cfg = config_store.sync()
    all_forms = await client.list_forms(session_id)
    forms = [f for f in all_forms if in_scope(f)]
    if limit_forms:
        forms = forms[:limit_forms]
    ns = environment if service_cache else cache_namespace(environment, session_id)
    counts = {
        "active_link": 0, "filter": 0, "escalation": 0, "menu": 0, "image": 0,
        "active_link_guide": 0, "filter_guide": 0, "web_service": 0, "association": 0, "packing_list": 0, "application": 0,
    }
    errors: list[dict] = []
    steps: list[dict] = []
    seen = {"active_link": set(), "filter": set(), "escalation": set()}

    async def step(name: str, func):
        started = datetime.now(timezone.utc).isoformat()
        try:
            result = await func()
            steps.append({"step": name, "status": "ok", "startedAt": started, "finishedAt": datetime.now(timezone.utc).isoformat(), **(result or {})})
        except Exception as e:
            err = {"step": name, "status": "error", "error": str(e), "startedAt": started, "finishedAt": datetime.now(timezone.utc).isoformat()}
            steps.append(err)
            errors.append(err)
            if not sync_cfg.get("continue_on_error", True):
                raise

    for form in forms:
        if sync_cfg.get("active_links", True):
            async def _al(form=form):
                data = await client.active_links(session_id, form=form)
                n = _upsert_many(ns, "active_link", data.get("activeLinks") or [], {"relatedForm": form}, seen["active_link"])
                counts["active_link"] += n
                return {"form": form, "count": n}
            await step(f"active_links:{form}", _al)

        if sync_cfg.get("filters", True):
            async def _flt(form=form):
                data = await client.filters(session_id, form=form)
                n = _upsert_many(ns, "filter", data.get("filters") or [], {"relatedForm": form}, seen["filter"])
                counts["filter"] += n
                return {"form": form, "count": n}
            await step(f"filters:{form}", _flt)

        if sync_cfg.get("escalations", False):
            async def _esc(form=form):
                data = await client.escalations(session_id, form=form)
                n = _upsert_many(ns, "escalation", data.get("escalations") or [], {"relatedForm": form}, seen["escalation"])
                counts["escalation"] += n
                return {"form": form, "count": n}
            await step(f"escalations:{form}", _esc)

        await asyncio.sleep(0)

    if include_global and sync_cfg.get("include_global", True):
        if sync_cfg.get("menus", True):
            async def _menus():
                raw = (await client.menus(session_id)).get("menus") or []
                filtered = filter_index_values(raw)
                n = _upsert_many(ns, "menu", filtered)
                counts["menu"] += n
                return {"count": n, "total": len(raw), "inScope": len(filtered), "scopeMode": "object_name"}
            await step("menus", _menus)

        if any(sync_cfg.get(k, False) for k in ("active_link_guides", "filter_guides", "web_services", "packing_lists", "applications", "containers")):
            async def _container_categories():
                data = await client.container_categories(session_id)
                result = {}
                mappings = [
                    ("active_link_guides", "activeLinkGuides", "active_link_guide"),
                    ("filter_guides", "filterGuides", "filter_guide"),
                    ("web_services", "webServices", "web_service"),
                    ("packing_lists", "packingLists", "packing_list"),
                    ("applications", "applications", "application"),
                ]
                for cfg_key, payload_key, object_type in mappings:
                    if sync_cfg.get(cfg_key, False):
                        raw = data.get(payload_key) or []
                        filtered = filter_index_values(raw)
                        n = _upsert_many(ns, object_type, filtered)
                        counts[object_type] += n
                        result[object_type] = {"indexed": n, "total": len(raw), "inScope": len(filtered), "scopeMode": "object_name"}
                # Keep the old generic bucket disabled by default. It is available only when explicitly requested.
                if sync_cfg.get("containers", False):
                    raw = data.get("otherContainers") or []
                    filtered = filter_index_values(raw)
                    n = _upsert_many(ns, "other_container", filtered)
                    counts["other_container"] = counts.get("other_container", 0) + n
                    result["other_container"] = {"indexed": n, "total": len(raw), "inScope": len(filtered), "scopeMode": "object_name"}
                return result
            await step("container_categories", _container_categories)

        if sync_cfg.get("associations", False):
            async def _associations():
                raw = (await client.associations(session_id)).get("associations") or []
                filtered = filter_index_values(raw)
                n = _upsert_many(ns, "association", filtered)
                counts["association"] += n
                return {"count": n, "total": len(raw), "inScope": len(filtered), "scopeMode": "object_name"}
            await step("associations", _associations)

        if sync_cfg.get("images", False):
            async def _images():
                raw = (await client.images(session_id)).get("images") or []
                filtered = filter_index_values(raw)
                n = _upsert_many(ns, "image", filtered)
                counts["image"] += n
                return {"count": n, "total": len(raw), "inScope": len(filtered), "scopeMode": "object_name"}
            await step("images", _images)

    return {
        "environment": environment,
        "cacheNamespace": ns,
        "type": "workflow",
        "formsTotal": len(all_forms),
        "formsInScope": len(forms),
        "scope": config_store.scope(),
        "sync": sync_cfg,
        "counts": counts,
        "steps": steps,
        "errors": errors,
        "status": "ok" if not errors else "partial",
    }


# Backwards-compatible name used by older FastAPI routes.
async def full_sync_workflow(environment: str, session_id: str, include_global: bool = True, limit_forms: int | None = None, service_cache: bool = False) -> dict:
    return await sync_workflow_robust(environment, session_id, include_global, limit_forms, service_cache)


def _sync_detail_types_from_config() -> list[str]:
    sync_cfg = config_store.sync()
    configured = sync_cfg.get("detail_object_types")
    if isinstance(configured, str):
        configured = [x.strip() for x in configured.split(",") if x.strip()]
    if not configured:
        configured = ["form", "active_link", "filter", "escalation", "menu", "active_link_guide", "filter_guide", "web_service", "association", "packing_list", "application", "image"]
    # Only deep-cache object families that were enabled/indexed, except forms which
    # are controlled by sync.forms. This prevents surprises when a category is disabled.
    enabled = []
    for t in configured:
        if t == "form" and sync_cfg.get("forms", True):
            enabled.append(t)
        elif t == "active_link" and sync_cfg.get("active_links", False):
            enabled.append(t)
        elif t == "filter" and sync_cfg.get("filters", False):
            enabled.append(t)
        elif t == "escalation" and sync_cfg.get("escalations", False):
            enabled.append(t)
        elif t == "menu" and sync_cfg.get("menus", False):
            enabled.append(t)
        elif t == "active_link_guide" and sync_cfg.get("active_link_guides", False):
            enabled.append(t)
        elif t == "filter_guide" and sync_cfg.get("filter_guides", False):
            enabled.append(t)
        elif t == "web_service" and sync_cfg.get("web_services", False):
            enabled.append(t)
        elif t == "association" and sync_cfg.get("associations", False):
            enabled.append(t)
        elif t == "packing_list" and sync_cfg.get("packing_lists", False):
            enabled.append(t)
        elif t == "application" and sync_cfg.get("applications", False):
            enabled.append(t)
        elif t == "image" and sync_cfg.get("images", False):
            enabled.append(t)
    return enabled


async def deep_cache_object_details(
    environment: str,
    session_id: str,
    service_cache: bool = False,
    object_types: list[str] | None = None,
    max_per_type: int | None = None,
    concurrency: int | None = None,
    refresh_existing: bool | None = None,
    progress_cb=None,
) -> dict:
    """Load full ARAPI definitions for indexed objects.

    The app still starts with index-only cache so the UI is usable quickly. This
    background step then loads rich metadata one object at a time, which is much
    safer for production-sized AR System environments than bulk object calls.
    The resulting JSON is what compare/diff uses.
    """
    sync_cfg = config_store.sync()
    ns = environment if service_cache else cache_namespace(environment, session_id)
    object_types = object_types or _sync_detail_types_from_config()
    max_per_type = sync_cfg.get("details_max_per_type", 0) if max_per_type is None else max_per_type
    max_per_type = int(max_per_type or 0)
    concurrency = int(concurrency or sync_cfg.get("details_concurrency", 2) or 2)
    concurrency = max(1, min(concurrency, 8))
    refresh_existing = bool(sync_cfg.get("details_refresh_existing", False) if refresh_existing is None else refresh_existing)
    continue_on_error = bool(sync_cfg.get("continue_on_error", True))

    def emit_progress(object_type: str, message: str, completed: int = 0, total: int = 0):
        if not progress_cb:
            return
        try:
            percent = 0 if not total else int((completed / max(total, 1)) * 100)
            progress_cb({"objectType": object_type, "message": message, "completed": completed, "total": total, "percent": percent})
        except Exception:
            pass

    client = ArApiClient()
    counts: dict[str, dict] = {}
    errors: list[dict] = []
    steps: list[dict] = []
    sem = asyncio.Semaphore(concurrency)

    async def load_one(object_type: str, name: str) -> tuple[bool, str | None]:
        async with sem:
            try:
                if object_type == "form":
                    detail = await client.get_form(session_id, name)
                else:
                    detail = await client.get_object_detail(session_id, object_type, name)
                detail["definitionLoaded"] = True
                detail["indexOnly"] = False
                detail["deepCachedAt"] = datetime.now(timezone.utc).isoformat()
                upsert_cached_object(ns, object_type, name, detail)
                return True, None
            except Exception as e:
                return False, str(e)

    for object_type in object_types:
        started = datetime.now(timezone.utc).isoformat()
        rows = []
        loaded = 0
        failed = 0
        skipped = 0
        requested = 0
        try:
            rows = get_cached_objects(ns, object_type)
            candidates = []
            for row in rows:
                try:
                    payload = json.loads(row.json_data)
                except Exception:
                    payload = {}
                if not refresh_existing and payload.get("definitionLoaded") is True and payload.get("indexOnly") is not True:
                    skipped += 1
                    continue
                candidates.append(row.object_name)
            if max_per_type > 0:
                candidates = candidates[:max_per_type]

            requested = len(candidates)
            emit_progress(object_type, f"Preparing {object_type} details ({requested} to load, {skipped} already cached)", 0, max(requested, 1))
            for i in range(0, requested, concurrency * 4):
                chunk = candidates[i:i + concurrency * 4]
                results = await asyncio.gather(*(load_one(object_type, name) for name in chunk), return_exceptions=True)
                for name, result in zip(chunk, results):
                    if isinstance(result, Exception):
                        ok, err = False, str(result)
                    else:
                        ok, err = result
                    if ok:
                        loaded += 1
                    else:
                        failed += 1
                        error = {"objectType": object_type, "name": name, "error": err}
                        errors.append(error)
                        if not continue_on_error:
                            raise RuntimeError(f"Detail cache failed for {object_type} {name}: {err}")
                emit_progress(object_type, f"Loaded {loaded}/{requested} {object_type} details", loaded + failed, max(requested, 1))
                await asyncio.sleep(0)
        except Exception as e:
            failed += 1
            err = str(e)
            errors.append({"objectType": object_type, "name": "*type*", "error": err})
            emit_progress(object_type, f"{object_type} detail cache failed: {err}", requested, max(requested, 1))
            if not continue_on_error:
                raise

        emit_progress(object_type, f"Finished {object_type}: {loaded} loaded, {failed} failed, {skipped} skipped", requested, max(requested, 1))
        counts[object_type] = {"requested": requested, "loaded": loaded, "failed": failed, "skipped": skipped, "totalCached": len(rows)}
        steps.append({
            "step": f"details:{object_type}",
            "status": "ok" if failed == 0 else "partial",
            "startedAt": started,
            "finishedAt": datetime.now(timezone.utc).isoformat(),
            **counts[object_type],
        })

    return {
        "environment": environment,
        "cacheNamespace": ns,
        "type": "details",
        "mode": "deep_cache",
        "objectTypes": object_types,
        "counts": counts,
        "steps": steps,
        "errors": errors,
        "status": "ok" if not errors else "partial",
        "sync": sync_cfg,
        "scope": config_store.scope(),
    }
