# examples/async_session_domains.py
"""List CDN domains asynchronously using an explicit local JSON session file."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from arvancld import AsyncArvanCloud, InvalidSessionError, SessionExpiredError


async def main() -> None:
    session_path = Path(os.environ.get("ARVANCLD_SESSION", ".arvancld-session.json"))

    async with AsyncArvanCloud() as client:
        try:
            client.auth.load_session(session_path)
        except (FileNotFoundError, InvalidSessionError, SessionExpiredError):
            await client.auth.login(
                email=os.environ["ARVANCLD_EMAIL"],
                password=os.environ["ARVANCLD_PASSWORD"],
            )
            client.auth.save_session(session_path)

        page = await client.cdn.domains.list(
            page=int(os.environ.get("ARVANCLD_PAGE", "1")),
            per_page=int(os.environ.get("ARVANCLD_PER_PAGE", "5")),
        )

        for domain in page.data:
            print(f"{domain.domain}\t{domain.status}")


if __name__ == "__main__":
    asyncio.run(main())
