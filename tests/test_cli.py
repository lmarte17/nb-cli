from __future__ import annotations

import io
import json

from nb_cli.cli import main


class FakeClient:
    def __init__(self, config):
        self.config = config

    def status(self):
        return {"netbox-version": "4.5.0"}

    def list_resources(self, search=None):
        return [{"resource": "dcim.devices", "path": "/api/dcim/devices/", "methods": ["GET"]}]

    def schema(self, resource):
        return {"resource": resource, "list_operations": {"GET": {"parameters": [{"name": "name"}]}}}

    def choices(self, resource):
        return {"status": [{"value": "active"}]}

    def count(self, resource, search, filters):
        return 7

    def query(self, resource, search, filters, limit, offset, brief, fields, exclude, ordering):
        return [{"resource": resource, "limit": limit, "filters": filters, "brief": brief}]

    def get(self, resource, record_id, lookup):
        return {"id": record_id or 99, "resource": resource, "lookup": lookup}

    def create(self, resource, payload):
        return {"id": 101, "resource": resource, "payload": payload}

    def preview_update(self, resource, record_id, lookup, payload):
        return {"resource": resource, "target": {"id": record_id or 99}, "changes": {"status": {"before": "planned", "after": payload.get("status")}}}

    def update(self, resource, record_id, lookup, payload):
        return {"updated": True, "resource": resource, "id": record_id, "lookup": lookup, "payload": payload}

    def delete(self, resource, record_id, lookup):
        return {"deleted": True, "resource": resource, "id": record_id, "lookup": lookup}

    def request(self, method, path, params, payload):
        return {"method": method, "path": path, "params": params, "payload": payload}

    def openapi(self):
        return {"openapi": "3.0.0"}

    def bulk_update(self, resource, payload):
        return {"updated": len(payload), "resource": resource, "ids": [item["id"] for item in payload]}

    def bulk_delete(self, resource, ids):
        return {"deleted": len(ids), "resource": resource, "ids": ids}

    def resolve_id(self, resource, value, lookup_fields=("slug", "name")):
        return {
            "dcim.device_types": 11,
            "dcim.device_roles": 22,
            "dcim.sites": 33,
            "tenancy.tenants": 44,
            "dcim.locations": 55,
            "circuits.providers": 66,
            "circuits.circuit_types": 77,
            "virtualization.cluster_types": 88,
            "virtualization.cluster_groups": 89,
            "dcim.devices": 90,
            "dcim.power_panels": 91,
            "ipam.rirs": 92,
            "tenancy.tenant_groups": 93,
            "tenancy.contact_groups": 94,
            "dcim.rear_ports": 95,
            "dcim.power_ports": 96,
            "virtualization.virtual_machines": 97,
            "ipam.ip_addresses": 98,
            "ipam.vrfs": 100,
        }.get(resource, 99)

    def allocate_available_ips(self, record_id, lookup, count, payload):
        return [{"address": f"10.0.0.{index}/24"} for index in range(1, count + 1)]

    def allocate_available_prefixes(self, record_id, lookup, count, payload):
        return [{"prefix": f"10.0.{index}.0/{payload['prefix_length']}"} for index in range(1, count + 1)]

    def assign_ip_address(self, record_id, lookup, device, interface, vm, vm_interface):
        return {"updated": True, "device": device, "interface": interface, "vm": vm, "vm_interface": vm_interface}


def run_cli(*argv, env_url=True):
    stdout = io.StringIO()
    stderr = io.StringIO()
    args = ["--url", "https://netbox.example.com", *argv] if env_url else list(argv)
    code = main(args, stdout=stdout, stderr=stderr, client_factory=FakeClient)
    return code, stdout.getvalue(), stderr.getvalue()


def test_status_command_outputs_success_envelope():
    code, stdout, stderr = run_cli("status")
    assert code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["ok"] is True
    assert payload["command"] == "status"
    assert payload["data"]["netbox-version"] == "4.5.0"


def test_query_uses_safe_default_limit():
    code, stdout, _ = run_cli("query", "dcim.devices", "--filter", "site=nyc")
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"][0]["limit"] == 50
    assert payload["data"][0]["filters"] == {"site": "nyc"}


