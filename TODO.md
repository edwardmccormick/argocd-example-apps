# TODO

This file tracks remaining high-value work for the local GitOps reliability lab. Completed work is noted briefly for context, but the focus is on what to build next.

## Recently Completed

### Progressive Delivery With Quality Gates

Argo Rollouts canary is live with staged promotion (`20%` -> `50%` -> `100%`) and analysis gates tied to semantic quality signals.

### Optional Generative Mode

The AI service now supports `extractive` and `generative` modes behind the same response contract, including grounded/result semantics and token usage reporting.

### Expanded Eval Coverage

The deterministic eval pack now contains a broad categorized suite (`retrieval_relevance`, `grounding_accuracy`, `structured_output_validity`, `insufficient_context`, `adversarial_robustness`) instead of a minimal smoke set.

### Optional LangSmith Tracing

Request, retrieval, and model traces are wired through the lightweight LangSmith client path when credentials are provided.

### Argo CD Local Bootstrap Hardening

The root bootstrap manifest now configures `argocd-server` with `--insecure` for local HTTP ingress compatibility on `localhost:8080`.

### CI Eval Metrics In Grafana

Deterministic eval summaries are now published as CI artifacts, pulled into the local cluster by a CronJob, pushed into Prometheus via Pushgateway, and visualized on a dedicated Grafana dashboard.

### Failure Drill Template Standardization

All active drill docs now share the same core structure (`Steady-State Hypothesis`, `Failure Injection`, `Expected Behavior During Failure`, `Recovery Procedure`, `SLO Impact`, and `What This Drill Validates`) for consistent game-day readability.

### Canary Burst Traffic And Sample-Size Gating

Canary analysis now runs rollout-triggered burst traffic and enforces minimum request volume before semantic quality ratios are accepted, reducing low-traffic signal noise during promotion.

---

## Next Up

### Event-Driven Scaling

Add a queue-backed producer/consumer path and KEDA scaling to demonstrate backlog-aware autoscaling.

### Secret Management Pattern

Add an external secret reference pattern so GitOps manages secret wiring rather than literal values.

---

## Good Follow-On Work

### ApplicationSet Expansion

Add a focused `ApplicationSet` example for multi-app or multi-environment generation.

---

## Useful Discussion Topics Even If Not Implemented

### AI Cost Modeling

Build cost-per-query visibility using real token usage and mode split.

### Multi-Environment Promotion

- environment branches or promotion repos
- immutable artifact promotion between stages
- separation of CI validation from deploy approval

### Policy As Code

- enforce probes, security context, and resource standards
- reject mutable image tags
- codify guardrails instead of relying only on review discipline

### Supply Chain Hardening

- pin actions by SHA
- verify installer checksums/signatures
- reduce privileged CI paths and secret exposure

### Argo CD Control Plane Hardening

- Git-manage more Argo CD install configuration
- minimize one-off live patches
- continue reducing restart-time brittleness

---

## What To Avoid Right Now

- adding controllers without a clear reliability story
- turning the repo into a broad platform demo instead of a focused reliability lab
- implementing features that do not map to concrete SLI/SLO or quality outcomes

Short version:

1. Add event-driven scaling so autoscaling covers queue depth and backlog behavior.
2. Add a practical external secret pattern for GitOps-managed secret references.
3. Use `ApplicationSet` as the next multi-app scale example.
