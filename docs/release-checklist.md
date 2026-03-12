# Release Checklist

Use this list before calling a release candidate "complete."

## Local

- run `python3 -m pytest`
- spot-check `nb-cli --help`
- spot-check at least one typed command help page such as `nb-cli device create --help`
- verify JSON, JSONL, table, and text output modes on at least one command
- verify profile loading and token resolution with a local config

## Live NetBox Validation

- validate read operations against a real NetBox instance
- validate create, update, and delete against a safe test instance
- validate `prefix allocate-ip`
- validate `prefix allocate-prefix`
- validate `ip-address assign-interface`
- validate raw `request` parity for at least one representative endpoint

## Compatibility

- run the Python matrix in CI
- confirm the supported `pynetbox` baseline still installs cleanly
- confirm the documented NetBox support range still matches reality

## Documentation

- update the cookbook when a new typed workflow is added
- update the command reference when flags or actions change
- update troubleshooting guidance if a new failure mode was discovered

## Stability

- review JSON envelope changes for backward compatibility
- review exit code changes for backward compatibility
- review help text examples for drift from actual command behavior
