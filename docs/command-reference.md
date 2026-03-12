# Command Reference

This document is the high-level command map for `nb-cli`.

Use `nb-cli --help` and `nb-cli <command> --help` for live flag details.
Use `nb-cli help <topic>` for long-form workflow documentation.

## Global Options

Available on every command:

- `--config`
- `--profile`
- `--url`
- `--token`
- `--token-file`
- `--timeout`
- `--verify-ssl` or `--no-verify-ssl`
- `--threading` or `--no-threading`
- `--strict-filters` or `--no-strict-filters`
- `--format {json,jsonl,text,table}`
- `--debug`

## Generic Commands

Generic commands work with any NetBox resource path.

### `version`

Print the installed `nb-cli` version.

### `help [topic]`

Show long-form help topics.

Available topics:

- `overview` — general overview of nb-cli modes and conventions
- `generic` — how to use generic commands (query, get, create, update, delete, request)
- `device` — device lifecycle workflows
- `interface` — interface CRUD and IP assignment
- `prefix` — prefix CRUD and IP/prefix allocation
- `ip-address` — IP address CRUD and interface assignment
- `circuits` — provider, circuit-type, and circuit workflows
- `tenancy` — tenant groups, contacts, and contact groups
- `virtualization` — cluster types, cluster groups, clusters, VMs
- `ipam-extras` — RIRs, ASNs, IP ranges, route targets, FHRP groups, services
- `dcim-components` — console ports, power ports/outlets, front/rear ports, module bays, inventory items, power panels/feeds
- `extras` — custom fields, webhooks, event rules, saved filters
- `bulk` — bulk-update and bulk-delete multi-object operations
- `configuration` — config file format and environment variables
- `output` — output format conventions

### `status`

Fetch the NetBox status endpoint.

### `openapi`

Fetch the raw OpenAPI document from the NetBox instance.

### `resources`

List resources discovered from OpenAPI.

Example:

```bash
nb-cli resources --search prefix
```

### `schema <resource>`

Show list and detail operations, parameters, and request-body fields for a resource.

Examples:

```bash
nb-cli schema dcim.devices
nb-cli schema ipam.ip-addresses
nb-cli schema circuits.circuits
```

### `choices <resource>`

Return choices for a resource when the endpoint exposes them. Use this to discover valid values for type, status, and protocol fields.

Examples:

```bash
nb-cli choices dcim.interfaces
nb-cli choices dcim.rear_ports
nb-cli choices circuits.circuits
```

### `query <resource>`

List objects from a resource.

Useful flags:

- `--search` — free-text search
- `--filter key=value` — field filter, repeatable
- `--limit` — max rows (default 50)
- `--offset` — pagination offset
- `--all` — return all matching rows
- `--brief` — request brief serializer output
- `--field` — restrict response fields, repeatable
- `--exclude` — exclude expensive fields, repeatable
- `--ordering` — sort expression
- `--count` — return only the count

Examples:

```bash
nb-cli query dcim.devices --filter site=nyc1 --format table
nb-cli query ipam.prefixes --filter status=active --all --format jsonl
nb-cli query circuits.circuits --filter provider=zayo --format table
```

### `get <resource>`

Fetch a single object by ID or lookup.

Examples:

```bash
nb-cli get dcim.devices --id 12
nb-cli get dcim.devices --lookup name=edge01
nb-cli get circuits.circuits --lookup cid=CID-001
```

### `create <resource>`

Create one object or a bulk list of objects from JSON.

Examples:

```bash
nb-cli create extras.tags --data '{"name":"edge","slug":"edge"}' --yes
nb-cli create extras.tags --data @tags.json --yes
nb-cli create dcim.devices --data @devices.json --yes
```

### `update <resource>`

Patch an object by ID or lookup with JSON payload data.

Flags:

- `--id` or `--lookup` — identify the target object
- `--data` — JSON payload, @file, or stdin
- `--diff` — show before/after changes
- `--dry-run` — preview without sending

Examples:

```bash
nb-cli update dcim.devices --lookup name=edge01 --data '{"status":"active"}' --yes --diff
```

### `delete <resource>`

Delete an object by ID or lookup.

### `bulk-update <resource>`

Bulk PATCH multiple objects in a single request. Each item in the payload array must include `id`.

Flags:

- `--data` (required) — JSON array, @file, or - for stdin
- `--dry-run` — preview without sending
- `--yes` — confirm

Examples:

```bash
nb-cli bulk-update dcim.devices --data '[{"id":1,"status":"active"},{"id":2,"status":"active"}]' --yes
nb-cli bulk-update dcim.devices --data @updates.json --yes
nb-cli bulk-update dcim.devices --data - --yes
```

