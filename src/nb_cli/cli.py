from __future__ import annotations

import argparse
import sys
import traceback
from typing import Any, Sequence

from . import __version__
from .client import NetBoxClient
from .config import AppConfig, load_config
from .exceptions import ConfigError, NBCLIError, ValidationError
from .manual import get_help_topic
from .output import error_envelope, render_output, success_envelope
from .parsing import load_json_data, parse_key_value_pairs, require_confirmation
from .workflows import COMMON_TEXT, RESOURCE_SPECS, add_field_arguments, collect_payload, validate_payload

TOP_LEVEL_DESCRIPTION = """\
nb-cli is a NetBox command line client designed for operators, automation, and LLM wrappers.

The CLI is intentionally opinionated:

- JSON output is the default machine contract.
- Generic commands cover the entire REST surface.
- Typed commands make high-value workflows safer and easier.
- Mutating commands require --yes unless --dry-run is used.
- Help text is verbose because discovery is part of the product.
"""

TOP_LEVEL_EPILOG = """\
Quick start:

  nb-cli status
  nb-cli resources --search device
  nb-cli schema dcim.devices
  nb-cli query dcim.devices --filter site=nyc --format table
  nb-cli help overview

Typed workflow examples:

  nb-cli device create --name edge01 --device-type qfx5120 --role leaf --site nyc1 --yes
  nb-cli prefix allocate-ip --lookup prefix=10.0.10.0/24 --count 2 --yes
  nb-cli ip-address assign-interface --lookup address=10.0.10.10/24 --device edge01 --interface xe-0/0/0 --yes
"""


class HelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nb-cli",
        description=TOP_LEVEL_DESCRIPTION,
        epilog=TOP_LEVEL_EPILOG,
        formatter_class=HelpFormatter,
    )
    parser.add_argument("--config", help="Path to a TOML config file.")
    parser.add_argument("--profile", help="Config profile name.")
    parser.add_argument("--url", help="NetBox base URL.")
    parser.add_argument("--token", help="NetBox token value.")
    parser.add_argument("--token-file", help="Path to a file containing the NetBox token.")
    parser.add_argument("--timeout", type=float, help="HTTP timeout in seconds.")
    parser.add_argument(
        "--verify-ssl",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable TLS certificate verification.",
    )
    parser.add_argument(
        "--threading",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable pynetbox threading support.",
    )
    parser.add_argument(
        "--strict-filters",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable strict filter validation.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "jsonl", "text", "table"],
        default="json",
        help="Output format. Prefer json for wrappers and table for quick human inspection.",
    )
    parser.add_argument("--debug", action="store_true", help="Print traceback details on failure.")

    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    subparsers.add_parser(
        "version",
        help="Print the nb-cli version.",
        description="Print the installed nb-cli version.",
        formatter_class=HelpFormatter,
    )
    subparsers.add_parser(
        "status",
        help="Fetch the NetBox status endpoint.",
        description="Return the NetBox status endpoint using the configured profile.",
        formatter_class=HelpFormatter,
    )
    subparsers.add_parser(
        "openapi",
        help="Fetch the NetBox OpenAPI schema.",
        description="Return the raw OpenAPI document exposed by NetBox.",
        formatter_class=HelpFormatter,
    )

    help_parser = subparsers.add_parser(
        "help",
        help="Show verbose help topics.",
        description="Show long-form help for common nb-cli workflows and conventions.",
        formatter_class=HelpFormatter,
        epilog=(
            "Examples:\n"
            "  nb-cli help\n"
            "  nb-cli help generic\n"
            "  nb-cli help device\n"
            "  nb-cli help circuits\n"
            "  nb-cli help tenancy\n"
            "  nb-cli help virtualization\n"
            "  nb-cli help ipam-extras\n"
            "  nb-cli help dcim-components\n"
            "  nb-cli help extras\n"
            "  nb-cli help bulk\n"
            "  nb-cli help output"
        ),
    )
    help_parser.add_argument("topics", nargs="*", help="Help topic. Examples: generic, device, prefix.")

    resources = subparsers.add_parser(
        "resources",
        help="List resources discovered from OpenAPI.",
        description="Discover list endpoints from the NetBox OpenAPI schema.",
        formatter_class=HelpFormatter,
    )
    resources.add_argument("--search", help="Filter resources by substring.")

    schema = subparsers.add_parser(
        "schema",
        help="Inspect schema details for a resource.",
        description="Show list/detail operations, parameters, and request-body fields for a resource.",
        formatter_class=HelpFormatter,
        epilog="Example:\n  nb-cli schema dcim.devices\n  nb-cli schema ipam.ip-addresses",
    )
    schema.add_argument("resource", help="Dotted resource path like dcim.devices.")

    choices = subparsers.add_parser(
        "choices",
        help="Return endpoint choices.",
        description="Return choice metadata for a resource when the endpoint exposes it.",
        formatter_class=HelpFormatter,
    )
    choices.add_argument("resource", help="Dotted resource path like dcim.devices.")

    query = subparsers.add_parser(
        "query",
        help="List objects from a resource.",
        description="Run a list query against any NetBox resource.",
        formatter_class=HelpFormatter,
        epilog="Examples:\n  nb-cli query dcim.devices --filter site=nyc --format table\n  nb-cli query ipam.prefixes --search prod --all",
    )
    query.add_argument("resource", help="Dotted resource path like dcim.devices.")
    _add_query_arguments(query)

    get = subparsers.add_parser(
        "get",
        help="Fetch a single object.",
        description="Fetch a single object by ID or unique lookup values.",
        formatter_class=HelpFormatter,
        epilog="Examples:\n  nb-cli get dcim.devices --id 12\n  nb-cli get dcim.devices --lookup name=edge01",
    )
    get.add_argument("resource", help="Dotted resource path like dcim.devices.")
    _add_lookup_arguments(get)

    create = subparsers.add_parser(
        "create",
        help="Create an object or bulk objects.",
        description="Create objects against any NetBox resource using a JSON payload.",
        formatter_class=HelpFormatter,
        epilog="Examples:\n  nb-cli create extras.tags --data '{\"name\":\"edge\",\"slug\":\"edge\"}' --yes",
    )
    create.add_argument("resource", help="Dotted resource path like dcim.devices.")
    create.add_argument("--data", required=True, help="JSON payload, @file, or - for stdin.")
    _add_mutation_arguments(create, include_diff=False)

    update = subparsers.add_parser(
        "update",
        help="Patch an existing object.",
        description="Patch an existing object using ID or lookup filters and a JSON payload.",
        formatter_class=HelpFormatter,
        epilog="Examples:\n  nb-cli update dcim.devices --lookup name=edge01 --data '{\"status\":\"active\"}' --yes --diff",
    )
    update.add_argument("resource", help="Dotted resource path like dcim.devices.")
    _add_lookup_arguments(update)
    update.add_argument("--data", required=True, help="JSON payload, @file, or - for stdin.")
    _add_mutation_arguments(update, include_diff=True)

    delete = subparsers.add_parser(
        "delete",
        help="Delete an object.",
        description="Delete an object by ID or unique lookup values.",
        formatter_class=HelpFormatter,
        epilog="Examples:\n  nb-cli delete dcim.devices --lookup name=old-edge01 --yes",
    )
    delete.add_argument("resource", help="Dotted resource path like dcim.devices.")
    _add_lookup_arguments(delete)
    _add_mutation_arguments(delete, include_data=False, include_diff=False)

    bulk_update = subparsers.add_parser(
        "bulk-update",
        help="Bulk PATCH multiple objects by ID in a single request.",
        description=(
            "Send a PATCH request with a JSON array to NetBox's bulk-update list endpoint. "
            "Each object in the array must include an 'id' field plus the fields to change. "
            "See: nb-cli help bulk"
        ),
        formatter_class=HelpFormatter,
        epilog=(
            "Examples:\n"
            "  nb-cli bulk-update dcim.devices --data '[{\"id\":1,\"status\":\"active\"},{\"id\":2,\"status\":\"active\"}]' --yes\n"
            "  nb-cli bulk-update dcim.devices --data @updates.json --yes\n"
            "  nb-cli bulk-update dcim.devices --data - --yes"
        ),
    )
    bulk_update.add_argument("resource", help="Dotted resource path like dcim.devices.")
    bulk_update.add_argument(
        "--data",
        required=True,
        help="JSON array payload, @file path, or - for stdin. Each object must include 'id'.",
    )
    _add_mutation_arguments(bulk_update, include_diff=False)

    bulk_delete = subparsers.add_parser(
        "bulk-delete",
        help="Bulk DELETE multiple objects by ID in a single request.",
        description=(
            "Delete multiple NetBox objects in a single API call. "
            "Provide IDs as space-separated integers with --id, or as a JSON array with --data. "
            "See: nb-cli help bulk"
        ),
        formatter_class=HelpFormatter,
        epilog=(
            "Examples:\n"
            "  nb-cli bulk-delete dcim.devices --id 1 2 3 --yes\n"
            "  nb-cli bulk-delete dcim.devices --data '[{\"id\":1},{\"id\":2}]' --yes\n"
            "  nb-cli bulk-delete dcim.devices --data @ids.json --yes"
        ),
    )
    bulk_delete.add_argument("resource", help="Dotted resource path like dcim.devices.")
    bulk_delete.add_argument(
        "--id",
        type=int,
        nargs="+",
        dest="ids",
        help="One or more numeric object IDs to delete.",
    )
    bulk_delete.add_argument(
        "--data",
        help="JSON array of {\"id\":N} objects, @file path, or - for stdin. Alternative to --id.",
    )
    _add_mutation_arguments(bulk_delete, include_data=False, include_diff=False)

    request = subparsers.add_parser(
        "request",
        help="Perform a raw HTTP request against NetBox.",
        description="Call the NetBox REST API directly using the configured HTTP session.",
        formatter_class=HelpFormatter,
        epilog="Examples:\n  nb-cli request get /api/dcim/devices/?name=edge01\n  nb-cli request post /api/extras/tags/ --data '{\"name\":\"edge\",\"slug\":\"edge\"}' --yes",
    )
    request.add_argument("method", help="HTTP method, such as GET, POST, PATCH, or DELETE.")
    request.add_argument("path", help="Absolute API path beginning with /.")
    request.add_argument("--query", action="append", default=[], help="Query parameter as key=value.")
    request.add_argument("--data", help="JSON payload, @file, or - for stdin.")
    _add_mutation_arguments(request, include_data=False, include_diff=False)

    for spec in RESOURCE_SPECS.values():
        _add_typed_resource_parser(subparsers, spec)

    return parser


