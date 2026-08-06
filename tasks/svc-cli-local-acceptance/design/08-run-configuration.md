# Design Dossier — Run Configuration Resolution

## Status

Sir accepted this pre-implementation configuration direction on 2026-08-06. It
replaces the earlier field-by-field rule that allowed a local `env` override
but treated `argv` and `cwd` as inherently committed authority. Acceptance of
this design is not authorization to mutate canonical source or code.

## Governing Principle

A declared run has two different kinds of stability:

1. The committed entry name and its complete default launch specification form
   the shared project interface. They let a fresh checkout, another Human or
   Agent, an IDE carrier, and CI identify the same bounded project operation.
2. The effective launch specification is the binding for the current execution
   context. It is produced by sparsely overlaying local configuration onto that
   committed default and is the only specification the runtime executes.

The boundary is therefore not `env` versus `cwd` versus `argv`. All three are
process-launch inputs, all three commonly vary with a local toolchain or
workspace layout, and all three can change program behavior. SVC cannot prove
that an overridden working directory preserves intent any more than it can
prove that an overridden executable, argument, or environment value does.

The mechanically enforceable collaboration boundary is instead:

```text
committed entry name + complete default
                 |
                 + local sparse launch override
                 v
       one validated effective entry
                 |
                 + resolved argv/cwd/environment digest
                 v
       one local convergence identity
```

The receipt exposes the resolved `argv` and `cwd`, so an Agent or Human can see
what actually ran. Raw environment values remain private. Project owners and
collaborators, not SVC field restrictions, judge whether a local realization
still implements the named operation.

## Why `cwd` Is Often Local

`cwd` is not just project structure metadata. It can bind the same operation to
a locally generated build tree, a worktree-specific checkout, a mounted volume,
or a toolchain-managed directory. The same pattern applies to `env` values and,
occasionally, to `argv` when a local launcher such as `mise`, `nix`, a container
wrapper, or an absolute tool path is required.

Treating only `env` as local would therefore create a false semantic boundary
and force projects to hide ordinary launch adaptation inside wrapper scripts.
Allowing `cwd` but forbidding `argv` would repeat the same mistake one field
later.

## Minimum Schema

Use a direct map from committed run-entry names to one flat launch
specification. `argv` reuses the exact-array vocabulary already used by the
`dev` configuration and makes the no-shell contract explicit:

```json
{
  "schema_version": 2,
  "svc_version": "11.0.0",
  "run": {
    "core-full": {
      "argv": ["cargo", "test", "--manifest-path", "core/Cargo.toml"],
      "cwd": ".",
      "env_files": [".env.shared"],
      "env": {
        "CARGO_TERM_COLOR": "always"
      }
    }
  }
}
```

Each entry has exactly:

- required non-empty `argv: string[]`; `argv[0]` is non-empty, later empty
  arguments remain valid, and no item contains NUL;
- optional `cwd: string`, defaulting to `.`;
- optional ordered `env_files: string[]`, defaulting to `[]`;
- optional `env: object<string,string>`, defaulting to `{}`.

There is no `exec` wrapper object because a run entry has no second execution
kind. There are no profiles: `svc.local.json` already selects the one effective
local context without adding another naming and selection layer.

Relative `cwd` values resolve from the workspace root. An absolute value is a
valid explicit local binding; the directory must exist when invocation starts.
SVC does not infer a directory from the caller's current shell directory. Cwd
and env-file path strings must be non-empty and NUL-free. The complete argv,
cwd, env-file paths, and environment must be encodable by the current process
launch platform before execution publication.

## Local Overlay

The local file may sparsely override any launch field of an entry already named
in committed configuration:

```json
{
  "run": {
    "core-full": {
      "cwd": "/Volumes/WorkSSD/Development/beluna",
      "env_files": [".env.shared", ".env"],
      "env": {
        "CARGO_TARGET_DIR": "/Volumes/WorkSSD/Caches/beluna-target"
      }
    }
  }
}
```

Resolution reuses the established configuration rules:

- objects merge recursively;
- scalar values replace the base value;
- arrays replace the base value atomically;
- the effective result is validated by the complete schema;
- `null`, unknown fields, invalid values, and adoption/version overrides remain
  rejected.

Consequently, local `argv` and `env_files` replace their complete arrays, local
`cwd` replaces the base value, and local `env` adds or replaces individual
keys. The first slice does not add environment interpolation or an unset/delete
operator.

Each env file is required when listed. A locally optional file belongs in
`svc.local.json`, where that machine can omit the declaration when the file is
absent; the first slice does not add a second `required` policy to every path.
Relative env-file paths resolve from the workspace root, independently of
`cwd`, and absolute paths remain valid explicit local bindings.

