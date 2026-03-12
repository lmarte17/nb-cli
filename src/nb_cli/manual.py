from __future__ import annotations

from typing import Any

from .exceptions import NotFoundError

OVERVIEW = """\
nb-cli is designed for three modes of use:

1. Direct operator use from a terminal
2. Automation and CI execution
3. LLM wrappers that need a deterministic NetBox execution layer

Core conventions:

- JSON output is the default and the safest choice for wrappers.
- Table output is for quick human inspection of list and object results.
- Mutating commands require --yes unless --dry-run is used.
- Generic commands cover the whole API surface.
- Typed commands cover common workflows with friendlier flags.

Configuration precedence:

1. CLI flags
2. Environment variables
3. .nb-cli.toml in the current directory
4. ~/.config/nb-cli/config.toml

Start here:

- nb-cli status
- nb-cli resources --search device
- nb-cli schema dcim.devices
- nb-cli help generic
- nb-cli help device
"""

GENERIC = """\
Generic commands are the lowest-friction way to cover the full NetBox REST API.

Recommended discovery flow:

1. Use `resources` to find a resource path.
2. Use `schema <resource>` to inspect methods and fields.
3. Use `query` or `get` to inspect live objects.
4. Use `create`, `update`, `delete`, or `request` for mutation.

Examples:

- nb-cli query dcim.devices --filter site=nyc --brief
- nb-cli get ipam.prefixes --lookup prefix=10.0.0.0/24
- nb-cli create extras.tags --data '{"name":"edge","slug":"edge"}' --yes
- nb-cli update dcim.devices --lookup name=edge01 --data '{"status":"active"}' --yes --diff
- nb-cli request get /api/dcim/devices/?name=edge01

When to prefer generic commands:

- the resource does not have a typed workflow yet
- you want full payload control
- you are debugging or exploring a plugin endpoint
"""

DEVICE = """\
The `device` command family is for common lifecycle work around DCIM devices.

Examples:

- nb-cli device list --filter site=nyc --filter status=active --format table
- nb-cli device show --lookup name=edge01
- nb-cli device create --name edge01 --device-type qfx5120 --role leaf --site nyc --status active --yes
- nb-cli device update --lookup name=edge01 --serial ABC123 --platform junos --yes --diff
- nb-cli device delete --lookup name=old-edge01 --yes

Important notes:

- device-type resolves against dcim.device_types using slug or model
- role resolves against dcim.device_roles using slug or name
- site, location, rack, platform, and tenant are resolved to IDs automatically
- use --data to add advanced fields not exposed as first-class flags
"""

INTERFACE = """\
The `interface` command family covers CRUD for interfaces and common attachment workflows.

Examples:

- nb-cli interface list --filter device=edge01 --format table
- nb-cli interface create --device edge01 --name xe-0/0/0 --type 1000base-t --yes
- nb-cli interface update --lookup device_id=12 --lookup name=xe-0/0/0 --description 'Uplink to spine01' --yes
- nb-cli ip-address assign-interface --lookup address=10.0.0.10/24 --device edge01 --interface xe-0/0/0 --yes

Important notes:

- interface lookups are usually easiest with --lookup device_id=<id> --lookup name=<name>
- --device on create resolves the device name to its NetBox object ID
- use the ip-address command family for assignment workflows
"""

PREFIX = """\
The `prefix` command family covers CRUD plus allocation helpers.

Examples:

- nb-cli prefix list --filter vrf=prod --format table
- nb-cli prefix create --prefix 10.0.10.0/24 --status active --site nyc --yes
- nb-cli prefix allocate-ip --lookup prefix=10.0.10.0/24 --count 2 --status active --yes
- nb-cli prefix allocate-prefix --lookup prefix=10.0.0.0/16 --prefix-length 24 --count 4 --yes

Important notes:

- allocate-ip uses the NetBox available-ips detail endpoint
- allocate-prefix uses the available-prefixes detail endpoint
- use --dry-run to preview allocation intent before executing
"""

IP_ADDRESS = """\
The `ip-address` command family covers CRUD plus interface assignment.

Examples:

- nb-cli ip-address list --filter status=active --format table
- nb-cli ip-address create --address 10.0.10.10/24 --status active --dns-name edge01.example.com --yes
- nb-cli ip-address assign-interface --lookup address=10.0.10.10/24 --device edge01 --interface xe-0/0/0 --yes
- nb-cli ip-address assign-interface --lookup address=192.0.2.10/32 --vm app01 --vm-interface eth0 --yes

Important notes:

- assignment updates assigned_object_type and assigned_object_id on the IP object
- use --device/--interface for DCIM interfaces
- use --vm/--vm-interface for virtualization interfaces
"""

