"""Wrapper around Certbot for initial ArvanCloud DNS-01 issuance."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path


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
        if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
            value = value[1:-1]

        if name not in os.environ:
            os.environ[name] = value


def _build_hook_command(
    mode: str,
) -> str:
    hook = Path(__file__).with_name("certbot_arvancld_dns_hook.py")
    if os.name == "nt":
        return subprocess.list2cmdline([sys.executable, str(hook), "--mode", mode])
    return shlex.join([sys.executable, str(hook), "--mode", mode])


def _split_domains(raw: str | None) -> list[str]:
    if raw is None:
        return []

    normalized: list[str] = []
    for chunk in raw.replace(",", " ").split():
        value = chunk.strip()
        if value:
            normalized.append(value)
    return normalized


def _bool_env(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_domains(
    explicit: Sequence[str],
    env_value: str | None,
) -> list[str]:
    if explicit:
        return list(explicit)
    return _split_domains(env_value)


def build_certbot_args(
    *,
    certbot_binary: str,
    domains: Sequence[str],
    email: str | None,
    staging: bool,
    dry_run: bool,
    key_type: str | None,
    agree_tos: bool,
    force: bool,
    extra_args: Sequence[str] | None = None,
) -> list[str]:
    command = [
        certbot_binary,
        "certonly",
        "--manual",
        "--preferred-challenges",
        "dns-01",
        "--manual-auth-hook",
        _build_hook_command("auth"),
        "--manual-cleanup-hook",
        _build_hook_command("cleanup"),
    ]

    if force:
        command.append("--force-renewal")
    if staging:
        command.append("--staging")
    if dry_run:
        command.append("--dry-run")

    if email:
        command.extend(["--email", email])
    else:
        command.append("--register-unsafely-without-email")

    if agree_tos:
        command.append("--agree-tos")

    if key_type:
        command.extend(["--key-type", key_type])

    for domain in domains:
        command.extend(["-d", domain])

    if extra_args:
        command.extend(extra_args)

    return command


def _log_command(command: Sequence[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(list(command))
    return shlex.join(command)


def run_generate(args: argparse.Namespace) -> int:
    domains = _resolve_domains(
        args.domain,
        os.environ.get("ARVANCLD_CERTBOT_DOMAINS"),
    )
    if not domains:
        raise ValueError("domain is required")

    command = build_certbot_args(
        certbot_binary=args.certbot_binary,
        domains=domains,
        email=args.email or os.environ.get("ARVANCLD_EMAIL"),
        staging=args.staging,
        dry_run=args.dry_run,
        key_type=args.key_type or os.environ.get("ARVANCLD_CERTBOT_KEY_TYPE"),
        agree_tos=args.agree_tos,
        force=args.force,
        extra_args=args.extra,
    )

    print(f"[certbot] {_log_command(command)}")
    return subprocess.run(command, check=True).returncode


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Issue certificates with certbot and ArvanCloud DNS hooks",
    )
    parser.add_argument(
        "-d",
        "--domain",
        action="append",
        default=[],
        help="Domain(s) to request. Can also be provided via ARVANCLD_CERTBOT_DOMAINS.",
    )
    parser.add_argument("--certbot-binary", default="certbot")
    parser.add_argument("--email")
    parser.add_argument(
        "--staging",
        action="store_true",
        default=_bool_env(os.environ.get("ARVANCLD_CERTBOT_STAGING")),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=_bool_env(os.environ.get("ARVANCLD_CERTBOT_DRY_RUN")),
    )
    parser.add_argument("--key-type", default=os.environ.get("ARVANCLD_CERTBOT_KEY_TYPE"))
    parser.add_argument(
        "--agree-tos",
        action="store_true",
        default=_bool_env(os.environ.get("ARVANCLD_CERTBOT_AGREE_TOS")),
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--extra",
        nargs="*",
        default=[],
        help="Extra certbot args appended unchanged.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        _load_dotenv()
        args = parse_args(argv)
        return run_generate(args)
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    raise SystemExit(main())
