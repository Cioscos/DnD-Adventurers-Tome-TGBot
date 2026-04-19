"""GraphQL introspection query and result parser.

Sends a single ``__schema`` query to the D&D 5e GraphQL API and converts
the raw JSON into :class:`~bot.schema.types.TypeInfo` objects.
"""

from __future__ import annotations

import logging
from typing import Any

from bot.schema.types import FieldInfo, TypeInfo

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Introspection query — fetches every type, its fields, and root query args.
# We need 4 levels of ``ofType`` nesting to fully unwrap NON_NULL<LIST<…>>.
# ---------------------------------------------------------------------------
INTROSPECTION_QUERY = """
{
  __schema {
    queryType {
      fields {
        name
        args { name }
        type {
          name kind
          ofType {
            name kind
            ofType {
              name kind
              ofType { name kind }
            }
          }
        }
      }
    }
    types {
      name kind
      fields {
        name
        type {
          name kind
          ofType {
            name kind
            ofType {
              name kind
              ofType { name kind }
            }
          }
        }
      }
      possibleTypes { name }
    }
  }
}
"""


# ---------------------------------------------------------------------------
# Type-wrapper resolver
# ---------------------------------------------------------------------------

def resolve_type(
    type_obj: dict[str, Any] | None,
) -> tuple[str, str, bool, bool]:
    """Unwrap ``NON_NULL`` / ``LIST`` wrappers to find the base type.

    Returns ``(type_name, type_kind, is_list, is_non_null)``.
    """
    is_list = False
    is_non_null = False
    t = type_obj
    while t:
        kind = t.get("kind")
        if kind == "NON_NULL":
            is_non_null = True
            t = t.get("ofType")
        elif kind == "LIST":
            is_list = True
            t = t.get("ofType")
        else:
            return (
                t.get("name") or "Unknown",
                kind or "UNKNOWN",
                is_list,
                is_non_null,
            )
    return "Unknown", "UNKNOWN", is_list, is_non_null


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_introspection(
    schema_data: dict[str, Any],
) -> tuple[dict[str, TypeInfo], list[dict[str, Any]]]:
    """Convert raw ``__schema`` JSON into a *type_map* and *root_fields*.

    Returns ``(type_map, root_fields)`` where *type_map* maps type names
    to :class:`TypeInfo` and *root_fields* is the list of raw root query
    field dicts (used later by the registry to set list/detail mappings).
    """
    type_map: dict[str, TypeInfo] = {}

    for raw_type in schema_data.get("types", []):
        name = raw_type.get("name", "")
        if name.startswith("__"):
            continue

        kind = raw_type.get("kind", "")
        ti = TypeInfo(name=name, kind=kind)

        for raw_field in raw_type.get("fields") or []:
            fname = raw_field.get("name", "")
            if fname.startswith("__"):
                continue
            type_name, type_kind, is_list, is_non_null = resolve_type(
                raw_field.get("type"),
            )
            ti.fields[fname] = FieldInfo(
                name=fname,
                type_name=type_name,
                type_kind=type_kind,
                is_list=is_list,
                is_non_null=is_non_null,
            )

        for pt in raw_type.get("possibleTypes") or []:
            if pt.get("name"):
                ti.possible_types.append(pt["name"])

        type_map[name] = ti

    root_fields = (
        schema_data.get("queryType", {}).get("fields", [])
    )
    return type_map, root_fields