def _add_query_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--search", help="Free-text search string passed as q=.")
    parser.add_argument("--filter", action="append", default=[], help="Filter expression as key=value.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum number of rows to return.")
    parser.add_argument("--offset", type=int, default=0, help="Offset into the result set.")
    parser.add_argument("--all", action="store_true", help="Return all matching rows.")
    parser.add_argument("--brief", action="store_true", help="Request brief serializer output when supported.")
    parser.add_argument("--field", action="append", default=[], help="Restrict response fields.")
    parser.add_argument("--exclude", action="append", default=[], help="Exclude expensive response fields.")
    parser.add_argument("--ordering", help="Ordering expression supported by the endpoint.")
    parser.add_argument("--count", action="store_true", help="Return only the count of matching rows.")


def _add_lookup_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--id", type=int, help="Numeric object ID.")
    parser.add_argument("--lookup", action="append", default=[], help="Lookup expression as key=value.")


def _add_mutation_arguments(
    parser: argparse.ArgumentParser,
    *,
    include_data: bool = True,
    include_diff: bool = False,
) -> None:
    parser.add_argument("--dry-run", action="store_true", help="Preview the operation without sending it.")
    parser.add_argument("--yes", action="store_true", help="Confirm a mutating operation.")
    if include_diff:
        parser.add_argument("--diff", action="store_true", help="Show before/after changes for updates.")


