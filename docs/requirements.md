# nb-cli Requirements

## 1. Purpose

This document defines the functional and non-functional requirements for a complete `nb-cli` release.

The intent is to turn `nb-cli` into the best CLI execution layer for NetBox operations, with enough safety, breadth, and determinism that:

- human operators can use it directly for day-to-day NetBox work
- automation and CI jobs can rely on it as a stable interface
- LLM wrappers can translate natural language into explicit, auditable CLI actions

For this document:

- `MUST` means required for the first "complete" release
- `SHOULD` means strongly recommended and planned unless a clear constraint blocks it
- `MAY` means optional or follow-on

## 2. Product Goals

`nb-cli` MUST:

- provide broad NetBox coverage without forcing users into raw HTTP for common workflows
- be safe by default for destructive and high-impact operations
- be deterministic enough for agent wrappers and scripts
- expose NetBox in a way that is easier to validate than direct natural-language execution
- remain useful even when new NetBox endpoints appear, via generic and schema-driven commands

`nb-cli` MUST NOT:

- depend on interactive prompts as the primary safety mechanism
- hide the underlying NetBox behavior or silently coerce operations
- require users to drop to Python for routine NetBox tasks
- optimize only for humans at the expense of machine readability

## 3. Primary Users

The complete CLI MUST serve three primary user types:

1. Operators
   Operators need discoverable commands, readable output, safe defaults, and clear errors.
2. Automation authors
   Automation needs stable output formats, predictable exit codes, non-interactive execution, and composable commands.
3. LLM wrappers
   Wrappers need a narrow and deterministic execution contract, discoverability commands, validation hooks, and explicit safety boundaries.

## 4. Product Principles

The complete tool MUST follow these principles:

- CLI-first: the CLI is the product boundary, not a thin demo wrapper.
- Schema-aware: the CLI should use NetBox OpenAPI and endpoint metadata wherever it improves validation and discoverability.
- Safe-by-default: default behavior should minimize accidental wide reads and unsafe writes.
- Machine-readable first: all commands must have structured output and structured failure modes.
- Human-usable: text and table affordances should exist without weakening the machine contract.
- Canonical fallback: users must always have a generic escape hatch for API features not yet modeled by typed commands.

## 5. Scope

### 5.1 In Scope

The complete CLI MUST include:

- generic CRUD and raw API access
- typed workflows for high-value NetBox objects and relationships
- schema and endpoint discovery
- bulk operations
- profile-based configuration
- machine-readable output and error contracts
- comprehensive documentation
- unit and integration tests
- packaging for normal CLI installation flows

### 5.2 Out of Scope for the First Complete Release

The first complete release does not need to include:

- a graphical UI
- a daemon or server mode
- a GraphQL-first workflow surface
- autonomous orchestration or policy engines
- embedded chat or natural-language parsing

Those can be layered on later, but the CLI itself must remain the execution substrate.

## 6. Functional Requirements

### 6.1 Installation and Distribution

The project MUST:

- publish a Python package installable with `uv`, `pip`, and `pipx`
- expose a stable executable name
- define and test a supported Python version range
- define and test a supported NetBox version range
- pin a minimum supported `pynetbox` version

The project SHOULD:

- publish platform-agnostic install instructions
- include shell completion installation instructions for Bash, Zsh, and Fish

### 6.2 Compatibility Matrix

The complete CLI MUST explicitly define compatibility for:

- Python versions
- NetBox versions
- `pynetbox` versions

The release process MUST validate the matrix in CI for supported combinations where practical.

### 6.3 Global CLI Behavior

Every command MUST:

- support `--format`
- return structured output on success
- return structured errors on stderr
- use stable exit codes
- avoid interactive prompts by default
- support `--debug` for traceback-rich diagnostics

The CLI SHOULD provide:

- `--verbose`
- `--quiet`
- `--no-color`
- `--profile`
- `--config`
- `--timeout`
- `--verify-ssl` and `--no-verify-ssl`
- `--version`

The CLI MUST behave safely in non-TTY contexts and MUST NOT emit spinners, pagers, or prompts unless explicitly requested.

### 6.4 Configuration and Authentication

The CLI MUST support layered configuration from:

1. CLI flags
2. environment variables
3. current-directory config
4. user-level config

Configuration MUST support:

