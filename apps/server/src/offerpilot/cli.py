import argparse
import asyncio
import getpass

from sqlalchemy import select

from offerpilot.infrastructure.config import settings
from offerpilot.infrastructure.db import Session
from offerpilot.modules.identity.models import ModelConsent, User
from offerpilot.modules.identity.schemas import Credentials
from offerpilot.modules.identity.service import register


async def run(command: str, username: str | None, admin: bool) -> None:
    cfg = settings()
    if command == "create-user":
        if not username:
            raise SystemExit("--username is required")
        password = getpass.getpass("Password (at least 10 characters): ")
        async with Session() as db:
            await register(db, Credentials(username=username, password=password), admin)
        print("Account created")
    elif command == "seed-demo":
        if cfg.environment == "production" or cfg.app_mode != "demo":
            raise SystemExit("seed-demo requires APP_MODE=demo and non-production")
        for name in ["demo", "demo_other"]:
            async with Session() as db:
                user = await db.scalar(select(User).where(User.username == name))
                if not user:
                    user = await register(
                        db,
                        Credentials(username=name, password="offerpilot-demo-2026"),
                        name == "demo",
                    )
                    db.add(ModelConsent(owner_id=user.id, granted=False, version=1))
                    await db.commit()
        print("Explicit synthetic accounts: demo / demo_other; password: offerpilot-demo-2026")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["create-user", "seed-demo"])
    parser.add_argument("--username")
    parser.add_argument("--admin", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.command, args.username, args.admin))


if __name__ == "__main__":
    main()
