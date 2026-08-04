"""Wrapper around `certbot renew` for ArvanCloud DNS-01 renewals."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
from collections.abc import Sequence


def _bool_env(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _log_command(command: Sequence[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(list(command))
    return shlex.join(command)


def build_renew_args(
    *,
    certbot_binary: str,
    force: bool,
    dry_run: bool,
    deploy_hook: str | None,
    no_random_sleep: bool,
) -> list[str]:
    command = [certbot_binary, "renew", "--non-interactive"]

    if force:
        command.append("--force-renewal")
    if dry_run:
        command.append("--dry-run")
    if deploy_hook:
        command.extend(["--deploy-hook", deploy_hook])
    if no_random_sleep:
        command.append("--no-random-sleep-on-renew")

    return command


def run_renew(args: argparse.Namespace) -> int:
    command = build_renew_args(
        certbot_binary=args.certbot_binary,
        force=args.force,
        dry_run=args.dry_run,
        deploy_hook=args.deploy_hook,
        no_random_sleep=args.no_random_sleep,
    )

    print(f"[certbot] {_log_command(command)}")
    return subprocess.run(command, check=True).returncode


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Renew ACME certificates with Certbot")
    parser.add_argument("--certbot-binary", default="certbot")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Pass through --force-renewal.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=_bool_env(os.environ.get("ARVANCLD_CERTBOT_DRY_RUN")),
        help="Pass through --dry-run.",
    )
    parser.add_argument(
        "--deploy-hook",
        default=os.environ.get("ARVANCLD_CERTBOT_DEPLOY_HOOK"),
        help="Optional deploy hook passed to certbot renew.",
    )
    parser.add_argument(
        "--no-random-sleep",
        action="store_true",
        default=False,
        help="Pass through --no-random-sleep-on-renew.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        return run_renew(args)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
