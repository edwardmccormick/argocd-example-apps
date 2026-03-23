# TODO

This file is the forward-looking roadmap for the lab. The goal is not to collect every good idea. The goal is to keep the next steps aligned with the current shape of the repo: local, GitOps-driven, reliability-focused, and interview-useful.

## Next Up

### Progressive Delivery With Real Quality Gates

Add canary deployment for the AI service, tied to the metrics that now exist.

Why it matters:

- this is the most natural next step after GitOps, CI validation, observability, and autoscaling
- the AI service now has signals that are more interesting than raw pod health
- it creates a stronger reliability story than standard `RollingUpdate`

Target shape:

- use Argo Rollouts or a similar progressive-delivery controller
- gate promotion on:
  - `ai_docqa:workflow_completion_ratio:5m`
  - `ai_docqa:structured_output_validity_ratio:5m`
  - `ai_docqa:insufficient_context_ratio:5m`
  - `ai_docqa:latency_p95_seconds:5m`
- abort or fail promotion when those signals regress

Why this is the highest-value next item:

- it converts the current metrics from “observed after deploy” into “used during deploy”
- it is one of the clearest bridges from generic SRE to AI reliability engineering

### AI Replay / Analysis Against A Live Candidate

Extend the current deterministic eval concept so a canary or staged deployment can be validated with known prompts before promotion.

Why it matters:

- static smoke tests prove the service boots
- replay checks prove it still behaves acceptably on known questions
- this is much closer to real AI quality engineering than pod health alone

Target shape:

- curated replay set against `/ask`
- expected document classes or keyword coverage
- pass/fail signal that can be used during rollout analysis

## Good Follow-On Work

### Event-Driven Scaling

Add a queue-backed workload and autoscale it with KEDA.

Why it matters:

- demonstrates asynchronous workload behavior instead of only request/response services
- creates a stronger scaling story than replica counts alone
- gives the lab a realistic way to discuss lag, backlog, throughput, and scaling signals

Target shape:

- lightweight producer / consumer pair
- visible queue depth or lag metric
- KEDA-driven scaling policy
- Grafana view that correlates load, lag, and replica count

Priority note:

- valuable, but less directly aligned to the current AI quality thread than progressive delivery

### ApplicationSet Expansion

Add an `ApplicationSet` example for multi-service or multi-environment generation.

Why it matters:

- useful for talking about scale beyond a single app or cluster
- good way to discuss templated onboarding and Git-driven fleet management
- relevant to real Argo CD usage in larger organizations

Target shape:

- generate multiple child Applications from a Git directory or cluster list
- optionally show environment fan-out such as local / staging / prod
- keep the example narrow enough that it does not overwhelm the repo

Priority note:

- strong interview topic
- not the best immediate implementation target unless the repo is intentionally moving toward multi-app fleet management

### Secret Management

Add an external secret pattern instead of assuming low-secret local operation.

Why it matters:

- GitOps secret handling is a real platform question
- this repo currently avoids most secrets rather than demonstrating how to manage them well
- it creates a good discussion about separation of desired state from secret values

Possible target shape:

- External Secrets Operator pattern
- local secret store simulation or documented cloud-backed reference design
- Argo CD manages secret references, not literal secret values

Priority note:

- valuable as an interview talking point
- harder to make clean and local than progressive delivery or replay analysis

## Useful Discussion Topics Even If Not Implemented

These are worth understanding and being able to speak to, even if the repo never grows far enough to implement them all.

### Multi-Environment Promotion

- environment branches or promotion repos
- immutable artifact promotion between stages
- separation of CI validation from production deployment decisions

### Policy As Code

- enforce probes, security context, resource requests/limits
- reject mutable image tags
- encode cluster standards instead of relying on review discipline

### Supply Chain Hardening

- pinning actions by SHA
- verifying checksums or signatures
- internal artifact mirrors
- minimizing privileged CI workflows and secrets

### Control Plane Hardening

- Git-manage more of the Argo CD install itself
- remove live-only patches where practical
- continue reducing restart-time brittleness and reconciliation blind spots

## What To Avoid Right Now

- adding too many controllers at once without a clear story
- turning the lab into a generic platform zoo
- implementing features that are mechanically interesting but not tied to current service metrics or reliability goals

Short version:

1. Use the AI metrics you already have to drive rollout safety.
2. Add replay-style validation before promotion.
3. Treat event-driven scaling, ApplicationSets, and secret management as valuable next layers, not immediate distractions.
