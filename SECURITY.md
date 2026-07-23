# Security Policy

## Reporting

Report suspected vulnerabilities through the GitHub repository's private security
advisory interface. Do not attach repository archives, credentials, environment
values, customer data, or proprietary source.

## Scope

The read-only guarantee covers toolkit-controlled Git and filesystem operations.
Explicitly supplied test programs are outside that guarantee.

## Safe use

- Write reports outside the scanned repository.
- Add organization-specific cache and secret directories with `--exclude`.
- Review snapshots before sharing them.
- Treat sanitized remotes, branch names, tags, filenames, and dependency names as
  potentially sensitive metadata.
- Keep real backups independent of snapshot output.

The package does not verify backups or protect against a compromised Git executable,
filesystem, Python runtime, or test command.

