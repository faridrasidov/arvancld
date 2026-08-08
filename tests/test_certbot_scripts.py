from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

from arvancld import InvalidSessionError, SessionExpiredError

ROOT_DIR = Path(__file__).resolve().parents[1]


def _load_script(name: str, module_name: str):
    path = ROOT_DIR / "examples" / name
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


hook = _load_script("certbot_arvancld_dns_hook.py", "arvancld_certbot_hook_script")
generate = _load_script("generate_ssl.py", "arvancld_generate_ssl_script")
renew = _load_script("renew_ssl.py", "arvancld_renew_ssl_script")


class FakeAuth:
    def __init__(self, session_state: str = "ok"):
        self.session_state = session_state
        self.load_calls = 0
        self.login_calls = 0
        self.save_calls = 0

    def load_session(self, _path: Path) -> None:
        self.load_calls += 1
        if self.session_state == "missing":
            raise FileNotFoundError()
        if self.session_state == "expired":
            raise SessionExpiredError("expired")
        if self.session_state == "invalid":
            raise InvalidSessionError("invalid")

    def login(self, email: str, password: str) -> None:
        self.login_calls += 1
        assert email == "user@example.com"
        assert password == "secret"

    def save_session(self, _path: Path) -> None:
        self.save_calls += 1


class FakeDNSRecords:
    def __init__(self, records: list[Any]):
        self.records = records
        self.list_domains: list[str] = []
        self.create_domains: list[str] = []
        self.update_domains: list[str] = []
        self.delete_domains: list[UUID] = []
        self.create_calls: list[dict[str, object]] = []
        self.update_calls: list[tuple[str, object]] = []
        self.delete_calls: list[UUID] = []

    def list(
        self,
        _domain: str,
        *,
        page: int = 1,
        per_page: int = 100,
        record_types: object = None,
        search: object = None,
        match_type: object = None,
    ):
        assert page == 1
        assert per_page > 0
        assert search is None
        assert match_type is None
        assert record_types in (["TXT"], ["txt"], "TXT", "txt")
        self.list_domains.append(_domain)
        return SimpleNamespace(
            data=self.records,
            meta=SimpleNamespace(last_page=1),
        )

    def create(self, _domain: str, record: object) -> object:
        self.create_domains.append(_domain)
        self.create_calls.append({"record": record})
        return record

    def update(self, _domain: str, record: object) -> object:
        self.update_domains.append(_domain)
        self.update_calls.append(("", record))
        return record

    def delete(self, _domain: str, record_id: UUID) -> None:
        self.delete_domains.append(record_id)
        self.delete_calls.append(record_id)


class FakeCdn:
    def __init__(self, records: list[Any]):
        self.dns_records = FakeDNSRecords(records)


class FakeClient:
    def __init__(self, auth: FakeAuth, records: list[Any]):
        self.auth = auth
        self.cdn = FakeCdn(records)

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


def _txt_record(record_id: str, name: str, token: str) -> Any:
    return SimpleNamespace(
        id=UUID(record_id),
        type="txt",
        name=name,
        value={"text": token},
        ttl=120,
        cloud=False,
        upstream_https="default",
        ip_filter_mode=hook.DEFAULT_IP_FILTER,
    )


def _run_hook_with_fakes(
    *,
    mode: str,
    domain: str,
    validation: str,
    records: list[Any],
    session_state: str = "ok",
) -> FakeClient:
    auth = FakeAuth(session_state=session_state)
    client = FakeClient(auth, records)
    hook.run_hook(
        mode,
        domain=domain,
        validation=validation,
        session_path=Path(".arvancld-session.json"),
        client_factory=lambda: client,
    )
    return client


def test_hook_auth_reuses_session_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARVANCLD_EMAIL", "user@example.com")
    monkeypatch.setenv("ARVANCLD_PASSWORD", "secret")

    client = _run_hook_with_fakes(
        mode="auth",
        domain="snapp.ir",
        validation="token-1",
        records=[],
        session_state="ok",
    )

    assert client.auth.load_calls == 1
    assert client.auth.login_calls == 0
    assert client.auth.save_calls == 0
    assert len(client.cdn.dns_records.create_calls) == 1


def test_hook_auth_logs_in_when_session_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARVANCLD_EMAIL", "user@example.com")
    monkeypatch.setenv("ARVANCLD_PASSWORD", "secret")

    client = _run_hook_with_fakes(
        mode="auth",
        domain="snapp.ir",
        validation="token-2",
        records=[],
        session_state="expired",
    )

    assert client.auth.load_calls == 1
    assert client.auth.login_calls == 1
    assert client.auth.save_calls == 1
    assert len(client.cdn.dns_records.create_calls) == 1