def _add_typed_resource_parser(subparsers: Any, spec: Any) -> None:
    parser = subparsers.add_parser(
        spec.command_name,
        help=f"Typed workflow commands for {spec.label} objects.",
        description=f"{spec.description}\n\n{COMMON_TEXT}",
        epilog=spec.examples,
        formatter_class=HelpFormatter,
    )
    actions = parser.add_subparsers(dest="typed_action", required=True, metavar="ACTION")

    list_parser = actions.add_parser(
        "list",
        help=f"List {spec.label} objects.",
        description=f"List {spec.label} objects using the generic query surface for {spec.resource}.",
        formatter_class=HelpFormatter,
        epilog=spec.examples,
    )
    _add_query_arguments(list_parser)

    show_parser = actions.add_parser(
        "show",
        help=f"Show a single {spec.label}.",
        description=f"Fetch one {spec.label} by ID or lookup.",
        formatter_class=HelpFormatter,
        epilog=spec.examples,
    )
    _add_lookup_arguments(show_parser)

    create_parser = actions.add_parser(
        "create",
        help=f"Create a {spec.label}.",
        description=f"Create a {spec.label} with friendly flags and optional --data overrides.",
        formatter_class=HelpFormatter,
        epilog=spec.examples,
    )
    add_field_arguments(create_parser, spec)
    create_parser.add_argument("--data", help="Optional JSON payload merged with typed flags.")
    _add_mutation_arguments(create_parser, include_diff=False)

    update_parser = actions.add_parser(
        "update",
        help=f"Update a {spec.label}.",
        description=f"Patch a {spec.label} with friendly flags and optional --data overrides.",
        formatter_class=HelpFormatter,
        epilog=spec.examples,
    )
    _add_lookup_arguments(update_parser)
    add_field_arguments(update_parser, spec)
    update_parser.add_argument("--data", help="Optional JSON payload merged with typed flags.")
    _add_mutation_arguments(update_parser, include_diff=True)

    delete_parser = actions.add_parser(
        "delete",
        help=f"Delete a {spec.label}.",
        description=f"Delete a {spec.label} by ID or lookup.",
        formatter_class=HelpFormatter,
        epilog=spec.examples,
    )
    _add_lookup_arguments(delete_parser)
    _add_mutation_arguments(delete_parser, include_data=False, include_diff=False)

    if spec.command_name == "prefix":
        alloc_ip = actions.add_parser(
            "allocate-ip",
            help="Allocate one or more available IPs from a prefix.",
            description="Use NetBox's available-ips detail endpoint to allocate IP addresses from a prefix.",
            formatter_class=HelpFormatter,
            epilog="Examples:\n  nb-cli prefix allocate-ip --lookup prefix=10.0.10.0/24 --count 2 --status active --yes",
        )
        _add_lookup_arguments(alloc_ip)
        alloc_ip.add_argument("--count", type=int, default=1, help="Number of IPs to allocate.")
        alloc_ip.add_argument("--status", help="Optional status for created IPs.")
        alloc_ip.add_argument("--dns-name", help="Optional DNS name for a single allocation.")
        alloc_ip.add_argument("--description", help="Optional description.")
        alloc_ip.add_argument("--data", help="Optional JSON payload merged into each allocation.")
        _add_mutation_arguments(alloc_ip, include_data=False, include_diff=False)

        alloc_prefix = actions.add_parser(
            "allocate-prefix",
            help="Allocate one or more child prefixes from a parent prefix.",
            description="Use NetBox's available-prefixes detail endpoint to allocate child prefixes.",
            formatter_class=HelpFormatter,
            epilog="Examples:\n  nb-cli prefix allocate-prefix --lookup prefix=10.0.0.0/16 --prefix-length 24 --count 2 --yes",
        )
        _add_lookup_arguments(alloc_prefix)
        alloc_prefix.add_argument("--prefix-length", type=int, required=True, help="Length of child prefix to allocate.")
        alloc_prefix.add_argument("--count", type=int, default=1, help="Number of prefixes to allocate.")
        alloc_prefix.add_argument("--status", help="Optional status for created prefixes.")
        alloc_prefix.add_argument("--description", help="Optional description.")
        alloc_prefix.add_argument("--data", help="Optional JSON payload merged into each allocation.")
        _add_mutation_arguments(alloc_prefix, include_data=False, include_diff=False)

    if spec.command_name == "ip-address":
        assign = actions.add_parser(
            "assign-interface",
            help="Assign an IP address to an interface.",
            description="Assign an IP address to either a DCIM interface or a VM interface.",
            formatter_class=HelpFormatter,
            epilog="Examples:\n  nb-cli ip-address assign-interface --lookup address=10.0.10.10/24 --device edge01 --interface xe-0/0/0 --yes",
        )
        _add_lookup_arguments(assign)
        assign.add_argument("--device", help="Device name or ID for DCIM interface assignment.")
        assign.add_argument("--interface", help="Interface name for DCIM assignment.")
        assign.add_argument("--vm", help="Virtual machine name or ID for VM interface assignment.")
        assign.add_argument("--vm-interface", help="VM interface name for virtualization assignment.")
        _add_mutation_arguments(assign, include_data=False, include_diff=False)