- multiple profiles
- base URL
- token or token file
- SSL verification
- timeout
- threading or concurrency settings
- strict filter settings
- custom headers when needed

Authentication requirements:

- the CLI MUST support NetBox token authentication
- the CLI MUST support both legacy token behavior and current token formats used by supported NetBox versions
- the CLI MUST fail clearly when a mutating operation lacks required credentials

The project SHOULD support:

- proxy configuration
- CA bundle configuration
- environment-variable indirection for secrets

### 6.5 Discovery and Introspection

The complete CLI MUST include commands that let a user or wrapper discover what the NetBox instance supports.

Required capabilities:

- fetch instance status
- fetch OpenAPI schema
- list available resources
- inspect choices for a resource
- inspect fields, filters, and operations for a resource
- search resources by name or path

The CLI SHOULD provide:

- examples for a resource
- help text derived from schema metadata
- completion suggestions derived from schema and choices

### 6.6 Generic Resource Operations

The complete CLI MUST include generic commands that can operate against any supported REST resource:

- `query`
- `count`
- `get`
- `create`
- `update`
- `delete`
- `request`

Generic read commands MUST support:

- filtering
- free-text search where supported
- ordering
- pagination
- field selection
- brief responses where supported
- exclusion of expensive fields where supported

Generic write commands MUST support:

- object lookup by `id`
- object lookup by unique field filters
- JSON object and JSON array payloads
- dry-run preflight mode
- explicit confirmation for destructive operations
- changelog messages when supported by NetBox

The `request` command MUST remain as the final fallback for features not yet covered by typed or generic commands.

### 6.7 Typed Workflow Commands

The complete CLI MUST provide typed commands for the most common operational domains so users do not have to encode routine workflows as raw payload manipulation.

At minimum, the first complete release MUST include typed workflows for:

- sites and locations
- racks
- manufacturers, roles, and platforms
- device types
- devices
- interfaces
- cables
- virtual machines
- VM interfaces
- prefixes
- IP addresses
- VLANs
- VRFs
- tenants and tags

Typed commands MUST cover common operations such as:

- list and show
- create and update
- delete with confirmation
- assign or unassign relationships
- tag and untag
- resolve parent-child or attachment relationships

Examples of required typed behavior:

- device creation without forcing a raw JSON payload for every field
- interface assignment to devices and VMs
- IP assignment to interfaces
- prefix lookup and allocation helpers
- cable creation between valid endpoints

Typed commands SHOULD:

- validate required relationships before sending writes
- expose friendly flags for high-value fields
- support `--data` as an escape hatch for advanced payloads

### 6.8 Bulk and Import/Export Operations

The complete CLI MUST support bulk workflows because NetBox is often operated at inventory scale.

Required bulk capabilities:

- bulk create from JSON arrays
- bulk update from JSON arrays
- bulk delete by ID list or resolved lookup set
- export query results to JSON and JSONL

The tool SHOULD support:

- CSV import and export for selected typed resources
- partial-failure reporting where the underlying API allows it
- chunking for large operations

When the underlying NetBox API applies all-or-nothing semantics, the CLI MUST state that clearly in output and docs.

### 6.9 Safety and Validation

Safety requirements are mandatory.

The complete CLI MUST:

- enable strict filter validation by default
- bound broad list queries by default
- require `--yes` or `--dry-run` for destructive commands
- show resolved targets before executing destructive lookup-based writes when in text mode
- emit enough metadata in JSON mode for wrappers to understand what was targeted
- reject ambiguous object resolution
- reject invalid payloads before sending requests when validation is possible client-side

The complete CLI SHOULD:

- support `--diff` or preview output for updates
- support `--fail-if-empty` for commands where empty matches are risky
- support `--exact` or explicit lookup modes to reduce ambiguity

Dry-run behavior:

- all mutating commands MUST support dry-run
- dry-run output MUST be honest about what was validated locally vs. what still requires server-side validation

### 6.10 Output Contract

The complete CLI MUST define a stable machine contract.

Required output formats:

- `json`
- `text`

The CLI SHOULD also support:

- `jsonl`
- `table`

Success output MUST:

- include an `ok: true` marker in JSON mode
- identify the command executed
- contain command data in a stable envelope

Error output MUST:

- be structured in JSON mode
- include an error type
- include a human-readable message
- include machine-useful details when available

The CLI MUST document the JSON schema for success and error envelopes.