def test_hook_uses_zone_domain_for_wildcard_challenges() -> None:
    client = _run_hook_with_fakes(
        mode="auth",
        domain="*.fstk.ir",
        validation="wildcard-token",
        records=[],
    )

    assert client.cdn.dns_records.list_domains == ["fstk.ir"]
    assert client.cdn.dns_records.create_domains == ["fstk.ir"]


def test_hook_auth_uses_relative_acme_record_name() -> None:
    client = _run_hook_with_fakes(
        mode="auth",
        domain="*.fstk.ir",
        validation="wildcard-token",
        records=[],
    )

    assert len(client.cdn.dns_records.create_calls) == 1
    assert client.cdn.dns_records.create_calls[0]["record"].name == "_acme-challenge"


def test_hook_auth_creates_record_when_token_differs() -> None:
    existing = _txt_record(
        "0a0a0a0a-0000-4a0a-a0a0-aaaaaaaaaaaa",
        "_acme-challenge.snapp.ir",
        "old-token",
    )

    client = _run_hook_with_fakes(
        mode="auth",
        domain="snapp.ir",
        validation="new-token",
        records=[existing],
    )

    assert len(client.cdn.dns_records.create_calls) == 1
    assert len(client.cdn.dns_records.update_calls) == 0


def test_hook_auth_is_idempotent_for_existing_token() -> None:
    existing = _txt_record(
        "0a0a0a0a-0000-4a0a-a0a0-bbbbbbbbbbbb",
        "_acme-challenge.snapp.ir",
        "same-token",
    )

    client = _run_hook_with_fakes(
        mode="auth",
        domain="snapp.ir",
        validation="same-token",
        records=[existing],
    )

    assert len(client.cdn.dns_records.create_calls) == 0
    assert len(client.cdn.dns_records.update_calls) == 0


def test_hook_cleanup_removes_only_matching_token() -> None:
    keep = _txt_record(
        "0a0a0a0a-0000-4a0a-a0a0-bbbbbbbbbbbb",
        "_acme-challenge.snapp.ir",
        "keep-me",
    )
    remove = _txt_record(
        "1b1b1b1b-1111-4b1b-b1b1-cccccccccccc",
        "_acme-challenge.snapp.ir",
        "delete-me",
    )

    client = _run_hook_with_fakes(
        mode="cleanup",
        domain="snapp.ir",
        validation="delete-me",
        records=[keep, remove],
        session_state="ok",
    )

    assert client.cdn.dns_records.delete_calls == [remove.id]


def test_generate_script_builds_expected_certbot_arguments() -> None:
    command = generate.build_certbot_args(
        certbot_binary="certbot",
        domains=["snapp.ir", "www.snapp.ir"],
        email="user@example.com",
        staging=True,
        dry_run=True,
        key_type="ecdsa",
        agree_tos=True,
        force=True,
    )

    assert command == [
        "certbot",
        "certonly",
        "--manual",
        "--preferred-challenges",
        "dns-01",
        "--manual-auth-hook",
        generate._build_hook_command("auth"),
        "--manual-cleanup-hook",
        generate._build_hook_command("cleanup"),
        "--force-renewal",
        "--staging",
        "--dry-run",
        "--email",
        "user@example.com",
        "--agree-tos",
        "--key-type",
        "ecdsa",
        "-d",
        "snapp.ir",
        "-d",
        "www.snapp.ir",
    ]


def test_generate_script_supports_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARVANCLD_CERTBOT_DOMAINS", "snapp.ir,www.snapp.ir")
    monkeypatch.setenv("ARVANCLD_CERTBOT_STAGING", "1")
    monkeypatch.setenv("ARVANCLD_CERTBOT_DRY_RUN", "1")
    monkeypatch.setenv("ARVANCLD_CERTBOT_KEY_TYPE", "rsa")
    monkeypatch.setenv("ARVANCLD_CERTBOT_AGREE_TOS", "1")

    args = generate.parse_args([])
    assert args.domain == []
    assert args.staging is True
    assert args.dry_run is True
    assert args.key_type == "rsa"
    assert args.agree_tos is True


def test_renew_script_builds_expected_args() -> None:
    command = renew.build_renew_args(
        certbot_binary="certbot",
        force=True,
        dry_run=True,
        deploy_hook="deploy-cmd",
        no_random_sleep=True,
    )
    assert command == [
        "certbot",
        "renew",
        "--non-interactive",
        "--force-renewal",
        "--dry-run",
        "--deploy-hook",
        "deploy-cmd",
        "--no-random-sleep-on-renew",
    ]
