# Cookbook

This file collects common `nb-cli` workflows.

## Discover What an Instance Supports

```bash
nb-cli status
nb-cli resources --search interface
nb-cli schema dcim.interfaces
nb-cli choices dcim.devices
```

## List Devices in a Site

```bash
nb-cli query dcim.devices --filter site=nyc1 --brief --format table
```

Or via the typed command:

```bash
nb-cli device list --filter site=nyc1 --format table
```

## Create a Device

```bash
nb-cli device create \
  --name edge01 \
  --device-type qfx5120-48y \
  --role leaf \
  --site nyc1 \
  --status active \
  --yes
```

## Preview a Device Update Before Sending It

```bash
nb-cli device update \
  --lookup name=edge01 \
  --platform junos \
  --serial ABC123 \
  --dry-run
```

## Show a Diff for a Generic Update

```bash
nb-cli update dcim.devices \
  --lookup name=edge01 \
  --data '{"status":"active"}' \
  --yes \
  --diff
```

## Create a Prefix and Allocate Child IPs

```bash
nb-cli prefix create --prefix 10.0.10.0/24 --status active --site nyc1 --yes
nb-cli prefix allocate-ip --lookup prefix=10.0.10.0/24 --count 5 --status active --yes
```

## Allocate Child Prefixes

```bash
nb-cli prefix allocate-prefix \
  --lookup prefix=10.0.0.0/16 \
  --prefix-length 24 \
  --count 4 \
  --yes
```

## Create and Assign an IP Address

```bash
nb-cli ip-address create \
  --address 10.0.10.10/24 \
  --status active \
  --dns-name edge01.example.com \
  --yes

nb-cli ip-address assign-interface \
  --lookup address=10.0.10.10/24 \
  --device edge01 \
  --interface xe-0/0/0 \
  --yes
```

## Use Table Output for Fast Inspection

```bash
nb-cli query dcim.devices --format table
nb-cli prefix list --format table
```

## Use JSONL for Streaming-Friendly Pipelines

```bash
nb-cli query dcim.devices --all --format jsonl
```

## Reach an Unsupported Endpoint with `request`

```bash
nb-cli request get /api/plugins/example-plugin/widgets/
```

## Use a Specific Profile

```bash
nb-cli --profile prod status
nb-cli --profile prod device list --filter status=active
```

## Provision a Circuit End-to-End

```bash
# Create the provider hierarchy
nb-cli provider create --name Zayo --slug zayo --yes
nb-cli provider-account create --name 'Zayo Account A' --provider zayo --account ACC-001 --yes
nb-cli circuit-type create --name 'Dark Fiber' --slug dark-fiber --yes

# Create the circuit
nb-cli circuit create \
  --cid CID-001 \
  --provider zayo \
  --type dark-fiber \
  --status active \
  --commit-rate 10000 \
  --yes

# List all circuits for this provider
nb-cli circuit list --filter provider=zayo --format table
```

## Create a Tenant with Contacts

```bash
# Create the tenant group and tenant
nb-cli tenant-group create --name 'Enterprise Customers' --slug enterprise-customers --yes
nb-cli tenant create --name Acme --slug acme --group enterprise-customers --yes

# Create a contact group and contacts
nb-cli contact-group create --name NOC --slug noc --yes
nb-cli contact create \
  --name 'Jane Smith' \
  --email jane@example.com \
  --phone 555-1234 \
  --title 'NOC Engineer' \
  --group noc \
  --yes
```

## Create a Virtualization Cluster and Deploy a VM

```bash
# Build the cluster hierarchy
nb-cli cluster-type create --name VMware --slug vmware --yes
nb-cli cluster-group create --name Production --slug production --yes
nb-cli cluster create \
  --name prod-cluster \
  --type vmware \
  --group production \
  --site nyc1 \
  --status active \
  --yes

# Deploy a VM and assign an IP
nb-cli virtual-machine create --name app01 --cluster prod-cluster --status active --yes
nb-cli vm-interface create --virtual-machine app01 --name eth0 --yes
nb-cli ip-address create --address 10.0.10.20/24 --status active --yes
nb-cli ip-address assign-interface \
  --lookup address=10.0.10.20/24 \
  --vm app01 \
  --vm-interface eth0 \
  --yes
```

## Register ASNs

