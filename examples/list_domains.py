# examples/list_domains.py
"""List CDN domains without printing secrets."""

from __future__ import annotations

import os

from arvancld import ArvanCloud


def main() -> None:
    with ArvanCloud() as client:
        client.auth.login(
            email=os.environ["ARVANCLD_EMAIL"],
            password=os.environ["ARVANCLD_PASSWORD"],
        )

        page = client.cdn.domains.list(
            page=int(os.environ.get("ARVANCLD_PAGE", "1")),
            per_page=int(os.environ.get("ARVANCLD_PER_PAGE", "5")),
        )

        for domain in page.data:
            print(f"{domain.domain}\t{domain.status}")


if __name__ == "__main__":
    main()
