# examples/certbot_arvancld_dns_hook.py
"""Manual DNS-01 DNS hooks for Certbot using the ArvanCloud SDK."""

from __future__ import annotations

import argparse
import os
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from arvancld import (
    ArvanCloud,
    ArvanCloudError,
    DNSRecord,
    DNSRecordCreate,
    InvalidSessionError,
    IPFilterMode,
    SessionExpiredError,
)

DEFAULT_ACME_TTL = 120
DEFAULT_ACME_SESSION_PATH = ".arvancld-session.json"
DEFAULT_SESSION_PATH = DEFAULT_ACME_SESSION_PATH
ACME_CHALLENGE_LABEL = "_acme-challenge"
DEFAULT_IP_FILTER = IPFilterMode(
    count="single",
    geo_filter="none",
    order="none",
)


def _load_dotenv(path: str | Path = ".env") -> None:
    env_paths = [Path(path), Path(__file__).resolve().parent.parent / path]
    for env_path in env_paths:
        if env_path.exists():
            break
    else:
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if text.startswith("export "):
            text = text[len("export ") :].strip()
        if "=" not in text:
            continue

        name, value = text.split("=", 1)
        name = name.strip()
        if not name:
            continue

        value = value.strip()
        if len(value) >= 2 and (
            (value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")
        ):
            value = value[1:-1]

        if name not in os.environ:
            os.environ[name] = value


def _zone_domain(domain: str) -> str:
    cleaned_domain = domain.strip()
    if cleaned_domain.startswith("*."):
        cleaned_domain = cleaned_domain[2:]
    return cleaned_domain


def _acme_record_names(zone_domain: str) -> set[str]:
    return {
        ACME_CHALLENGE_LABEL,
        ACME_CHALLENGE_LABEL + "." + zone_domain,
    }


def _txt_value(token: str) -> dict[str, str]:
    return {"text": token}


def _extract_txt_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
        return

    if isinstance(value, list):
        for item in value:
            for item_value in _extract_txt_values(item):
                yield item_value
        return

    if isinstance(value, dict):
        for _, item in value.items():
            for item_value in _extract_txt_values(item):
                yield item_value
        return


def _record_has_txt_token(record: DNSRecord, token: str) -> bool:
    return any(candidate == token for candidate in _extract_txt_values(record.value))


def _is_acme_txt_record(record: DNSRecord, zone_domain: str) -> bool:
    return record.type.lower() == "txt" and record.name in _acme_record_names(zone_domain)


def _find_existing_records(
    client: ArvanCloud,
    domain: str,
) -> list[DNSRecord]:
    records: list[DNSRecord] = []
    page = 1
    while True:
        response = client.cdn.dns_records.list(
            domain,
            page=page,
            per_page=100,
            record_types=["TXT"],
        )
        records.extend(
            record
            for record in response.data
            if _is_acme_txt_record(record, domain)
        )
        if response.meta.last_page <= page:
            break
        page += 1

    return records


def _ensure_session(client: ArvanCloud, session_path: str | Path) -> None:
    try:
        client.auth.load_session(session_path)
        return
    except (FileNotFoundError, InvalidSessionError, SessionExpiredError):
        email = os.environ["ARVANCLD_EMAIL"]
        password = os.environ["ARVANCLD_PASSWORD"]
        client.auth.login(email=email, password=password)
        client.auth.save_session(session_path)


def _run_auth_hook(
    client: ArvanCloud,
    *,
    domain: str,
    validation: str,
    session_path: str | Path = DEFAULT_SESSION_PATH,
) -> None:
    zone_domain = _zone_domain(domain)
    record_name = ACME_CHALLENGE_LABEL
    _ensure_session(client, session_path)

    existing_records = _find_existing_records(client, zone_domain)
    if any(_record_has_txt_token(record, validation) for record in existing_records):
        return

    client.cdn.dns_records.create(
        zone_domain,
        DNSRecordCreate(
            type="TXT",
            name=record_name,
            cloud=False,
            value=_txt_value(validation),
            ttl=DEFAULT_ACME_TTL,
            upstream_https=None,
            ip_filter_mode=None,
        ),
    )


def _run_cleanup_hook(
    client: ArvanCloud,
    *,
    domain: str,
    validation: str,
    session_path: str | Path = DEFAULT_SESSION_PATH,
) -> None:
    zone_domain = _zone_domain(domain)
    _ensure_session(client, session_path)

    for record in _find_existing_records(client, zone_domain):
        if _record_has_txt_token(record, validation):
            client.cdn.dns_records.delete(zone_domain, record.id)


def run_hook(
    mode: str,
    *,
    domain: str,
    validation: str,
    session_path: str | Path = DEFAULT_ACME_SESSION_PATH,
    client_factory=ArvanCloud,
) -> int:
    try:
        with client_factory() as client:
            if mode == "auth":
                _run_auth_hook(
                    client,
                    domain=domain,
                    validation=validation,
                    session_path=session_path,
                )
            else:
                _run_cleanup_hook(
                    client,
                    domain=domain,
                    validation=validation,
                    session_path=session_path,
                )
    except KeyError as exc:
        raise SystemExit(f"missing required environment variable: {exc.args[0]}") from exc
    except ArvanCloudError as exc:
        raise SystemExit(str(exc)) from exc
    return 0


def _read_arg_sequence(values: Sequence[str]) -> list[str]:
    if len(values) == 1 and "," in values[0]:
        return [value.strip() for value in values[0].split(",") if value.strip()]
    return [value.strip() for value in values if value.strip()]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create and remove ACME TXT challenge records in ArvanCloud DNS",
    )
    parser.add_argument("--mode", choices=["auth", "cleanup"], required=True)
    parser.add_argument(
        "--domain",
        default=os.environ.get("CERTBOT_DOMAIN", "").strip(),
    )
    parser.add_argument(
        "--validation",
        default=os.environ.get("CERTBOT_VALIDATION", "").strip(),
    )
    parser.add_argument(
        "--session-path",
        default=os.environ.get("ARVANCLD_SESSION", DEFAULT_ACME_SESSION_PATH).strip(),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    _load_dotenv()
    args = parse_args(argv)

    domains = _read_arg_sequence([args.domain]) if args.domain else []
    if not domains:
        raise SystemExit("CERTBOT_DOMAIN must be set or --domain must be provided")
    if len(domains) != 1:
        raise SystemExit("exactly one CERTBOT_DOMAIN is expected for this hook")
    domain = domains[0]

    if args.mode == "auth" and not args.validation:
        raise SystemExit("CERTBOT_VALIDATION must be set when mode=auth")

    return run_hook(
        args.mode,
        domain=domain,
        validation=args.validation,
        session_path=args.session_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
