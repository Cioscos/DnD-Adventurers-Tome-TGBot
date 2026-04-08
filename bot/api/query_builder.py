"""Dynamic GraphQL query builder.

Generates list, detail, and sub-list queries from introspected
:class:`~bot.schema.types.TypeInfo` metadata so that **no** query
strings need to be hard-coded.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bot.schema.types import TypeInfo

if TYPE_CHECKING:
    from bot.schema.registry import SchemaRegistry

# Extra scalar fields included in *list* queries for badge display.
_LIST_BADGE_FIELDS = frozenset(
    ("level", "challenge_rating", "hit_die", "size", "type")
)

_DETAIL_DEPTH = 2  # recursion limit for detail field expansion

# Fields excluded from ALL generated queries due to API compatibility issues.
# Key: (TypeName, field_name)
#
# The DnD 5e 2014 API uses `desc` with conflicting GraphQL types across different
# types that appear as union members in the same query.  When two or more union
# members (e.g. Equipment and Skill inside ProficiencyReference) both have a
# `desc` field but with different nullability ([String!] vs [String!]!), the
# server rejects the query with HTTP 400 ("Fields desc conflict because they
# return conflicting types").  Excluding the outlier types from generated queries
# removes the conflict while still fetching desc in direct (non-union) queries.
#
# AbilityScore.desc is also excluded because the API returns null for it despite
# declaring it [String!]! (server bug), which causes partial-error warnings.
_FIELD_EXCLUSIONS: frozenset[tuple[str, str]] = frozenset({
    # [String!]! but the API server returns null → partial-error warning.
    # Also a conflict source when AbilityScore appears inside union fragments.
    ("AbilityScore", "desc"),
    # [String!] (nullable list) while all other desc-list fields are [String!]!
    # — the sole outlier in the ProficiencyReference union, causing HTTP 400.
    ("Equipment", "desc"),
    # [String!]! but the API server returns null for DamageType items that
    # appear nested inside Monster actions — causes partial-error warnings.
    ("DamageType", "desc"),
})


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def build_list_query(ti: TypeInfo, reg: "SchemaRegistry") -> str:
    """Build a query that fetches a paginated (or full) list of items."""
    field = ti.list_query_field
    if not field:
        raise ValueError(f"No list query field for {ti.name}")

    vars_decl = ""
    vars_use = ""
    if ti.has_pagination:
        vars_decl = "($skip: Int, $limit: Int)"
        vars_use = "(skip: $skip, limit: $limit)"

    if ti.kind == "UNION":
        inner = _union_fragments(ti, reg, fields=("index", "name"))
    else:
        lines = ["    index", "    name"]
        for fname in _LIST_BADGE_FIELDS:
            fi = ti.fields.get(fname)
            if fi and fi.is_scalar:
                lines.append(f"    {fname}")
        inner = "\n".join(lines)

    return f"query{vars_decl} {{\n  {field}{vars_use} {{\n{inner}\n  }}\n}}"


def build_detail_query(ti: TypeInfo, reg: "SchemaRegistry") -> str:
    """Build a query that fetches all relevant fields for a single item."""
    field = ti.detail_query_field
    if not field:
        raise ValueError(f"No detail query field for {ti.name}")

    if ti.kind == "UNION":
        inner = "    __typename\n" + _detail_union(ti, reg, _DETAIL_DEPTH)
    else:
        inner = _build_fields(ti, reg, _DETAIL_DEPTH, indent=4, _expand_nav=True)

    return f"query($index: String!) {{\n  {field}(index: $index) {{\n{inner}\n  }}\n}}"


def build_sub_list_query(
    parent_ti: TypeInfo,
    field_name: str,
    reg: "SchemaRegistry",
    concrete_type: str = "",
) -> str:
    """Build a query that fetches a nested sub-list from a parent item.

    For union parents (e.g. ``AnyEquipment``) *concrete_type* must be the
    specific member type that owns *field_name* (e.g. ``"Weapon"``).
    """
    detail_field = parent_ti.detail_query_field
    if not detail_field:
        raise ValueError(f"No detail query field for parent {parent_ti.name}")

    fi = (parent_ti.fields if parent_ti.kind != "UNION" else {}).get(field_name)

    # Determine the element type for the sub-list
    sub_type_name = fi.type_name if fi else None
    sub_ti = reg.get_type(sub_type_name) if sub_type_name else None

    # Build the sub-field's inner selection
    sub_inner = _sub_list_inner(sub_ti, reg)

    if parent_ti.kind == "UNION" and concrete_type:
        inner = f"    ... on {concrete_type} {{\n      {field_name} {{\n{sub_inner}\n      }}\n    }}"
    else:
        inner = f"    {field_name} {{\n{sub_inner}\n    }}"

    return f"query($index: String!) {{\n  {detail_field}(index: $index) {{\n{inner}\n  }}\n}}"


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _sub_list_inner(sub_ti: TypeInfo | None, reg: "SchemaRegistry") -> str:
    """Selection set for items inside a sub-list."""
    prefix = "        "
    if sub_ti is None:
        return f"{prefix}index\n{prefix}name"

    if sub_ti.kind == "UNION" and sub_ti.possible_types:
        frags = []
        for pt_name in sub_ti.possible_types:
            pt = reg.get_type(pt_name)
            if pt:
                extras = _badge_extras(pt)
                extra_str = " " + " ".join(extras) if extras else ""
                frags.append(f"{prefix}... on {pt_name} {{ index name{extra_str} }}")
        return "\n".join(frags)

    lines = [f"{prefix}index", f"{prefix}name"]
    for fname in _LIST_BADGE_FIELDS:
        fi = sub_ti.fields.get(fname)
        if fi and fi.is_scalar:
            lines.append(f"{prefix}{fname}")
    return "\n".join(lines)


def _badge_extras(ti: TypeInfo) -> list[str]:
    extras = []
    for fname in _LIST_BADGE_FIELDS:
        fi = ti.fields.get(fname)
        if fi and fi.is_scalar:
            extras.append(fname)
    return extras


def _union_fragments(
    ti: TypeInfo,
    reg: "SchemaRegistry",
    fields: tuple[str, ...] = ("index", "name"),
) -> str:
    """Build ``... on TypeName { field1 field2 }`` for each union member."""
    frags = []
    joined = " ".join(fields)
    for pt_name in ti.possible_types:
        frags.append(f"    ... on {pt_name} {{ {joined} }}")
    return "\n".join(frags)


def _detail_union(
    ti: TypeInfo,
    reg: "SchemaRegistry",
    depth: int,
) -> str:
    """Build full fragments for every union member (used in detail queries)."""
    frags = []
    for pt_name in ti.possible_types:
        pt = reg.get_type(pt_name)
        if pt:
            # Top-level union members expand navigable fields (for 📂 buttons)
            inner = _build_fields(pt, reg, depth, indent=6, _expand_nav=True)
            if inner.strip():
                frags.append(f"    ... on {pt_name} {{\n{inner}\n    }}")
    return "\n".join(frags)


def _build_fields(
    ti: TypeInfo,
    reg: "SchemaRegistry",
    depth: int,
    indent: int = 4,
    _seen: frozenset[str] | None = None,
    _expand_nav: bool = True,
) -> str:
    """Recursively emit field selections for *ti*.

    * Scalar/enum fields are always included.
    * Navigable list fields get ``{ index name }`` **only** when
      *_expand_nav* is True (top-level).  Nested types skip them to
      keep the query small.
    * Other object/union fields are expanded up to *depth* levels.
    * At ``depth == 0`` object fields still get their scalar children.
    * *_seen* guards against infinite recursion on self-referential types.
    """
    if _seen is None:
        _seen = frozenset()
    if ti.name in _seen:
        return ""
    _seen = _seen | {ti.name}

    prefix = " " * indent
    lines: list[str] = []

    for fi in ti.fields.values():
        if fi.name == "updated_at":
            continue

        # ---- Scalars / enums ----
        if fi.type_kind in ("SCALAR", "ENUM"):
            if (ti.name, fi.name) not in _FIELD_EXCLUSIONS:
                lines.append(f"{prefix}{fi.name}")
            continue

        # ---- Navigable list fields ----
        if fi.name in ti.navigable_fields:
            if _expand_nav:
                lines.append(f"{prefix}{fi.name} {{ index name }}")
            # When not expanding nav, skip entirely (avoid bloating nested queries)
            continue

        ref = reg.get_type(fi.type_name)
        if ref is None:
            continue

        # ---- Union fields ----
        if fi.type_kind == "UNION":
            _emit_union(lines, prefix, fi.name, ref, reg, depth, _seen)
            continue

        # ---- Object / Interface fields ----
        if fi.type_kind in ("OBJECT", "INTERFACE"):
            if depth > 0:
                sub = _build_fields(ref, reg, depth - 1, indent + 2, _seen, _expand_nav=False)
                if sub.strip():
                    lines.append(f"{prefix}{fi.name} {{\n{sub}\n{prefix}}}")
            else:
                # Leaf expansion: scalar children only
                scalars = _scalar_names(ref)
                if scalars:
                    lines.append(f"{prefix}{fi.name} {{ {' '.join(scalars)} }}")

    return "\n".join(lines)


def _emit_union(
    lines: list[str],
    prefix: str,
    field_name: str,
    ref: TypeInfo,
    reg: "SchemaRegistry",
    depth: int,
    _seen: frozenset[str],
) -> None:
    if not ref.possible_types:
        return
    parts = [f"{prefix}{field_name} {{"]
    parts.append(f"{prefix}  __typename")
    for pt_name in ref.possible_types:
        pt = reg.get_type(pt_name)
        if pt is None:
            continue
        if depth > 0:
            sub = _build_fields(pt, reg, depth - 1, len(prefix) + 4, _seen, _expand_nav=False)
            if sub.strip():
                parts.append(f"{prefix}  ... on {pt_name} {{")
                parts.append(sub)
                parts.append(f"{prefix}  }}")
        else:
            scalars = _scalar_names(pt)
            if scalars:
                parts.append(
                    f"{prefix}  ... on {pt_name} {{ {' '.join(scalars)} }}"
                )
    parts.append(f"{prefix}}}")
    lines.append("\n".join(parts))


def _scalar_names(ti: TypeInfo) -> list[str]:
    """Return the names of all scalar/enum fields, excluding updated_at and any
    field listed in *_FIELD_EXCLUSIONS* for this type."""
    return [
        fi.name
        for fi in ti.fields.values()
        if fi.type_kind in ("SCALAR", "ENUM")
        and fi.name != "updated_at"
        and (ti.name, fi.name) not in _FIELD_EXCLUSIONS
    ]
