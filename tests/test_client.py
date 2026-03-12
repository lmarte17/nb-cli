from __future__ import annotations

import types

import pytest

from nb_cli.client import NetBoxClient
from nb_cli.config import AppConfig
from nb_cli.exceptions import ValidationError


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text="", headers=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = headers or {"Content-Type": "application/json"}
        self.content = b"x" if payload is not None or text else b""

    def json(self):
        if self._payload is None:
            raise ValueError("no payload")
        return self._payload


class FakeSession:
    def __init__(self):
        self.verify = True
        self.headers = {}
        self.requests = []

    def mount(self, *_args, **_kwargs):
        return None

    def request(self, **kwargs):
        self.requests.append(kwargs)
        return FakeResponse(payload={"ok": True})


class FakeDetailEndpoint:
    def __init__(self, field_name, prefix):
        self.field_name = field_name
        self.prefix = prefix

    def create(self, data=None):
        data = data or {}
        if isinstance(data, list):
            return [{self.field_name: f"{self.prefix}{index}"} for index, _ in enumerate(data, start=1)]
        return {self.field_name: f"{self.prefix}1", **data}


class FakeRecord:
    def __init__(self, data):
        self.data = dict(data)
        self.id = self.data["id"]
        self.available_ips = FakeDetailEndpoint("address", "10.0.0.")
        self.available_prefixes = FakeDetailEndpoint("prefix", "10.0.")

    def serialize(self):
        return dict(self.data)

    def update(self, payload):
        self.data.update(payload)
        return True

    def delete(self):
        return True


class FakeEndpoint:
    def __init__(self):
        self.calls = []

    def filter(self, *args, **kwargs):
        self.calls.append(("filter", args, kwargs))
        return [{"id": 1}]

    def count(self, *args, **kwargs):
        self.calls.append(("count", args, kwargs))
        return 3

    def get(self, *args, **kwargs):
        self.calls.append(("get", args, kwargs))
        if args:
            return FakeRecord({"id": args[0]})
        return FakeRecord({"id": 9, **kwargs})

    def create(self, *args, **kwargs):
        self.calls.append(("create", args, kwargs))
        if args:
            return args[0]
        return kwargs

    def update(self, objects):
        self.calls.append(("update", (), {"objects": objects}))
        return [{"id": objects[0]["id"], "updated": True}]

    def delete(self, objects):
        self.calls.append(("delete", (), {"objects": objects}))
        return True

    def choices(self):
        return {"status": [{"value": "active"}]}


class FakeAPI:
    def __init__(self, session):
        self.http_session = session
        self.dcim = types.SimpleNamespace(devices=FakeEndpoint(), interfaces=FakeEndpoint())
        self.ipam = types.SimpleNamespace(prefixes=FakeEndpoint(), ip_addresses=FakeEndpoint(), vlans=FakeEndpoint())
        self.virtualization = types.SimpleNamespace(
            virtual_machines=FakeEndpoint(),
            interfaces=FakeEndpoint(),
        )

    def status(self):
        return {"netbox-version": "4.5.0"}

    def openapi(self):
        return {
            "paths": {
                "/api/dcim/devices/": {"get": {}, "post": {}, "parameters": []},
                "/api/dcim/devices/{id}/": {"get": {}, "patch": {}},
                "/api/ipam/ip-addresses/": {"get": {"parameters": [{"name": "address", "in": "query"}]}},
                "/api/ipam/ip-addresses/{id}/": {"get": {}, "patch": {"requestBody": {"content": {"application/json": {"schema": {"type": "object", "properties": {"address": {"type": "string"}}}}}}}},
            }
        }


