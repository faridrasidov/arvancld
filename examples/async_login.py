# examples/async_login.py
"""Log in asynchronously without printing secrets."""

from __future__ import annotations

import asyncio
import os

from arvancld import AsyncArvanCloud


async def main() -> None:
    async with AsyncArvanCloud() as client:
        result = await client.auth.login(
            email=os.environ["ARVANCLD_EMAIL"],
            password=os.environ["ARVANCLD_PASSWORD"],
        )

        print(f"Default account: {result.default_account}")
        print(f"Access token expires at: {result.expires_at.isoformat()}")


if __name__ == "__main__":
    asyncio.run(main())
