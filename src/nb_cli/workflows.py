from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .exceptions import ValidationError
from .parsing import load_json_data


@dataclass(frozen=True, slots=True)
class FieldSpec:
    dest: str
    flags: tuple[str, ...]
    payload_key: str
    help: str
    required_on_create: bool = False
    resolver: str | None = None
    lookup_fields: tuple[str, ...] = ("slug", "name")
    value_type: type | None = None
    multiple: bool = False
    boolean: bool = False
    metavar: str | None = None


@dataclass(frozen=True, slots=True)
class ResourceSpec:
    command_name: str
    resource: str
    label: str
    description: str
    examples: str
    fields: tuple[FieldSpec, ...]
    transform_payload: Callable[[dict[str, Any]], dict[str, Any]] | None = None


COMMON_TEXT = (
    "All typed resources support list/show/create/update/delete. "
    "Use --data for advanced fields not exposed as first-class flags."
)


def _f(
    dest: str,
    flag: str,
    payload_key: str,
    help: str,
    *,
    required_on_create: bool = False,
    resolver: str | None = None,
    lookup_fields: tuple[str, ...] = ("slug", "name"),
    value_type: type | None = None,
    multiple: bool = False,
    boolean: bool = False,
    metavar: str | None = None,
) -> FieldSpec:
    return FieldSpec(
        dest=dest,
        flags=(flag,),
        payload_key=payload_key,
        help=help,
        required_on_create=required_on_create,
        resolver=resolver,
        lookup_fields=lookup_fields,
        value_type=value_type,
        multiple=multiple,
        boolean=boolean,
        metavar=metavar,
    )