CONFIGURATION = """\
Configuration sources are merged in this order:

1. CLI flags
2. Environment variables
3. Local .nb-cli.toml
4. User config in ~/.config/nb-cli/config.toml

Recommended secret handling:

- store URLs and non-secret defaults in config profiles
- store tokens in environment variables or token files
- prefer token_env in config instead of literal token values

Useful variables:

- NBCLI_PROFILE
- NBCLI_URL
- NBCLI_TOKEN
- NBCLI_TIMEOUT
- NBCLI_VERIFY_SSL
- NBCLI_THREADING
- NBCLI_STRICT_FILTERS
"""

OUTPUT = """\
Output modes:

- json: default structured envelope for wrappers and scripts
- jsonl: one JSON object per line when command data is a list
- table: simple human-readable table for dict/list data
- text: pretty-printed text

Conventions:

- success JSON includes ok=true, command, and data
- errors are written to stderr with ok=false, error type, and message
- table and text modes are for humans; json/jsonl are for automation
"""

CIRCUITS = """\
The `provider`, `provider-account`, `circuit-type`, and `circuit` commands manage the Circuits module.

Examples:

- nb-cli provider create --name Zayo --slug zayo --yes
- nb-cli provider list --format table
- nb-cli provider-account create --name 'Zayo Account A' --provider zayo --account ACC-001 --yes
- nb-cli circuit-type create --name 'Dark Fiber' --slug dark-fiber --yes
- nb-cli circuit create --cid CID-001 --provider zayo --type dark-fiber --status active --yes
- nb-cli circuit list --filter provider=zayo --format table
- nb-cli circuit update --lookup cid=CID-001 --status decommissioning --yes --diff
- nb-cli circuit show --lookup cid=CID-001

Important notes:

- --cid is the circuit ID string (free text, unique per provider)
- --provider resolves against circuits.providers using slug or name
- --type resolves against circuits.circuit_types using slug or name
- --status valid values: active, planned, provisioning, decommissioning, decommissioned, offline
- --commit-rate is in Kbps (integer)
- provider-account --provider resolves the same way as circuit --provider
- use nb-cli choices circuits.circuits to see all valid status and type enumerations
"""

TENANCY = """\
The `tenant`, `tenant-group`, `contact`, and `contact-group` commands manage the Tenancy module.

Examples:

- nb-cli tenant-group create --name 'Enterprise Customers' --slug enterprise-customers --yes
- nb-cli tenant-group create --name 'Sub-group' --parent enterprise-customers --yes
- nb-cli tenant create --name Acme --slug acme --group enterprise-customers --yes
- nb-cli contact-group create --name NOC --slug noc --yes
- nb-cli contact create --name 'Jane Smith' --email jane@example.com --phone 555-1234 --group noc --yes
- nb-cli contact list --filter group=noc --format table
- nb-cli tenant list --filter group=enterprise-customers --format table

Important notes:

- tenant-group supports --parent to form hierarchies; resolves against tenancy.tenant_groups using slug or name
- contact-group supports --parent to form hierarchies; resolves against tenancy.contact_groups using slug or name
- tenant --group resolves against tenancy.tenant_groups using slug or name
- contact --group resolves against tenancy.contact_groups using slug or name
- contact fields --phone, --email, --address, --title, and --link are all free text
- contact --link is a URL (e.g. LinkedIn profile, team wiki page)
"""

VIRTUALIZATION = """\
The `cluster-type`, `cluster-group`, `cluster`, `virtual-machine`, and `vm-interface` commands manage the Virtualization module.

Examples:

- nb-cli cluster-type create --name VMware --slug vmware --yes
- nb-cli cluster-group create --name Production --slug production --yes
- nb-cli cluster create --name prod-cluster --type vmware --group production --site nyc1 --status active --yes
- nb-cli virtual-machine create --name app01 --cluster prod-cluster --status active --yes
- nb-cli vm-interface create --virtual-machine app01 --name eth0 --yes
- nb-cli ip-address create --address 10.0.10.20/24 --status active --yes
- nb-cli ip-address assign-interface --lookup address=10.0.10.20/24 --vm app01 --vm-interface eth0 --yes
- nb-cli cluster list --filter site=nyc1 --format table
- nb-cli virtual-machine list --filter cluster=prod-cluster --format table

Important notes:

- cluster --type resolves against virtualization.cluster_types using slug or name
- cluster --group resolves against virtualization.cluster_groups using slug or name
- cluster --site resolves against dcim.sites using slug or name
- cluster --status valid values: active, planned, staging, decommissioning, offline
- virtual-machine --cluster resolves against virtualization.clusters using name
- create cluster-type and cluster-group before creating cluster
"""

