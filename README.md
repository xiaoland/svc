# Sustainable Vibe Coding

Sustainable Vibe Coding (SVC) is a source-first framework delivered as a versioned local corpus and a small development-collaboration CLI. It helps AI-assisted teams retain costly-to-rediscover truth without copying upstream framework documents into every repository.

## Develop SVC

Requirements: Python 3.11+ and PDM 2.28+.

```bash
pdm install
pdm run check
pdm run svc --help
pdm build -p cli
```

Edit canonical framework content under `corpus/`. It contains SVC Corpus content
plus an exact maintainer-only `AGENTS.md`; SVC's own durable project truth lives
under `docs/`. The installable runtime and its tests live under the `cli/`
workspace member, while repository-only release tools remain under `tools/`.

## Use SVC

Read the [User Manual](USER_MANUAL.md).

## Repository Layout

```text
corpus/                      canonical SVC Corpus
cli/
  pyproject.toml             installable distribution member
  src/svc_cli/               Python runtime and static package data
  tests/                     CLI runtime tests
  pdm_build.py               sdist/wheel Corpus projection hook
towncrier.{cli,corpus}.toml  independent release-note configurations
.changes/{cli,corpus}/       independent pending fragments
CHANGELOG.md                 shared release history before the split
tools/                       catalog, release, and acceptance tooling
tests/                       root Corpus and repository-tool tests
tasks/                       volatile work packets
```
