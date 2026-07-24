# examples/list_dns_records.py
"""List CDN DNS records without printing secrets."""

from __future__ import annotations

import os

from arvancld import ArvanCloud


def _optional_record_types() -> list[str] | None:
    value = os.environ.get("ARVANCLD_DNS_RECORD_TYPES")
    if value is None or not value.strip():
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> None:
    with ArvanCloud() as client:
        client.auth.login(
            email=os.environ["ARVANCLD_EMAIL"],
            password=os.environ["ARVANCLD_PASSWORD"],
        )

        page = client.cdn.dns_records.list(
            os.environ["ARVANCLD_DOMAIN"],
            page=int(os.environ.get("ARVANCLD_PAGE", "1")),
            per_page=int(os.environ.get("ARVANCLD_PER_PAGE", "25")),
            record_types=_optional_record_types(),
            search=os.environ.get("ARVANCLD_DNS_SEARCH"),
            match_type=os.environ.get("ARVANCLD_DNS_MATCH_TYPE"),
        )

        for record in page.data:
            print(f"{record.type}\t{record.name}\t{record.ttl}")


if __name__ == "__main__":
    main()