def test_delete_requires_confirmation():
    code, stdout, stderr = run_cli("delete", "dcim.devices", "--id", "1")
    assert code == 5
    assert stdout == ""
    payload = json.loads(stderr)
    assert payload["ok"] is False
    assert payload["error"]["type"] == "validation_error"


def test_request_dry_run_does_not_require_yes():
    code, stdout, stderr = run_cli(
        "request",
        "post",
        "/api/dcim/devices/",
        "--data",
        '{"name":"edge01"}',
        "--dry-run",
    )
    assert code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["data"]["dry_run"] is True
    assert payload["data"]["method"] == "POST"


def test_help_topic_is_available_without_connection():
    code, stdout, stderr = run_cli("help", "device", env_url=False)
    assert code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["data"]["topic"] == "device"
    assert "device create" in payload["data"]["body"]


def test_typed_device_create_dry_run_builds_resolved_payload():
    code, stdout, stderr = run_cli(
        "device",
        "create",
        "--name",
        "edge01",
        "--device-type",
        "qfx5120",
        "--role",
        "leaf",
        "--site",
        "nyc1",
        "--dry-run",
    )
    assert code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["command"] == "device create"
    assert payload["data"]["payload"]["device_type"] == 11
    assert payload["data"]["payload"]["role"] == 22
    assert payload["data"]["payload"]["site"] == 33


def test_typed_location_create_supports_tenant_resolution():
    code, stdout, stderr = run_cli(
        "location",
        "create",
        "--name",
        "SuiteA",
        "--site",
        "nyc1",
        "--tenant",
        "acme",
        "--dry-run",
    )
    assert code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["command"] == "location create"
    assert payload["data"]["payload"]["site"] == 33
    assert payload["data"]["payload"]["tenant"] == 44


def test_table_output_renders_rows():
    code, stdout, stderr = run_cli("--format", "table", "query", "dcim.devices")
    assert code == 0
    assert stderr == ""
    assert "resource" in stdout
    assert "limit" in stdout


# ── Bulk operations ───────────────────────────────────────────────────────────

def test_bulk_update_dry_run_shows_payload():
    code, stdout, stderr = run_cli(
        "bulk-update",
        "dcim.devices",
        "--data",
        '[{"id":1,"status":"active"},{"id":2,"status":"active"}]',
        "--dry-run",
    )
    assert code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["ok"] is True
    assert payload["command"] == "bulk-update"
    assert payload["data"]["dry_run"] is True
    assert payload["data"]["resource"] == "dcim.devices"
    assert len(payload["data"]["payload"]) == 2


def test_bulk_update_requires_yes_or_dry_run():
    code, stdout, stderr = run_cli(
        "bulk-update",
        "dcim.devices",
        "--data",
        '[{"id":1,"status":"active"}]',
    )
    assert code != 0
    error = json.loads(stderr)
    assert error["ok"] is False


def test_bulk_update_rejects_non_array():
    code, stdout, stderr = run_cli(
        "bulk-update",
        "dcim.devices",
        "--data",
        '{"id":1,"status":"active"}',
        "--dry-run",
    )
    assert code != 0
    error = json.loads(stderr)
    assert error["ok"] is False


def test_bulk_delete_dry_run_with_id_flags():
    code, stdout, stderr = run_cli(
        "bulk-delete",
        "dcim.devices",
        "--id", "1", "2", "3",
        "--dry-run",
    )
    assert code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["data"]["dry_run"] is True
    assert payload["data"]["ids"] == [1, 2, 3]
    assert payload["data"]["resource"] == "dcim.devices"


def test_bulk_delete_dry_run_with_data():
    code, stdout, stderr = run_cli(
        "bulk-delete",
        "dcim.devices",
        "--data",
        '[{"id":10},{"id":20}]',
        "--dry-run",
    )
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["ids"] == [10, 20]


def test_bulk_delete_requires_yes_or_dry_run():
    code, stdout, stderr = run_cli(
        "bulk-delete",
        "dcim.devices",
        "--id", "1",
    )
    assert code != 0


def test_bulk_delete_requires_id_or_data():
    code, stdout, stderr = run_cli(
        "bulk-delete",
        "dcim.devices",
        "--dry-run",
    )
    assert code != 0


# ── New typed resources ───────────────────────────────────────────────────────