```bash
nb-cli rir create --name ARIN --slug arin --yes
nb-cli rir create --name RFC1918 --slug rfc1918 --is-private --yes
nb-cli asn create --asn 65001 --rir arin --yes
nb-cli asn create --asn 64512 --rir rfc1918 --tenant acme --yes
nb-cli asn list --filter rir=arin --format table
```

## Create an IP Range

```bash
nb-cli ip-range create \
  --start-address 10.0.0.1/24 \
  --end-address 10.0.0.100/24 \
  --status active \
  --yes
```

## Create FHRP Groups

```bash
# VRRP group
nb-cli fhrp-group create --protocol vrrp2 --group-id 10 --yes

# HSRP group with authentication
nb-cli fhrp-group create \
  --protocol hsrp \
  --group-id 1 \
  --name 'Gateway HSRP 1' \
  --auth-type md5 \
  --auth-key mysecret \
  --yes
```

## Create a Service on a Device

```bash
nb-cli service create \
  --name SSH \
  --device edge01 \
  --ports 22 \
  --protocol tcp \
  --description 'Management SSH' \
  --yes

# Multi-port service
nb-cli service create \
  --name 'Web' \
  --device web01 \
  --ports 80 \
  --ports 443 \
  --protocol tcp \
  --yes
```

## Wire Up Patch Panel Ports

```bash
# Always create rear-ports before front-ports
nb-cli rear-port create \
  --device patch-panel01 \
  --name RP1 \
  --type 8p8c \
  --positions 1 \
  --yes

nb-cli front-port create \
  --device patch-panel01 \
  --name FP1 \
  --type 8p8c \
  --rear-port RP1 \
  --rear-port-position 1 \
  --yes
```

## Add Inventory Items to a Device

```bash
nb-cli inventory-item create \
  --device edge01 \
  --name 'SFP+ Port 0' \
  --manufacturer finisar \
  --part-id FTLX8574D3BCL \
  --serial SFP00001 \
  --yes
```

## Set Up Power Infrastructure

```bash
# Create power panel and feeds
nb-cli power-panel create --name 'Panel A' --site nyc1 --yes

nb-cli power-feed create \
  --name 'Feed A1' \
  --power-panel 'Panel A' \
  --type primary \
  --voltage 120 \
  --amperage 20 \
  --phase single-phase \
  --yes
```

## Bulk Update Device Status

```bash
# Query IDs of planned devices, generate update payload, then bulk-update
nb-cli query dcim.devices --filter site=nyc1 --filter status=planned \
  --field id --all --format jsonl \
  | jq -s 'map({id: .id, status: "active"})' > updates.json

# Preview first
nb-cli bulk-update dcim.devices --data @updates.json --dry-run

# Execute
nb-cli bulk-update dcim.devices --data @updates.json --yes
```

## Bulk Delete Decommissioned Devices

```bash
# Query IDs of decommissioned devices
nb-cli query dcim.devices --filter status=decommissioned \
  --field id --all --format jsonl \
  | jq -s 'map(.id)' > decom_ids.json

# Preview: convert id array to bulk-delete --data format
cat decom_ids.json | jq 'map({id: .})' > decom_payload.json
nb-cli bulk-delete dcim.devices --data @decom_payload.json --dry-run

# Execute
nb-cli bulk-delete dcim.devices --data @decom_payload.json --yes
```

## Manage Custom Fields

```bash
# Add a custom field to devices and prefixes
nb-cli custom-field create \
  --name env_tier \
  --label 'Environment Tier' \
  --type select \
  --object-types dcim.device \
  --object-types ipam.prefix \
  --yes

# Set the custom field value on a device via --data
nb-cli device update \
  --lookup name=edge01 \
  --data '{"custom_fields": {"env_tier": "production"}}' \
  --yes

nb-cli custom-field list --format table
```

## Set Up a Webhook and Event Rule

```bash
# Create the webhook destination
nb-cli webhook create \
  --name 'Slack Alerts' \
  --payload-url https://hooks.slack.com/services/xxx/yyy/zzz \
  --http-method POST \
  --enabled \
  --yes

# Create an event rule that fires the webhook on device changes
nb-cli event-rule create \
  --name 'Device Change Alert' \
  --object-types dcim.device \
  --event-types object_created \
  --event-types object_updated \
  --action-type webhook \
  --enabled \
  --yes
```
