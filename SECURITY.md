# Security Policy

## Supported code

Security fixes should target the latest `master` branch and the latest published release.

## Reporting a vulnerability

Please do not publish credentials, private user data, exploit details, or sensitive
logs in a public issue.

If GitHub private vulnerability reporting is available for this repository, use it.
If it is not available, open a minimal public issue stating that you found a security
problem and request a private contact channel. Do not include sensitive reproduction
details in that public issue.

## Secrets

Never commit:

- `.env`
- API keys or tokens
- browser cookies
- private chat exports
- account session data
- downloaded private media
- local credential caches

The repository `.gitignore` is intended to exclude common local/runtime artifacts, but
contributors should still inspect staged changes before every commit.

## Scope

Examples of security-relevant issues include accidental secret exposure, unsafe handling
of local files, path traversal, command injection, insecure temporary-file behavior, or
unintended exposure of collected data.
