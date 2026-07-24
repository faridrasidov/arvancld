# Security Policy

## Reporting security issues

Please report security issues privately to the project maintainer. Do not open
public issues containing credentials, bearer tokens, session JSON, DNS zone
captures, request headers, or account identifiers.

If you need to share a reproduction, redact sensitive values first and replace
real domains with a harmless example such as `snapp.ir`.

## Local session files

`arvancld` can explicitly save login tokens to a JSON file through
`client.auth.save_session(path)`. That file is plaintext and should be treated
like browser cookies or local session data.

Recommended handling:

- Keep session files outside source control.
- Use `.arvancld-session*.json` filenames so the repository `.gitignore` covers
  common local session files.
- Do not paste session files into issue trackers, chat, logs, CI output, or test
  fixtures.
- Delete local sessions with `client.auth.clear_session(path)` when they are no
  longer needed.

Refresh-token behavior is intentionally not implemented until the real refresh
endpoint contract is known.
