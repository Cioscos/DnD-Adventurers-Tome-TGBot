"""core/ is shared by api/ and the bot: it must never import from api/."""
import re
from pathlib import Path

CORE = Path(__file__).resolve().parents[2] / "core"
_API_IMPORT = re.compile(r"^\s*(from\s+api[\s.]|import\s+api\b)", re.MULTILINE)


def test_core_has_no_api_imports() -> None:
    offenders = [
        str(p.relative_to(CORE)) for p in CORE.rglob("*.py") if _API_IMPORT.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == []
