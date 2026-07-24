# examples/update_dns_record.py
"""Update a CDN DNS record without printing secrets."""

from __future__ import annotations

import os
from uuid import UUID

from arvancld import ArvanCloud, DNSRecordIPValue, DNSRecordUpdate, IPFilterMode


def main() -> None:
    with ArvanCloud() as client:
        client.auth.login(
            email=os.environ["ARVANCLD_EMAIL"],
            password=os.environ["ARVANCLD_PASSWORD"],
        )

        record = client.cdn.dns_records.update(
            os.environ.get("ARVANCLD_DOMAIN", "snapp.ir"),
            DNSRecordUpdate(
                id=UUID(os.environ["ARVANCLD_RECORD_ID"]),
                type=os.environ.get("ARVANCLD_RECORD_TYPE", "A"),
                name=os.environ.get("ARVANCLD_RECORD_NAME", "sss"),
                cloud=True,
                value=[
                    DNSRecordIPValue(
                        ip=os.environ.get("ARVANCLD_RECORD_IP", "85.5.5.6"),
                        port=None,
                        weight=100,
                        country="",
                    )
                ],
                ttl=int(os.environ.get("ARVANCLD_RECORD_TTL", "120")),
                upstream_https="default",
                ip_filter_mode=IPFilterMode(
                    count="single",
                    order="none",
                    geo_filter="none",
                ),
            ),
        )

        print(f"Updated DNS record: {record.id}")


if __name__ == "__main__":
    main()
