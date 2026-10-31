"""Verify the Italian translation of the SRD catalogue. Exit code 1 if any problem is found."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from srd_translation_batches import DATA_DIR, KINDS, load, scoped_fields  # noqa: E402


def check(data_dir: Path = DATA_DIR) -> list[str]:
    glossary = json.loads((data_dir / "glossary-it.json").read_text(encoding="utf-8"))
    official = {k.casefold(): v for k, v in glossary["official_names"].items()}
    times = glossary["casting_times"]
    durations = glossary["durations"]
    problems = []
    for kind in KINDS:
        for item in load(kind, data_dir)["items"]:
            where = f"{kind}/{item['index']}"
            for path, cont in scoped_fields(kind, item).items():
                it = cont.get("it")
                if not isinstance(it, str) or not it.strip():
                    problems.append(f"{where}: missing it for {path}")
                    continue
                en = cont["en"]
                if path.endswith("name") and en.casefold() in official and it != official[en.casefold()]:
                    problems.append(f"{where}: {path} {it!r} != glossary {official[en.casefold()]!r}")
                if kind == "spells" and path in ("casting_time", "duration"):
                    table = times if path == "casting_time" else durations
                    if it not in table.values():
                        problems.append(f"{where}: {path}.it {it!r} not in glossary")
                    elif en in table and it != table[en]:
                        problems.append(f"{where}: {path} {en!r} -> {it!r}, glossary says {table[en]!r}")
    return problems


if __name__ == "__main__":
    found = check()
    for p in found[:50]:
        print(p)
    print(f"{len(found)} problem(s)")
    sys.exit(1 if found else 0)
