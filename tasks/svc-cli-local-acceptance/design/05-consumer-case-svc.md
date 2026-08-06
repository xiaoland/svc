# Consumer Case — SVC Repository Acceptance

## Purpose and Boundary

This is a directly inspectable consumer-project dogfood case. It tests whether
the current SVC repository's real acceptance surfaces demonstrate distinct
`svc run` value. It is not a claim that the framework repository represents all
large consumer projects.

## Observed Native Surfaces

`pyproject.toml` exposes project-owned PDM scripts for tests, document checks,
test lint, type checking, import boundaries, workflow lint, CLI invocation, and
monolith generation. `CONTRIBUTING.md` gives Humans and Agents the same direct
commands.

GitHub Actions uses those commands in independent CI checkouts:

- the Python matrix invokes `pdm run test`;
- the quality job invokes the five project-owned quality scripts;
- the distribution job builds the wheel and monolith, then performs a larger
  inline installed-wheel smoke flow.

CI therefore shares command/declaration semantics with local callers but cannot
share a local active execution or execution ID.

Primary evidence:

- `pyproject.toml:42-50`
- `CONTRIBUTING.md:17-25`
- `.github/workflows/ci.yml:14-87`

## Measured Direct Test Baseline

On 2026-08-06, the current worktree's native test entry was invoked directly:

```text
pdm run test
131 passed in 1.58s
real 2.10s
```

The native pytest presentation already supplies environment context, bounded
per-file progress, failure locality when applicable, and a compact terminal
summary. A JSON envelope would not improve this successful result.

The active execution window is only about two seconds. Avoiding a coincident
duplicate or letting another local participant join that run has little value
in this case. The test entry therefore does not independently repay shared-run
declaration, coordination, and receipt complexity.

## Distribution Acceptance Gap

The distribution job is a more costly and semantically important acceptance
flow, but the project does not currently expose it as one native bounded entry.
Its build, wheel download, digest binding, fixture acceptance, fresh-venv
installation, lookup, init, and status checks are expanded inside GitHub Actions
shell steps.

This is a real local/CI acceptance-entry gap, but it does not decide where the
integration belongs. Two placements are honest:

1. the project extracts one native driver using a script, PDM composite, or
   another project-owned tool, and a run entry invokes that command; or
2. a run entry owns a minimal ordered sequence of project-tool invocations.

The second placement initially looks more convenient, but this flow passes
dynamic values between steps: selected wheel path, artifact digest, temporary
environment, init plan digest, and generated repository path. A plain command
list cannot express the actual flow. Adding variables, conditions, artifacts,
and step-output references would move `svc run` toward a workflow language.

Sir accepted one project-owned command as the minimum run-entry boundary on
2026-08-06. SVC must not infer or copy CI YAML; the project extracts a driver
using the orchestration mechanism it already owns.

## Case Result

The short test slice does not admit `svc run`:

- the directly callable `test` operation is too short and already presents
  useful native output;
- CI is correctly isolated from local live execution.

The distribution slice supplies genuine admission pressure but does not yet
provide a callable driver against which shared execution can be tested.

It does validate two design boundaries:

1. Native output should pass through when it is already Agent-friendly; format
   conversion is not value.
2. SVC must not infer an acceptance flow from CI or tool configuration. The
   project explicitly owns whichever bounded operation a run entry identifies.

The next consumer case must supply an existing, materially costly bounded
command so shared execution can be tested without first changing the project.