def test_client_query_passes_strict_filters(monkeypatch):
    session = FakeSession()
    fake_api = FakeAPI(session)

    def fake_import(name):
        if name == "pynetbox":
            return types.SimpleNamespace(api=lambda *args, **kwargs: fake_api)
        if name == "requests":
            return types.SimpleNamespace(
                Session=lambda: session,
                adapters=types.SimpleNamespace(HTTPAdapter=object),
            )
        raise AssertionError(name)

    monkeypatch.setattr("nb_cli.client.importlib.import_module", fake_import)

    client = NetBoxClient(
        AppConfig(
            profile="default",
            url="https://netbox.example.com",
            token="abc123",
            verify_ssl=True,
            timeout=30.0,
            threading=True,
            strict_filters=True,
        )
    )

    data = client.query(
        "dcim.devices",
        search=None,
        filters={"site": "nyc"},
        limit=10,
        offset=0,
        brief=True,
        fields=["id", "name"],
        exclude=["config_context"],
        ordering="name",
    )

    assert data == [{"id": 1}]
    endpoint = client.api.dcim.devices
    _, _, kwargs = endpoint.calls[0]
    assert kwargs["strict_filters"] is True
    assert kwargs["limit"] == 10
    assert kwargs["brief"] == 1


def test_client_request_uses_configured_session(monkeypatch):
    session = FakeSession()
    fake_api = FakeAPI(session)

    def fake_import(name):
        if name == "pynetbox":
            return types.SimpleNamespace(api=lambda *args, **kwargs: fake_api)
        if name == "requests":
            return types.SimpleNamespace(
                Session=lambda: session,
                adapters=types.SimpleNamespace(HTTPAdapter=object),
            )
        raise AssertionError(name)

    monkeypatch.setattr("nb_cli.client.importlib.import_module", fake_import)

    client = NetBoxClient(
        AppConfig(
            profile="default",
            url="https://netbox.example.com",
            token="nbt_token",
            verify_ssl=False,
            timeout=15.0,
            threading=True,
            strict_filters=True,
        )
    )

    result = client.request("get", "/api/dcim/devices/", params={"name": "edge01"}, payload=None)

    assert result == {"ok": True}
    assert session.verify is False
    assert session.headers["Authorization"] == "Bearer nbt_token"
    assert session.requests[0]["url"] == "https://netbox.example.com/api/dcim/devices/"


def test_client_rejects_unknown_resource(monkeypatch):
    session = FakeSession()
    fake_api = FakeAPI(session)

    def fake_import(name):
        if name == "pynetbox":
            return types.SimpleNamespace(api=lambda *args, **kwargs: fake_api)
        if name == "requests":
            return types.SimpleNamespace(
                Session=lambda: session,
                adapters=types.SimpleNamespace(HTTPAdapter=object),
            )
        raise AssertionError(name)

    monkeypatch.setattr("nb_cli.client.importlib.import_module", fake_import)

    client = NetBoxClient(
        AppConfig(
            profile="default",
            url="https://netbox.example.com",
            token="abc123",
            verify_ssl=True,
            timeout=30.0,
            threading=True,
            strict_filters=True,
        )
    )

    with pytest.raises(ValidationError):
        client.query(
            "dcim.unknown",
            search=None,
            filters={},
            limit=10,
            offset=0,
            brief=False,
            fields=[],
            exclude=[],
            ordering=None,
        )


def test_list_resources_filters_non_http_path_keys(monkeypatch):
    session = FakeSession()
    fake_api = FakeAPI(session)

    def fake_import(name):
        if name == "pynetbox":
            return types.SimpleNamespace(api=lambda *args, **kwargs: fake_api)
        if name == "requests":
            return types.SimpleNamespace(
                Session=lambda: session,
                adapters=types.SimpleNamespace(HTTPAdapter=object),
            )
        raise AssertionError(name)

    monkeypatch.setattr("nb_cli.client.importlib.import_module", fake_import)

    client = NetBoxClient(
        AppConfig(
            profile="default",
            url="https://netbox.example.com",
            token="abc123",
            verify_ssl=True,
            timeout=30.0,
            threading=True,
            strict_filters=True,
        )
    )

    resources = client.list_resources()

    assert resources == [
        {
            "resource": "dcim.devices",
            "path": "/api/dcim/devices/",
            "methods": ["GET", "POST"],
        },
        {
            "resource": "ipam.ip-addresses",
            "path": "/api/ipam/ip-addresses/",
            "methods": ["GET"],
        },
    ]