def _service_transform_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Translate --device/--virtual-machine to parent_object_type/parent_object_id (NetBox 4.5+)."""
    if "device" in payload:
        payload["parent_object_type"] = "dcim.device"
        payload["parent_object_id"] = payload.pop("device")
    elif "virtual_machine" in payload:
        payload["parent_object_type"] = "virtualization.virtualmachine"
        payload["parent_object_id"] = payload.pop("virtual_machine")
    return payload


RESOURCE_SPECS: dict[str, ResourceSpec] = {
    "manufacturer": ResourceSpec(
        command_name="manufacturer",
        resource="dcim.manufacturers",
        label="manufacturer",
        description="Manage DCIM manufacturers.",
        examples="Examples:\n  nb-cli manufacturer create --name Juniper --slug juniper --yes",
        fields=(
            _f("name", "--name", "name", "Manufacturer name.", required_on_create=True),
            _f("slug", "--slug", "slug", "Unique slug."),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "device-role": ResourceSpec(
        command_name="device-role",
        resource="dcim.device_roles",
        label="device role",
        description="Manage DCIM device roles.",
        examples="Examples:\n  nb-cli device-role create --name Leaf --slug leaf --color 00aa00 --yes",
        fields=(
            _f("name", "--name", "name", "Role name.", required_on_create=True),
            _f("slug", "--slug", "slug", "Unique slug."),
            _f("color", "--color", "color", "Hex color without #."),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "platform": ResourceSpec(
        command_name="platform",
        resource="dcim.platforms",
        label="platform",
        description="Manage device platforms.",
        examples="Examples:\n  nb-cli platform create --name Junos --slug junos --manufacturer juniper --yes",
        fields=(
            _f("name", "--name", "name", "Platform name.", required_on_create=True),
            _f("slug", "--slug", "slug", "Unique slug."),
            _f(
                "manufacturer",
                "--manufacturer",
                "manufacturer",
                "Manufacturer name, slug, or ID.",
                resolver="dcim.manufacturers",
            ),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "device-type": ResourceSpec(
        command_name="device-type",
        resource="dcim.device_types",
        label="device type",
        description="Manage device types.",
        examples="Examples:\n  nb-cli device-type create --model qfx5120-48y --slug qfx5120-48y --manufacturer juniper --yes",
        fields=(
            _f("model", "--model", "model", "Device type model.", required_on_create=True),
            _f("slug", "--slug", "slug", "Unique slug."),
            _f(
                "manufacturer",
                "--manufacturer",
                "manufacturer",
                "Manufacturer name, slug, or ID.",
                resolver="dcim.manufacturers",
            ),
            _f("part_number", "--part-number", "part_number", "Part number string."),
            _f("u_height", "--u-height", "u_height", "Rack units consumed.", value_type=float),
            _f("is_full_depth", "--full-depth", "is_full_depth", "Whether the device type is full depth.", boolean=True),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "site": ResourceSpec(
        command_name="site",
        resource="dcim.sites",
        label="site",
        description="Manage NetBox sites.",
        examples="Examples:\n  nb-cli site create --name NYC1 --slug nyc1 --status active --yes",
        fields=(
            _f("name", "--name", "name", "Site name.", required_on_create=True),
            _f("slug", "--slug", "slug", "Unique slug."),
            _f("status", "--status", "status", "Status choice."),
            _f("facility", "--facility", "facility", "Facility string."),
            _f(
                "tenant",
                "--tenant",
                "tenant",
                "Tenant name, slug, or ID.",
                resolver="tenancy.tenants",
            ),
            _f("description", "--description", "description", "Description text."),
            _f("comments", "--comments", "comments", "Long-form comments."),
        ),
    ),
    "location": ResourceSpec(
        command_name="location",
        resource="dcim.locations",
        label="location",
        description="Manage NetBox locations.",
        examples="Examples:\n  nb-cli location create --name SuiteA --site nyc1 --slug suitea --yes",
        fields=(
            _f("name", "--name", "name", "Location name.", required_on_create=True),
            _f("slug", "--slug", "slug", "Unique slug."),
            _f(
                "site",
                "--site",
                "site",
                "Site name, slug, or ID.",
                required_on_create=True,
                resolver="dcim.sites",
            ),
            _f("status", "--status", "status", "Status choice."),
            _f(
                "tenant",
                "--tenant",
                "tenant",
                "Tenant name, slug, or ID.",
                resolver="tenancy.tenants",
            ),
            _f("description", "--description", "description", "Description text."),
            _f("comments", "--comments", "comments", "Long-form comments."),
        ),
    ),
    "rack": ResourceSpec(
        command_name="rack",
        resource="dcim.racks",
        label="rack",
        description="Manage racks.",
        examples="Examples:\n  nb-cli rack create --name R101 --site nyc1 --u-height 42 --yes",
        fields=(
            _f("name", "--name", "name", "Rack name.", required_on_create=True),
            _f(
                "site",
                "--site",
                "site",
                "Site name, slug, or ID.",
                required_on_create=True,
                resolver="dcim.sites",
            ),
            _f(
                "location",
                "--location",
                "location",
                "Location name, slug, or ID.",
                resolver="dcim.locations",
            ),
            _f(
                "tenant",
                "--tenant",
                "tenant",
                "Tenant name, slug, or ID.",
                resolver="tenancy.tenants",
            ),
            _f("facility_id", "--facility-id", "facility_id", "Facility identifier."),
            _f("status", "--status", "status", "Status choice."),
            _f("serial", "--serial", "serial", "Rack serial number."),
            _f("asset_tag", "--asset-tag", "asset_tag", "Asset tag."),
            _f("width", "--width", "width", "Rack width.", value_type=int),
            _f("u_height", "--u-height", "u_height", "Rack height in U.", value_type=int),
            _f("description", "--description", "description", "Description text."),
            _f("comments", "--comments", "comments", "Long-form comments."),
        ),
    ),
    "tenant": ResourceSpec(
        command_name="tenant",
        resource="tenancy.tenants",
        label="tenant",
        description="Manage tenants.",
        examples="Examples:\n  nb-cli tenant create --name Acme --slug acme --yes",
        fields=(
            _f("name", "--name", "name", "Tenant name.", required_on_create=True),
            _f("slug", "--slug", "slug", "Unique slug."),
            _f(
                "group",
                "--group",
                "group",
                "Tenant group name, slug, or ID.",
                resolver="tenancy.tenant_groups",
            ),
            _f("description", "--description", "description", "Description text."),
            _f("comments", "--comments", "comments", "Long-form comments."),
        ),
    ),
    "tag": ResourceSpec(
        command_name="tag",
        resource="extras.tags",
        label="tag",
        description="Manage tags.",
        examples="Examples:\n  nb-cli tag create --name edge --slug edge --color 0099ff --yes",
        fields=(
            _f("name", "--name", "name", "Tag name.", required_on_create=True),
            _f("slug", "--slug", "slug", "Unique slug."),
            _f("color", "--color", "color", "Hex color without #."),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "vlan": ResourceSpec(
        command_name="vlan",
        resource="ipam.vlans",
        label="VLAN",
        description="Manage VLANs.",
        examples="Examples:\n  nb-cli vlan create --vid 100 --name prod-users --status active --yes",
        fields=(
            _f("vid", "--vid", "vid", "VLAN ID.", required_on_create=True, value_type=int),
            _f("name", "--name", "name", "VLAN name.", required_on_create=True),
            _f("status", "--status", "status", "Status choice."),
            _f(
                "site",
                "--site",
                "site",
                "Site name, slug, or ID.",
                resolver="dcim.sites",
            ),
            _f(
                "tenant",
                "--tenant",
                "tenant",
                "Tenant name, slug, or ID.",
                resolver="tenancy.tenants",
            ),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "vrf": ResourceSpec(
        command_name="vrf",
        resource="ipam.vrfs",
        label="VRF",
        description="Manage VRFs.",
        examples="Examples:\n  nb-cli vrf create --name prod --rd 65000:100 --yes",
        fields=(
            _f("name", "--name", "name", "VRF name.", required_on_create=True),
            _f("rd", "--rd", "rd", "Route distinguisher."),
            _f(
                "tenant",
                "--tenant",
                "tenant",
                "Tenant name, slug, or ID.",
                resolver="tenancy.tenants",
            ),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "device": ResourceSpec(
        command_name="device",
        resource="dcim.devices",
        label="device",
        description="Manage devices.",
        examples="Examples:\n  nb-cli device create --name edge01 --device-type qfx5120 --role leaf --site nyc1 --yes",
        fields=(
            _f("name", "--name", "name", "Device name.", required_on_create=True),
            _f(
                "device_type",
                "--device-type",
                "device_type",
                "Device type slug, model, or ID.",
                required_on_create=True,
                resolver="dcim.device_types",
                lookup_fields=("slug", "model", "name"),
            ),
            _f(
                "role",
                "--role",
                "role",
                "Device role slug, name, or ID.",
                required_on_create=True,
                resolver="dcim.device_roles",
            ),
            _f(
                "site",
                "--site",
                "site",
                "Site slug, name, or ID.",
                required_on_create=True,
                resolver="dcim.sites",
            ),
            _f("status", "--status", "status", "Status choice."),
            _f(
                "location",
                "--location",
                "location",
                "Location slug, name, or ID.",
                resolver="dcim.locations",
            ),
            _f("rack", "--rack", "rack", "Rack name or ID.", resolver="dcim.racks", lookup_fields=("name",)),
            _f("position", "--position", "position", "Rack position.", value_type=float),
            _f("face", "--face", "face", "Rack face choice."),
            _f(
                "platform",
                "--platform",
                "platform",
                "Platform slug, name, or ID.",
                resolver="dcim.platforms",
            ),
            _f("serial", "--serial", "serial", "Serial number."),
            _f("asset_tag", "--asset-tag", "asset_tag", "Asset tag."),
            _f(
                "tenant",
                "--tenant",
                "tenant",
                "Tenant slug, name, or ID.",
                resolver="tenancy.tenants",
            ),
            _f("comments", "--comments", "comments", "Long-form comments."),
        ),
    ),
    "virtual-machine": ResourceSpec(
        command_name="virtual-machine",
        resource="virtualization.virtual_machines",
        label="virtual machine",
        description="Manage virtual machines.",
        examples="Examples:\n  nb-cli virtual-machine create --name app01 --cluster prod-cluster --status active --yes",
        fields=(
            _f("name", "--name", "name", "Virtual machine name.", required_on_create=True),
            _f("status", "--status", "status", "Status choice."),
            _f(
                "cluster",
                "--cluster",
                "cluster",
                "Cluster name or ID.",
                resolver="virtualization.clusters",
                lookup_fields=("name",),
            ),
            _f(
                "site",
                "--site",
                "site",
                "Site name, slug, or ID.",
                resolver="dcim.sites",
            ),
            _f(
                "platform",
                "--platform",
                "platform",
                "Platform name, slug, or ID.",
                resolver="dcim.platforms",
            ),
            _f(
                "tenant",
                "--tenant",
                "tenant",
                "Tenant name, slug, or ID.",
                resolver="tenancy.tenants",
            ),
            _f("comments", "--comments", "comments", "Long-form comments."),
        ),
    ),
    "interface": ResourceSpec(
        command_name="interface",
        resource="dcim.interfaces",
        label="interface",
        description="Manage interfaces.",
        examples="Examples:\n  nb-cli interface create --device edge01 --name xe-0/0/0 --type 1000base-t --yes",
        fields=(
            _f(
                "device",
                "--device",
                "device",
                "Device name or ID.",
                required_on_create=True,
                resolver="dcim.devices",
                lookup_fields=("name",),
            ),
            _f("name", "--name", "name", "Interface name.", required_on_create=True),
            _f("type", "--type", "type", "Interface type choice.", required_on_create=True),
            _f("enabled", "--enabled", "enabled", "Whether the interface is enabled.", boolean=True),
            _f("mtu", "--mtu", "mtu", "MTU value.", value_type=int),
            _f("mode", "--mode", "mode", "Switchport mode."),
            _f(
                "untagged_vlan",
                "--untagged-vlan",
                "untagged_vlan",
                "Untagged VLAN ID or lookup value.",
                resolver="ipam.vlans",
                lookup_fields=("vid", "name"),
            ),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "vm-interface": ResourceSpec(
        command_name="vm-interface",
        resource="virtualization.interfaces",
        label="VM interface",
        description="Manage VM interfaces.",
        examples="Examples:\n  nb-cli vm-interface create --virtual-machine app01 --name eth0 --yes",
        fields=(
            _f(
                "virtual_machine",
                "--virtual-machine",
                "virtual_machine",
                "Virtual machine name or ID.",
                required_on_create=True,
                resolver="virtualization.virtual_machines",
                lookup_fields=("name",),
            ),
            _f("name", "--name", "name", "VM interface name.", required_on_create=True),
            _f("enabled", "--enabled", "enabled", "Whether the interface is enabled.", boolean=True),
            _f("mtu", "--mtu", "mtu", "MTU value.", value_type=int),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "cable": ResourceSpec(
        command_name="cable",
        resource="dcim.cables",
        label="cable",
        description="Manage cables. For complex terminations, prefer --data or the generic request command.",
        examples="Examples:\n  nb-cli cable create --status connected --data @cable.json --yes",
        fields=(
            _f("status", "--status", "status", "Status choice."),
            _f("type", "--type", "type", "Cable type choice."),
            _f("label", "--label", "label", "Cable label."),
            _f("color", "--color", "color", "Hex color without #."),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "prefix": ResourceSpec(
        command_name="prefix",
        resource="ipam.prefixes",
        label="prefix",
        description="Manage prefixes.",
        examples="Examples:\n  nb-cli prefix create --prefix 10.0.10.0/24 --status active --site nyc1 --yes",
        fields=(
            _f("prefix", "--prefix", "prefix", "Prefix in CIDR notation.", required_on_create=True),
            _f("status", "--status", "status", "Status choice."),
            _f(
                "vrf",
                "--vrf",
                "vrf",
                "VRF name, RD, or ID.",
                resolver="ipam.vrfs",
                lookup_fields=("name", "rd"),
            ),
            _f(
                "tenant",
                "--tenant",
                "tenant",
                "Tenant slug, name, or ID.",
                resolver="tenancy.tenants",
            ),
            _f(
                "site",
                "--site",
                "site",
                "Site slug, name, or ID.",
                resolver="dcim.sites",
            ),
            _f(
                "vlan",
                "--vlan",
                "vlan",
                "VLAN VID, name, or ID.",
                resolver="ipam.vlans",
                lookup_fields=("vid", "name"),
            ),
            _f("is_pool", "--is-pool", "is_pool", "Treat the prefix as a pool.", boolean=True),
            _f(
                "mark_utilized",
                "--mark-utilized",
                "mark_utilized",
                "Mark prefix as fully utilized.",
                boolean=True,
            ),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "ip-address": ResourceSpec(
        command_name="ip-address",
        resource="ipam.ip_addresses",
        label="IP address",
        description="Manage IP addresses.",
        examples="Examples:\n  nb-cli ip-address create --address 10.0.10.10/24 --status active --yes",
        fields=(
            _f("address", "--address", "address", "IP address with mask.", required_on_create=True),
            _f("status", "--status", "status", "Status choice."),
            _f(
                "vrf",
                "--vrf",
                "vrf",
                "VRF name, RD, or ID.",
                resolver="ipam.vrfs",
                lookup_fields=("name", "rd"),
            ),
            _f(
                "tenant",
                "--tenant",
                "tenant",
                "Tenant slug, name, or ID.",
                resolver="tenancy.tenants",
            ),
            _f("dns_name", "--dns-name", "dns_name", "DNS name."),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    # ── Circuits ─────────────────────────────────────────────────────────────
    "provider": ResourceSpec(
        command_name="provider",
        resource="circuits.providers",
        label="circuit provider",
        description="Manage circuit providers.",
        examples=(
            "Examples:\n"
            "  nb-cli provider create --name Zayo --slug zayo --yes\n"
            "  nb-cli provider list --format table\n"
            "  nb-cli provider show --lookup slug=zayo"
        ),
        fields=(
            _f("name", "--name", "name", "Provider name (free text).", required_on_create=True),
            _f("slug", "--slug", "slug", "Unique slug. Auto-generated from name if omitted."),
            _f("description", "--description", "description", "Description text."),
            _f("asn", "--asn", "asn", "Legacy ASN integer.", value_type=int),
            _f("account", "--account", "account", "Account identifier string."),
            _f("portal_url", "--portal-url", "portal_url", "Provider portal URL."),
            _f("comments", "--comments", "comments", "Long-form comments."),
        ),
    ),
    "provider-account": ResourceSpec(
        command_name="provider-account",
        resource="circuits.provider_accounts",
        label="provider account",
        description="Manage circuit provider accounts.",
        examples=(
            "Examples:\n"
            "  nb-cli provider-account create --name 'Zayo Account A' --provider zayo --account ACC-001 --yes\n"
            "  nb-cli provider-account list --filter provider=zayo --format table"
        ),
        fields=(
            _f("name", "--name", "name", "Account name.", required_on_create=True),
            _f(
                "provider",
                "--provider",
                "provider",
                "Provider slug, name, or ID.",
                required_on_create=True,
                resolver="circuits.providers",
            ),
            _f("account", "--account", "account", "Account identifier string."),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "circuit-type": ResourceSpec(
        command_name="circuit-type",
        resource="circuits.circuit_types",
        label="circuit type",
        description="Manage circuit types (e.g. Dark Fiber, MPLS, Metro-E).",
        examples=(
            "Examples:\n"
            "  nb-cli circuit-type create --name 'Dark Fiber' --slug dark-fiber --yes\n"
            "  nb-cli circuit-type list --format table"
        ),
        fields=(
            _f("name", "--name", "name", "Circuit type name.", required_on_create=True),
            _f("slug", "--slug", "slug", "Unique slug. Auto-generated from name if omitted."),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "circuit": ResourceSpec(
        command_name="circuit",
        resource="circuits.circuits",
        label="circuit",
        description="Manage circuits.",
        examples=(
            "Examples:\n"
            "  nb-cli circuit create --cid CID-001 --provider zayo --type dark-fiber --status active --yes\n"
            "  nb-cli circuit list --filter provider=zayo --format table\n"
            "  nb-cli circuit update --lookup cid=CID-001 --status decommissioning --yes"
        ),
        fields=(
            _f("cid", "--cid", "cid", "Circuit ID string (free text, unique per provider).", required_on_create=True),
            _f(
                "provider",
                "--provider",
                "provider",
                "Provider slug, name, or ID.",
                required_on_create=True,
                resolver="circuits.providers",
            ),
            _f(
                "type",
                "--type",
                "type",
                "Circuit type slug, name, or ID.",
                required_on_create=True,
                resolver="circuits.circuit_types",
            ),
            _f(
                "status",
                "--status",
                "status",
                "Status: active, planned, provisioning, decommissioning, decommissioned, offline.",
            ),
            _f(
                "tenant",
                "--tenant",
                "tenant",
                "Tenant slug, name, or ID.",
                resolver="tenancy.tenants",
            ),
            _f("commit_rate", "--commit-rate", "commit_rate", "Committed rate in Kbps (integer).", value_type=int),
            _f("description", "--description", "description", "Description text."),
            _f("comments", "--comments", "comments", "Long-form comments."),
        ),
    ),
    # ── Tenancy extensions ────────────────────────────────────────────────────
    "tenant-group": ResourceSpec(
        command_name="tenant-group",
        resource="tenancy.tenant_groups",
        label="tenant group",
        description="Manage tenant groups. Supports hierarchy via --parent.",
        examples=(
            "Examples:\n"
            "  nb-cli tenant-group create --name 'Enterprise Customers' --slug enterprise-customers --yes\n"
            "  nb-cli tenant-group create --name 'Sub-group' --parent enterprise-customers --yes"
        ),
        fields=(
            _f("name", "--name", "name", "Tenant group name.", required_on_create=True),
            _f("slug", "--slug", "slug", "Unique slug. Auto-generated from name if omitted."),
            _f(
                "parent",
                "--parent",
                "parent",
                "Parent tenant group slug, name, or ID.",
                resolver="tenancy.tenant_groups",
            ),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "contact-group": ResourceSpec(
        command_name="contact-group",
        resource="tenancy.contact_groups",
        label="contact group",
        description="Manage contact groups. Supports hierarchy via --parent.",
        examples=(
            "Examples:\n"
            "  nb-cli contact-group create --name NOC --slug noc --yes\n"
            "  nb-cli contact-group create --name 'NOC Tier 1' --parent noc --yes"
        ),
        fields=(
            _f("name", "--name", "name", "Contact group name.", required_on_create=True),
            _f("slug", "--slug", "slug", "Unique slug. Auto-generated from name if omitted."),
            _f(
                "parent",
                "--parent",
                "parent",
                "Parent contact group slug, name, or ID.",
                resolver="tenancy.contact_groups",
            ),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "contact": ResourceSpec(
        command_name="contact",
        resource="tenancy.contacts",
        label="contact",
        description="Manage contacts (people or organizations).",
        examples=(
            "Examples:\n"
            "  nb-cli contact create --name 'Jane Smith' --email jane@example.com --group noc --yes\n"
            "  nb-cli contact list --filter group=noc --format table"
        ),
        fields=(
            _f("name", "--name", "name", "Contact full name.", required_on_create=True),
            _f("phone", "--phone", "phone", "Phone number string."),
            _f("email", "--email", "email", "Email address."),
            _f("address", "--address", "address", "Postal address (free text)."),
            _f("title", "--title", "title", "Job title."),
            _f("link", "--link", "link", "URL link (e.g. LinkedIn profile)."),
            _f(
                "group",
                "--group",
                "group",
                "Contact group slug, name, or ID.",
                resolver="tenancy.contact_groups",
            ),
            _f("description", "--description", "description", "Description text."),
            _f("comments", "--comments", "comments", "Long-form comments."),
        ),
    ),
    # ── Virtualization hierarchy ──────────────────────────────────────────────
    "cluster-type": ResourceSpec(
        command_name="cluster-type",
        resource="virtualization.cluster_types",
        label="cluster type",
        description="Manage virtualization cluster types (e.g. VMware, KVM, OpenStack).",
        examples=(
            "Examples:\n"
            "  nb-cli cluster-type create --name VMware --slug vmware --yes\n"
            "  nb-cli cluster-type list --format table"
        ),
        fields=(
            _f("name", "--name", "name", "Cluster type name.", required_on_create=True),
            _f("slug", "--slug", "slug", "Unique slug. Auto-generated from name if omitted."),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "cluster-group": ResourceSpec(
        command_name="cluster-group",
        resource="virtualization.cluster_groups",
        label="cluster group",
        description="Manage virtualization cluster groups.",
        examples=(
            "Examples:\n"
            "  nb-cli cluster-group create --name Production --slug production --yes\n"
            "  nb-cli cluster-group list --format table"
        ),
        fields=(
            _f("name", "--name", "name", "Cluster group name.", required_on_create=True),
            _f("slug", "--slug", "slug", "Unique slug. Auto-generated from name if omitted."),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "cluster": ResourceSpec(
        command_name="cluster",
        resource="virtualization.clusters",
        label="cluster",
        description="Manage virtualization clusters. Virtual machines are assigned to clusters.",
        examples=(
            "Examples:\n"
            "  nb-cli cluster create --name prod-cluster --type vmware --site nyc1 --status active --yes\n"
            "  nb-cli cluster list --filter site=nyc1 --format table"
        ),
        fields=(
            _f("name", "--name", "name", "Cluster name.", required_on_create=True),
            _f(
                "type",
                "--type",
                "type",
                "Cluster type slug, name, or ID.",
                required_on_create=True,
                resolver="virtualization.cluster_types",
            ),
            _f(
                "group",
                "--group",
                "group",
                "Cluster group slug, name, or ID.",
                resolver="virtualization.cluster_groups",
            ),
            _f(
                "site",
                "--site",
                "site",
                "Site slug, name, or ID.",
                resolver="dcim.sites",
            ),
            _f(
                "tenant",
                "--tenant",
                "tenant",
                "Tenant slug, name, or ID.",
                resolver="tenancy.tenants",
            ),
            _f(
                "status",
                "--status",
                "status",
                "Status: active, planned, staging, decommissioning, offline.",
            ),
            _f("description", "--description", "description", "Description text."),
            _f("comments", "--comments", "comments", "Long-form comments."),
        ),
    ),
    # ── IPAM extras ───────────────────────────────────────────────────────────
    "rir": ResourceSpec(
        command_name="rir",
        resource="ipam.rirs",
        label="RIR",
        description="Manage Regional Internet Registries (RIRs) such as ARIN, RIPE, APNIC.",
        examples=(
            "Examples:\n"
            "  nb-cli rir create --name ARIN --slug arin --yes\n"
            "  nb-cli rir create --name RFC1918 --slug rfc1918 --is-private --yes"
        ),
        fields=(
            _f("name", "--name", "name", "RIR name (e.g. ARIN, RIPE, APNIC, RFC1918).", required_on_create=True),
            _f("slug", "--slug", "slug", "Unique slug. Auto-generated from name if omitted."),
            _f(
                "is_private",
                "--is-private",
                "is_private",
                "Mark as private or internal address space (e.g. RFC1918).",
                boolean=True,
            ),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "asn": ResourceSpec(
        command_name="asn",
        resource="ipam.asns",
        label="ASN",
        description="Manage Autonomous System Numbers (ASNs).",
        examples=(
            "Examples:\n"
            "  nb-cli asn create --asn 65001 --rir arin --yes\n"
            "  nb-cli asn create --asn 64512 --rir rfc1918 --tenant acme --yes\n"
            "  nb-cli asn list --filter rir=arin --format table"
        ),
        fields=(
            _f("asn", "--asn", "asn", "ASN integer (1-4294967295 for 32-bit ASNs).", required_on_create=True, value_type=int),
            _f(
                "rir",
                "--rir",
                "rir",
                "RIR slug, name, or ID.",
                required_on_create=True,
                resolver="ipam.rirs",
            ),
            _f(
                "tenant",
                "--tenant",
                "tenant",
                "Tenant slug, name, or ID.",
                resolver="tenancy.tenants",
            ),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "ip-range": ResourceSpec(
        command_name="ip-range",
        resource="ipam.ip_ranges",
        label="IP range",
        description="Manage IP address ranges (a contiguous block between two addresses).",
        examples=(
            "Examples:\n"
            "  nb-cli ip-range create --start-address 10.0.0.1/24 --end-address 10.0.0.100/24 --status active --yes\n"
            "  nb-cli ip-range list --filter vrf=prod --format table"
        ),
        fields=(
            _f(
                "start_address",
                "--start-address",
                "start_address",
                "Start address with prefix length (e.g. 10.0.0.1/24).",
                required_on_create=True,
            ),
            _f(
                "end_address",
                "--end-address",
                "end_address",
                "End address with prefix length (e.g. 10.0.0.100/24).",
                required_on_create=True,
            ),
            _f(
                "status",
                "--status",
                "status",
                "Status: active, reserved, deprecated, available.",
            ),
            _f(
                "vrf",
                "--vrf",
                "vrf",
                "VRF name, RD, or ID.",
                resolver="ipam.vrfs",
                lookup_fields=("name", "rd"),
            ),
            _f(
                "tenant",
                "--tenant",
                "tenant",
                "Tenant slug, name, or ID.",
                resolver="tenancy.tenants",
            ),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "route-target": ResourceSpec(
        command_name="route-target",
        resource="ipam.route_targets",
        label="route target",
        description="Manage BGP route targets (used to control VRF import/export policy).",
        examples=(
            "Examples:\n"
            "  nb-cli route-target create --name 65000:100 --yes\n"
            "  nb-cli route-target list --format table"
        ),
        fields=(
            _f("name", "--name", "name", "Route target value string (e.g. 65000:100 or 10.0.0.1:100).", required_on_create=True),
            _f(
                "tenant",
                "--tenant",
                "tenant",
                "Tenant slug, name, or ID.",
                resolver="tenancy.tenants",
            ),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "fhrp-group": ResourceSpec(
        command_name="fhrp-group",
        resource="ipam.fhrp_groups",
        label="FHRP group",
        description=(
            "Manage First Hop Redundancy Protocol groups (VRRP, HSRP, GLBP, CARP, etc.). "
            "A name is optional; protocol and group-id together identify the group."
        ),
        examples=(
            "Examples:\n"
            "  nb-cli fhrp-group create --protocol vrrp2 --group-id 10 --yes\n"
            "  nb-cli fhrp-group create --protocol hsrp --group-id 1 --name 'Gateway HSRP 1' --auth-type md5 --auth-key secret --yes\n"
            "  nb-cli fhrp-group list --format table"
        ),
        fields=(
            _f("name", "--name", "name", "Optional name for reference."),
            _f(
                "protocol",
                "--protocol",
                "protocol",
                "Protocol: vrrp2, vrrp3, carp, clusterxl, hsrp, glbp, other.",
                required_on_create=True,
            ),
            _f("group_id", "--group-id", "group_id", "Protocol group ID integer (0-65535).", required_on_create=True, value_type=int),
            _f("auth_type", "--auth-type", "auth_type", "Authentication type: plaintext, md5."),
            _f("auth_key", "--auth-key", "auth_key", "Authentication key string."),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "service": ResourceSpec(
        command_name="service",
        resource="ipam.services",
        label="service",
        description=(
            "Manage IP services attached to a device or virtual machine. "
            "Exactly one of --device or --virtual-machine is required on create."
        ),
        examples=(
            "Examples:\n"
            "  nb-cli service create --name SSH --device edge01 --ports 22 --protocol tcp --yes\n"
            "  nb-cli service create --name HTTPS --virtual-machine app01 --ports 443 --protocol tcp --yes\n"
            "  nb-cli service list --filter device=edge01 --format table"
        ),
        fields=(
            _f("name", "--name", "name", "Service name (e.g. SSH, HTTP, BGP).", required_on_create=True),
            _f(
                "device",
                "--device",
                "device",
                "Device name or ID. Required if not using --virtual-machine.",
                resolver="dcim.devices",
                lookup_fields=("name",),
            ),
            _f(
                "virtual_machine",
                "--virtual-machine",
                "virtual_machine",
                "Virtual machine name or ID. Required if not using --device.",
                resolver="virtualization.virtual_machines",
                lookup_fields=("name",),
            ),
            _f(
                "ports",
                "--ports",
                "ports",
                "TCP/UDP port number (integer). Repeatable: --ports 22 --ports 443.",
                multiple=True,
                value_type=int,
            ),
            _f(
                "protocol",
                "--protocol",
                "protocol",
                "Transport protocol: tcp, udp, sctp.",
                required_on_create=True,
            ),
            _f(
                "ipaddresses",
                "--ipaddresses",
                "ipaddresses",
                "IP address in CIDR notation to associate. Repeatable. Resolved against ipam.ip_addresses.",
                multiple=True,
                resolver="ipam.ip_addresses",
                lookup_fields=("address",),
            ),
            _f("description", "--description", "description", "Description text."),
        ),
        transform_payload=_service_transform_payload,
    ),
    # ── DCIM components ───────────────────────────────────────────────────────
    "console-port": ResourceSpec(
        command_name="console-port",
        resource="dcim.console_ports",
        label="console port",
        description="Manage console ports (serial console inputs) attached to a device.",
        examples=(
            "Examples:\n"
            "  nb-cli console-port create --device edge01 --name console0 --type rj-45 --yes\n"
            "  nb-cli console-port list --filter device=edge01 --format table"
        ),
        fields=(
            _f(
                "device",
                "--device",
                "device",
                "Device name or ID.",
                required_on_create=True,
                resolver="dcim.devices",
                lookup_fields=("name",),
            ),
            _f("name", "--name", "name", "Port name.", required_on_create=True),
            _f(
                "type",
                "--type",
                "type",
                "Port type (e.g. rj-45, de-9, usb-a, usb-b, usb-c). Use: nb-cli choices dcim.console_ports",
            ),
            _f(
                "speed",
                "--speed",
                "speed",
                "Port speed in bps (integer). Common: 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200.",
                value_type=int,
            ),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "console-server-port": ResourceSpec(
        command_name="console-server-port",
        resource="dcim.console_server_ports",
        label="console server port",
        description="Manage console server ports (serial console outputs) attached to a device.",
        examples=(
            "Examples:\n"
            "  nb-cli console-server-port create --device console-server01 --name port1 --type rj-45 --yes\n"
            "  nb-cli console-server-port list --filter device=console-server01 --format table"
        ),
        fields=(
            _f(
                "device",
                "--device",
                "device",
                "Device name or ID.",
                required_on_create=True,
                resolver="dcim.devices",
                lookup_fields=("name",),
            ),
            _f("name", "--name", "name", "Port name.", required_on_create=True),
            _f(
                "type",
                "--type",
                "type",
                "Port type (e.g. rj-45, rj-11, usb-a, usb-b, usb-c). Use: nb-cli choices dcim.console_server_ports",
            ),
            _f(
                "speed",
                "--speed",
                "speed",
                "Port speed in bps (integer).",
                value_type=int,
            ),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "power-port": ResourceSpec(
        command_name="power-port",
        resource="dcim.power_ports",
        label="power port",
        description="Manage power ports (power inputs) attached to a device.",
        examples=(
            "Examples:\n"
            "  nb-cli power-port create --device edge01 --name PSU0 --type iec-60320-c14 --yes\n"
            "  nb-cli power-port list --filter device=edge01 --format table"
        ),
        fields=(
            _f(
                "device",
                "--device",
                "device",
                "Device name or ID.",
                required_on_create=True,
                resolver="dcim.devices",
                lookup_fields=("name",),
            ),
            _f("name", "--name", "name", "Port name.", required_on_create=True),
            _f(
                "type",
                "--type",
                "type",
                "Power port type (e.g. iec-60320-c14, nema-5-15p, nema-l5-20p). Use: nb-cli choices dcim.power_ports",
            ),
            _f("maximum_draw", "--maximum-draw", "maximum_draw", "Maximum draw in watts (integer).", value_type=int),
            _f("allocated_draw", "--allocated-draw", "allocated_draw", "Allocated draw in watts (integer).", value_type=int),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "power-outlet": ResourceSpec(
        command_name="power-outlet",
        resource="dcim.power_outlets",
        label="power outlet",
        description="Manage power outlets (power outputs) attached to a device such as a PDU.",
        examples=(
            "Examples:\n"
            "  nb-cli power-outlet create --device pdu01 --name outlet1 --type iec-60320-c13 --yes\n"
            "  nb-cli power-outlet create --device pdu01 --name outlet2 --type iec-60320-c13 --power-port PSU0 --yes"
        ),
        fields=(
            _f(
                "device",
                "--device",
                "device",
                "Device name or ID.",
                required_on_create=True,
                resolver="dcim.devices",
                lookup_fields=("name",),
            ),
            _f("name", "--name", "name", "Outlet name.", required_on_create=True),
            _f(
                "type",
                "--type",
                "type",
                "Power outlet type (e.g. iec-60320-c13, nema-5-15r). Use: nb-cli choices dcim.power_outlets",
            ),
            _f(
                "power_port",
                "--power-port",
                "power_port",
                "Upstream power port name or ID on the same device (feeds this outlet). Use numeric ID if name is ambiguous.",
                resolver="dcim.power_ports",
                lookup_fields=("name", "id"),
            ),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "rear-port": ResourceSpec(
        command_name="rear-port",
        resource="dcim.rear_ports",
        label="rear port",
        description="Manage rear ports (back face) on patch panels and pass-through devices. Create rear-ports before front-ports.",
        examples=(
            "Examples:\n"
            "  nb-cli rear-port create --device patch-panel01 --name RP1 --type 8p8c --positions 1 --yes\n"
            "  nb-cli rear-port list --filter device=patch-panel01 --format table"
        ),
        fields=(
            _f(
                "device",
                "--device",
                "device",
                "Device name or ID.",
                required_on_create=True,
                resolver="dcim.devices",
                lookup_fields=("name",),
            ),
            _f("name", "--name", "name", "Rear port name.", required_on_create=True),
            _f(
                "type",
                "--type",
                "type",
                "Port type (e.g. 8p8c, 110-punch, bnc, fc, lc, sc, mpo). Use: nb-cli choices dcim.rear_ports",
                required_on_create=True,
            ),
            _f("positions", "--positions", "positions", "Number of positions on this rear port (integer, 1-1024).", value_type=int),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "front-port": ResourceSpec(
        command_name="front-port",
        resource="dcim.front_ports",
        label="front port",
        description=(
            "Manage front ports (face side) on patch panels. "
            "Each front-port must reference an existing rear-port on the same device. "
            "Create rear-ports first."
        ),
        examples=(
            "Examples:\n"
            "  nb-cli rear-port create --device patch-panel01 --name RP1 --type 8p8c --positions 1 --yes\n"
            "  nb-cli front-port create --device patch-panel01 --name FP1 --type 8p8c --rear-port RP1 --rear-port-position 1 --yes"
        ),
        fields=(
            _f(
                "device",
                "--device",
                "device",
                "Device name or ID.",
                required_on_create=True,
                resolver="dcim.devices",
                lookup_fields=("name",),
            ),
            _f("name", "--name", "name", "Front port name.", required_on_create=True),
            _f(
                "type",
                "--type",
                "type",
                "Port type. Must match rear port type (e.g. 8p8c, lc, sc). Use: nb-cli choices dcim.front_ports",
                required_on_create=True,
            ),
            _f(
                "rear_port",
                "--rear-port",
                "rear_port",
                "Rear port name or ID on the same device.",
                required_on_create=True,
                resolver="dcim.rear_ports",
                lookup_fields=("name", "id"),
            ),
            _f(
                "rear_port_position",
                "--rear-port-position",
                "rear_port_position",
                "Position on the rear port (integer, default 1).",
                value_type=int,
            ),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "module-bay": ResourceSpec(
        command_name="module-bay",
        resource="dcim.module_bays",
        label="module bay",
        description="Manage module bays on a device (slots for line cards, expansion modules, etc.).",
        examples=(
            "Examples:\n"
            "  nb-cli module-bay create --device spine01 --name 'Line Card 1' --yes\n"
            "  nb-cli module-bay list --filter device=spine01 --format table"
        ),
        fields=(
            _f(
                "device",
                "--device",
                "device",
                "Device name or ID.",
                required_on_create=True,
                resolver="dcim.devices",
                lookup_fields=("name",),
            ),
            _f("name", "--name", "name", "Module bay name.", required_on_create=True),
            _f("label", "--label", "label", "Physical label printed on the device chassis."),
            _f("position", "--position", "position", "Bay position identifier string."),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "inventory-item": ResourceSpec(
        command_name="inventory-item",
        resource="dcim.inventory_items",
        label="inventory item",
        description="Manage inventory items (transceivers, line cards, PSUs, fans) installed in a device.",
        examples=(
            "Examples:\n"
            "  nb-cli inventory-item create --device edge01 --name 'SFP+ Port 1' --manufacturer finisar --part-id FTLX8574D3BCL --yes\n"
            "  nb-cli inventory-item list --filter device=edge01 --format table"
        ),
        fields=(
            _f(
                "device",
                "--device",
                "device",
                "Device name or ID.",
                required_on_create=True,
                resolver="dcim.devices",
                lookup_fields=("name",),
            ),
            _f("name", "--name", "name", "Inventory item name.", required_on_create=True),
            _f(
                "manufacturer",
                "--manufacturer",
                "manufacturer",
                "Manufacturer slug, name, or ID.",
                resolver="dcim.manufacturers",
            ),
            _f("part_id", "--part-id", "part_id", "Manufacturer part ID string."),
            _f("serial", "--serial", "serial", "Serial number string."),
            _f("asset_tag", "--asset-tag", "asset_tag", "Asset tag string (must be globally unique if set)."),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "power-panel": ResourceSpec(
        command_name="power-panel",
        resource="dcim.power_panels",
        label="power panel",
        description="Manage power panels (electrical distribution panels) in a site.",
        examples=(
            "Examples:\n"
            "  nb-cli power-panel create --name 'Panel A' --site nyc1 --yes\n"
            "  nb-cli power-panel list --filter site=nyc1 --format table"
        ),
        fields=(
            _f("name", "--name", "name", "Power panel name.", required_on_create=True),
            _f(
                "site",
                "--site",
                "site",
                "Site slug, name, or ID.",
                required_on_create=True,
                resolver="dcim.sites",
            ),
            _f(
                "location",
                "--location",
                "location",
                "Location slug, name, or ID.",
                resolver="dcim.locations",
            ),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "power-feed": ResourceSpec(
        command_name="power-feed",
        resource="dcim.power_feeds",
        label="power feed",
        description="Manage power feeds connected to a power panel. Power feeds supply racks.",
        examples=(
            "Examples:\n"
            "  nb-cli power-feed create --name 'Feed A1' --power-panel 'Panel A' --voltage 120 --amperage 20 --yes\n"
            "  nb-cli power-feed list --filter power-panel='Panel A' --format table"
        ),
        fields=(
            _f("name", "--name", "name", "Power feed name.", required_on_create=True),
            _f(
                "power_panel",
                "--power-panel",
                "power_panel",
                "Power panel name or ID.",
                required_on_create=True,
                resolver="dcim.power_panels",
                lookup_fields=("name",),
            ),
            _f(
                "rack",
                "--rack",
                "rack",
                "Rack name or ID.",
                resolver="dcim.racks",
                lookup_fields=("name",),
            ),
            _f("type", "--type", "type", "Feed type: primary, redundant."),
            _f("status", "--status", "status", "Status: active, planned, failed, offline."),
            _f("voltage", "--voltage", "voltage", "Voltage in volts (integer).", value_type=int),
            _f("amperage", "--amperage", "amperage", "Amperage in amps (integer).", value_type=int),
            _f("phase", "--phase", "phase", "Phase: single-phase, three-phase."),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    # ── Extras ────────────────────────────────────────────────────────────────
    "custom-field": ResourceSpec(
        command_name="custom-field",
        resource="extras.custom_fields",
        label="custom field",
        description=(
            "Manage custom field definitions. "
            "Changes take effect globally for all targeted object types."
        ),
        examples=(
            "Examples:\n"
            "  nb-cli custom-field create --name rack_room --label 'Rack Room' --type text --object-types dcim.device --yes\n"
            "  nb-cli custom-field list --format table\n"
            "  nb-cli custom-field update --lookup name=rack_room --required --yes"
        ),
        fields=(
            _f("name", "--name", "name", "Custom field name (snake_case, no spaces, unique).", required_on_create=True),
            _f("label", "--label", "label", "Human-readable label shown in the NetBox UI."),
            _f(
                "object_types",
                "--object-types",
                "object_types",
                "Object type(s) to attach this field to. Format: app_label.model (e.g. dcim.device). Repeatable.",
                multiple=True,
            ),
            _f(
                "type",
                "--type",
                "type",
                (
                    "Field data type: text, longtext, integer, decimal, boolean, date, datetime, "
                    "url, json, select, multiselect, object, multiobject."
                ),
                required_on_create=True,
            ),
            _f("required", "--required", "required", "Mark field as required on all targeted objects.", boolean=True),
            _f(
                "default",
                "--default",
                "default",
                "Default value. Must be a JSON-encoded string matching the field type.",
            ),
            _f("weight", "--weight", "weight", "Display order weight (integer, lower = first).", value_type=int),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "webhook": ResourceSpec(
        command_name="webhook",
        resource="extras.webhooks",
        label="webhook",
        description=(
            "Manage webhook definitions for HTTP event delivery. "
            "Attach webhooks to event-rules to trigger them on object changes."
        ),
        examples=(
            "Examples:\n"
            "  nb-cli webhook create --name 'Slack Alert' --payload-url https://hooks.slack.com/xxx --http-method POST --enabled --yes\n"
            "  nb-cli webhook list --format table"
        ),
        fields=(
            _f("name", "--name", "name", "Webhook name.", required_on_create=True),
            _f("payload_url", "--payload-url", "payload_url", "Destination URL for the HTTP request.", required_on_create=True),
            _f(
                "http_method",
                "--http-method",
                "http_method",
                "HTTP method: GET, POST, PUT, PATCH, DELETE. Default: POST.",
            ),
            _f(
                "content_types",
                "--content-types",
                "content_types",
                "Content type(s) this webhook handles. Format: app_label.model. Repeatable.",
                multiple=True,
            ),
            _f("enabled", "--enabled", "enabled", "Whether the webhook is active.", boolean=True),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "event-rule": ResourceSpec(
        command_name="event-rule",
        resource="extras.event_rules",
        label="event rule",
        description=(
            "Manage event rules that trigger actions (webhooks or scripts) on object changes. "
            "Event rules replaced direct webhook triggers in NetBox 4.x."
        ),
        examples=(
            "Examples:\n"
            "  nb-cli event-rule create --name 'Device Change' --object-types dcim.device "
            "--event-types object_created --event-types object_updated --action-type webhook --enabled --yes\n"
            "  nb-cli event-rule list --format table"
        ),
        fields=(
            _f("name", "--name", "name", "Event rule name.", required_on_create=True),
            _f(
                "object_types",
                "--object-types",
                "object_types",
                "Object type(s) to watch. Format: app_label.model (e.g. dcim.device). Repeatable.",
                multiple=True,
            ),
            _f(
                "event_types",
                "--event-types",
                "event_types",
                (
                    "Events to watch. Repeatable. Values: object_created, object_updated, object_deleted, "
                    "job_started, job_completed, job_failed, job_errored."
                ),
                multiple=True,
            ),
            _f(
                "action_type",
                "--action-type",
                "action_type",
                "Action to execute when triggered: webhook, script.",
                required_on_create=True,
            ),
            _f("enabled", "--enabled", "enabled", "Whether the rule is active.", boolean=True),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
    "saved-filter": ResourceSpec(
        command_name="saved-filter",
        resource="extras.saved_filters",
        label="saved filter",
        description="Manage saved filters for reuse in the NetBox UI and API queries.",
        examples=(
            "Examples:\n"
            "  nb-cli saved-filter create --name 'Active Devices NYC' --slug active-devices-nyc --object-types dcim.device --yes\n"
            "  nb-cli saved-filter list --format table"
        ),
        fields=(
            _f("name", "--name", "name", "Saved filter name.", required_on_create=True),
            _f("slug", "--slug", "slug", "Unique slug. Auto-generated from name if omitted."),
            _f(
                "object_types",
                "--object-types",
                "object_types",
                "Object type(s) this filter applies to. Format: app_label.model. Repeatable.",
                multiple=True,
            ),
            _f(
                "params",
                "--params",
                "parameters",
                "Filter parameters as a JSON string (e.g. '{\"status\":[\"active\"]}').",
            ),
            _f("description", "--description", "description", "Description text."),
        ),
    ),
}


def add_field_arguments(parser: argparse.ArgumentParser, spec: ResourceSpec) -> None:
    for field in spec.fields:
        kwargs: dict[str, Any] = {
            "dest": field.dest,
            "help": field.help,
        }
        if field.metavar:
            kwargs["metavar"] = field.metavar
        if field.boolean:
            kwargs["action"] = argparse.BooleanOptionalAction
            kwargs["default"] = None
        elif field.multiple:
            kwargs["action"] = "append"
            kwargs["default"] = []
            if field.value_type is not None:
                kwargs["type"] = field.value_type
        elif field.value_type is not None:
            kwargs["type"] = field.value_type
        parser.add_argument(*field.flags, **kwargs)


def collect_payload(
    spec: ResourceSpec,
    args: argparse.Namespace,
    client: Any,
) -> dict[str, Any]:
    raw_payload = load_json_data(getattr(args, "data", None)) or {}
    if raw_payload is None:
        raw_payload = {}
    if not isinstance(raw_payload, dict):
        raise ValidationError("--data for typed commands must be a JSON object")

    payload = dict(raw_payload)
    for field in spec.fields:
        value = getattr(args, field.dest, None)
        if value is None or value == []:
            continue
        if field.resolver:
            value = _resolve_value(client, field, value)
        payload[field.payload_key] = value
    if spec.transform_payload is not None:
        payload = spec.transform_payload(payload)
    return payload


def validate_payload(spec: ResourceSpec, payload: dict[str, Any], *, for_create: bool) -> None:
    if for_create:
        missing = [field.payload_key for field in spec.fields if field.required_on_create and field.payload_key not in payload]
        if missing:
            raise ValidationError(
                f"{spec.command_name} create is missing required fields: {', '.join(missing)}"
            )
    if not payload:
        raise ValidationError("no changes were provided")


def _resolve_value(client: Any, field: FieldSpec, value: Any) -> Any:
    if field.multiple:
        return [client.resolve_id(field.resolver, item, lookup_fields=field.lookup_fields) for item in value]
    return client.resolve_id(field.resolver, value, lookup_fields=field.lookup_fields)
