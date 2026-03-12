# Design Notes

## Primary Goal

Build a NetBox CLI that is good enough to become the execution layer under an LLM wrapper later.

That means the CLI must be:

- predictable
- explicit
- safe by default
- broad enough to cover real NetBox work
- documented well enough that a wrapper can treat it as a contract

## Architecture

The current v0 is split into:

- `config.py` for layered configuration resolution
- `client.py` for the `pynetbox` wrapper and raw HTTP escape hatch
- `cli.py` for argparse-based command routing
- `output.py` for normalization and stable JSON envelopes
- `parsing.py` for common CLI parsing helpers

## Why `argparse`

The first cut intentionally stays standard-library only at import time.

That gives a few benefits:

- fewer packaging dependencies while the shape is still moving
- tests can run in environments without downloading extra CLI libraries
- the only required third-party dependency remains `pynetbox`

If the command surface grows enough that richer help generation or composable subcommand plugins become important, migrating to Click or Typer later is straightforward because the business logic is already separated from parsing.

## Command Philosophy

There are two command categories:

1. Curated generic primitives: `query`, `get`, `create`, `update`, `delete`, `choices`
2. Escape hatch: `request`

This lets the project stay useful immediately without pretending that every NetBox workflow has a polished bespoke command yet.

## Safety Rules

- strict filter validation is on by default
- list queries are bounded by default
- destructive actions require confirmation
- errors are structured and stable

## Expansion Path

The likely next layer is schema-driven command augmentation:

- discover endpoints from OpenAPI
- expose allowed fields and enums
- pre-validate payloads when practical
- add typed workflows for high-value objects like devices, interfaces, prefixes, and IP addresses
