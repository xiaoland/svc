# Deployment

Deployment is an optional owner for non-trivial runtime and operational truth: packaging, environment configuration, migrations, rollout, telemetry, mitigation, rollback, recovery, and runtime data locations.

Create it only when operators or developers need stable information that code, configuration, automation, or platform definitions do not expose clearly enough.

Reality work may use logs, metrics, traces, and runbooks as evidence, but the diagnosed cause selects the final owner. Keep code-local recurrence tripwires in the nearest local `AGENTS.md` and product promises in product truth.

Use [the deployment runbook template](../assets/templates/deployment-runbook.template.md) when an operational response needs a repeatable evidence, mitigation, and recovery path.
