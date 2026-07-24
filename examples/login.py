# examples/login.py
"""Log in synchronously without printing secrets."""

from __future__ import annotations

import os

from arvancld import ArvanCloud


def main() -> None:
    with ArvanCloud() as client:
        result = client.auth.login(
            email=os.environ["ARVANCLD_EMAIL"],
            password=os.environ["ARVANCLD_PASSWORD"],
        )

        print(f"Default account: {result.default_account}")
        print(f"Access token expires at: {result.expires_at.isoformat()}")


if __name__ == "__main__":
    main()
