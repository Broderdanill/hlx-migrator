import httpx
from .settings import ARAPI_BASE_URL, config_store


class ArApiClient:
    def __init__(self, base_url: str = ARAPI_BASE_URL):
        self.base_url = base_url.rstrip("/")

    def _headers(self, session_id: str | None = None) -> dict:
        return {"X-HLX-Session": session_id} if session_id else {}

    def _clean_export_items(self, items: list[dict]) -> list[dict]:
        """Keep only fields accepted by the Java ARAPI ExportItem model.

        Difference-view rows contain UI metadata such as status, timestamp,
        lastChangedBy and diff details. Those must not be sent to the ARAPI
        service because it only expects name/objectType/type.
        """
        cleaned = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("objectName") or item.get("object_name")
            object_type = item.get("objectType") or item.get("object_type") or item.get("typeName")
            browser_type = item.get("type", 0)
            if not name:
                continue
            cleaned.append({
                "name": name,
                "objectType": object_type or "form",
                "type": browser_type if isinstance(browser_type, int) else 0,
            })
        return cleaned

    def _raise_for_status_with_body(self, r: httpx.Response) -> None:
        if r.status_code < 400:
            return
        try:
            payload = r.json()
            message = payload.get("message") or payload.get("detail") or str(payload)
            ar_status = payload.get("arStatus")
            if ar_status:
                details = []
                for s in ar_status:
                    details.append(f"ARERR {s.get('number')}: {s.get('text') or ''} {s.get('appendedText') or ''}".strip())
                if details:
                    message = message + " | " + " | ".join(details)
        except Exception:
            message = r.text
        raise httpx.HTTPStatusError(f"{r.status_code} from ARAPI service: {message}", request=r.request, response=r)

    async def health(self) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self.base_url}/health")
            self._raise_for_status_with_body(r)
            return r.json()

    async def login(self, env: str, username: str, password: str, authentication: str = "") -> dict:
        payload = config_store.get_login_payload(env, username, password, authentication)
        return await self.login_payload(payload)

    async def server_login(self, env: str) -> dict:
        payload = config_store.get_server_login_payload(env)
        result = await self.login_payload(payload)
        result["serverLogin"] = True
        return result

    async def login_payload(self, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{self.base_url}/sessions/login", json=payload)
            self._raise_for_status_with_body(r)
            return r.json()

    async def logout(self, session_id: str) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(f"{self.base_url}/sessions/logout", headers=self._headers(session_id))
            self._raise_for_status_with_body(r)
            return r.json()

    async def me(self, session_id: str) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(f"{self.base_url}/sessions/me", headers=self._headers(session_id))
            self._raise_for_status_with_body(r)
            return r.json()

    async def list_forms(self, session_id: str) -> list[str]:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.get(f"{self.base_url}/metadata/forms", headers=self._headers(session_id))
            self._raise_for_status_with_body(r)
            return r.json()["forms"]

    async def get_form(self, session_id: str, name: str) -> dict:
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.get(f"{self.base_url}/metadata/forms/{name}", headers=self._headers(session_id))
            self._raise_for_status_with_body(r)
            return r.json()

    async def active_links(self, session_id: str, form: str | None = None) -> dict:
        params = {"form": form} if form else None
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.get(f"{self.base_url}/metadata/active-links", headers=self._headers(session_id), params=params)
            self._raise_for_status_with_body(r)
            return r.json()

    async def filters(self, session_id: str, form: str | None = None) -> dict:
        params = {"form": form} if form else None
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.get(f"{self.base_url}/metadata/filters", headers=self._headers(session_id), params=params)
            self._raise_for_status_with_body(r)
            return r.json()

    async def escalations(self, session_id: str, form: str | None = None) -> dict:
        params = {"form": form} if form else None
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.get(f"{self.base_url}/metadata/escalations", headers=self._headers(session_id), params=params)
            self._raise_for_status_with_body(r)
            return r.json()

    async def workflow(self, session_id: str, form: str | None = None) -> dict:
        params = {"form": form} if form else None
        async with httpx.AsyncClient(timeout=240) as client:
            r = await client.get(f"{self.base_url}/metadata/workflow", headers=self._headers(session_id), params=params)
            self._raise_for_status_with_body(r)
            return r.json()

    async def menus(self, session_id: str) -> dict:
        async with httpx.AsyncClient(timeout=240) as client:
            r = await client.get(f"{self.base_url}/metadata/menus", headers=self._headers(session_id))
            self._raise_for_status_with_body(r)
            return r.json()

    async def containers(self, session_id: str) -> dict:
        async with httpx.AsyncClient(timeout=240) as client:
            r = await client.get(f"{self.base_url}/metadata/containers", headers=self._headers(session_id))
            self._raise_for_status_with_body(r)
            return r.json()

    async def container_categories(self, session_id: str) -> dict:
        async with httpx.AsyncClient(timeout=240) as client:
            r = await client.get(f"{self.base_url}/metadata/container-categories", headers=self._headers(session_id))
            self._raise_for_status_with_body(r)
            return r.json()

    async def associations(self, session_id: str) -> dict:
        async with httpx.AsyncClient(timeout=240) as client:
            r = await client.get(f"{self.base_url}/metadata/associations", headers=self._headers(session_id))
            self._raise_for_status_with_body(r)
            return r.json()

    async def images(self, session_id: str) -> dict:
        async with httpx.AsyncClient(timeout=240) as client:
            r = await client.get(f"{self.base_url}/metadata/images", headers=self._headers(session_id))
            self._raise_for_status_with_body(r)
            return r.json()


    async def get_object_detail(self, session_id: str, object_type: str, name: str) -> dict:
        endpoint_map = {
            "form": "forms",
            "active_link": "active-links",
            "filter": "filters",
            "escalation": "escalations",
            "menu": "menus",
            "image": "images",
            "active_link_guide": "containers",
            "filter_guide": "containers",
            "packing_list": "containers",
            "application": "containers",
            "web_service": "containers",
            "association": "associations",
            "other_container": "containers",
        }
        endpoint = endpoint_map.get(object_type)
        if not endpoint:
            raise ValueError(f"Unsupported object type for detail load: {object_type}")
        async with httpx.AsyncClient(timeout=240) as client:
            r = await client.get(f"{self.base_url}/metadata/{endpoint}/{name}", headers=self._headers(session_id))
            self._raise_for_status_with_body(r)
            return r.json()

    async def export_def(self, session_id: str, items: list[dict], file_name: str, related: bool = True) -> dict:
        async with httpx.AsyncClient(timeout=300) as client:
            r = await client.post(
                f"{self.base_url}/export/def",
                headers=self._headers(session_id),
                json={"items": self._clean_export_items(items), "fileName": file_name, "related": related},
            )
            self._raise_for_status_with_body(r)
            return r.json()
    async def migrate_def(self, source_session_id: str, target_session_id: str, items: list[dict], file_name: str, related: bool = True) -> dict:
        async with httpx.AsyncClient(timeout=600) as client:
            r = await client.post(
                f"{self.base_url}/migrate/def",
                json={
                    "sourceSessionId": source_session_id,
                    "targetSessionId": target_session_id,
                    "items": self._clean_export_items(items),
                    "fileName": file_name,
                    "related": related,
                },
            )
            self._raise_for_status_with_body(r)
            return r.json()

    async def export_data(self, session_id: str, form: str, qualification: str = "", max_rows: int = 0, fmt: str = "csv", fields: list[str] | None = None, file_name: str | None = None) -> dict:
        async with httpx.AsyncClient(timeout=900) as client:
            r = await client.post(
                f"{self.base_url}/data/export",
                headers=self._headers(session_id),
                json={"form": form, "qualification": qualification or "", "maxRows": max_rows or 0, "format": fmt or "csv", "fields": fields or [], "fileName": file_name},
            )
            self._raise_for_status_with_body(r)
            return r.json()

    async def migrate_data(self, source_session_id: str, target_session_id: str, form: str, qualification: str = "", max_rows: int = 0, mode: str = "update") -> dict:
        async with httpx.AsyncClient(timeout=1800) as client:
            r = await client.post(
                f"{self.base_url}/data/migrate",
                json={"sourceSessionId": source_session_id, "targetSessionId": target_session_id, "form": form, "qualification": qualification or "", "maxRows": max_rows or 0, "mode": mode or "update"},
            )
            self._raise_for_status_with_body(r)
            return r.json()