### 6.11 Exit Codes

The complete CLI MUST reserve and document exit codes for at least:

- success
- usage error
- config error
- auth error
- not found
- validation error
- API error
- connectivity error
- internal error

Exit code behavior MUST remain stable across minor releases.

### 6.12 Logging and Diagnostics

The complete CLI MUST support diagnostics sufficient for real operational debugging.

Required capabilities:

- debug traceback output
- request/response context in debug mode without leaking secrets
- clear distinction between client-side and server-side errors

The CLI SHOULD support:

- HTTP debug logging
- request correlation IDs when available
- timing metrics for slow calls

### 6.13 Performance

The complete CLI MUST be usable against large NetBox instances.

Performance requirements:

- query defaults MUST avoid unbounded table dumps
- pagination MUST be explicit and controllable
- expensive nested payloads SHOULD be suppressible
- timeouts MUST be configurable

The CLI SHOULD support:

- streaming output for large result sets
- concurrency controls for safe parallel reads
- schema caching with explicit invalidation

### 6.14 Documentation and Help

Documentation is part of the product.

The complete release MUST include:

- installation instructions
- configuration reference
- command reference
- output contract reference
- safety model
- examples for common workflows
- troubleshooting guidance
- compatibility matrix

The CLI help output MUST be good enough that a new user can discover common commands without reading source code.

The project SHOULD also include:

- a cookbook of real NetBox tasks
- migration notes for breaking changes
- examples written specifically for wrappers and automation

### 6.15 Extensibility

The complete CLI SHOULD be structured so new typed commands can be added without breaking the core contract.

The architecture MUST:

- separate parsing, business logic, and NetBox transport
- permit schema-driven command generation or augmentation
- keep generic and typed layers interoperable

The project MAY support:

- plugins for site-specific command groups
- custom output transformers
- generated client helpers for plugin resources

## 7. Non-Functional Requirements

### 7.1 Reliability

The CLI MUST behave predictably under:

- invalid config
- invalid filters
- missing credentials
- TLS failures
- timeouts
- API validation failures
- empty query results
- ambiguous lookups

### 7.2 Security

The CLI MUST:

- avoid printing tokens or secrets
- avoid logging sensitive headers in debug output
- document safe secret handling patterns
- support token files and environment-based secret loading

### 7.3 Backward Compatibility

The project MUST version and honor its CLI contract.

Specifically:

- output envelope changes in JSON mode MUST be treated as breaking changes
- exit code changes MUST be treated as breaking changes
- removal or semantic redefinition of stable flags MUST be treated as breaking changes

### 7.4 Testability

The implementation MUST be testable without live NetBox access for core command logic.

The project MUST include:

- unit tests for parsing and config resolution
- unit tests for command routing
- unit tests for error translation
- integration tests against a live NetBox instance in CI or a reproducible local workflow

The project SHOULD maintain strong coverage over core libraries and command behavior.

## 8. Acceptance Criteria for a "Complete" Release

The CLI can be considered complete only when all of the following are true:

1. A user can perform common NetBox inventory tasks without raw HTTP.
2. A wrapper can discover resources, fields, and choices programmatically.
3. Mutating commands support dry-run and explicit confirmation semantics.
4. JSON mode is stable, documented, and covered by tests.
5. Error handling is structured and uses stable exit codes.
6. The compatibility matrix is documented and validated.
7. The command reference and cookbook cover the top operational workflows.
8. Integration tests verify real reads and writes against supported NetBox versions.
9. Generic commands still provide full REST escape-hatch coverage.

## 9. Delivery Phases

### Phase 1: Foundation

- package and install flow
- config and auth
- JSON output contract
- generic CRUD commands
- raw request fallback
- status, schema, resources, choices

### Phase 2: Typed Core Workflows

- devices
- interfaces
- prefixes
- IP addresses
- sites and racks
- tags and tenants

### Phase 3: Safety and Scale

- dry-run previews
- diff output
- chunked bulk operations
- schema caching
- JSONL and table output

### Phase 4: Complete Release Gate

- compatibility matrix validation
- cookbook and troubleshooting docs
- shell completion
- integration test matrix
- semver-ready CLI stability review

## 10. Source of Truth

This document is the product requirement baseline for `nb-cli`.

Implementation, roadmap, and release work SHOULD be evaluated against these requirements rather than adding features ad hoc.