IPAM_EXTRAS = """\
The `rir`, `asn`, `ip-range`, `route-target`, `fhrp-group`, and `service` commands manage extended IPAM objects.

Examples:

- nb-cli rir create --name ARIN --slug arin --yes
- nb-cli rir create --name RFC1918 --slug rfc1918 --is-private --yes
- nb-cli asn create --asn 65001 --rir arin --yes
- nb-cli asn create --asn 64512 --rir rfc1918 --tenant acme --yes
- nb-cli ip-range create --start-address 10.0.0.1/24 --end-address 10.0.0.100/24 --status active --yes
- nb-cli route-target create --name 65000:100 --yes
- nb-cli fhrp-group create --protocol vrrp2 --group-id 10 --yes
- nb-cli fhrp-group create --protocol hsrp --group-id 1 --auth-type md5 --auth-key secret --yes
- nb-cli service create --name SSH --device edge01 --ports 22 --protocol tcp --yes
- nb-cli service create --name HTTPS --virtual-machine app01 --ports 443 --protocol tcp --yes
- nb-cli service create --name BGP --device edge01 --ports 179 --protocol tcp --ipaddresses 10.0.0.1/24 --yes

Important notes:

- asn --asn is an integer (1-4294967295 for 32-bit ASNs); --rir resolves against ipam.rirs using slug or name
- ip-range start and end addresses must include prefix length (e.g. 10.0.0.1/24, not 10.0.0.1)
- ip-range --status valid values: active, reserved, deprecated, available
- ip-range --vrf resolves against ipam.vrfs using name or rd
- fhrp-group --protocol valid values: vrrp2, vrrp3, carp, clusterxl, hsrp, glbp, other
- fhrp-group --group-id is an integer (0-65535); name is optional
- fhrp-group --auth-type valid values: plaintext, md5
- service requires either --device or --virtual-machine (not both, not neither); NetBox enforces this
- service --ports is repeatable and takes integers (--ports 22 --ports 443)
- service --protocol valid values: tcp, udp, sctp
- service --ipaddresses is repeatable; resolves against ipam.ip_addresses using the address field
"""

DCIM_COMPONENTS = """\
Commands for device-attached DCIM components: console ports, power ports/outlets, front/rear ports, module bays, inventory items, power panels, and power feeds.

Examples:

- nb-cli console-port create --device edge01 --name console0 --type rj-45 --speed 9600 --yes
- nb-cli console-server-port create --device console-server01 --name port1 --type rj-45 --yes
- nb-cli power-port create --device edge01 --name PSU0 --type iec-60320-c14 --maximum-draw 300 --yes
- nb-cli power-outlet create --device pdu01 --name outlet1 --type iec-60320-c13 --yes
- nb-cli rear-port create --device patch-panel01 --name RP1 --type 8p8c --positions 1 --yes
- nb-cli front-port create --device patch-panel01 --name FP1 --type 8p8c --rear-port RP1 --rear-port-position 1 --yes
- nb-cli module-bay create --device spine01 --name 'Line Card 1' --yes
- nb-cli inventory-item create --device edge01 --name 'SFP+ Port 1' --manufacturer finisar --part-id FTLX8574D3BCL --yes
- nb-cli power-panel create --name 'Panel A' --site nyc1 --yes
- nb-cli power-feed create --name 'Feed A1' --power-panel 'Panel A' --voltage 120 --amperage 20 --yes
- nb-cli console-port list --filter device=edge01 --format table
- nb-cli inventory-item list --filter device=edge01 --format table

Important notes:

- all port/bay/item commands require --device (resolved against dcim.devices using name)
- front-port requires --rear-port (resolved against dcim.rear_ports using name or id); always create rear-port first
- front-port --type must match the rear-port type exactly
- power-outlet --power-port resolves against dcim.power_ports using name or id; use numeric ID when port names are ambiguous
- power-feed --power-panel resolves against dcim.power_panels using name
- power-feed --type valid values: primary, redundant
- power-feed --phase valid values: single-phase, three-phase
- power-feed --status valid values: active, planned, failed, offline
- use nb-cli choices dcim.console_ports (or dcim.power_ports, dcim.rear_ports, etc.) for all valid type choices
- inventory-item --manufacturer resolves against dcim.manufacturers using slug or name
- inventory-item --asset-tag must be globally unique if set
"""

