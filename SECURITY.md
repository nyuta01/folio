# Security policy

## Supported versions

Folio is in early alpha (`0.x`). Only the latest minor version
receives security fixes.

| Version | Supported |
|---|---|
| `0.1.x` (latest) | ✅ |
| Older          | ❌ |

## Reporting a vulnerability

**Do not open public GitHub issues for security bugs.** Use one of
the private channels below so a fix can ship before the issue is
disclosed.

1. **Preferred — GitHub Private Vulnerability Reporting**
   <https://github.com/nyuta01/folio/security/advisories/new>
   (the "Report a vulnerability" button on the Security tab).
2. **Email** — `yuta.n@carnot.ai` with `[folio-security]` in the
   subject. Include reproduction steps, affected version, and any
   mitigations you've identified.

We aim to acknowledge new reports within **3 business days** and
to issue a fix or workaround within **30 days** for confirmed
vulnerabilities. Critical issues (RCE, credential leak, sandbox
escape) are prioritized.

## Scope

Reports against the following are in scope:

- `folio` CLI and `folio-viewer` backend
- The Python SDK (`folio` package)
- The Electron desktop app under `apps/desktop/`
- Release pipelines under `.github/workflows/`

Out of scope:

- The `anthropic` Python SDK or other vendor dependencies. Report
  those to the respective project.
- Vulnerabilities that require local filesystem access to a sheet
  Folio is already authorized to write — sheets are designed to
  trust their actors.

## Disclosure timeline

We follow a coordinated-disclosure model:

1. Report received → ack within 3 business days.
2. We confirm + investigate. We may ask for additional info.
3. Fix is developed and tested. CVE requested if applicable.
4. Patched release ships to PyPI / npm / GitHub Releases.
5. Public advisory published, crediting the reporter unless they
   prefer to remain anonymous.

Thank you for keeping Folio safe.
