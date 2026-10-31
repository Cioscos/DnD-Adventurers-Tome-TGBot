"""Split the SRD catalogue into translation batches and merge Italian results back.

    uv run python scripts/srd_translation_batches.py split --out DIR [--size 40]
    uv run python scripts/srd_translation_batches.py merge --in DIR

Batch file ``DIR/<kind>-NNN.json``: ``[{"index": ..., "fields": {"traits.2.name": "<en>"}}]``.
Translated file ``DIR/<kind>-NNN.it.json`` has the same shape with Italian values.
Scope (spec decision 15): everything for non-monsters; monsters get name and
trait/action names always, trait/action desc only for beasts or CR <= 2.
"""
import argparse
import json
import re
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "webapp" / "src" / "data" / "srd"
KINDS = ["spells", "magic-items", "equipment", "races", "backgrounds", "feats", "monsters"]


def _walk(node, path):
    """Yield (dotted path, {"en": ...} container) for every localizable leaf."""
    if isinstance(node, dict):
        if isinstance(node.get("en"), str):
            yield path, node
            return
        for k, v in node.items():
            yield from _walk(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}.{i}" if path else str(i))


def _in_scope(kind: str, item: dict, path: str) -> bool:
    if kind != "monsters":
        return True
    if path == "name" or path.endswith(".name"):
        return True
    return item.get("type") == "beast" or (item.get("challenge_rating") or 0) <= 2


def scoped_fields(kind: str, item: dict) -> dict:
    """path -> container dict for the in-scope localizable fields of one item."""
    return {p: c for p, c in _walk(item, "") if _in_scope(kind, item, p)}


def load(kind: str, data_dir: Path = DATA_DIR) -> dict:
    return json.loads((data_dir / f"{kind}.json").read_text(encoding="utf-8"))


def save(kind: str, doc: dict, data_dir: Path = DATA_DIR) -> None:
    text = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
    (data_dir / f"{kind}.json").write_text(text, encoding="utf-8", newline="\n")


def split(out: Path, size: int = 40, data_dir: Path = DATA_DIR) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    stats = {}
    for kind in KINDS:
        entries = []
        for item in load(kind, data_dir)["items"]:
            fields = {p: c["en"] for p, c in scoped_fields(kind, item).items() if "it" not in c}
            if fields:
                entries.append({"index": item["index"], "fields": fields})
        files = chars = 0
        for n, start in enumerate(range(0, len(entries), size), 1):
            batch = entries[start:start + size]
            (out / f"{kind}-{n:03d}.json").write_text(
                json.dumps(batch, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
            files += 1
            chars += sum(len(v) for e in batch for v in e["fields"].values())
        stats[kind] = (files, chars)
    return stats


def merge(src: Path, data_dir: Path = DATA_DIR) -> int:
    done = 0
    docs = {}
    for f in sorted(src.glob("*.it.json")):
        m = re.fullmatch(r"(.+)-\d{3}\.it\.json", f.name)
        if not m or m.group(1) not in KINDS:
            raise SystemExit(f"unrecognised translation file: {f.name}")
        kind = m.group(1)
        doc = docs.setdefault(kind, load(kind, data_dir))
        by_index = {i["index"]: i for i in doc["items"]}
        for entry in json.loads(f.read_text(encoding="utf-8")):
            item = by_index.get(entry["index"])
            if item is None:
                raise SystemExit(f"{f.name}: unknown index {entry['index']!r}")
            allowed = scoped_fields(kind, item)
            for path, value in entry["fields"].items():
                if path not in allowed:
                    raise SystemExit(f"{f.name}: {entry['index']}: unknown or out-of-scope path {path!r}")
                if not isinstance(value, str) or not value.strip():
                    raise SystemExit(f"{f.name}: {entry['index']}: empty translation for {path!r}")
                allowed[path]["it"] = value
                done += 1
    for kind, doc in docs.items():
        save(kind, doc, data_dir)
    return done


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("split")
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--size", type=int, default=40)
    m = sub.add_parser("merge")
    m.add_argument("--in", dest="src", type=Path, required=True)
    args = ap.parse_args()
    if args.cmd == "split":
        stats = split(args.out, args.size)
        for kind, (files, chars) in stats.items():
            print(f"{kind}: {files} files, {chars} chars")
        print(f"total: {sum(f for f, _ in stats.values())} files, {sum(c for _, c in stats.values())} chars")
    else:
        print(f"merged {merge(args.src)} fields")


if __name__ == "__main__":
    sys.exit(main())
