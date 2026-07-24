# arvancld

`arvancld` is a typed Python client for ArvanCloud services. The first release
implements account login plus CDN domain listing, DNS record listing, DNS record
creation, DNS record editing, DNS record deletion, and DNS cloud proxy toggling
with synchronous and asynchronous clients.

## Requirements

- Python 3.10 or newer
- `httpx`
- Pydantic v2

## Install from source

```bash
python -m pip install -e .
```

For development:

```bash
python -m pip install -e ".[dev]"
```

## Synchronous login

Set credentials outside your source code:

```bash
export ARVANCLD_EMAIL="you@example.com"
export ARVANCLD_PASSWORD="your-password"
export ARVANCLD_DOMAIN="snapp.ir"
export ARVANCLD_RECORD_ID="00000000-0000-4000-8000-000000000001"
```

PowerShell:

```powershell
$env:ARVANCLD_EMAIL = "you@example.com"
$env:ARVANCLD_PASSWORD = "your-password"
$env:ARVANCLD_DOMAIN = "snapp.ir"
$env:ARVANCLD_RECORD_ID = "00000000-0000-4000-8000-000000000001"
```

Then log in:

```python
import os

from arvancld import ArvanCloud

with ArvanCloud() as client:
    result = client.auth.login(
        email=os.environ["ARVANCLD_EMAIL"],
        password=os.environ["ARVANCLD_PASSWORD"],
    )

    print(result.default_account)
    print(result.expires_at)
```

## CDN domain listing

CDN requests use the access token from a successful login and keep it only in
process memory:

```python
import os

from arvancld import ArvanCloud

with ArvanCloud() as client:
    client.auth.login(
        email=os.environ["ARVANCLD_EMAIL"],
        password=os.environ["ARVANCLD_PASSWORD"],
    )

    domains = client.cdn.domains.list(page=1, per_page=5)
    for domain in domains.data:
        print(domain.domain, domain.status)
```

## CDN DNS record listing

```python
import os

from arvancld import ArvanCloud

with ArvanCloud() as client:
    client.auth.login(
        email=os.environ["ARVANCLD_EMAIL"],
        password=os.environ["ARVANCLD_PASSWORD"],
    )

    records = client.cdn.dns_records.list(
        os.environ["ARVANCLD_DOMAIN"],
        page=1,
        per_page=25,
    )
    for record in records.data:
        print(record.type, record.name, record.ttl)
```

## CDN DNS record creation

```python
import os

from arvancld import ArvanCloud, DNSRecordCreate, DNSRecordIPValue, IPFilterMode

with ArvanCloud() as client:
    client.auth.login(
        email=os.environ["ARVANCLD_EMAIL"],
        password=os.environ["ARVANCLD_PASSWORD"],
    )

    record = client.cdn.dns_records.create(
        "snapp.ir",
        DNSRecordCreate(
            type="A",
            name="sss",
            cloud=True,
            value=[
                DNSRecordIPValue(
                    ip="85.5.5.5",
                    port=None,
                    weight=None,
                    country="",
                )
            ],
            ttl=120,
            upstream_https="default",
            ip_filter_mode=IPFilterMode(
                count="single",
                geo_filter="none",
                order="none",
            ),
        ),
    )
    print(record.id)
```

## CDN DNS cloud proxy toggle

```python
import os

from arvancld import ArvanCloud

with ArvanCloud() as client:
    client.auth.login(
        email=os.environ["ARVANCLD_EMAIL"],
        password=os.environ["ARVANCLD_PASSWORD"],
    )

    record = client.cdn.dns_records.set_cloud(
        os.environ.get("ARVANCLD_DOMAIN", "snapp.ir"),
        os.environ["ARVANCLD_RECORD_ID"],
        cloud=True,
    )
    print(record.cloud)
```

## CDN DNS record editing

```python
import os
from uuid import UUID

from arvancld import ArvanCloud, DNSRecordIPValue, DNSRecordUpdate, IPFilterMode

with ArvanCloud() as client:
    client.auth.login(
        email=os.environ["ARVANCLD_EMAIL"],
        password=os.environ["ARVANCLD_PASSWORD"],
    )

    record = client.cdn.dns_records.update(
        os.environ.get("ARVANCLD_DOMAIN", "snapp.ir"),
        DNSRecordUpdate(
            id=UUID(os.environ["ARVANCLD_RECORD_ID"]),
            type="A",
            name="sss",
            cloud=True,
            value=[
                DNSRecordIPValue(
                    ip=os.environ.get("ARVANCLD_RECORD_IP", "85.5.5.6"),
                    port=None,
                    weight=100,
                    country="",
                )
            ],
            ttl=120,
            upstream_https="default",
            ip_filter_mode=IPFilterMode(
                count="single",
                order="none",
                geo_filter="none",
            ),
        ),
    )
    print(record.updated_at)
```

