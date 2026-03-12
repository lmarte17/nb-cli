# Troubleshooting

## `NetBox URL is required`

Provide one of:

- `--url`
- `NBCLI_URL`
- `NETBOX_URL`
- a profile with `url` in config

## `a NetBox token is required for mutating commands`

Writes need credentials.

Provide one of:

- `--token`
- `--token-file`
- `NBCLI_TOKEN`
- `NETBOX_TOKEN`
- a profile that resolves `token` or `token_env`

## Filters Return Too Much Data

By default, `nb-cli` uses strict filter validation and caps list calls at `--limit 50`.

If you see more data than expected:

- inspect the resource schema with `nb-cli schema <resource>`
- confirm the filter field names with `nb-cli choices <resource>` when applicable
- prefer typed commands for common workflows

## Update or Delete Cannot Resolve a Target

Use one of:

- `--id`
- `--lookup key=value`

If lookup is ambiguous, switch to `--id` or use a more specific set of lookup fields.

Examples:

```bash
nb-cli get dcim.devices --lookup name=edge01
nb-cli get dcim.interfaces --lookup device_id=12 --lookup name=xe-0/0/0
```

## TLS Problems

Try:

- ensuring the CA chain is valid
- using a proper CA bundle through your environment or requests configuration
- only as a last resort, `--no-verify-ssl`

Do not disable verification permanently for normal production use.

## `payload is not valid JSON`

The `--data` flag accepts:

- inline JSON
- `@file.json`
- `-` to read from stdin

Examples:

```bash
nb-cli create extras.tags --data '{"name":"edge","slug":"edge"}' --yes
nb-cli create extras.tags --data @tag.json --yes
cat tag.json | nb-cli create extras.tags --data - --yes
```

## Table Output Looks Incomplete

Table output is intentionally shallow and intended for inspection.

If you need lossless machine-readable data, use:

- `--format json`
- `--format jsonl`

## Plugin Resources

Use the discovery commands first:

```bash
nb-cli resources --search plugin
nb-cli schema plugins.example.widgets
```

If no typed command exists, use `request` or the generic resource commands.
