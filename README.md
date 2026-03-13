# nb-cli

`nb-cli` is a NetBox CLI built on `pynetbox` for three audiences:

- **Operators** who need a dependable terminal workflow
- **Automation** that needs stable output and predictable exit codes
- **LLM/agent wrappers** that need an explicit execution contract instead of free-form API access

## Features

- Generic CRUD commands covering every NetBox REST endpoint
- ~46 typed workflow commands with friendly flags and automatic field resolution
- IP and prefix allocation helpers
- Bulk update and bulk delete operations
- Schema and resource discovery from live OpenAPI
- JSON, JSONL, text, and table output modes
- Multi-profile configuration (CLI flags > env vars > `.nb-cli.toml` > `~/.config/nb-cli/config.toml`)
- Verbose built-in help including long-form topic guides (`nb-cli help <topic>`)
- Validated against NetBox 4.5.3

## Installation

```bash
pip install nb-cli-tool
```

Or with `uv`:

```bash
uv pip install nb-cli-tool
```

The console entry points are `nb-cli` and `nbx`.

## Quick Start

```bash
# Discover the instance
nb-cli status
nb-cli resources --search device
nb-cli schema dcim.devices
nb-cli choices dcim.devices

# Read data
nb-cli query dcim.devices --filter site=nyc1 --format table
nb-cli device list --filter status=active --format table
nb-cli device show --lookup name=edge01

# Write data safely (--dry-run to preview, --yes to confirm)
nb-cli device create --name edge01 --device-type qfx5120 --role leaf --site nyc1 --yes
nb-cli device update --lookup name=edge01 --status active --serial ABC123 --yes --diff
nb-cli prefix allocate-ip --lookup prefix=10.0.10.0/24 --count 2 --status active --yes
nb-cli ip-address assign-interface --lookup address=10.0.10.10/24 --device edge01 --interface xe-0/0/0 --yes

# Raw escape hatch for unsupported endpoints
nb-cli request get /api/dcim/devices/?name=edge01
```

## Command Families

### Generic Commands

Work with any NetBox resource path — no typed wrapper required.

- `version` — print installed version
- `help [topic]` — long-form help topics
- `status` — fetch NetBox status endpoint
- `openapi` — fetch raw OpenAPI document
- `resources` — list resources discovered from OpenAPI
- `schema <resource>` — show fields and parameters for a resource
- `choices <resource>` — return valid choices for type/status/protocol fields
- `query <resource>` — list objects with filtering, pagination, field selection
- `get <resource>` — fetch a single object by ID or lookup
- `create <resource>` — create one object or a bulk list from JSON
- `update <resource>` — patch an object with JSON payload
- `delete <resource>` — delete an object by ID or lookup
- `bulk-update <resource>` — PATCH multiple objects in one request (each must include `id`)
- `bulk-delete <resource>` — DELETE multiple objects by ID in one request
- `request <method> <path>` — execute any raw REST request

### Typed Workflow Commands

Resource-specific commands with friendly flags and automatic slug/name-to-ID resolution. All support `list`, `show`, `create`, `update`, and `delete`.

**Circuits**
- `provider` — circuit providers (Zayo, Lumen, etc.)
- `provider-account` — provider billing accounts
- `circuit-type` — circuit type definitions
- `circuit` — individual circuits

**DCIM — Core**
- `manufacturer`
- `device-role`
- `platform`
- `device-type`
- `site`
- `location`
- `rack`
- `device`
- `interface`
- `cable`

**DCIM — Device Components**
- `console-port`
- `console-server-port`
- `power-port`
- `power-outlet`
- `rear-port`
- `front-port` (requires existing `rear-port`)
- `module-bay`
- `inventory-item`

**DCIM — Power Infrastructure**
- `power-panel`
- `power-feed`

**Tenancy**
- `tenant-group`
- `tenant`
- `contact-group`
- `contact`
- `tag`

**IPAM — Core**
- `vlan`
- `vrf`
- `prefix`
- `ip-address`

**IPAM — Extended**
- `rir` — Regional Internet Registries
- `asn` — Autonomous System Numbers
- `ip-range`
- `route-target`
- `fhrp-group` — VRRP/HSRP/GLBP/CARP groups
- `service` — IP services on devices or VMs

**Virtualization**
- `cluster-type`
- `cluster-group`
- `cluster`
- `virtual-machine`
- `vm-interface`

**Extras**
- `custom-field`
- `webhook`
- `event-rule`
- `saved-filter`

### Special Typed Actions

```bash
# Allocate IPs from a prefix
nb-cli prefix allocate-ip --lookup prefix=10.0.10.0/24 --count 5 --status active --yes

# Allocate child prefixes
nb-cli prefix allocate-prefix --lookup prefix=10.0.0.0/16 --prefix-length 24 --count 4 --yes

# Assign an IP to a device interface or VM interface
nb-cli ip-address assign-interface --lookup address=10.0.10.10/24 --device edge01 --interface xe-0/0/0 --yes
nb-cli ip-address assign-interface --lookup address=192.0.2.1/32 --vm app01 --vm-interface eth0 --yes
```

## Output Modes

```bash
nb-cli query dcim.devices --format json    # default: structured envelope
nb-cli query dcim.devices --format jsonl   # one object per line (stream-friendly)
nb-cli query dcim.devices --format table   # human-readable columns
nb-cli query dcim.devices --format text    # pretty-printed text
```

## Configuration

Configuration is loaded in priority order:

1. CLI flags
2. Environment variables (`NBCLI_URL`, `NBCLI_TOKEN`, etc.)
3. `.nb-cli.toml` in the current directory
4. `~/.config/nb-cli/config.toml`

Example config with multiple profiles:

```toml
default_profile = "lab"

[profiles.lab]
url = "https://netbox-lab.example.com"
token_env = "NETBOX_TOKEN_LAB"
verify_ssl = true
timeout = 30

[profiles.prod]
url = "https://netbox.example.com"
token_env = "NETBOX_TOKEN_PROD"
verify_ssl = true
threading = true
strict_filters = true
```

Switch profiles:

```bash
nb-cli --profile prod device list --filter status=active
```

## Built-in Help

```bash
nb-cli --help
nb-cli device create --help
nb-cli help overview
nb-cli help generic
nb-cli help device
nb-cli help prefix
nb-cli help ip-address
nb-cli help circuits
nb-cli help tenancy
nb-cli help virtualization
nb-cli help ipam-extras
nb-cli help dcim-components
nb-cli help extras
nb-cli help bulk
nb-cli help configuration
nb-cli help output
```

## Documentation

- [Command Reference](docs/command-reference.md)
- [Cookbook](docs/cookbook.md)

## Safety Model

- JSON output is the default — wrappers depend on deterministic, parseable output.
- List queries default to `--limit 50`.
- Strict filter validation is enabled by default.
- All mutating commands require `--yes` unless `--dry-run` is used.
- `--dry-run` previews the payload without sending it.
- `--diff` shows a before/after diff on updates.

## Development

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/lmarte17/nb-cli
cd nb-cli
uv sync --dev
```

Run tests:

```bash
.venv/bin/python -m pytest tests/test_cli.py tests/test_config.py tests/test_client.py -v
```

Run live integration tests against a real NetBox instance:

```bash
NBCLI_URL="https://netbox.example.com" \
NBCLI_TOKEN="..." \
.venv/bin/python -m pytest tests/test_live_integration.py -v
```

## License

MIT — see [LICENSE](LICENSE).