### `bulk-delete <resource>`

Bulk DELETE multiple objects by ID in a single request.

Flags:

- `--id` — space-separated integer IDs
- `--data` — JSON array of `{"id":N}` objects, @file, or - for stdin
- `--dry-run` — preview without sending
- `--yes` — confirm

Examples:

```bash
nb-cli bulk-delete dcim.devices --id 1 2 3 --yes
nb-cli bulk-delete dcim.devices --data '[{"id":1},{"id":2}]' --yes
nb-cli bulk-delete dcim.devices --data @ids.json --yes
```

### `request <method> <path>`

Execute a raw REST request against any NetBox endpoint.

Examples:

```bash
nb-cli request get /api/dcim/devices/?name=edge01
nb-cli request post /api/extras/tags/ --data '{"name":"edge","slug":"edge"}' --yes
nb-cli request patch /api/dcim/devices/ --data @bulk_payload.json --yes
```

## Typed Commands

Typed commands are resource-specific wrappers with friendly flags and automatic field resolution.

All typed resources support: `list`, `show`, `create`, `update`, `delete`.

### Circuits

- `provider` — circuit providers (Zayo, Lumen, etc.)
- `provider-account` — provider billing accounts
- `circuit-type` — circuit type definitions (Dark Fiber, MPLS, Metro-E, etc.)
- `circuit` — individual circuits

### Inventory and DCIM

Core objects:

- `manufacturer`
- `device-role`
- `platform`
- `device-type`
- `site`
- `location`
- `rack`
- `device`
- `cable`

Interfaces:

- `interface` — physical/logical device interfaces

Device-attached components:

- `console-port` — console (serial) input ports
- `console-server-port` — console server output ports
- `power-port` — power inputs (PSUs)
- `power-outlet` — power outputs (PDU outlets)
- `rear-port` — patch panel rear face ports
- `front-port` — patch panel front face ports (requires rear-port)
- `module-bay` — line card / expansion module slots
- `inventory-item` — transceivers, line cards, fans, etc.

Power infrastructure:

- `power-panel` — electrical distribution panels
- `power-feed` — feeds from a panel to a rack

### Tenancy and Metadata

- `tenant-group`
- `tenant`
- `contact-group`
- `contact`
- `tag`

### IPAM

Core:

- `vlan`
- `vrf`
- `prefix`
- `ip-address`

Extended:

- `rir` — Regional Internet Registries
- `asn` — Autonomous System Numbers
- `ip-range` — contiguous address ranges
- `route-target` — BGP route targets
- `fhrp-group` — VRRP/HSRP/GLBP/CARP groups
- `service` — IP services on devices or VMs

### Virtualization

- `cluster-type`
- `cluster-group`
- `cluster`
- `virtual-machine`
- `vm-interface`

### Extras

- `custom-field` — custom field definitions
- `webhook` — HTTP webhook destinations
- `event-rule` — event-triggered action rules (NetBox 4.x)
- `saved-filter` — reusable query filter definitions
- `tag`

## Common Typed Actions

Most typed resources support:

- `list` — list objects with filter/search/pagination
- `show` — show a single object by ID or lookup
- `create` — create with typed flags (+ optional `--data` for advanced fields)
- `update` — patch with typed flags (+ `--diff` to preview changes)
- `delete` — delete by ID or lookup

Examples:

```bash
nb-cli site list --filter status=active --format table
nb-cli site create --name NYC1 --slug nyc1 --status active --yes
nb-cli device update --lookup name=edge01 --platform junos --yes --diff
nb-cli tag delete --lookup slug=edge --yes
nb-cli circuit list --filter provider=zayo --format table
nb-cli cluster create --name prod-cluster --type vmware --site nyc1 --status active --yes
```

## Special Typed Actions

### `prefix allocate-ip`

Allocate one or more available IPs from a prefix using NetBox's available-ips endpoint.

Example:

```bash
nb-cli prefix allocate-ip --lookup prefix=10.0.10.0/24 --count 2 --status active --yes
```

### `prefix allocate-prefix`

Allocate one or more child prefixes from a parent prefix.

Example:

```bash
nb-cli prefix allocate-prefix --lookup prefix=10.0.0.0/16 --prefix-length 24 --count 4 --yes
```

### `ip-address assign-interface`

Assign an IP address to a DCIM interface or VM interface.

Examples:

```bash
nb-cli ip-address assign-interface --lookup address=10.0.10.10/24 --device edge01 --interface xe-0/0/0 --yes
nb-cli ip-address assign-interface --lookup address=192.0.2.10/32 --vm app01 --vm-interface eth0 --yes
```