def test_schema_extracts_list_and_detail_operations(monkeypatch):
    session = FakeSession()
    fake_api = FakeAPI(session)

    def fake_import(name):
        if name == "pynetbox":
            return types.SimpleNamespace(api=lambda *args, **kwargs: fake_api)
        if name == "requests":
            return types.SimpleNamespace(
                Session=lambda: session,
                adapters=types.SimpleNamespace(HTTPAdapter=object),
            )
        raise AssertionError(name)

    monkeypatch.setattr("nb_cli.client.importlib.import_module", fake_import)

    client = NetBoxClient(
        AppConfig(
            profile="default",
            url="https://netbox.example.com",
            token="abc123",
            verify_ssl=True,
            timeout=30.0,
            threading=True,
            strict_filters=True,
        )
    )

    schema = client.schema("ipam.ip_addresses")

    assert schema["list_path"] == "/api/ipam/ip-addresses/"
    assert "GET" in schema["list_operations"]
    assert "PATCH" in schema["detail_operations"]


def test_allocate_available_ips_uses_detail_endpoint(monkeypatch):
    session = FakeSession()
    fake_api = FakeAPI(session)

    def fake_import(name):
        if name == "pynetbox":
            return types.SimpleNamespace(api=lambda *args, **kwargs: fake_api)
        if name == "requests":
            return types.SimpleNamespace(
                Session=lambda: session,
                adapters=types.SimpleNamespace(HTTPAdapter=object),
            )
        raise AssertionError(name)

    monkeypatch.setattr("nb_cli.client.importlib.import_module", fake_import)

    client = NetBoxClient(
        AppConfig(
            profile="default",
            url="https://netbox.example.com",
            token="abc123",
            verify_ssl=True,
            timeout=30.0,
            threading=True,
            strict_filters=True,
        )
    )

    result = client.allocate_available_ips(record_id=5, lookup={}, count=2, payload={"status": "active"})

    assert result == [{"address": "10.0.0.1"}, {"address": "10.0.0.2"}]


def test_resolve_id_prefers_lookup_fields_before_numeric_id(monkeypatch):
    session = FakeSession()
    fake_api = FakeAPI(session)

    def fake_import(name):
        if name == "pynetbox":
            return types.SimpleNamespace(api=lambda *args, **kwargs: fake_api)
        if name == "requests":
            return types.SimpleNamespace(
                Session=lambda: session,
                adapters=types.SimpleNamespace(HTTPAdapter=object),
            )
        raise AssertionError(name)

    monkeypatch.setattr("nb_cli.client.importlib.import_module", fake_import)

    client = NetBoxClient(
        AppConfig(
            profile="default",
            url="https://netbox.example.com",
            token="abc123",
            verify_ssl=True,
            timeout=30.0,
            threading=True,
            strict_filters=True,
        )
    )

    resolved = client.resolve_id("ipam.vlans", "2161", lookup_fields=("vid", "name"))

    assert resolved == 9


def test_assign_ip_address_uses_vm_interface_content_type(monkeypatch):
    session = FakeSession()
    fake_api = FakeAPI(session)

    def fake_import(name):
        if name == "pynetbox":
            return types.SimpleNamespace(api=lambda *args, **kwargs: fake_api)
        if name == "requests":
            return types.SimpleNamespace(
                Session=lambda: session,
                adapters=types.SimpleNamespace(HTTPAdapter=object),
            )
        raise AssertionError(name)

    monkeypatch.setattr("nb_cli.client.importlib.import_module", fake_import)

    client = NetBoxClient(
        AppConfig(
            profile="default",
            url="https://netbox.example.com",
            token="abc123",
            verify_ssl=True,
            timeout=30.0,
            threading=True,
            strict_filters=True,
        )
    )

    result = client.assign_ip_address(
        record_id=5,
        lookup={},
        device=None,
        interface=None,
        vm="app01",
        vm_interface="eth0",
    )

    assert result["updated"] is True
    assert result["after"]["assigned_object_type"] == "virtualization.vminterface"
