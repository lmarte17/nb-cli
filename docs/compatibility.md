# Compatibility

This document records the current intended support baseline for `nb-cli`.

## Runtime Matrix

### Python

Targeted:

- Python 3.11
- Python 3.12
- Python 3.13

Current local validation in this repository has been exercised on Python 3.12.

### NetBox

Target baseline:

- NetBox 4.5 and newer within the currently supported major line

Live validation completed on March 11, 2026 against:

- NetBox 4.5.3

Live-tested workflow coverage currently includes:

- discovery: `status`, `resources`, `schema`, raw `request`
- typed CRUD: `site`, `location`, `rack`, `tenant`, `manufacturer`, `device-role`, `device-type`, `device`, `interface`, `virtual-machine`, `vm-interface`, `vlan`, `vrf`, `prefix`, `cable`
- typed helpers: `prefix allocate-ip`, `ip-address assign-interface`
- generic CRUD: `create`, `update`, `query`

### pynetbox

Minimum pinned dependency in this repository:

- `pynetbox>=7.6.1`

## Notes

- Generic commands should remain the fallback for endpoints that move faster than typed workflows.
- The CLI contract is the primary compatibility concern for wrappers, not just Python package import behavior.
- JSON envelope changes and exit code changes should be treated as breaking changes.
