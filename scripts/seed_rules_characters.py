"""Crea i personaggi `[prova]` per le regole di classe. Solo sul DB locale di sviluppo."""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")


def main() -> int:
    db_path = Path(os.environ.get("DB_PATH", "data/dnd_bot.db"))
    if (ROOT / db_path).resolve() != (ROOT / "data" / "dnd_bot.db").resolve():
        print(f"Rifiuto: DB_PATH={db_path} non è il DB locale data/dnd_bot.db")
        return 1
    if not os.environ.get("DEV_USER_ID"):
        print("Rifiuto: manca DEV_USER_ID nel .env")
        return 1
    os.chdir(ROOT)
    from core.db.engine import AsyncSessionLocal, init_db  # dopo load_dotenv: l'engine legge DB_PATH
    from core.rules.sample_characters import seed_rules_characters

    async def run() -> int:
        await init_db()
        async with AsyncSessionLocal() as session:
            n = await seed_rules_characters(session, int(os.environ["DEV_USER_ID"]))
            await session.commit()
            return n

    print(f"Personaggi creati: {asyncio.run(run())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
