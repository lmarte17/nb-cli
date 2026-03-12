from __future__ import annotations

import importlib
from copy import deepcopy
from typing import Any
from urllib.parse import urljoin

from .config import AppConfig
from .exceptions import (
    APIError,
    AuthError,
    ConfigError,
    ConnectivityError,
    NotFoundError,
    ValidationError,
)
from .output import to_data
from .parsing import parse_resource


class NetBoxClient:
    HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._api: Any | None = None

    @property
    def api(self) -> Any:
        if self._api is None:
            self._api = self._build_api()
        return self._api

    def _build_api(self) -> Any:
        if not self.config.url:
            raise ConfigError("NetBox URL is required")

        pynetbox = importlib.import_module("pynetbox")
        requests = importlib.import_module("requests")

        session = requests.Session()
        session.verify = self.config.verify_ssl
        session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "nb-cli/0.1.0",
                **self.config.headers,
            }
        )
        if self.config.token:
            session.headers["Authorization"] = self._build_auth_header(self.config.token)
        adapter = _TimeoutHTTPAdapter(timeout=self.config.timeout)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        try:
            api = pynetbox.api(
                self.config.url,
                token=self.config.token,
                threading=self.config.threading,
                strict_filters=self.config.strict_filters,
            )
        except TypeError:
            api = pynetbox.api(
                self.config.url,
                token=self.config.token,
                threading=self.config.threading,
            )
        api.http_session = session
        return api

    def _build_auth_header(self, token: str) -> str:
        if token.startswith("Bearer ") or token.startswith("Token "):
            return token
        return f"Bearer {token}" if token.startswith("nbt_") else f"Token {token}"

    def _translate_exception(self, exc: Exception) -> Exception:
        status_code = getattr(getattr(exc, "req", None), "status_code", None)
        message = getattr(exc, "error", None) or str(exc) or exc.__class__.__name__
        class_name = exc.__class__.__name__

        if isinstance(exc, ValidationError):
            return exc
        if isinstance(exc, ValueError):
            return ValidationError(message)
        if class_name in {"ConnectTimeout", "ConnectionError", "ReadTimeout", "SSLError", "Timeout"}:
            return ConnectivityError(message)
        if status_code in {401, 403}:
            return AuthError(message)
        if status_code == 404:
            return NotFoundError(message)
        if class_name in {"RequestError", "ContentError", "AllocationError"}:
            return APIError(message, details={"status_code": status_code})
        return APIError(message)

    def _resolve_endpoint(self, resource: str) -> Any:
        current = self.api
        for part in parse_resource(resource):
            attribute = part.replace("-", "_")
            if not hasattr(current, attribute):
                raise ValidationError(f"unknown NetBox resource: {resource}")
            current = getattr(current, attribute)
        return current

    def _strict_kwargs(self, values: dict[str, Any] | None = None) -> dict[str, Any]:
        result = dict(values or {})
        if self.config.strict_filters:
            result["strict_filters"] = True
        return result

    def _get_record_object(
        self,
        resource: str,
        *,
        record_id: int | None,
        lookup: dict[str, Any],
    ) -> Any:
        endpoint = self._resolve_endpoint(resource)
        if record_id is not None and lookup:
            raise ValidationError("use either --id or --lookup, not both")
        if record_id is None and not lookup:
            raise ValidationError("an object lookup requires --id or at least one --lookup key=value pair")
        try:
            if record_id is not None:
                record = endpoint.get(record_id)
            else:
                record = endpoint.get(**self._strict_kwargs(lookup))
        except Exception as exc:
            raise self._translate_exception(exc) from exc
        if record is None:
            raise NotFoundError(f"no object matched resource {resource}")
        return record

    def _lookup_single(self, resource: str, filters: dict[str, Any]) -> Any:
        endpoint = self._resolve_endpoint(resource)
        try:
            record = endpoint.get(**self._strict_kwargs(filters))
        except Exception as exc:
            raise self._translate_exception(exc) from exc
        if record is None:
            raise NotFoundError(
                f"no object matched resource {resource}",
                details={"filters": filters},
            )
        return record

    def status(self) -> Any:
        try:
            return self.api.status()
        except Exception as exc:  # pragma: no cover - exercised via tests on translation
            raise self._translate_exception(exc) from exc

    def openapi(self) -> Any:
        try:
            return self.api.openapi()
        except Exception as exc:  # pragma: no cover
            raise self._translate_exception(exc) from exc

    def list_resources(self, search: str | None = None) -> list[dict[str, Any]]:
        schema = self.openapi()
        paths = schema.get("paths", {})
        results: list[dict[str, Any]] = []
        for path, operations in sorted(paths.items()):
            if not path.startswith("/api/") or "{id}" in path:
                continue
            methods = sorted(
                method.upper() for method in operations.keys() if method.lower() in self.HTTP_METHODS
            )
            if not methods:
                continue
            resource = self._resource_from_api_path(path)
            if search and search.lower() not in resource.lower() and search.lower() not in path.lower():
                continue
            results.append(
                {
                    "resource": resource,
                    "path": path,
                    "methods": methods,
                }
            )
        return results

    def schema(self, resource: str) -> dict[str, Any]:
        document = self.openapi()
        paths = document.get("paths", {})
        list_path, detail_path = self._path_candidates_from_resource(resource)
        list_operations = self._normalize_path_item(document, paths.get(list_path, {}))
        detail_operations = self._normalize_path_item(document, paths.get(detail_path, {}))
        if not list_operations and not detail_operations:
            raise NotFoundError(
                f"resource {resource} was not found in the OpenAPI schema",
                details={"tried_paths": [list_path, detail_path]},
            )
        return {
            "resource": resource,
            "list_path": list_path,
            "detail_path": detail_path,
            "list_operations": list_operations,
            "detail_operations": detail_operations,
        }

    def choices(self, resource: str) -> Any:
        endpoint = self._resolve_endpoint(resource)
        try:
            return endpoint.choices()
        except Exception as exc:  # pragma: no cover
            raise self._translate_exception(exc) from exc

    def query(
        self,
        resource: str,
        *,
        search: str | None,
        filters: dict[str, Any],
        limit: int | None,
        offset: int | None,
        brief: bool,
        fields: list[str],
        exclude: list[str],
        ordering: str | None,
    ) -> list[Any]:
        endpoint = self._resolve_endpoint(resource)
        query: dict[str, Any] = dict(filters)
        if limit is not None:
            query["limit"] = limit
        if offset is not None:
            query["offset"] = offset
        if brief:
            query["brief"] = 1
        if fields:
            query["fields"] = ",".join(fields)
        if exclude:
            query["exclude"] = ",".join(exclude)
        if ordering:
            query["ordering"] = ordering
        query = self._strict_kwargs(query)

        try:
            if search:
                result = endpoint.filter(search, **query)
            else:
                result = endpoint.filter(**query)
            return [to_data(item) for item in result]
        except Exception as exc:
            raise self._translate_exception(exc) from exc

    def count(
        self,
        resource: str,
        *,
        search: str | None,
        filters: dict[str, Any],
    ) -> int:
        endpoint = self._resolve_endpoint(resource)
        kwargs = self._strict_kwargs(filters)
        try:
            if search:
                return int(endpoint.count(search, **kwargs))
            return int(endpoint.count(**kwargs))
        except Exception as exc:
            raise self._translate_exception(exc) from exc

    def get(self, resource: str, *, record_id: int | None, lookup: dict[str, Any]) -> Any:
        record = self._get_record_object(resource, record_id=record_id, lookup=lookup)
        return to_data(record)

    def create(self, resource: str, payload: Any) -> Any:
        endpoint = self._resolve_endpoint(resource)
        try:
            if isinstance(payload, list):
                return to_data(endpoint.create(payload))
            if isinstance(payload, dict):
                return to_data(endpoint.create(**payload))
            raise ValidationError("create payload must be a JSON object or array")
        except Exception as exc:
            raise self._translate_exception(exc) from exc

    def preview_update(
        self,
        resource: str,
        *,
        record_id: int | None,
        lookup: dict[str, Any],
        payload: Any,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValidationError("update payload must be a JSON object")
        record = self._get_record_object(resource, record_id=record_id, lookup=lookup)
        before = to_data(record)
        after = deepcopy(before)
        after.update(to_data(payload))
        changes = {
            key: {"before": before.get(key), "after": after.get(key)}
            for key in payload
            if before.get(key) != after.get(key)
        }
        return {
            "resource": resource,
            "target": {"id": before.get("id")},
            "before": before,
            "after": after,
            "changes": changes,
        }

    def update(
        self,
        resource: str,
        *,
        record_id: int | None,
        lookup: dict[str, Any],
        payload: Any,
    ) -> Any:
        if not isinstance(payload, dict):
            raise ValidationError("update payload must be a JSON object")
        record = self._get_record_object(resource, record_id=record_id, lookup=lookup)
        before = to_data(record)
        try:
            result = record.update(payload)
        except Exception as exc:
            raise self._translate_exception(exc) from exc
        return {
            "updated": bool(result),
            "before": before,
            "after": to_data(record),
        }

    def delete(self, resource: str, *, record_id: int | None, lookup: dict[str, Any]) -> Any:
        record = self._get_record_object(resource, record_id=record_id, lookup=lookup)
        snapshot = to_data(record)
        try:
            result = record.delete()
        except Exception as exc:
            raise self._translate_exception(exc) from exc
        return {
            "deleted": bool(result),
            "record": snapshot,
        }

    def bulk_update(self, resource: str, payload: list[dict[str, Any]]) -> Any:
        """PATCH an array of objects to the NetBox bulk-update list endpoint."""
        if not isinstance(payload, list):
            raise ValidationError("bulk-update payload must be a JSON array")
        if not all(isinstance(item, dict) and "id" in item for item in payload):
            raise ValidationError("each item in bulk-update payload must be an object with an 'id' key")
        endpoint = self._resolve_endpoint(resource)
        try:
            result = endpoint.update(payload)
        except Exception as exc:
            raise self._translate_exception(exc) from exc
        return to_data(result)

    def bulk_delete(self, resource: str, ids: list[int]) -> Any:
        """DELETE a list of objects by ID using NetBox's bulk-delete list endpoint."""
        if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
            raise ValidationError("bulk-delete requires a list of integer IDs")
        endpoint = self._resolve_endpoint(resource)
        payload = [{"id": i} for i in ids]
        url = str(endpoint.url).rstrip("/") + "/"
        try:
            response = self.api.http_session.delete(url, json=payload)
            response.raise_for_status()
        except Exception as exc:
            resp = getattr(exc, "response", None)
            sc = getattr(resp, "status_code", None)
            msg = str(exc)
            if sc in {401, 403}:
                raise AuthError(msg) from exc
            if sc == 404:
                raise NotFoundError(msg) from exc
            raise APIError(msg, details={"status_code": sc}) from exc
        return {"deleted": True, "ids": ids}

    def resolve_id(
        self,
        resource: str,
        value: Any,
        *,
        lookup_fields: tuple[str, ...] = ("slug", "name"),
    ) -> int:
        if isinstance(value, int):
            return value
        endpoint = self._resolve_endpoint(resource)
        if isinstance(value, str):
            for field in lookup_fields:
                try:
                    record = endpoint.get(**self._strict_kwargs({field: value}))
                except Exception:
                    continue
                if record is not None:
                    return int(record.id)
            if value.isdigit():
                return int(value)
        else:
            for field in lookup_fields:
                try:
                    record = endpoint.get(**self._strict_kwargs({field: value}))
                except Exception:
                    continue
                if record is not None:
                    return int(record.id)
        raise NotFoundError(
            f"unable to resolve {value!r} in {resource}",
            details={"lookup_fields": list(lookup_fields)},
        )

    def assign_ip_address(
        self,
        *,
        record_id: int | None,
        lookup: dict[str, Any],
        device: str | None,
        interface: str | None,
        vm: str | None,
        vm_interface: str | None,
    ) -> Any:
        ip_record = self._get_record_object("ipam.ip_addresses", record_id=record_id, lookup=lookup)
        before = to_data(ip_record)

        if device and interface:
            device_id = self.resolve_id("dcim.devices", device, lookup_fields=("name",))
            target = self._lookup_single(
                "dcim.interfaces",
                {"device_id": device_id, "name": interface},
            )
            payload = {
                "assigned_object_type": "dcim.interface",
                "assigned_object_id": int(target.id),
            }
        elif vm and vm_interface:
            vm_id = self.resolve_id("virtualization.virtual_machines", vm, lookup_fields=("name",))
            target = self._lookup_single(
                "virtualization.interfaces",
                {"virtual_machine_id": vm_id, "name": vm_interface},
            )
            payload = {
                "assigned_object_type": "virtualization.vminterface",
                "assigned_object_id": int(target.id),
            }
        else:
            raise ValidationError(
                "assign-interface requires either --device and --interface or --vm and --vm-interface"
            )

        try:
            result = ip_record.update(payload)
        except Exception as exc:
            raise self._translate_exception(exc) from exc

        return {
            "updated": bool(result),
            "before": before,
            "after": to_data(ip_record),
        }

    def allocate_available_ips(
        self,
        *,
        record_id: int | None,
        lookup: dict[str, Any],
        count: int,
        payload: dict[str, Any] | None,
    ) -> Any:
        prefix = self._get_record_object("ipam.prefixes", record_id=record_id, lookup=lookup)
        data = payload or {}
        request_data: Any = [dict(data) for _ in range(count)] if count > 1 else data
        try:
            result = prefix.available_ips.create(request_data)
        except Exception as exc:
            raise self._translate_exception(exc) from exc
        return to_data(result)

    def allocate_available_prefixes(
        self,
        *,
        record_id: int | None,
        lookup: dict[str, Any],
        count: int,
        payload: dict[str, Any],
    ) -> Any:
        prefix = self._get_record_object("ipam.prefixes", record_id=record_id, lookup=lookup)
        request_data: Any = [dict(payload) for _ in range(count)] if count > 1 else payload
        try:
            result = prefix.available_prefixes.create(request_data)
        except Exception as exc:
            raise self._translate_exception(exc) from exc
        return to_data(result)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any],
        payload: Any,
    ) -> Any:
        if not path.startswith("/"):
            raise ValidationError("request path must start with /")
        if not self.config.url:
            raise ConfigError("NetBox URL is required")
        url = urljoin(f"{self.config.url}/", path.lstrip("/"))
        try:
            response = self.api.http_session.request(
                method=method.upper(),
                url=url,
                params=params or None,
                json=payload,
            )
        except Exception as exc:
            raise self._translate_exception(exc) from exc

        if response.status_code in {401, 403}:
            raise AuthError("request was not authorized", details={"status_code": response.status_code})
        if response.status_code == 404:
            raise NotFoundError(path)
        if response.status_code >= 400:
            details: Any
            try:
                details = response.json()
            except Exception:
                details = response.text
            raise APIError(
                f"NetBox returned HTTP {response.status_code}",
                details=details,
            )
        if response.content:
            content_type = response.headers.get("Content-Type", "")
            if "json" in content_type:
                return response.json()
            return response.text
        return {"status_code": response.status_code}

    def _resource_from_api_path(self, path: str) -> str:
        parts = [part for part in path.strip("/").split("/") if part]
        if len(parts) < 3 or parts[0] != "api":
            return path
        return ".".join(parts[1:])

    def _path_candidates_from_resource(self, resource: str) -> tuple[str, str]:
        parts = parse_resource(resource)
        path_parts = [part.replace("_", "-") for part in parts]
        if path_parts[0] == "plugins":
            list_path = f"/api/{'/'.join(path_parts)}/"
        else:
            list_path = f"/api/{'/'.join(path_parts)}/"
        detail_path = f"{list_path}{{id}}/"
        return list_path, detail_path

    def _normalize_path_item(self, document: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
        operations: dict[str, Any] = {}
        for method, operation in item.items():
            if method.lower() not in self.HTTP_METHODS:
                continue
            operation = self._resolve_ref(document, operation)
            parameters = [self._normalize_parameter(document, param) for param in operation.get("parameters", [])]
            operations[method.upper()] = {
                "summary": operation.get("summary"),
                "description": operation.get("description"),
                "operation_id": operation.get("operationId"),
                "parameters": parameters,
                "request_body": self._normalize_request_body(document, operation.get("requestBody")),
            }
        return operations

    def _normalize_parameter(self, document: dict[str, Any], parameter: dict[str, Any]) -> dict[str, Any]:
        parameter = self._resolve_ref(document, parameter)
        schema = self._resolve_ref(document, parameter.get("schema", {}))
        return {
            "name": parameter.get("name"),
            "in": parameter.get("in"),
            "required": parameter.get("required", False),
            "description": parameter.get("description"),
            "type": schema.get("type"),
            "enum": schema.get("enum"),
        }

    def _normalize_request_body(self, document: dict[str, Any], body: dict[str, Any] | None) -> dict[str, Any] | None:
        if not body:
            return None
        body = self._resolve_ref(document, body)
        content = body.get("content", {})
        app_json = self._resolve_ref(document, content.get("application/json", {}))
        schema = self._resolve_ref(document, app_json.get("schema", {}))
        if schema.get("type") == "array":
            schema = self._resolve_ref(document, schema.get("items", {}))
        properties = self._resolve_ref(document, schema.get("properties", {}))
        return {
            "required": body.get("required", False),
            "fields": sorted(properties.keys()) if isinstance(properties, dict) else [],
        }

    def _resolve_ref(self, document: dict[str, Any], value: Any) -> Any:
        if not isinstance(value, dict) or "$ref" not in value:
            return value
        ref = value["$ref"]
        if not ref.startswith("#/"):
            return value
        target: Any = document
        for part in ref[2:].split("/"):
            target = target.get(part)
            if target is None:
                return value
        return target


class _TimeoutHTTPAdapter:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        self._adapter = self._build_requests_adapter()

    def _build_requests_adapter(self) -> Any:
        requests = importlib.import_module("requests")
        base = requests.adapters.HTTPAdapter

        class Adapter(base):
            def __init__(self, timeout: float) -> None:
                self.timeout = timeout
                super().__init__()

            def send(self, request: Any, **kwargs: Any) -> Any:
                kwargs.setdefault("timeout", self.timeout)
                return super().send(request, **kwargs)

        return Adapter(self.timeout)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._adapter, name)
