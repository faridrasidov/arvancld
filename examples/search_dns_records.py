# examples/search_dns_records.py
"""Search CDN DNS records without printing secrets."""

from __future__ import annotations

import os

from arvancld import ArvanCloud


def main() -> None:
    with ArvanCloud() as client:
        client.auth.login(
            email=os.environ["ARVANCLD_EMAIL"],
            password=os.environ["ARVANCLD_PASSWORD"],
        )

        page = client.cdn.dns_records.list(
            os.environ.get("ARVANCLD_DOMAIN", "snapp.ir"),
            search=os.environ["ARVANCLD_DNS_SEARCH"],
            match_type=os.environ.get("ARVANCLD_DNS_MATCH_TYPE", "exact"),
            record_types=[os.environ.get("ARVANCLD_DNS_RECORD_TYPE", "aaaa")],
            page=1,
            per_page=100,
        )

        for record in page.data:
            print(f"{record.type}\t{record.name}\t{record.ttl}")


if __name__ == "__main__":
    main()
