# Sustainable Vibe Coding

Sustainable Vibe Coding (SVC) is a source-first framework delivered as a versioned local corpus and a small development-collaboration CLI. It helps AI-assisted teams retain costly-to-rediscover truth without copying upstream framework documents into every repository.

## Develop SVC

Requirements: Python 3.11+ and PDM 2.28+.

```bash
pdm install
pdm run check
pdm run svc --help
pdm build -p svc_cli
```

Edit canonical framework content under `src/`. It contains SVC Corpus content
plus an exact maintainer-only `AGENTS.md`; SVC's own durable project truth lives
under `docs/`. The installable runtime and its tests live under the `svc_cli/`
workspace member, while repository-only release tools remain under `tools/`.

## Use SVC

Read the [User Manual](USER_MANUAL.md).

## Repository Layout

```text
src/                         canonical SVC corpus
svc_cli/
  pyproject.toml             installable distribution member
  src/svc_cli/               Python runtime and static package data
  tests/                     CLI runtime tests
towncrier.toml               Towncrier release-note configuration
.changes/                    pending Towncrier fragments
CHANGELOG.md                 Towncrier-generated release notes
tools/                       catalog, release, and acceptance tooling
svc_cli/pdm_build.py         member sdist/wheel Corpus projection hook
tests/                       root Corpus and repository-tool tests
tasks/                       volatile work packets
```
