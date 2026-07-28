# Changelog

All notable changes to `arvancld` will be documented in this file.

## 0.1.0 - Unreleased

### Added

- Synchronous and asynchronous `ArvanCloud` clients.
- Account login support with typed token and account metadata parsing.
- Explicit JSON session persistence with opt-in `save_session`, `load_session`, and `clear_session`.
- CDN domain listing support.
- CDN DNS record listing support.
- CDN DNS record creation support.
- CDN DNS record update support.
- CDN DNS record deletion support.
- CDN DNS cloud proxy toggle support.
- Lazy sync and async iteration across all CDN domain and DNS record pages.
- Optional bounded async page prefetch with ordered results.
- Configurable GET-only retries with bounded jitter and `Retry-After` support.
- Native HTTPX granular timeout and connection-pool configuration.
- Direct Pydantic validation from response bytes without an intermediate JSON object.
- Non-blocking async session save, load, and clear methods.
- Mocked pytest coverage for login, sessions, CDN domains, and DNS records.
