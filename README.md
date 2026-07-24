# arvancld

`arvancld` is a typed Python client for ArvanCloud services. The first release
implements account login with synchronous and asynchronous clients and reserves
a separate package boundary for the CDN API.

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
```

PowerShell:

```powershell
$env:ARVANCLD_EMAIL = "you@example.com"
$env:ARVANCLD_PASSWORD = "your-password"
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

## Asynchronous login

```python
import asyncio
import os

from arvancld import AsyncArvanCloud


async def main() -> None:
    async with AsyncArvanCloud() as client:
        result = await client.auth.login(
            email=os.environ["ARVANCLD_EMAIL"],
            password=os.environ["ARVANCLD_PASSWORD"],
        )
        print(result.default_account)


asyncio.run(main())
```

## Configuration

Both clients accept these keyword arguments:

- `auth_base_url`: defaults to `https://dejban.arvancloud.ir`
- `cdn_base_url`: reserved for CDN adapters and defaults to
  `https://napi.arvancloud.ir/cdn/4.0`
- `redirect_uri`: defaults to `https://panel.arvancloud.ir/`
- `timeout`: request timeout in seconds, defaulting to `30.0`
- `user_agent`: defaults to `arvancld/0.1.0`

The library sends a normal SDK user agent and does not imitate browser
fingerprints or send browser-only security headers.

## Credential handling

- Passwords are used only to construct the login request and are not retained.
- Access and refresh tokens are held in memory at `client.auth.tokens`.
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