## CDN DNS record deletion

```python
import os
from uuid import UUID

from arvancld import ArvanCloud

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
```

## Asynchronous login

```python
import asyncio
import os
from uuid import UUID

from arvancld import (
    AsyncArvanCloud,
    DNSRecordCreate,
    DNSRecordIPValue,
    DNSRecordUpdate,
    IPFilterMode,
)


async def main() -> None:
    async with AsyncArvanCloud() as client:
        result = await client.auth.login(
            email=os.environ["ARVANCLD_EMAIL"],
            password=os.environ["ARVANCLD_PASSWORD"],
        )
        print(result.default_account)

        domains = await client.cdn.domains.list(page=1, per_page=5)
        print(f"Domains: {domains.meta.total}")

        records = await client.cdn.dns_records.list(os.environ["ARVANCLD_DOMAIN"])
        print(f"DNS records: {records.meta.total}")

        created = await client.cdn.dns_records.create(
            "snapp.ir",
            DNSRecordCreate(
                type="A",
                name="sss",
                cloud=True,
                value=[DNSRecordIPValue(ip="85.5.5.5", port=None, weight=None, country="")],
                ttl=120,
                upstream_https="default",
                ip_filter_mode=IPFilterMode(count="single", geo_filter="none", order="none"),
            ),
        )
        print(created.id)

        updated = await client.cdn.dns_records.update(
            os.environ.get("ARVANCLD_DOMAIN", "snapp.ir"),
            DNSRecordUpdate(
                id=UUID(os.environ["ARVANCLD_RECORD_ID"]),
                type="A",
                name="sss",
                cloud=True,
                value=[DNSRecordIPValue(ip="85.5.5.6", port=None, weight=100, country="")],
                ttl=120,
                upstream_https="default",
                ip_filter_mode=IPFilterMode(count="single", order="none", geo_filter="none"),
            ),
        )
        print(updated.updated_at)

        deleted = await client.cdn.dns_records.delete(
            os.environ.get("ARVANCLD_DOMAIN", "snapp.ir"),
            os.environ["ARVANCLD_RECORD_ID"],
        )
        print(deleted.message)

        proxied = await client.cdn.dns_records.set_cloud(
            os.environ.get("ARVANCLD_DOMAIN", "snapp.ir"),
            os.environ["ARVANCLD_RECORD_ID"],
            cloud=False,
        )
        print(proxied.cloud)


asyncio.run(main())
```

## Configuration

Both clients accept these keyword arguments:

- `auth_base_url`: defaults to `https://dejban.arvancloud.ir`
- `cdn_base_url`: defaults to `https://napi.arvancloud.ir/cdn/4.0`
- `redirect_uri`: defaults to `https://panel.arvancloud.ir/`
- `timeout`: request timeout in seconds, defaulting to `30.0`
- `user_agent`: defaults to `arvancld/0.1.0`

The library sends a normal SDK user agent and does not imitate browser
fingerprints or send browser-only security headers.

## Credential handling

- Passwords are used only to construct the login request and are not retained.
- Access and refresh tokens are held in memory at `client.auth.tokens`.
- CDN listing calls use the in-memory access token from `client.auth.tokens`.
- CDN create calls use the same in-memory access token and do not persist new
  credentials.
- CDN edit calls use the same in-memory access token and do not persist new
  credentials.
- CDN delete calls use the same in-memory access token and do not persist new
  credentials.
- CDN cloud proxy toggles use the same in-memory access token and do not persist
  new credentials.
- Token fields are excluded from model representations.
- Tokens are not written to disk and refresh is not implemented until the
  refresh endpoint contract is known.
- API exceptions do not include request bodies, passwords, or token values.

## Development

```bash
python -m ruff check .
python -m pytest
```

Tests mock all HTTP traffic. They do not contact ArvanCloud or require real
credentials.
