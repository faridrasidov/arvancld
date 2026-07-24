# examples/delete_dns_record.py
"""Delete a CDN DNS record without printing secrets."""

from __future__ import annotations

import os
from uuid import UUID

from arvancld import ArvanCloud


def main() -> None:
    with ArvanCloud() as client:
        client.auth.login(
            email=os.environ["ARVANCLD_EMAIL"],
            password=os.environ["ARVANCLD_PASSWORD"],
        )

        result = client.cdn.dns_records.delete(
            os.environ.get("ARVANCLD_DOMAIN", "snapp.ir"),
            UUID(os.environ["ARVANCLD_RECORD_ID"]),
        )

        print(result.message)


if __name__ == "__main__":
    main()