Environment resolution is deterministic:

```text
owner ambient environment
-> env_files in listed order (later files replace earlier keys)
-> inline env (replaces file and ambient keys)
```

Files use dotenv assignment syntax, are read without mutating the SVC process
environment, and reject missing, unreadable, malformed, or valueless entries
before an execution ID is published. Variable interpolation is disabled in the
first slice so file contents do not silently depend on the launching shell.
Configuration resolution reads each file exactly once as one UTF-8 snapshot.
It uses python-dotenv's maintained `parse_stream` binding parser, rejects every
binding whose `error` flag is set and every variable without a value, and
derives both the child environment and private digest from that same snapshot.
The convenient `dotenv_values()` API is not sufficient for strict validation
because malformed bindings are warned about and skipped. SVC does not implement
a partial dotenv grammar and does not reopen a file between identity resolution
and launch.

After precedence is applied, all effective environment keys and values are
validated for the current subprocess platform before publication: keys are
non-empty and contain neither `=` nor NUL, and values contain no NUL. Any
additional platform encoding failure is a configuration error, not a late
process-start failure. Key identity follows the launch platform: case-sensitive
on POSIX and case-insensitive on Windows. Precedence and the private digest use
that normalized identity so `Path` and `PATH` cannot become ambiguous duplicate
variables on Windows.

One deliberate authority boundary remains: local configuration cannot create a
new run-entry name. The small committed name set is the cross-carrier project
interface admitted for `svc run`; a local-only convenience command has no such
shared meaning and can remain a project-tool or shell concern. The base entry
must therefore be complete even when every current developer overrides part of
its realization.

## Execution and Convergence Consequences

The runtime resolves the effective entry before choosing an active slot:

- relative `cwd` becomes a normalized absolute path;
- `argv` remains an exact ordered argument vector;
- env files are resolved, snapshotted, strictly parsed, and validated before
  slot selection;
- the child inherits the owner's ambient environment, then ordered file values
  and effective inline `env` replace matching keys;
- a canonical private digest covers effective `argv`, resolved `cwd`, ordered
  resolved env-file paths and parsed snapshot values, and effective inline
  environment. The in-memory values used for this digest are the same values
  later applied to the child environment.

That digest participates in the convergence key. Changing any explicit launch
field creates a different intent for coordination purposes; SVC does not join a
new invocation to an active execution that used a different effective entry.
Equivalent path spellings converge after `cwd` resolution.

Ambient environment outside the declaration is not fingerprinted. The active
owner's actual process remains the execution authority, and the receipt does
not claim complete environmental reproducibility.

Neither raw file/inline environment values nor the inherited ambient
environment are written to the execution record or printed by SVC. The record
retains the opaque effective-entry digest plus resolved `argv`, `cwd`, and
env-file source paths needed for review.

## Rejected Shapes

- **`env`-only or `env`+`cwd` allowlists**: draw a semantic boundary that the
  runtime cannot justify and keep growing as another legitimate local binding
  appears.
- **Profiles**: duplicate the existing local resolution layer and require
  callers to coordinate on an additional selection.
- **A shell string**: transfers quoting and shell-selection ambiguity into SVC.
- **A nested `exec` object**: adds depth without distinguishing another run
  kind.
- **Local-only run entries**: turn the admitted shared project interface back
  into a private generic task runner.

## Verification Obligations

- Base-only configuration resolves the documented defaults.
- Local `argv`, `cwd`, `env_files`, and individual `env` keys follow the
  established replace/replace/replace/merge behavior.
- Env files resolve from the workspace root, load in declaration order, and are
  overridden by inline env; missing, invalid, or valueless entries fail before
  execution publication.
- Malformed dotenv lines are rejected rather than warned-and-skipped; a file is
  read only once, and changing it cannot cause identity to describe different
  launch values.
- NUL, invalid environment keys, and platform encoding failures fail before
  execution publication.
- Invalid argv/path launch encodings likewise fail before publication rather
  than leaving a published attempt that could never reach `Popen`.
- Windows case-insensitive key collisions obey the same file/inline precedence
  as exact-key collisions and have one canonical digest representation.
- A local entry absent from the committed run map is rejected during resolution.
- The resolved directory, not the caller shell directory, is used.
- Relative and equivalent absolute path spellings produce the same effective
  entry digest; a genuinely different `argv`, `cwd`, env-file input, or inline
  `env` produces a different digest and active slot.
- Receipt and SVC-owned output show resolved `argv`, `cwd`, and env-file paths
  but contain no raw environment values.
