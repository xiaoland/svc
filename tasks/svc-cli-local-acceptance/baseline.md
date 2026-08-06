# SVC CLI Integrated Development Baseline

## Role

This file records the starting product and runtime facts for the task. It is
supporting evidence, not the Human current view or a durable SVC owner.

## Accepted Product Input

- SVC CLI is the delivery and distribution runtime for the SVC Corpus. This
  identity is established and is not an open positioning question in this task.
- Its runtime evolution should favor as few deep capabilities as possible that
  lower Agent cost when understanding, operating, and taking over large
  projects. This is an evaluation principle for Corpus projections, not a new
  product definition.
- SVC CLI should improve the semantic quality of stdout and stderr for Agents.
- Agent-friendly output is chosen from result meaning and LLM usability; JSON
  alone does not make an interface Agent-friendly. Compact JSON is preferable
  to prettified JSON when JSON is the appropriate carrier.
- Acceptance infrastructure remains a direction worth exploring, but a new
  `run` product surface is not admitted merely because it would complete a
  unified development-tool shape. If admitted, it remains separate from the
  existing `dev` domain and must produce a distinct SVC outcome over direct use
  of project-owned tools.
- The direct consumers are Agents and Humans. IDE Tasks is an optional
  Human-facing invocation carrier, not a third consumer and not a surface that
  SVC CLI replaces.
- CI may invoke the same development surface used locally. This does not by
  itself assign CI orchestration, merge policy, releases, remote runners, or the
  semantics of integrated tools to SVC CLI.
- General project context acquisition remains with tools such as `rg`, `jq`,
  code graphs, and `ast-grep`.

## Current Runtime Facts

- `svc_cli/cli.py` defines command-specific emitters plus a shared compact JSON
  writer. Existing non-JSON output ranges from raw Markdown and tab-separated
  lookup results to short status summaries and formatted diagnostic details.
- Recognized JSON results are normally compact single-line values. Some CLI and
  analysis error paths use different envelopes, so the current machine surface
  is not one uniform semantic output model.
- `svc dev setup vscode` can project declared development targets into VS Code
  Tasks, and `svc dev setup npm` can project exact package scripts. These are
  bounded integrations with Consumer-owned files.
- The current `dev` model owns readiness and provisioning for long-lived
  development capabilities. No general declared-run namespace or bounded-run
  contract is currently exposed.
- Existing test, build, lint, smoke, runtime, and diagnostic tools remain
  project-owned. Any development design must compose them instead of cloning
  their semantics inside SVC.

## External Reference Evidence (2026-08-05)

- PostHog documents detached `hogli` development stacks as useful for CI,
  automated testing, Agent sessions, and headless development, with companion
  readiness and shutdown commands:
  <https://github.com/PostHog/posthog/blob/master/docs/published/handbook/engineering/developing-locally.md>
- PostHog's own workflows invoke `hogli` for project checks and environment or
  generated-state preparation such as schema restore, product bootstrap, lint,
  and OpenAPI generation:
  <https://github.com/PostHog/posthog/blob/master/.github/workflows/ci-backend.yml>
- PostHog's command hooks attach environment and Agent context to command
  telemetry, while `devex:feedback` lets Humans or Agents report slow, broken,
  or confusing development experiences explicitly. Passive command telemetry
  is currently disabled in CI, so this is evidence for one observable
  Human/Agent development surface, not evidence that friction must be collected
  inside CI:
  <https://github.com/PostHog/posthog/blob/master/tools/hogli-commands/hogli_commands/telemetry_props.py>,
  <https://github.com/PostHog/posthog/blob/master/tools/hogli-commands/hogli_commands/feedback.py>
- Vite+ describes itself as one integrated entry point over runtime, package
  management, development, checks, tests, builds, and task orchestration. The
  relevant lesson is integration and workflow consistency, not adopting its
  JavaScript-specific tool ownership:
  <https://viteplus.dev/guide/why>

## Why This Is Not a Small Task

The accepted output direction and the open run-admission hypothesis cross
several coupled questions:

1. What semantic result shapes recur across existing commands?
2. What belongs on stdout, stderr, or only in an exit status?
3. Which output forms work best for LLM consumption without degrading Human
   terminal use?
4. Does a distinct `run` acceptance interface materially outperform direct
   native-tool invocation for Agent maintenance and Human-Agent collaboration?
5. If admitted, what is the minimum independent `run` declaration and execution
   contract without generalizing the existing `dev` model?
6. How do Agent, Human-terminal, Human-through-IDE, and CI invocation differ
   within each separate domain?
7. Which execution data reveals genuine Agent friction without conflating
   observability, feedback, and CI logs?
8. How does a new public role affect configuration, compatibility, tests,
   documentation, installed skills, editor and CI projections, and Behavioral
   SemVer?

A compact `packet.md` cannot preserve the necessary derivation and alternatives
without becoming hard for the Human to scan. The workspace therefore separates
current view, baseline, decisions, routing, and active design dossiers.