def test_circuit_create_dry_run_resolves_provider_and_type():
    code, stdout, stderr = run_cli(
        "circuit",
        "create",
        "--cid", "CID-001",
        "--provider", "zayo",
        "--type", "dark-fiber",
        "--dry-run",
    )
    assert code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["command"] == "circuit create"
    assert payload["data"]["payload"]["cid"] == "CID-001"
    assert payload["data"]["payload"]["provider"] == 66
    assert payload["data"]["payload"]["type"] == 77


def test_cluster_create_dry_run_resolves_type_and_site():
    code, stdout, stderr = run_cli(
        "cluster",
        "create",
        "--name", "prod-cluster",
        "--type", "vmware",
        "--site", "nyc1",
        "--dry-run",
    )
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["payload"]["name"] == "prod-cluster"
    assert payload["data"]["payload"]["type"] == 88
    assert payload["data"]["payload"]["site"] == 33


def test_cluster_group_create_dry_run():
    code, stdout, stderr = run_cli(
        "cluster-group",
        "create",
        "--name", "Production",
        "--dry-run",
    )
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["payload"]["name"] == "Production"


def test_contact_create_dry_run_resolves_group():
    code, stdout, stderr = run_cli(
        "contact",
        "create",
        "--name", "Jane Smith",
        "--email", "jane@example.com",
        "--group", "noc",
        "--dry-run",
    )
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["payload"]["name"] == "Jane Smith"
    assert payload["data"]["payload"]["email"] == "jane@example.com"
    assert payload["data"]["payload"]["group"] == 94


def test_tenant_group_create_dry_run():
    code, stdout, stderr = run_cli(
        "tenant-group",
        "create",
        "--name", "Enterprise",
        "--dry-run",
    )
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["payload"]["name"] == "Enterprise"


def test_rir_create_dry_run():
    code, stdout, stderr = run_cli(
        "rir",
        "create",
        "--name", "ARIN",
        "--slug", "arin",
        "--dry-run",
    )
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["payload"]["name"] == "ARIN"


def test_asn_create_dry_run_resolves_rir():
    code, stdout, stderr = run_cli(
        "asn",
        "create",
        "--asn", "65001",
        "--rir", "arin",
        "--dry-run",
    )
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["payload"]["asn"] == 65001
    assert payload["data"]["payload"]["rir"] == 92


def test_ip_range_create_dry_run():
    code, stdout, stderr = run_cli(
        "ip-range",
        "create",
        "--start-address", "10.0.0.1/24",
        "--end-address", "10.0.0.100/24",
        "--status", "active",
        "--dry-run",
    )
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["payload"]["start_address"] == "10.0.0.1/24"
    assert payload["data"]["payload"]["end_address"] == "10.0.0.100/24"


def test_fhrp_group_create_dry_run():
    code, stdout, stderr = run_cli(
        "fhrp-group",
        "create",
        "--protocol", "vrrp2",
        "--group-id", "10",
        "--dry-run",
    )
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["payload"]["protocol"] == "vrrp2"
    assert payload["data"]["payload"]["group_id"] == 10


def test_service_create_dry_run_with_ports_as_int():
    code, stdout, stderr = run_cli(
        "service",
        "create",
        "--name", "SSH",
        "--device", "edge01",
        "--ports", "22",
        "--protocol", "tcp",
        "--dry-run",
    )
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["payload"]["name"] == "SSH"
    assert payload["data"]["payload"]["parent_object_type"] == "dcim.device"
    assert payload["data"]["payload"]["parent_object_id"] == 90
    assert payload["data"]["payload"]["ports"] == [22]
    assert payload["data"]["payload"]["protocol"] == "tcp"


def test_console_port_create_dry_run():
    code, stdout, stderr = run_cli(
        "console-port",
        "create",
        "--device", "edge01",
        "--name", "console0",
        "--dry-run",
    )
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["payload"]["device"] == 90
    assert payload["data"]["payload"]["name"] == "console0"


def test_power_port_create_dry_run():
    code, stdout, stderr = run_cli(
        "power-port",
        "create",
        "--device", "edge01",
        "--name", "PSU0",
        "--maximum-draw", "300",
        "--dry-run",
    )
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["payload"]["maximum_draw"] == 300


def test_rear_port_create_dry_run():
    code, stdout, stderr = run_cli(
        "rear-port",
        "create",
        "--device", "patch-panel01",
        "--name", "RP1",
        "--type", "8p8c",
        "--dry-run",
    )
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["payload"]["name"] == "RP1"
    assert payload["data"]["payload"]["type"] == "8p8c"


