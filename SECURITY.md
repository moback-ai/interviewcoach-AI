# Security Policy

## Supported versions

| Branch    | Supported |
|-----------|-----------|
| `develop` | Yes       |
| `main`    | Yes       |

## Reporting a vulnerability

Email security concerns to your team admin (do not open public issues for exploitable bugs).

## Automated scanning

**Veracode only** — runs on every production deploy after `production` environment approval.

Requires repository secrets: `VERACODE_API_ID`, `VERACODE_API_KEY`.

See [docs/SECURITY_SCANNING.md](docs/SECURITY_SCANNING.md).