def _print(stream: Any, content: Any, fmt: str) -> None:
    stream.write(render_output(content, fmt))
    stream.write("\n")


def _require_connection(config: AppConfig) -> None:
    if not config.url:
        raise ConfigError("NetBox URL is required. Set --url, NBCLI_URL, or a profile url.")


def _require_token(config: AppConfig) -> None:
    if not config.token:
        raise ConfigError("a NetBox token is required for mutating commands")


def _command_label(args: argparse.Namespace) -> str:
    if getattr(args, "typed_action", None):
        return f"{args.command} {args.typed_action}"
    return args.command


def _build_lookup(args: argparse.Namespace) -> dict[str, Any]:
    return parse_key_value_pairs(getattr(args, "lookup", []), "--lookup")


def _run_generic_update(args: argparse.Namespace, config: AppConfig, client: NetBoxClient) -> Any:
    payload = load_json_data(args.data)
    require_confirmation(yes=args.yes, dry_run=args.dry_run, action="update")
    lookup = _build_lookup(args)
    preview = client.preview_update(
        args.resource,
        record_id=args.id,
        lookup=lookup,
        payload=payload,
    )
    if args.dry_run:
        return {"dry_run": True, **preview}
    _require_token(config)
    result = client.update(
        args.resource,
        record_id=args.id,
        lookup=lookup,
        payload=payload,
    )
    if args.diff:
        result["changes"] = preview["changes"]
    return result


