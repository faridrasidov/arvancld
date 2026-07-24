# examples/set_dns_record_cloud.py
"""Turn a CDN DNS record cloud proxy on or off without printing secrets."""

from __future__ import annotations

import os

from arvancld import ArvanCloud


def _read_cloud_flag() -> bool:
    value = os.environ.get("ARVANCLD_CLOUD", "true").strip().lower()
    return value in {"1", "true", "yes", "on"}


def main() -> None:
    with ArvanCloud() as client:
        client.auth.login(
            email=os.environ["ARVANCLD_EMAIL"],
            password=os.environ["ARVANCLD_PASSWORD"],
        )

        record = client.cdn.dns_records.set_cloud(
            os.environ.get("ARVANCLD_DOMAIN", "snapp.ir"),
            os.environ["ARVANCLD_RECORD_ID"],
            cloud=_read_cloud_flag(),
        )

        print(f"DNS record cloud proxy: {record.cloud}")


if __name__ == "__main__":
    main()