EXTRAS = """\
The `custom-field`, `webhook`, `event-rule`, and `saved-filter` commands manage the Extras module.

Examples:

- nb-cli custom-field create --name rack_room --label 'Rack Room' --type text --object-types dcim.device --yes
- nb-cli custom-field create --name env_tier --type select --object-types dcim.device --object-types ipam.prefix --required --yes
- nb-cli webhook create --name 'Slack Alert' --payload-url https://hooks.slack.com/xxx --http-method POST --enabled --yes
- nb-cli event-rule create --name 'Device Change' --object-types dcim.device --event-types object_created --event-types object_updated --action-type webhook --enabled --yes
- nb-cli saved-filter create --name 'Active Devices' --slug active-devices --object-types dcim.device --yes
- nb-cli custom-field list --format table
- nb-cli event-rule list --format table

Important notes:

- custom-field --name must be snake_case with no spaces and globally unique
- custom-field --type valid values: text, longtext, integer, decimal, boolean, date, datetime, url, json, select, multiselect, object, multiobject
- custom-field --object-types is repeatable; format is app_label.model (e.g. dcim.device, ipam.prefix)
- custom-field --default must be a valid JSON-encoded value matching the chosen type (e.g. '"active"' for text, '42' for integer)
- custom-field changes take effect globally across all targeted object types
- webhook --http-method valid values: GET, POST, PUT, PATCH, DELETE (default: POST)
- webhook is a destination definition; attach it to an event-rule to trigger it
- event-rule is the NetBox 4.x mechanism for triggering webhooks or scripts on object changes
- event-rule --event-types valid values: object_created, object_updated, object_deleted, job_started, job_completed, job_failed, job_errored; repeatable
- event-rule --action-type valid values: webhook, script
- saved-filter --params should be a JSON string (e.g. '{"status":["active"]}')
"""

BULK = """\
The `bulk-update` and `bulk-delete` commands perform multi-object mutations in a single API call.

Examples:

- nb-cli bulk-update dcim.devices --data '[{"id":1,"status":"active"},{"id":2,"status":"active"}]' --yes
- nb-cli bulk-update dcim.devices --data @updates.json --yes
- nb-cli bulk-update dcim.devices --data - --yes
- nb-cli bulk-delete dcim.devices --id 1 2 3 --yes
- nb-cli bulk-delete dcim.devices --data '[{"id":1},{"id":2}]' --yes
- nb-cli bulk-delete dcim.devices --data @ids.json --yes

Important notes:

- bulk-update payload must be a JSON array; each object must include an 'id' field plus the fields to change
- bulk-delete accepts --id as space-separated integers OR --data as a JSON array of {"id":N} objects
- --dry-run is supported for both commands; shows the resolved payload or ID list without sending
- --yes is required for both commands (or use --dry-run to preview)
- bulk operations use NetBox's native PATCH/DELETE list endpoints (e.g. PATCH /api/dcim/devices/)
- --data supports: raw JSON inline, @/path/to/file.json to load from a file, or - to read from stdin
- not all NetBox endpoints support bulk operations; if you get an APIError, use the generic request command:
  nb-cli request patch /api/dcim/devices/ --data @updates.json --yes
"""

TOPICS = {
    "overview": OVERVIEW,
    "generic": GENERIC,
    "device": DEVICE,
    "interface": INTERFACE,
    "prefix": PREFIX,
    "ip-address": IP_ADDRESS,
    "configuration": CONFIGURATION,
    "output": OUTPUT,
    "circuits": CIRCUITS,
    "tenancy": TENANCY,
    "virtualization": VIRTUALIZATION,
    "ipam-extras": IPAM_EXTRAS,
    "dcim-components": DCIM_COMPONENTS,
    "extras": EXTRAS,
    "bulk": BULK,
}


def get_help_topic(topics: list[str] | None) -> dict[str, Any]:
    if not topics:
        key = "overview"
    else:
        key = " ".join(topics).strip().lower()
    if key not in TOPICS:
        raise NotFoundError(
            f"unknown help topic: {key}",
            details={"available_topics": sorted(TOPICS)},
        )
    return {
        "topic": key,
        "body": TOPICS[key],
        "available_topics": sorted(TOPICS),
    }