def _run_typed_command(args: argparse.Namespace, config: AppConfig, client: NetBoxClient) -> Any:
    spec = RESOURCE_SPECS[args.command]
    action = args.typed_action

    if action == "list":
        filters = parse_key_value_pairs(args.filter, "--filter")
        limit = None if args.all else args.limit
        offset = None if args.all and args.offset == 0 else args.offset
        if args.count:
            return {
                "resource": spec.resource,
                "count": client.count(resource=spec.resource, search=args.search, filters=filters),
            }
        return client.query(
            spec.resource,
            search=args.search,
            filters=filters,
            limit=limit,
            offset=offset,
            brief=args.brief,
            fields=args.field,
            exclude=args.exclude,
            ordering=args.ordering,
        )

    if action == "show":
        return client.get(spec.resource, record_id=args.id, lookup=_build_lookup(args))

    if action == "create":
        payload = collect_payload(spec, args, client)
        validate_payload(spec, payload, for_create=True)
        require_confirmation(yes=args.yes, dry_run=args.dry_run, action=f"{spec.command_name} create")
        if args.dry_run:
            return {"dry_run": True, "resource": spec.resource, "payload": payload}
        _require_token(config)
        return client.create(spec.resource, payload)

    if action == "update":
        payload = collect_payload(spec, args, client)
        validate_payload(spec, payload, for_create=False)
        require_confirmation(yes=args.yes, dry_run=args.dry_run, action=f"{spec.command_name} update")
        lookup = _build_lookup(args)
        preview = client.preview_update(spec.resource, record_id=args.id, lookup=lookup, payload=payload)
        if args.dry_run:
            return {"dry_run": True, **preview}
        _require_token(config)
        result = client.update(spec.resource, record_id=args.id, lookup=lookup, payload=payload)
        if args.diff:
            result["changes"] = preview["changes"]
        return result

    if action == "delete":
        require_confirmation(yes=args.yes, dry_run=args.dry_run, action=f"{spec.command_name} delete")
        lookup = _build_lookup(args)
        if args.dry_run:
            return {"dry_run": True, "resource": spec.resource, "lookup": lookup, "id": args.id}
        _require_token(config)
        return client.delete(spec.resource, record_id=args.id, lookup=lookup)

    if action == "allocate-ip" and spec.command_name == "prefix":
        require_confirmation(yes=args.yes, dry_run=args.dry_run, action="prefix allocate-ip")
        base_payload = load_json_data(args.data) or {}
        if base_payload and not isinstance(base_payload, dict):
            raise ValidationError("--data must be a JSON object for allocate-ip")
        payload = dict(base_payload)
        if args.status:
            payload["status"] = args.status
        if args.dns_name:
            payload["dns_name"] = args.dns_name
        if args.description:
            payload["description"] = args.description
        if args.dry_run:
            return {
                "dry_run": True,
                "resource": spec.resource,
                "lookup": _build_lookup(args),
                "id": args.id,
                "count": args.count,
                "payload": payload,
            }
        _require_token(config)
        return client.allocate_available_ips(
            record_id=args.id,
            lookup=_build_lookup(args),
            count=args.count,
            payload=payload,
        )

    if action == "allocate-prefix" and spec.command_name == "prefix":
        require_confirmation(yes=args.yes, dry_run=args.dry_run, action="prefix allocate-prefix")
        base_payload = load_json_data(args.data) or {}
        if base_payload and not isinstance(base_payload, dict):
            raise ValidationError("--data must be a JSON object for allocate-prefix")
        payload = dict(base_payload)
        payload["prefix_length"] = args.prefix_length
        if args.status:
            payload["status"] = args.status
        if args.description:
            payload["description"] = args.description
        if args.dry_run:
            return {
                "dry_run": True,
                "resource": spec.resource,
                "lookup": _build_lookup(args),
                "id": args.id,
                "count": args.count,
                "payload": payload,
            }
        _require_token(config)
        return client.allocate_available_prefixes(
            record_id=args.id,
            lookup=_build_lookup(args),
            count=args.count,
            payload=payload,
        )

    if action == "assign-interface" and spec.command_name == "ip-address":
        require_confirmation(yes=args.yes, dry_run=args.dry_run, action="ip-address assign-interface")
        lookup = _build_lookup(args)
        if args.dry_run:
            return {
                "dry_run": True,
                "resource": spec.resource,
                "lookup": lookup,
                "id": args.id,
                "device": args.device,
                "interface": args.interface,
                "vm": args.vm,
                "vm_interface": args.vm_interface,
            }
        _require_token(config)
        return client.assign_ip_address(
            record_id=args.id,
            lookup=lookup,
            device=args.device,
            interface=args.interface,
            vm=args.vm,
            vm_interface=args.vm_interface,
        )

    raise NBCLIError(f"unsupported typed action: {spec.command_name} {action}")


