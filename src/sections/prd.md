# Product Truth

Product truth owns what the product is for, what users or external systems can observe, which rules and scope apply, and why those commitments exist. It does not own implementation topology, internal sequencing, wire details, or local code contracts.

## Minimal Shape

Start with one `docs/10-prd/README.md` containing:

- product purpose and current pressure
- product claims and evaluation expectations
- capabilities and observable workflows
- rules, invariants, and scope boundaries
- business terms whose meaning must remain stable

Use [the product-truth template](../assets/templates/product-truth.template.md). Do not create an empty glossary or directory family.

## Derivation

Keep the reasoning direction explicit:

```text
drivers -> product behavior and claims -> derived domain structure
```

Market, user, business, hard-constraint, and operational pressures are upstream. Domain boundaries may stabilize language after behavior is understood, but they cannot invent new product obligations.

For each material claim, preserve enough of the following to evaluate it:

- the problem or outcome being committed to
- the driver or rationale
- observable success dimensions
- expected evidence

Do not add hard numeric gates unless the product actually requires them.

## Ownership Boundary

An Intent lens often points here, but only when the product promise changes. A dependency, environment, or implementation constraint can leave product truth unchanged. When product truth does change, update it before describing downstream realization.

Use Product TDD for admitted cross-unit technical contracts, Unit TDD for admitted internal unit design, and Deployment for non-trivial runtime or recovery truth.

## Corpus Delivery and Project Evolution

The SVC CLI is the local delivery and distribution surface for the versioned
SVC Corpus. Agents and Humans can progressively browse one logical level,
search bounded path/content evidence, and read one exact canonical document
without copying the framework into every project. CLI help owns the executable
interface; Corpus lookup owns framework guidance and is not a substitute CLI
manual.

Three evolution axes remain visibly independent: the installed CLI version,
the project configuration schema, and the project-declared Corpus baseline. A
supported configuration transform may be automated through an exact plan. A
Corpus migration cannot be reduced to a file rewrite: SVC presents the exact
release guidance, an Agent/Human changes Consumer-owned SVC documents, and SVC
records only the reviewed baseline. An unchanged Corpus must not manufacture
empty migration work merely because CLI implementation changed.

Ordinary command text is shaped for Agent/Human decisions from the command's
actual semantics. Compact JSON is a deliberate scripts/CI projection, not the
definition of agent-friendly output. Expected non-success domain results stay
self-contained; grammar, invalid requests, and infrastructure failure remain
errors. SVC does not add a universal result schema across unrelated commands.

## Declared Development Capabilities

SVC lets independent Agent, Human, editor, and CI callers observe and express
one named long-lived development capability without starting the same intent
twice. Readiness, coordination scope, provisioning, access, and optional stop
cleanup remain Consumer declarations integrated by SVC rather than
reimplementations of HTTP servers, package managers, Compose, or project
scripts. Once readiness is proved, the capability survives the starter CLI and
native output remains available through a stable shared log.

Ensure and stop serialize at the same capability boundary, while equivalent
callers converge on the same observable execution. Stop runs only declared
Consumer cleanup and verifies the final readiness state; a historical PID is
never cleanup authority. This preserves Consumer ownership rules such as an
attached client refusing to tear down another repository's runtime.

## Agent Task-Performance Analysis

SVC provides a local, Agent-driven evidence capability for understanding whether an Agent produced a good, complete, and sufficiently verified terminal task result under changing scope, dependencies, interruption, and context pressure. The calling Agent selects evidence and owns content use, semantic interpretation, competing explanations, and any SVC-mechanism hypothesis; SVC does not issue a quality score, causal verdict, or model-generated conclusion.

The observable promise is bounded and evidence-led: an Agent can inspect immutable collected evidence, distinguish a supported observation from an unavailable boundary, and connect task outcome, possible contributors, verification or handoff horizon, and residual unknowns. Provider health, latency, token or memory use, throughput, and generic tool failure rates are not independent task-performance outcomes. Product evaluation requires evidence-grounded, decision-relevant insight from real task trajectories without forcing a defect or treating chronology as causality.

### Local trust and exposure boundary

Agent-thread evidence is an explicit same-user local workflow. SVC trusts the
calling user, the selected provider location, the local account, and the
operating system; it does not promise protection from root, a hostile process
running as the same user, or adversarial path replacement. Provider data may
still be malformed, oversized, unreadable, or changing, and SVC must report
those ordinary input and capture boundaries honestly.

SVC protects the selected source from its own writes, captured native fidelity,
snapshot identity, an existing output from replacement, Consumer-owned project
files, and release artifact integrity. Resource policy is limited to source,
frame, request, and response-page boundaries. The native evidence authority may
contain every selected provider byte. Structural projection and omission are
derived navigation, not redaction; SVC provides no confidentiality, privacy
mode, or sandbox. The caller owns source selection, output storage, access
control, retention, and disclosure.

## Shared Declared Runs

SVC provides a narrow bounded-run collaboration surface for project-owned
development and acceptance commands. A project names one exact command; local
Human and Agent callers expressing that same effective intent converge on one
observable execution instead of rerunning it merely to share progress or a
handoff. The starter remains the foreground owner, while other callers can
follow captured native output or inspect the execution receipt.

The observable outcome is one execution ID, recoverable command output, and
honest terminal facts that survive caller handoff while local runtime storage
survives. A settled receipt is evidence about that invocation, never a cached
freshness claim or an acceptance verdict. Project tools continue to own test,
build, lint, and artifact semantics; SVC does not add a workflow graph,
dependency system, background runner, readiness model, or command interpreter.

Declared bounded runs and long-lived dev capabilities remain separate public
domains. Both may reuse private process-attempt mechanics, but `svc dev` alone
owns capability readiness, scope, reuse, and release after readiness.

## Managed External Boundaries

SVC lets a Consumer verify one named product claim against its real application
when an external HTTP system is unavailable, unsafe, costly, or unsuitable for
deterministic writes. A versioned boundary-scenario module can declare strict
outbound request matching and deterministic responses, plus named inbound
events that a test emits explicitly. Examples, matchers, captures, derived
values, closed semantic generators, managed assets, and provenance remain
separate roles so protocol-shaped data does not invent provider business truth.

The observable workflow is `svc double validate|start|emit|observe|stop`. Each
start creates a fresh isolated loopback responder and reports its replay facts,
fidelity boundary, and explicit non-claims. Observe returns bounded interaction
evidence, not a test verdict. The Consumer test drives the real product and is
the sole product oracle; SVC neither runs that test nor adds a combined
`double check` result. Events never follow automatically from a response.

The deterministic lane never proxies, falls through, or retrieves remote
contracts/assets. SVC constrains its responder, built-in materialization, and
event target delivery, but does not launch or sandbox the Consumer. Consumer
egress is therefore not enforced. A declared external materializer is also
Consumer-owned arbitrary code: SVC bounds its envelope and execution resources
without claiming its egress, determinism, immutability, or provider fidelity.
OpenAPI may verify one selected local static 3.1 operation's schema mechanics;
it does not define provider behavior or prove provider currentness.

## Expansion Rule

Split the single file only when real content has distinct consumers or change cadence. Common pressure-driven splits are drivers, behavior, scope, glossary, and derived domain structure. Every new file needs an owner and content at creation time.