def test_front_port_create_dry_run_resolves_rear_port():
    code, stdout, stderr = run_cli(
        "front-port",
        "create",
        "--device", "patch-panel01",
        "--name", "FP1",
        "--type", "8p8c",
        "--rear-port", "RP1",
        "--dry-run",
    )
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["payload"]["name"] == "FP1"
    assert payload["data"]["payload"]["rear_port"] == 95


def test_inventory_item_create_dry_run():
    code, stdout, stderr = run_cli(
        "inventory-item",
        "create",
        "--device", "edge01",
        "--name", "SFP+ Port 1",
        "--dry-run",
    )
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["payload"]["device"] == 90
    assert payload["data"]["payload"]["name"] == "SFP+ Port 1"


def test_power_panel_create_dry_run():
    code, stdout, stderr = run_cli(
        "power-panel",
        "create",
        "--name", "Panel A",
        "--site", "nyc1",
        "--dry-run",
    )
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["payload"]["name"] == "Panel A"
    assert payload["data"]["payload"]["site"] == 33


def test_custom_field_create_dry_run():
    code, stdout, stderr = run_cli(
        "custom-field",
        "create",
        "--name", "rack_room",
        "--type", "text",
        "--object-types", "dcim.device",
        "--dry-run",
    )
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["payload"]["name"] == "rack_room"
    assert payload["data"]["payload"]["type"] == "text"
    assert payload["data"]["payload"]["object_types"] == ["dcim.device"]


def test_webhook_create_dry_run():
    code, stdout, stderr = run_cli(
        "webhook",
        "create",
        "--name", "Slack Alert",
        "--payload-url", "https://hooks.slack.com/xxx",
        "--dry-run",
    )
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["payload"]["payload_url"] == "https://hooks.slack.com/xxx"


def test_event_rule_create_dry_run():
    code, stdout, stderr = run_cli(
        "event-rule",
        "create",
        "--name", "Device Change",
        "--action-type", "webhook",
        "--dry-run",
    )
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["payload"]["name"] == "Device Change"
    assert payload["data"]["payload"]["action_type"] == "webhook"


# ── New help topics ───────────────────────────────────────────────────────────

def test_help_topic_circuits():
    code, stdout, stderr = run_cli("help", "circuits", env_url=False)
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["topic"] == "circuits"
    assert "provider" in payload["data"]["body"]
    assert "circuit" in payload["data"]["body"]


def test_help_topic_tenancy():
    code, stdout, stderr = run_cli("help", "tenancy", env_url=False)
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["topic"] == "tenancy"
    assert "contact" in payload["data"]["body"]


def test_help_topic_virtualization():
    code, stdout, stderr = run_cli("help", "virtualization", env_url=False)
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["topic"] == "virtualization"
    assert "cluster" in payload["data"]["body"]


def test_help_topic_ipam_extras():
    code, stdout, stderr = run_cli("help", "ipam-extras", env_url=False)
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["topic"] == "ipam-extras"
    assert "fhrp-group" in payload["data"]["body"]


def test_help_topic_dcim_components():
    code, stdout, stderr = run_cli("help", "dcim-components", env_url=False)
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["topic"] == "dcim-components"
    assert "rear-port" in payload["data"]["body"]
    assert "front-port" in payload["data"]["body"]


def test_help_topic_extras():
    code, stdout, stderr = run_cli("help", "extras", env_url=False)
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["topic"] == "extras"
    assert "custom-field" in payload["data"]["body"]
    assert "event-rule" in payload["data"]["body"]


def test_help_topic_bulk():
    code, stdout, stderr = run_cli("help", "bulk", env_url=False)
    assert code == 0
    payload = json.loads(stdout)
    assert payload["data"]["topic"] == "bulk"
    assert "bulk-update" in payload["data"]["body"]
    assert "bulk-delete" in payload["data"]["body"]


def test_help_lists_all_new_topics():
    code, stdout, stderr = run_cli("help", env_url=False)
    assert code == 0
    payload = json.loads(stdout)
    available = payload["data"]["available_topics"]
    for expected in ["circuits", "tenancy", "virtualization", "ipam-extras", "dcim-components", "extras", "bulk"]:
        assert expected in available