def run_command(args: argparse.Namespace, config: AppConfig, client: NetBoxClient) -> Any:
    if args.command == "version":
        return {"version": __version__}
    if args.command == "help":
        return get_help_topic(args.topics)

    _require_connection(config)

    if args.command == "status":
        return client.status()
    if args.command == "openapi":
        return client.openapi()
    if args.command == "resources":
        return client.list_resources(search=args.search)
    if args.command == "schema":
        return client.schema(args.resource)
    if args.command == "choices":
        return client.choices(args.resource)
    if args.command == "query":
        filters = parse_key_value_pairs(args.filter, "--filter")
        limit = None if args.all else args.limit
        offset = None if args.all and args.offset == 0 else args.offset
        if args.count:
            return {
                "resource": args.resource,
                "count": client.count(resource=args.resource, search=args.search, filters=filters),
            }
        return client.query(
            args.resource,
            search=args.search,
            filters=filters,
            limit=limit,
            offset=offset,
            brief=args.brief,
            fields=args.field,
            exclude=args.exclude,
            ordering=args.ordering,
        )
    if args.command == "get":
        return client.get(args.resource, record_id=args.id, lookup=_build_lookup(args))
    if args.command == "create":
        payload = load_json_data(args.data)
        require_confirmation(yes=args.yes, dry_run=args.dry_run, action="create")
        if args.dry_run:
            return {"dry_run": True, "resource": args.resource, "payload": payload}
        _require_token(config)
        return client.create(args.resource, payload)
    if args.command == "update":
        return _run_generic_update(args, config, client)
    if args.command == "delete":
        require_confirmation(yes=args.yes, dry_run=args.dry_run, action="delete")
        lookup = _build_lookup(args)
        if args.dry_run:
            return {"dry_run": True, "resource": args.resource, "id": args.id, "lookup": lookup}
        _require_token(config)
        return client.delete(args.resource, record_id=args.id, lookup=lookup)
    if args.command == "bulk-update":
        payload = load_json_data(args.data)
        if not isinstance(payload, list):
            raise ValidationError("bulk-update --data must be a JSON array")
        require_confirmation(yes=args.yes, dry_run=args.dry_run, action="bulk-update")
        if args.dry_run:
            return {"dry_run": True, "resource": args.resource, "payload": payload}
        _require_token(config)
        return client.bulk_update(args.resource, payload)
    if args.command == "bulk-delete":
        if args.data:
            raw = load_json_data(args.data)
            if not isinstance(raw, list):
                raise ValidationError("bulk-delete --data must be a JSON array of {\"id\":N} objects")
            ids = [item["id"] for item in raw if isinstance(item, dict) and "id" in item]
        elif getattr(args, "ids", None):
            ids = args.ids
        else:
            raise ValidationError("bulk-delete requires --id or --data")
        require_confirmation(yes=args.yes, dry_run=args.dry_run, action="bulk-delete")
        if args.dry_run:
            return {"dry_run": True, "resource": args.resource, "ids": ids}
        _require_token(config)
        return client.bulk_delete(args.resource, ids)
    if args.command == "request":
        method = args.method.upper()
        payload = load_json_data(args.data) if args.data is not None else None
        if method not in {"GET", "HEAD", "OPTIONS"}:
            require_confirmation(yes=args.yes, dry_run=args.dry_run, action=f"request {method}")
        params = parse_key_value_pairs(args.query, "--query")
        if args.dry_run:
            return {
                "dry_run": True,
                "method": method,
                "path": args.path,
                "params": params,
                "payload": payload,
            }
        if method not in {"GET", "HEAD", "OPTIONS"}:
            _require_token(config)
        return client.request(method, args.path, params=params, payload=payload)
    if args.command in RESOURCE_SPECS:
        return _run_typed_command(args, config, client)
    raise NBCLIError(f"unsupported command: {args.command}")


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: Any | None = None,
    stderr: Any | None = None,
    client_factory: Any = NetBoxClient,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args)
        client = client_factory(config)
        result = run_command(args, config, client)
        _print(stdout, success_envelope(_command_label(args), result), args.format)
        return 0
    except NBCLIError as exc:
        _print(stderr, error_envelope(exc.to_payload()), args.format)
        if args.debug:
            traceback.print_exc(file=stderr)
        return exc.exit_code
    except Exception as exc:  # pragma: no cover - fallback path
        error = NBCLIError(str(exc))
        _print(stderr, error_envelope(error.to_payload()), args.format)
        if args.debug:
            traceback.print_exc(file=stderr)
        return error.exit_code
