# arvancld: ArvanCloud Python SDK for CDN v4.0 and DNS Records

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Typed: Pydantic v2](https://img.shields.io/badge/typed-Pydantic%20v2-blue)
![HTTP: httpx](https://img.shields.io/badge/http-httpx-blue)

`arvancld` is a typed Python SDK for ArvanCloud account login and the
ArvanCloud CDN v4.0 API. It currently implements authenticated access to CDN
domains and CDN DNS records through `https://napi.arvancloud.ir/cdn/4.0`, with
both synchronous and asynchronous clients.

Use `arvancld` when you need a Python client for ArvanCloud CDN DNS automation:
listing domains, listing DNS records, creating DNS records, editing records,
deleting records, toggling the cloud proxy, and reusing login sessions safely
between local runs.

## Features

- Typed sync client: `ArvanCloud`
- Typed async client: `AsyncArvanCloud`
- Account login, TOTP challenge completion, and token refresh through
  `dejban.arvancloud.ir`
- Explicit JSON session persistence for local token reuse
- ArvanCloud CDN v4.0 domain listing
- ArvanCloud CDN DNS record listing with pagination, type filters, search, and
  match type
- DNS record create, update, delete, and cloud proxy toggle
- Pydantic v2 models with snake-case Python fields and JSON aliases
- Mocked test suite; no live ArvanCloud requests in tests

## Supported ArvanCloud APIs

| SDK area | API host | Implemented operations |
| --- | --- | --- |
| Account auth | `https://dejban.arvancloud.ir` | Login, TOTP challenge, token refresh |
| CDN v4.0 | `https://napi.arvancloud.ir/cdn/4.0` | List domains |
| CDN v4.0 DNS records | `https://napi.arvancloud.ir/cdn/4.0` | List, search, create, update, delete, cloud proxy toggle |

The SDK sends normal functional headers such as `Accept`, `User-Agent`, and
`Authorization`. It does not imitate browser fingerprints or send browser-only
headers such as `Origin`, `Referer`, `Sec-Fetch-*`, `DNT`, or `Sec-GPC`.

## Requirements

- Python 3.10 or newer
- `httpx`
- Pydantic v2

## Installation

Install from source:

```bash
python -m pip install -e .
```

For development:

```bash
python -m pip install -e ".[dev]"
```

## Environment variables

Keep credentials and local test values outside source code:

```bash
export ARVANCLD_EMAIL="you@example.com"
export ARVANCLD_PASSWORD="your-password"
export ARVANCLD_DOMAIN="snapp.ir"
export ARVANCLD_RECORD_ID="00000000-0000-4000-8000-000000000001"
export ARVANCLD_RECORD_IP="85.5.5.6"
export ARVANCLD_SESSION=".arvancld-session.json"
export ARVANCLD_DNS_RECORD_TYPES="a,aaaa,cname"
export ARVANCLD_DNS_RECORD_TYPE="aaaa"
export ARVANCLD_DNS_SEARCH="sss"
export ARVANCLD_DNS_MATCH_TYPE="exact"
```

PowerShell:

```powershell
$env:ARVANCLD_EMAIL = "you@example.com"
$env:ARVANCLD_PASSWORD = "your-password"
$env:ARVANCLD_DOMAIN = "snapp.ir"
$env:ARVANCLD_RECORD_ID = "00000000-0000-4000-8000-000000000001"
$env:ARVANCLD_RECORD_IP = "85.5.5.6"
$env:ARVANCLD_SESSION = ".arvancld-session.json"
$env:ARVANCLD_DNS_RECORD_TYPES = "a,aaaa,cname"
$env:ARVANCLD_DNS_RECORD_TYPE = "aaaa"
$env:ARVANCLD_DNS_SEARCH = "sss"
$env:ARVANCLD_DNS_MATCH_TYPE = "exact"
```

## Certbot DNS-01 helpers

The following scripts automate ACME DNS-01 challenge updates with ArvanCloud DNS.

`generate_ssl.py` and the hook script load `.env` automatically when present in the current
working directory or project root.

Required environment for the hook:

```powershell
$env:ARVANCLD_EMAIL = "you@example.com"
$env:ARVANCLD_PASSWORD = "your-password"
$env:ARVANCLD_SESSION = ".arvancld-session.json"
```

Wildcard and apex certificates use the same ArvanCloud zone. For `*.example.com`
and `example.com`, the hook creates/cleans `_acme-challenge.example.com`
TXT challenge entries using the zone-relative challenge name (`_acme-challenge`).

The hook sends TXT challenge payloads as ArvanCloud DNS API JSON like:

```json
{"type":"TXT","name":"_acme-challenge","cloud":false,"value":{"text":"<token>"},"ttl":120,"upstream_https":null,"ip_filter_mode":null}
```

Supported certificate generation env vars:

```powershell
$env:ARVANCLD_CERTBOT_DOMAINS = "snapp.ir,www.snapp.ir"
$env:ARVANCLD_CERTBOT_KEY_TYPE = "ecdsa"
$env:ARVANCLD_CERTBOT_STAGING = "true"
$env:ARVANCLD_CERTBOT_DRY_RUN = "true"
$env:ARVANCLD_CERTBOT_AGREE_TOS = "true"
```

Optional renew env vars:

```powershell
$env:ARVANCLD_CERTBOT_DEPLOY_HOOK = "python examples/certbot_arvancld_dns_hook.py --mode cleanup"
```

Hook usage (single-domain challenge context):

```bash
python examples/certbot_arvancld_dns_hook.py --mode auth
python examples/certbot_arvancld_dns_hook.py --mode cleanup
```

`CERTBOT_DOMAIN` and `CERTBOT_VALIDATION` are expected by the hook and passed by
Certbot automatically during challenge handling.

The Certbot hook never prompts for a TOTP code. For an MFA-enabled account,
create a valid saved session interactively before running unattended Certbot
automation. If password login reaches an MFA challenge without a valid saved
session, the hook fails with `TOTPRequiredError`.

Issue certificates:

```bash
python examples/generate_ssl.py --domain snapp.ir --domain www.snapp.ir --staging --dry-run --agree-tos --key-type ecdsa
python examples/generate_ssl.py --domain snapp.ir --staging --email ops@example.com
python examples/generate_ssl.py --force
```

Renew certificates:

```bash
python examples/renew_ssl.py --dry-run
python examples/renew_ssl.py --force
python examples/renew_ssl.py --deploy-hook "python examples/certbot_arvancld_dns_hook.py --mode cleanup"
```

## Quickstart: login and list CDN domains

```python
import getpass
import os

from arvancld import ArvanCloud, TOTPRequiredError

with ArvanCloud() as client:
    try:
        result = client.auth.login(
            email=os.environ["ARVANCLD_EMAIL"],
            password=os.environ["ARVANCLD_PASSWORD"],
        )
    except TOTPRequiredError:
        result = client.auth.submit_totp(getpass.getpass("TOTP code: "))

    print(result.default_account)

    domains = client.cdn.domains.list(page=1, per_page=5)
    for domain in domains.data:
        print(domain.domain, domain.status)
```

The SDK never prompts internally. When login requires TOTP, it keeps a
`TOTPChallenge` only in `client.auth.pending_totp`, leaves any active tokens
unchanged, and raises `TOTPRequiredError`. Pass the user-supplied code to
`submit_totp()` to finish login. Starting another login replaces the pending
challenge; completed session files never contain a code or flow token.

## Reuse an ArvanCloud login session

Session files are opt-in and path-based. They store access and refresh tokens in
plaintext JSON, so treat them like browser cookies or local session data. Keep
them outside source control; common `.arvancld-session*.json` filenames are
ignored by this repository.

Call `client.auth.refresh()` after a server rejects a loaded access token, then
save the session again so the rotated access and refresh tokens are persisted.
The async client exposes `await client.auth.refresh()`. If a saved session is
already expired locally, loading still raises `SessionExpiredError` and you
should log in again.

```python
import getpass
import os
from pathlib import Path

from arvancld import (
    ArvanCloud,
    InvalidSessionError,
    SessionExpiredError,
    TOTPRequiredError,
)

session_path = Path(os.environ.get("ARVANCLD_SESSION", ".arvancld-session.json"))

with ArvanCloud() as client:
    try:
        client.auth.load_session(session_path)
    except (FileNotFoundError, InvalidSessionError, SessionExpiredError):
        try:
            client.auth.login(
                email=os.environ["ARVANCLD_EMAIL"],
                password=os.environ["ARVANCLD_PASSWORD"],
            )
        except TOTPRequiredError:
            client.auth.submit_totp(getpass.getpass("TOTP code: "))
        client.auth.save_session(session_path)

    domains = client.cdn.domains.list()
    for domain in domains.data:
        print(domain.domain, domain.status)
```

Async clients keep the same synchronous methods for compatibility and also
provide `aload_session()`, `asave_session()`, and `aclear_session()` to move
filesystem work off the event loop:

```python
import asyncio
import getpass
import os
from pathlib import Path

from arvancld import (
    AsyncArvanCloud,
    InvalidSessionError,
    SessionExpiredError,
    TOTPRequiredError,
)


async def main() -> None:
    session_path = Path(os.environ.get("ARVANCLD_SESSION", ".arvancld-session.json"))

    async with AsyncArvanCloud() as client:
        try:
            await client.auth.aload_session(session_path)
        except (FileNotFoundError, InvalidSessionError, SessionExpiredError):
            try:
                await client.auth.login(
                    email=os.environ["ARVANCLD_EMAIL"],
                    password=os.environ["ARVANCLD_PASSWORD"],
                )
            except TOTPRequiredError:
                await client.auth.submit_totp(getpass.getpass("TOTP code: "))
            await client.auth.asave_session(session_path)

        domains = await client.cdn.domains.list()
        for domain in domains.data:
            print(domain.domain, domain.status)


asyncio.run(main())
```

## List and search ArvanCloud CDN DNS records

```python
import os

from arvancld import ArvanCloud


def optional_record_types() -> list[str] | None:
    value = os.environ.get("ARVANCLD_DNS_RECORD_TYPES")
    if value is None or not value.strip():
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


with ArvanCloud() as client:
    client.auth.login(
        email=os.environ["ARVANCLD_EMAIL"],
        password=os.environ["ARVANCLD_PASSWORD"],
    )

    records = client.cdn.dns_records.list(
        os.environ.get("ARVANCLD_DOMAIN", "snapp.ir"),
        page=1,
        per_page=100,
        record_types=optional_record_types(),
        search=os.environ.get("ARVANCLD_DNS_SEARCH"),
        match_type=os.environ.get("ARVANCLD_DNS_MATCH_TYPE"),
    )
    for record in records.data:
        print(record.type, record.name, record.ttl)
```

## Iterate through every page lazily

Use `iter_all()` when you want items rather than a single pagination envelope.
The existing endpoint defaults remain `5` domains and `25` DNS records per
request:

```python
with ArvanCloud() as client:
    client.auth.load_session(".arvancld-session.json")

    for domain in client.cdn.domains.iter_all():
        print(domain.domain)

    for record in client.cdn.dns_records.iter_all(
        "snapp.ir",
        per_page=100,
        record_types=["a", "aaaa"],
    ):
        print(record.name)
```

`per_page=100` can reduce network round trips when the endpoint accepts it. This
SDK does not assume a universal page-size ceiling because one has not been
verified; choose a larger value explicitly for the endpoint and account you use.

Async iterators are sequential by default. Set `prefetch` above `1` to load a
bounded number of future pages concurrently while preserving page order:

```python
async for record in client.cdn.dns_records.iter_all(
    "snapp.ir",
    per_page=100,
    prefetch=4,
):
    print(record.name)
```

Supported DNS record type filters:

```text
a, aaaa, aname, cname, ns, mx, srv, txt, ptr, caa, tlsa
```

Exact search example:

```python
import os

from arvancld import ArvanCloud

with ArvanCloud() as client:
    client.auth.login(
        email=os.environ["ARVANCLD_EMAIL"],
        password=os.environ["ARVANCLD_PASSWORD"],
    )

    records = client.cdn.dns_records.list(
        os.environ.get("ARVANCLD_DOMAIN", "snapp.ir"),
        search=os.environ["ARVANCLD_DNS_SEARCH"],
        match_type=os.environ.get("ARVANCLD_DNS_MATCH_TYPE", "exact"),
        record_types=[os.environ.get("ARVANCLD_DNS_RECORD_TYPE", "aaaa")],
        page=1,
        per_page=100,
    )
    for record in records.data:
        print(record.type, record.name, record.ttl)
```

## Create a CDN DNS record

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

## Update, delete, or toggle CDN cloud proxy

```python
import os
from uuid import UUID

from arvancld import ArvanCloud, DNSRecordIPValue, DNSRecordUpdate, IPFilterMode

with ArvanCloud() as client:
    client.auth.login(
        email=os.environ["ARVANCLD_EMAIL"],
        password=os.environ["ARVANCLD_PASSWORD"],
    )

    updated = client.cdn.dns_records.update(
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
    print(updated.updated_at)

    proxied = client.cdn.dns_records.set_cloud(
        os.environ.get("ARVANCLD_DOMAIN", "snapp.ir"),
        os.environ["ARVANCLD_RECORD_ID"],
        cloud=True,
    )
    print(proxied.cloud)

    result = client.cdn.dns_records.delete(
        os.environ.get("ARVANCLD_DOMAIN", "snapp.ir"),
        UUID(os.environ["ARVANCLD_RECORD_ID"]),
    )
    print(result.message)
```

## Async ArvanCloud CDN example

```python
import asyncio
import getpass
import os

from arvancld import AsyncArvanCloud, TOTPRequiredError


async def main() -> None:
    async with AsyncArvanCloud() as client:
        try:
            await client.auth.login(
                email=os.environ["ARVANCLD_EMAIL"],
                password=os.environ["ARVANCLD_PASSWORD"],
            )
        except TOTPRequiredError:
            await client.auth.submit_totp(getpass.getpass("TOTP code: "))

        domains = await client.cdn.domains.list(page=1, per_page=5)
        print(f"Domains: {domains.meta.total}")

        records = await client.cdn.dns_records.list(
            os.environ.get("ARVANCLD_DOMAIN", "snapp.ir"),
            record_types=["a", "aaaa", "cname"],
            page=1,
            per_page=100,
        )
        print(f"DNS records: {records.meta.total}")


asyncio.run(main())
```

## Configuration

Both clients accept these keyword arguments:

- `auth_base_url`: defaults to `https://dejban.arvancloud.ir`
- `cdn_base_url`: defaults to `https://napi.arvancloud.ir/cdn/4.0`
- `redirect_uri`: defaults to `https://panel.arvancloud.ir/`
- `timeout`: a timeout in seconds or `httpx.Timeout`, defaulting to `30.0`
- `user_agent`: defaults to `arvancld/0.1.0`
- `limits`: optional native `httpx.Limits`; HTTPX defaults are used when omitted
- `retry_policy`: defaults to `RetryPolicy()`; pass `None` for single-attempt
  requests

Default retries apply only to `GET` requests. The client makes up to three
attempts for timeouts, network failures, remote protocol failures, and HTTP
`429`, `502`, `503`, or `504` responses. It respects a bounded `Retry-After`
header. Login, token refresh, and every DNS mutation remain single-attempt
operations.

```python
import httpx

from arvancld import ArvanCloud, RetryPolicy

client = ArvanCloud(
    timeout=httpx.Timeout(connect=5, read=30, write=10, pool=5),
    limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
    retry_policy=RetryPolicy(max_attempts=3),
)

# Disable automatic GET retries:
single_attempt_client = ArvanCloud(retry_policy=None)
```

## Credential handling

- Passwords are used only to construct the login request and are not retained.
- Access and refresh tokens are held in memory at `client.auth.tokens`.
- A pending TOTP challenge is held only in memory at
  `client.auth.pending_totp`; its flow token is redacted from representations.
- `client.auth.refresh()` rotates the current access and refresh tokens while
  preserving the account-routing fields returned by login.
- `client.auth.save_session(path)` can explicitly write those tokens to a
  plaintext JSON session file; it never stores the password.
- `client.auth.load_session(path)` restores unexpired saved tokens into memory.
- `client.auth.clear_session(path)` deletes the local session file and clears
  in-memory tokens.
- Async clients can await the corresponding `asave_session`, `aload_session`,
  and `aclear_session` methods to avoid blocking the event loop.
- CDN requests build ArvanCloud's account-scoped bearer header from the login
  `accessToken` and `defaultAccount` values in memory.
- Token fields are excluded from model representations.
- Tokens are written to disk only when you explicitly call `save_session(...)`.
- TOTP codes and challenge flow tokens are never written to session files.
- API exceptions do not include request bodies, passwords, or token values.

## Development

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

Tests mock all HTTP traffic. They do not contact ArvanCloud or require real
credentials.
