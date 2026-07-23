# Safety Model

## Read-only command allowlist

The Git adapter permits only the following command families:

- `rev-parse`
- `symbolic-ref`
- `status`
- `for-each-ref`
- `remote -v`
- `rev-list`
- `ls-files`
- `diff --name-status`
- `show`

Arguments are constructed by the package. User text is never joined into a shell
command.

## Explicitly forbidden behavior

The package contains no implementation path for Git mutation commands, filesystem
deletion, remote synchronization, branch creation, dependency installation, or
credential discovery. Reports describe manual checkpoints but do not execute them.

## Privacy controls

Default redaction covers `.env`, credential, secret, token, key, cookie, wallet, and
keystore-like filenames. Redacted paths use a stable digest token; contents are never
read. Remote user information, passwords, query strings, and fragments are removed.
Local-path remotes are represented as `<local-path>`.

Large files are hashed by streaming but are not decoded for symbol analysis. Symlinks
are not followed. `.git`, dependency environments, build outputs, caches, and common
IDE metadata are excluded from inventory.

## Test execution

Tests run only when the user supplies an explicit argument vector. The tool:

- uses `shell=False`;
- runs in the repository root;
- applies a timeout;
- records exit status, elapsed milliseconds, and SHA-256 of combined output;
- does not store stdout or stderr text.

Test execution can still change a repository because test suites are arbitrary. The
CLI prints this boundary and requires `--allow-test-execution`.

