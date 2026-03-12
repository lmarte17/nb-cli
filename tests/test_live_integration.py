from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass, field
from types import SimpleNamespace
from uuid import uuid4

import pytest

from nb_cli.cli import main
from nb_cli.client import NetBoxClient
from nb_cli.config import AppConfig

pytestmark = pytest.mark.live


def _live_url() -> str | None:
    return os.environ.get("NBCLI_URL") or os.environ.get("NETBOX_URL")


def _live_token() -> str | None:
    return os.environ.get("NBCLI_TOKEN") or os.environ.get("NETBOX_TOKEN")


def _run_cli(*argv: str) -> tuple[int, dict | str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = main(list(argv), stdout=stdout, stderr=stderr)
    out = stdout.getvalue()
    err = stderr.getvalue()
    if out:
        try:
            parsed = json.loads(out)
        except json.JSONDecodeError:
            parsed = out
    else:
        parsed = ""
    return code, parsed, err


def _run_ok(*argv: str) -> dict | str:
    code, payload, stderr = _run_cli(*argv)
    assert code == 0, stderr
    return payload


@dataclass
class ResourceTracker:
    client: NetBoxClient
    created: list[tuple[str, int]] = field(default_factory=list)

    def add(self, resource: str, object_id: int) -> None:
        self.created.append((resource, object_id))

    def cleanup(self) -> None:
        errors: list[str] = []
        for resource, object_id in reversed(self.created):
            try:
                self.client.delete(resource, record_id=object_id, lookup={})
            except Exception as exc:  # pragma: no cover - cleanup best effort
                errors.append(f"{resource}:{object_id}: {exc}")
        if errors:
            raise AssertionError("live cleanup failures:\n" + "\n".join(errors))


@pytest.fixture(scope="module")
def live_tracker() -> ResourceTracker:
    url = _live_url()
    token = _live_token()
    if not url or not token:
        pytest.skip("NBCLI_URL and NBCLI_TOKEN are required for live integration tests")

    config = AppConfig(
        profile="live",
        url=url.rstrip("/"),
        token=token,
        verify_ssl=True,
        timeout=30.0,
        threading=True,
        strict_filters=True,
    )
    tracker = ResourceTracker(NetBoxClient(config))
    yield tracker
    tracker.cleanup()


def test_live_status_and_discovery() -> None:
    if not _live_url() or not _live_token():
        pytest.skip("NBCLI_URL and NBCLI_TOKEN are required for live integration tests")

    code, payload, stderr = _run_cli("status")
    assert code == 0, stderr
    assert payload["data"]["netbox-version"] == "4.5.3"

    code, payload, stderr = _run_cli("resources", "--search", "device")
    assert code == 0, stderr
    assert any(item["resource"] == "dcim.devices" for item in payload["data"])

    code, payload, stderr = _run_cli("schema", "dcim.devices")
    assert code == 0, stderr
    assert "GET" in payload["data"]["list_operations"]

    code, payload, stderr = _run_cli("request", "get", "/api/status/")
    assert code == 0, stderr
    assert payload["data"]["netbox-version"] == "4.5.3"


def test_live_typed_and_generic_workflows(live_tracker: ResourceTracker) -> None:
    suffix = uuid4().hex[:8]

    site_name = f"NBCLI Live Site {suffix}"
    site_slug = f"nbcli-live-site-{suffix}"
    manufacturer_name = f"NBCLI Manufacturer {suffix}"
    manufacturer_slug = f"nbcli-mfg-{suffix}"
    role_name = f"NBCLI Role {suffix}"
    role_slug = f"nbcli-role-{suffix}"
    device_type_model = f"NBCLI-Model-{suffix}"
    device_type_slug = f"nbcli-dt-{suffix}"
    device_name = f"nbcli-dev-{suffix}"
    interface_name = "ge-0/0/0"
    prefix_cidr = f"10.252.{int(suffix[:2], 16)}.0/24"
    tag_slug = f"nbcli-tag-{suffix}"

    code, payload, stderr = _run_cli(
        "site",
        "create",
        "--name",
        site_name,
        "--slug",
        site_slug,
        "--status",
        "active",
        "--yes",
    )
    assert code == 0, stderr
    site = payload["data"]
    live_tracker.add("dcim.sites", site["id"])

    code, payload, stderr = _run_cli(
        "manufacturer",
        "create",
        "--name",
        manufacturer_name,
        "--slug",
        manufacturer_slug,
        "--yes",
    )
    assert code == 0, stderr
    manufacturer = payload["data"]
    live_tracker.add("dcim.manufacturers", manufacturer["id"])

    code, payload, stderr = _run_cli(
        "device-role",
        "create",
        "--name",
        role_name,
        "--slug",
        role_slug,
        "--color",
        "00aa00",
        "--yes",
    )
    assert code == 0, stderr
    role = payload["data"]
    live_tracker.add("dcim.device_roles", role["id"])

    code, payload, stderr = _run_cli(
        "device-type",
        "create",
        "--model",
        device_type_model,
        "--slug",
        device_type_slug,
        "--manufacturer",
        manufacturer_slug,
        "--yes",
    )
    assert code == 0, stderr
    device_type = payload["data"]
    live_tracker.add("dcim.device_types", device_type["id"])

    code, payload, stderr = _run_cli(
        "device",
        "create",
        "--name",
        device_name,
        "--device-type",
        device_type_slug,
        "--role",
        role_slug,
        "--site",
        site_slug,
        "--status",
        "active",
        "--yes",
    )
    assert code == 0, stderr
    device = payload["data"]
    live_tracker.add("dcim.devices", device["id"])

    code, payload, stderr = _run_cli(
        "interface",
        "create",
        "--device",
        device_name,
        "--name",
        interface_name,
        "--type",
        "1000base-t",
        "--enabled",
        "--yes",
    )
    assert code == 0, stderr
    interface = payload["data"]
    live_tracker.add("dcim.interfaces", interface["id"])

    code, payload, stderr = _run_cli(
        "prefix",
        "create",
        "--prefix",
        prefix_cidr,
        "--status",
        "active",
        "--site",
        site_slug,
        "--yes",
    )
    assert code == 0, stderr
    prefix = payload["data"]
    live_tracker.add("ipam.prefixes", prefix["id"])

    code, payload, stderr = _run_cli(
        "prefix",
        "allocate-ip",
        "--lookup",
        f"prefix={prefix_cidr}",
        "--count",
        "1",
        "--status",
        "active",
        "--yes",
    )
    assert code == 0, stderr
    allocated_ip = payload["data"][0] if isinstance(payload["data"], list) else payload["data"]
    live_tracker.add("ipam.ip_addresses", allocated_ip["id"])

    code, payload, stderr = _run_cli(
        "ip-address",
        "assign-interface",
        "--id",
        str(allocated_ip["id"]),
        "--device",
        device_name,
        "--interface",
        interface_name,
        "--yes",
    )
    assert code == 0, stderr
    assert payload["data"]["updated"] is True
    assert payload["data"]["after"]["assigned_object_type"] == "dcim.interface"

    code, payload, stderr = _run_cli(
        "device",
        "update",
        "--lookup",
        f"name={device_name}",
        "--serial",
        f"SERIAL-{suffix}",
        "--yes",
        "--diff",
    )
    assert code == 0, stderr
    assert payload["data"]["updated"] is True
    assert payload["data"]["after"]["serial"] == f"SERIAL-{suffix}"

    code, payload, stderr = _run_cli(
        "create",
        "extras.tags",
        "--data",
        json.dumps({"name": f"NBCLI Tag {suffix}", "slug": tag_slug}),
        "--yes",
    )
    assert code == 0, stderr
    tag = payload["data"]
    live_tracker.add("extras.tags", tag["id"])

    code, payload, stderr = _run_cli(
        "update",
        "extras.tags",
        "--id",
        str(tag["id"]),
        "--data",
        json.dumps({"description": f"updated-{suffix}"}),
        "--yes",
        "--diff",
    )
    assert code == 0, stderr
    assert payload["data"]["updated"] is True
    assert payload["data"]["after"]["description"] == f"updated-{suffix}"

    code, payload, stderr = _run_cli("query", "dcim.devices", "--filter", f"name={device_name}")
    assert code == 0, stderr
    assert any(item["name"] == device_name for item in payload["data"])


def test_live_location_rack_vlan_vrf_and_vm_flows(live_tracker: ResourceTracker) -> None:
    suffix = uuid4().hex[:8]

    site_name = f"NBCLI Infra Site {suffix}"
    site_slug = f"nbcli-infra-site-{suffix}"
    tenant_name = f"NBCLI Tenant {suffix}"
    tenant_slug = f"nbcli-tenant-{suffix}"
    location_name = f"NBCLI Location {suffix}"
    location_slug = f"nbcli-location-{suffix}"
    rack_name = f"NBCLI-RACK-{suffix}"
    vlan_name = f"NBCLI VLAN {suffix}"
    vlan_vid = 2000 + int(suffix[:2], 16) % 1000
    vrf_name = f"NBCLI VRF {suffix}"
    vrf_rd = f"65000:{int(suffix[:4], 16)}"
    vm_name = f"nbcli-vm-{suffix}"
    vm_interface_name = "eth0"
    prefix_cidr = f"10.253.{int(suffix[:2], 16)}.0/24"

    payload = _run_ok(
        "site",
        "create",
        "--name",
        site_name,
        "--slug",
        site_slug,
        "--status",
        "active",
        "--yes",
    )
    site = payload["data"]
    live_tracker.add("dcim.sites", site["id"])

    payload = _run_ok(
        "tenant",
        "create",
        "--name",
        tenant_name,
        "--slug",
        tenant_slug,
        "--yes",
    )
    tenant = payload["data"]
    live_tracker.add("tenancy.tenants", tenant["id"])

    payload = _run_ok(
        "location",
        "create",
        "--name",
        location_name,
        "--slug",
        location_slug,
        "--site",
        site_slug,
        "--status",
        "active",
        "--tenant",
        tenant_slug,
        "--yes",
    )
    location = payload["data"]
    live_tracker.add("dcim.locations", location["id"])

    payload = _run_ok(
        "rack",
        "create",
        "--name",
        rack_name,
        "--site",
        site_slug,
        "--location",
        location_slug,
        "--status",
        "active",
        "--u-height",
        "42",
        "--width",
        "19",
        "--yes",
    )
    rack = payload["data"]
    live_tracker.add("dcim.racks", rack["id"])

    payload = _run_ok(
        "vlan",
        "create",
        "--vid",
        str(vlan_vid),
        "--name",
        vlan_name,
        "--site",
        site_slug,
        "--tenant",
        tenant_slug,
        "--status",
        "active",
        "--yes",
    )
    vlan = payload["data"]
    live_tracker.add("ipam.vlans", vlan["id"])

    payload = _run_ok(
        "vrf",
        "create",
        "--name",
        vrf_name,
        "--rd",
        vrf_rd,
        "--tenant",
        tenant_slug,
        "--yes",
    )
    vrf = payload["data"]
    live_tracker.add("ipam.vrfs", vrf["id"])

    payload = _run_ok(
        "virtual-machine",
        "create",
        "--name",
        vm_name,
        "--site",
        site_slug,
        "--tenant",
        tenant_slug,
        "--status",
        "active",
        "--yes",
    )
    vm = payload["data"]
    live_tracker.add("virtualization.virtual_machines", vm["id"])

    payload = _run_ok(
        "vm-interface",
        "create",
        "--virtual-machine",
        vm_name,
        "--name",
        vm_interface_name,
        "--enabled",
        "--yes",
    )
    vm_interface = payload["data"]
    live_tracker.add("virtualization.interfaces", vm_interface["id"])

    payload = _run_ok(
        "prefix",
        "create",
        "--prefix",
        prefix_cidr,
        "--status",
        "active",
        "--site",
        site_slug,
        "--vrf",
        vrf_name,
        "--vlan",
        str(vlan_vid),
        "--tenant",
        tenant_slug,
        "--yes",
    )
    prefix = payload["data"]
    live_tracker.add("ipam.prefixes", prefix["id"])

    payload = _run_ok(
        "prefix",
        "allocate-ip",
        "--lookup",
        f"prefix={prefix_cidr}",
        "--count",
        "1",
        "--status",
        "active",
        "--yes",
    )
    allocated_ip = payload["data"][0] if isinstance(payload["data"], list) else payload["data"]
    live_tracker.add("ipam.ip_addresses", allocated_ip["id"])

    payload = _run_ok(
        "ip-address",
        "assign-interface",
        "--id",
        str(allocated_ip["id"]),
        "--vm",
        vm_name,
        "--vm-interface",
        vm_interface_name,
        "--yes",
    )
    assert payload["data"]["updated"] is True
    assert payload["data"]["after"]["assigned_object_type"] == "virtualization.vminterface"

    payload = _run_ok("get", "dcim.racks", "--id", str(rack["id"]))
    assert payload["data"]["name"] == rack_name

    payload = _run_ok("query", "ipam.vlans", "--filter", f"vid={vlan_vid}")
    assert any(item["id"] == vlan["id"] for item in payload["data"])

    payload = _run_ok(
        "update",
        "ipam.vrfs",
        "--id",
        str(vrf["id"]),
        "--data",
        json.dumps({"description": f"live-{suffix}"}),
        "--yes",
        "--diff",
    )
    assert payload["data"]["updated"] is True
    assert payload["data"]["after"]["description"] == f"live-{suffix}"


def test_live_cable_workflow(live_tracker: ResourceTracker) -> None:
    suffix = uuid4().hex[:8]

    site_name = f"NBCLI Cable Site {suffix}"
    site_slug = f"nbcli-cable-site-{suffix}"
    manufacturer_name = f"NBCLI Cable Manufacturer {suffix}"
    manufacturer_slug = f"nbcli-cable-mfg-{suffix}"
    role_name = f"NBCLI Cable Role {suffix}"
    role_slug = f"nbcli-cable-role-{suffix}"
    device_type_model = f"NBCLI-Cable-{suffix}"
    device_type_slug = f"nbcli-cable-dt-{suffix}"
    device_a_name = f"nbcli-cable-a-{suffix}"
    device_b_name = f"nbcli-cable-b-{suffix}"
    interface_name = "eth1"
    cable_label = f"NBCLI-CABLE-{suffix}"

    payload = _run_ok(
        "site",
        "create",
        "--name",
        site_name,
        "--slug",
        site_slug,
        "--status",
        "active",
        "--yes",
    )
    site = payload["data"]
    live_tracker.add("dcim.sites", site["id"])

    payload = _run_ok(
        "manufacturer",
        "create",
        "--name",
        manufacturer_name,
        "--slug",
        manufacturer_slug,
        "--yes",
    )
    manufacturer = payload["data"]
    live_tracker.add("dcim.manufacturers", manufacturer["id"])

    payload = _run_ok(
        "device-role",
        "create",
        "--name",
        role_name,
        "--slug",
        role_slug,
        "--color",
        "aa5500",
        "--yes",
    )
    role = payload["data"]
    live_tracker.add("dcim.device_roles", role["id"])

    payload = _run_ok(
        "device-type",
        "create",
        "--model",
        device_type_model,
        "--slug",
        device_type_slug,
        "--manufacturer",
        manufacturer_slug,
        "--yes",
    )
    device_type = payload["data"]
    live_tracker.add("dcim.device_types", device_type["id"])

    for device_name in (device_a_name, device_b_name):
        payload = _run_ok(
            "device",
            "create",
            "--name",
            device_name,
            "--device-type",
            device_type_slug,
            "--role",
            role_slug,
            "--site",
            site_slug,
            "--status",
            "active",
            "--yes",
        )
        device = payload["data"]
        live_tracker.add("dcim.devices", device["id"])

    payload = _run_ok(
        "interface",
        "create",
        "--device",
        device_a_name,
        "--name",
        interface_name,
        "--type",
        "1000base-t",
        "--enabled",
        "--yes",
    )
    interface_a = payload["data"]
    live_tracker.add("dcim.interfaces", interface_a["id"])

    payload = _run_ok(
        "interface",
        "create",
        "--device",
        device_b_name,
        "--name",
        interface_name,
        "--type",
        "1000base-t",
        "--enabled",
        "--yes",
    )
    interface_b = payload["data"]
    live_tracker.add("dcim.interfaces", interface_b["id"])

    cable_payload = {
        "a_terminations": [{"object_type": "dcim.interface", "object_id": interface_a["id"]}],
        "b_terminations": [{"object_type": "dcim.interface", "object_id": interface_b["id"]}],
    }
    payload = _run_ok(
        "cable",
        "create",
        "--status",
        "connected",
        "--type",
        "cat6",
        "--label",
        cable_label,
        "--data",
        json.dumps(cable_payload),
        "--yes",
    )
    cable = payload["data"]
    live_tracker.add("dcim.cables", cable["id"])

    payload = _run_ok("query", "dcim.cables", "--filter", f"label={cable_label}")
    assert any(item["id"] == cable["id"] for item in payload["data"])


def test_live_circuits_workflow(live_tracker: ResourceTracker) -> None:
    suffix = uuid4().hex[:8]

    provider_name = f"NBCLI Prov {suffix}"
    provider_slug = f"nbcli-prov-{suffix}"
    ct_name = f"NBCLI CT {suffix}"
    ct_slug = f"nbcli-ct-{suffix}"
    circuit_cid = f"NBCLI-CID-{suffix}"
    account_name = f"NBCLI Acct {suffix}"

    payload = _run_ok(
        "provider", "create",
        "--name", provider_name, "--slug", provider_slug, "--yes",
    )
    provider = payload["data"]
    live_tracker.add("circuits.providers", provider["id"])

    payload = _run_ok(
        "circuit-type", "create",
        "--name", ct_name, "--slug", ct_slug, "--yes",
    )
    circuit_type = payload["data"]
    live_tracker.add("circuits.circuit_types", circuit_type["id"])

    payload = _run_ok(
        "circuit", "create",
        "--cid", circuit_cid,
        "--provider", provider_slug,
        "--type", ct_slug,
        "--status", "active",
        "--yes",
    )
    circuit = payload["data"]
    live_tracker.add("circuits.circuits", circuit["id"])

    payload = _run_ok(
        "provider-account", "create",
        "--name", account_name,
        "--provider", provider_slug,
        "--account", f"ACC-{suffix}",
        "--yes",
    )
    acct = payload["data"]
    live_tracker.add("circuits.provider_accounts", acct["id"])

    # List and update
    payload = _run_ok("circuit", "list", "--filter", f"cid={circuit_cid}")
    assert any(item["cid"] == circuit_cid for item in payload["data"])

    payload = _run_ok(
        "circuit", "update",
        "--lookup", f"cid={circuit_cid}",
        "--description", f"live-{suffix}",
        "--yes", "--diff",
    )
    assert payload["data"]["updated"] is True

    payload = _run_ok("provider", "list")
    assert any(item["slug"] == provider_slug for item in payload["data"])


def test_live_tenancy_extensions(live_tracker: ResourceTracker) -> None:
    suffix = uuid4().hex[:8]

    tg_name = f"NBCLI TGrp {suffix}"
    tg_slug = f"nbcli-tg-{suffix}"
    cg_name = f"NBCLI CGrp {suffix}"
    cg_slug = f"nbcli-cg-{suffix}"
    contact_name = f"NBCLI Contact {suffix}"

    payload = _run_ok(
        "tenant-group", "create",
        "--name", tg_name, "--slug", tg_slug, "--yes",
    )
    tg = payload["data"]
    live_tracker.add("tenancy.tenant_groups", tg["id"])

    payload = _run_ok(
        "contact-group", "create",
        "--name", cg_name, "--slug", cg_slug, "--yes",
    )
    cg = payload["data"]
    live_tracker.add("tenancy.contact_groups", cg["id"])

    payload = _run_ok(
        "contact", "create",
        "--name", contact_name,
        "--email", f"live-{suffix}@example.com",
        "--phone", "555-0100",
        "--title", "Test Engineer",
        "--group", cg_slug,
        "--yes",
    )
    contact = payload["data"]
    live_tracker.add("tenancy.contacts", contact["id"])

    # Verify
    payload = _run_ok("contact", "show", "--id", str(contact["id"]))
    assert payload["data"]["name"] == contact_name

    payload = _run_ok("tenant-group", "list")
    assert any(item["slug"] == tg_slug for item in payload["data"])


def test_live_virtualization_hierarchy(live_tracker: ResourceTracker) -> None:
    suffix = uuid4().hex[:8]

    site_name = f"NBCLI VZ Site {suffix}"
    site_slug = f"nbcli-vz-{suffix}"
    cltype_name = f"NBCLI ClType {suffix}"
    cltype_slug = f"nbcli-cltype-{suffix}"
    clgroup_name = f"NBCLI ClGrp {suffix}"
    clgroup_slug = f"nbcli-clgrp-{suffix}"
    cluster_name = f"NBCLI Cluster {suffix}"

    payload = _run_ok(
        "site", "create",
        "--name", site_name, "--slug", site_slug, "--status", "active", "--yes",
    )
    site = payload["data"]
    live_tracker.add("dcim.sites", site["id"])

    payload = _run_ok(
        "cluster-type", "create",
        "--name", cltype_name, "--slug", cltype_slug, "--yes",
    )
    cluster_type = payload["data"]
    live_tracker.add("virtualization.cluster_types", cluster_type["id"])

    payload = _run_ok(
        "cluster-group", "create",
        "--name", clgroup_name, "--slug", clgroup_slug, "--yes",
    )
    cluster_group = payload["data"]
    live_tracker.add("virtualization.cluster_groups", cluster_group["id"])

    payload = _run_ok(
        "cluster", "create",
        "--name", cluster_name,
        "--type", cltype_slug,
        "--group", clgroup_slug,
        "--site", site_slug,
        "--status", "active",
        "--yes",
    )
    cluster = payload["data"]
    live_tracker.add("virtualization.clusters", cluster["id"])

    # Verify
    payload = _run_ok("cluster", "list", "--filter", f"name={cluster_name}")
    assert any(item["name"] == cluster_name for item in payload["data"])

    payload = _run_ok("cluster", "show", "--id", str(cluster["id"]))
    assert payload["data"]["name"] == cluster_name


def test_live_ipam_extras(live_tracker: ResourceTracker) -> None:
    suffix = uuid4().hex[:8]

    rir_name = f"NBCLI RIR {suffix}"
    rir_slug = f"nbcli-rir-{suffix}"
    asn_number = 64512 + int(suffix[:2], 16) % 500
    octet = int(suffix[:2], 16)
    start_addr = f"10.201.{octet}.1/24"
    end_addr = f"10.201.{octet}.50/24"
    rt_name = f"65001:{int(suffix[:4], 16)}"
    fhrp_gid = int(suffix[:2], 16) % 240 + 10  # 10-250

    payload = _run_ok(
        "rir", "create",
        "--name", rir_name, "--slug", rir_slug, "--yes",
    )
    rir = payload["data"]
    live_tracker.add("ipam.rirs", rir["id"])

    payload = _run_ok(
        "asn", "create",
        "--asn", str(asn_number), "--rir", rir_slug, "--yes",
    )
    asn = payload["data"]
    live_tracker.add("ipam.asns", asn["id"])

    payload = _run_ok(
        "ip-range", "create",
        "--start-address", start_addr,
        "--end-address", end_addr,
        "--status", "active",
        "--yes",
    )
    ip_range = payload["data"]
    live_tracker.add("ipam.ip_ranges", ip_range["id"])

    payload = _run_ok(
        "route-target", "create",
        "--name", rt_name, "--yes",
    )
    rt = payload["data"]
    live_tracker.add("ipam.route_targets", rt["id"])

    payload = _run_ok(
        "fhrp-group", "create",
        "--protocol", "vrrp2",
        "--group-id", str(fhrp_gid),
        "--yes",
    )
    fhrp = payload["data"]
    live_tracker.add("ipam.fhrp_groups", fhrp["id"])

    # Verify
    payload = _run_ok("rir", "show", "--id", str(rir["id"]))
    assert payload["data"]["name"] == rir_name

    payload = _run_ok("asn", "list", "--filter", f"rir={rir_slug}")
    assert any(item["asn"] == asn_number for item in payload["data"])

    payload = _run_ok("fhrp-group", "show", "--id", str(fhrp["id"]))
    assert payload["data"]["group_id"] == fhrp_gid


def test_live_dcim_components_and_service(live_tracker: ResourceTracker) -> None:
    suffix = uuid4().hex[:8]

    site_name = f"NBCLI Comp Site {suffix}"
    site_slug = f"nbcli-comp-{suffix}"
    mfg_name = f"NBCLI Comp Mfg {suffix}"
    mfg_slug = f"nbcli-comp-mfg-{suffix}"
    role_name = f"NBCLI Comp Role {suffix}"
    role_slug = f"nbcli-comp-role-{suffix}"
    dt_model = f"NBCLI-Comp-{suffix}"
    dt_slug = f"nbcli-comp-dt-{suffix}"
    device_name = f"nbcli-comp-dev-{suffix}"
    psu_name = f"PSU-{suffix}"
    rp_name = f"RP-{suffix}"
    fp_name = f"FP-{suffix}"
    panel_name = f"Panel-{suffix}"
    feed_name = f"Feed-{suffix}"

    # --- Prerequisites ---
    payload = _run_ok(
        "site", "create",
        "--name", site_name, "--slug", site_slug, "--status", "active", "--yes",
    )
    site = payload["data"]
    live_tracker.add("dcim.sites", site["id"])

    payload = _run_ok(
        "manufacturer", "create",
        "--name", mfg_name, "--slug", mfg_slug, "--yes",
    )
    mfg = payload["data"]
    live_tracker.add("dcim.manufacturers", mfg["id"])

    payload = _run_ok(
        "device-role", "create",
        "--name", role_name, "--slug", role_slug, "--color", "005588", "--yes",
    )
    role = payload["data"]
    live_tracker.add("dcim.device_roles", role["id"])

    payload = _run_ok(
        "device-type", "create",
        "--model", dt_model, "--slug", dt_slug, "--manufacturer", mfg_slug, "--yes",
    )
    dt = payload["data"]
    live_tracker.add("dcim.device_types", dt["id"])

    payload = _run_ok(
        "device", "create",
        "--name", device_name,
        "--device-type", dt_slug,
        "--role", role_slug,
        "--site", site_slug,
        "--status", "active",
        "--yes",
    )
    device = payload["data"]
    live_tracker.add("dcim.devices", device["id"])

    # --- DCIM Components ---
    payload = _run_ok(
        "console-port", "create",
        "--device", device_name, "--name", "con0", "--yes",
    )
    cp = payload["data"]
    live_tracker.add("dcim.console_ports", cp["id"])

    payload = _run_ok(
        "console-server-port", "create",
        "--device", device_name, "--name", "csp0", "--yes",
    )
    csp = payload["data"]
    live_tracker.add("dcim.console_server_ports", csp["id"])

    payload = _run_ok(
        "power-port", "create",
        "--device", device_name,
        "--name", psu_name,
        "--maximum-draw", "350",
        "--yes",
    )
    pp = payload["data"]
    live_tracker.add("dcim.power_ports", pp["id"])

    payload = _run_ok(
        "power-outlet", "create",
        "--device", device_name,
        "--name", f"outlet-{suffix}",
        "--power-port", psu_name,
        "--yes",
    )
    po = payload["data"]
    live_tracker.add("dcim.power_outlets", po["id"])

    payload = _run_ok(
        "rear-port", "create",
        "--device", device_name,
        "--name", rp_name,
        "--type", "8p8c",
        "--positions", "1",
        "--yes",
    )
    rp = payload["data"]
    live_tracker.add("dcim.rear_ports", rp["id"])

    payload = _run_ok(
        "front-port", "create",
        "--device", device_name,
        "--name", fp_name,
        "--type", "8p8c",
        "--rear-port", rp_name,
        "--rear-port-position", "1",
        "--yes",
    )
    fp = payload["data"]
    live_tracker.add("dcim.front_ports", fp["id"])

    payload = _run_ok(
        "module-bay", "create",
        "--device", device_name,
        "--name", f"MBay-{suffix}",
        "--yes",
    )
    mb = payload["data"]
    live_tracker.add("dcim.module_bays", mb["id"])

    payload = _run_ok(
        "inventory-item", "create",
        "--device", device_name,
        "--name", f"SFP-{suffix}",
        "--yes",
    )
    ii = payload["data"]
    live_tracker.add("dcim.inventory_items", ii["id"])

    # --- Power Infrastructure ---
    payload = _run_ok(
        "power-panel", "create",
        "--name", panel_name,
        "--site", site_slug,
        "--yes",
    )
    panel = payload["data"]
    live_tracker.add("dcim.power_panels", panel["id"])

    payload = _run_ok(
        "power-feed", "create",
        "--name", feed_name,
        "--power-panel", panel_name,
        "--type", "primary",
        "--voltage", "120",
        "--amperage", "20",
        "--phase", "single-phase",
        "--yes",
    )
    feed = payload["data"]
    live_tracker.add("dcim.power_feeds", feed["id"])

    # --- Service ---
    payload = _run_ok(
        "service", "create",
        "--name", "SSH",
        "--device", device_name,
        "--ports", "22",
        "--protocol", "tcp",
        "--description", f"live-service-{suffix}",
        "--yes",
    )
    service = payload["data"]
    live_tracker.add("ipam.services", service["id"])

    # Verify a few
    assert payload["data"]["name"] == "SSH"
    assert pp["maximum_draw"] == 350
    payload = _run_ok("console-port", "list", "--filter", f"device={device_name}")
    assert any(item["name"] == "con0" for item in payload["data"])


def test_live_extras(live_tracker: ResourceTracker) -> None:
    suffix = uuid4().hex[:8]

    cf_name = f"nbcli_cf_{suffix}"
    webhook_name = f"NBCLI Hook {suffix}"
    er_name = f"NBCLI ER {suffix}"
    sf_name = f"NBCLI SF {suffix}"
    sf_slug = f"nbcli-sf-{suffix}"

    payload = _run_ok(
        "custom-field", "create",
        "--name", cf_name,
        "--type", "text",
        "--object-types", "dcim.device",
        "--yes",
    )
    cf = payload["data"]
    live_tracker.add("extras.custom_fields", cf["id"])

    payload = _run_ok(
        "webhook", "create",
        "--name", webhook_name,
        "--payload-url", f"https://example.com/hook/{suffix}",
        "--yes",
    )
    webhook = payload["data"]
    live_tracker.add("extras.webhooks", webhook["id"])

    payload = _run_ok(
        "event-rule", "create",
        "--name", er_name,
        "--object-types", "dcim.device",
        "--event-types", "object_created",
        "--action-type", "webhook",
        "--enabled",
        "--data", json.dumps({"action_object_id": webhook["id"], "action_object_type": "extras.webhook"}),
        "--yes",
    )
    er = payload["data"]
    live_tracker.add("extras.event_rules", er["id"])

    payload = _run_ok(
        "saved-filter", "create",
        "--name", sf_name,
        "--slug", sf_slug,
        "--object-types", "dcim.device",
        "--data", '{"parameters": {"status": ["active"]}}',
        "--yes",
    )
    sf = payload["data"]
    live_tracker.add("extras.saved_filters", sf["id"])

    # Verify
    payload = _run_ok("custom-field", "show", "--id", str(cf["id"]))
    assert payload["data"]["name"] == cf_name

    payload = _run_ok("webhook", "list")
    assert any(item["name"] == webhook_name for item in payload["data"])

    payload = _run_ok("event-rule", "show", "--id", str(er["id"]))
    assert payload["data"]["name"] == er_name

    payload = _run_ok("saved-filter", "list")
    assert any(item["slug"] == sf_slug for item in payload["data"])


def test_live_bulk_operations() -> None:
    if not _live_url() or not _live_token():
        pytest.skip("NBCLI_URL and NBCLI_TOKEN are required for live integration tests")

    suffix = uuid4().hex[:8]

    # Create 3 tags to exercise bulk-update and bulk-delete
    tag_ids = []
    for i in range(3):
        tag_slug = f"nbcli-bulk-{suffix}-{i}"
        payload = _run_ok(
            "create", "extras.tags",
            "--data", json.dumps({"name": f"NBCLI Bulk {suffix} {i}", "slug": tag_slug}),
            "--yes",
        )
        tag_ids.append(payload["data"]["id"])

    bulk_payload = json.dumps([{"id": tid, "description": f"bulk-{suffix}"} for tid in tag_ids])
    code, payload, stderr = _run_cli("bulk-update", "extras.tags", "--data", bulk_payload, "--yes")
    assert code == 0, stderr

    # Verify one was updated
    payload = _run_ok("get", "extras.tags", "--id", str(tag_ids[0]))
    assert payload["data"]["description"] == f"bulk-{suffix}"

    # Bulk delete all 3 (no tracker entry needed — they'll be gone)
    delete_payload = json.dumps([{"id": tid} for tid in tag_ids])
    code, payload, stderr = _run_cli("bulk-delete", "extras.tags", "--data", delete_payload, "--yes")
    assert code == 0, stderr

    # Verify they're gone
    code, payload, stderr = _run_cli("get", "extras.tags", "--id", str(tag_ids[0]))
    assert code != 0
