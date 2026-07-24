# examples/create_dns_record.py
"""Create a CDN DNS record without printing secrets."""

from __future__ import annotations

import os

from arvancld import ArvanCloud, DNSRecordCreate, DNSRecordIPValue, IPFilterMode


def main() -> None:
    with ArvanCloud() as client:
        client.auth.login(
            email=os.environ["ARVANCLD_EMAIL"],
            password=os.environ["ARVANCLD_PASSWORD"],
        )

        record = client.cdn.dns_records.create(
            os.environ.get("ARVANCLD_DOMAIN", "snapp.ir"),
            DNSRecordCreate(
                type="A",
                name=os.environ.get("ARVANCLD_RECORD_NAME", "sss"),
                cloud=True,
                value=[
                    DNSRecordIPValue(
                        ip=os.environ.get("ARVANCLD_RECORD_IP", "85.5.5.5"),
                        port=None,
                        weight=None,
                        country="",
                    )
                ],
                ttl=int(os.environ.get("ARVANCLD_RECORD_TTL", "120")),
                upstream_https="default",
                ip_filter_mode=IPFilterMode(
                    count="single",
                    geo_filter="none",
                    order="none",
                ),
            ),
        )

        print(f"Created DNS record: {record.id}")


if __name__ == "__main__":
    main()
